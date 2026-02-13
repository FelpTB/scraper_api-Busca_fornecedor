"""
Gerenciador de provedores LLM v3.2.

Centraliza configuração e chamadas aos providers.
Integrado com RateLimiter v2.0 para controle separado de RPM e TPM.

v3.2: Integração com rate limiter que controla RPM e TPM separadamente
      - Antes de cada chamada, adquire slot de RPM E tokens de TPM
      - Estima tokens da requisição baseado no conteúdo das mensagens

v3.5: Modo por instância SGLang — quando SGLANG_BASE_URL está definida, apenas
      um provider (SGLang) é registrado, sem balanceamento nem fallback.
"""

import asyncio
import os
import time
import logging
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError, BadRequestError

from app.core.config import settings
from app.services.concurrency_manager.config_loader import (
    get_section as get_concurrency_section,
)
from .priority import LLMPriority
from .rate_limiter import rate_limiter
from app.core.token_utils import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuração de um provider LLM."""
    name: str
    api_key: str
    base_url: str
    model: str
    max_concurrent: int = 100
    priority: int = 50
    timeout: float = 90.0
    enabled: bool = True
    weight: int = 10


class ProviderError(Exception):
    """Erro genérico de provider."""
    pass


class ProviderRateLimitError(ProviderError):
    """Erro de rate limit."""
    pass


class ProviderTimeoutError(ProviderError):
    """Erro de timeout."""
    pass


class ProviderBadRequestError(ProviderError):
    """Erro de requisição inválida."""
    pass


class ProviderManager:
    """
    Gerencia conexões e chamadas aos providers LLM.
    
    v3.3: Separação de providers por prioridade
          - HIGH (Discovery/LinkSelector) → Google Gemini exclusivo
          - NORMAL (Profile Building) → Outros providers (OpenAI, OpenRouter)
          - Elimina competição entre etapas críticas e profile building
    """
    
    def __init__(self, configs: List[ProviderConfig] = None):
        self._configs: Dict[str, ProviderConfig] = {}
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # v3.3: Providers separados por prioridade
        self._high_priority_providers: List[str] = []   # Google Gemini exclusivo
        self._normal_priority_providers: List[str] = [] # Todos os outros
        
        # Sistema de prioridade (mantido para compatibilidade, mas menos crítico agora)
        self._high_priority_active = 0
        self._high_priority_done = asyncio.Event()
        self._high_priority_done.set()
        self._counter_lock = asyncio.Lock()
        
        # Rate limiter global
        self._rate_limiter = rate_limiter
        
        if configs:
            for config in configs:
                self.add_provider(config)
        else:
            self._load_default_providers()

    def _is_sglang_fixed_mode(self) -> bool:
        """True quando o processo está pinado a uma instância SGLang (variável SGLANG_BASE_URL)."""
        return bool(os.environ.get("SGLANG_BASE_URL", "").strip())

    def _build_base_v1(self, url: str) -> str:
        """Garante que a URL termine com /v1 (API OpenAI-compatible)."""
        if not url:
            return ""
        return url if url.rstrip("/").endswith("/v1") else url.rstrip("/") + "/v1"

    def _load_default_providers(self):
        """Carrega providers das configurações do sistema."""
        # Modo por instância SGLang: um único provider, sem fallback
        if self._is_sglang_fixed_mode():
            self._load_sglang_fixed_provider_only()
            return

        limits = self._load_limits_from_file()
        safety_margin = limits.get("config", {}).get("safety_margin", 0.8)
        
        # Carregar configuração de providers habilitados
        provider_enabled = self._load_provider_enabled_config()
        
        # SGLang (Provider primário: LLM_URL + MODEL_NAME)
        runpod_config = limits.get("runpod", {}).get("mistralai/Ministral-3-8B-Instruct-2512", {})
        gemini_config = limits.get("google", {}).get("gemini-2.0-flash", {})
        openai_config = limits.get("openai", {}).get("gpt-4.1-nano", {})
        openrouter1_config = limits.get("openrouter", {}).get("google/gemini-2.0-flash-lite-001", {})
        openrouter2_config = limits.get("openrouter", {}).get("google/gemini-2.5-flash-lite", {})
        openrouter3_config = limits.get("openrouter", {}).get("openai/gpt-4.1-nano", {})
        
        runpod_rpm = runpod_config.get("rpm", 30000)
        gemini_rpm = gemini_config.get("rpm", 10000)
        openai_rpm = openai_config.get("rpm", 5000)
        openrouter1_rpm = openrouter1_config.get("rpm", 20000)
        openrouter2_rpm = openrouter2_config.get("rpm", 15000)
        openrouter3_rpm = openrouter3_config.get("rpm", 10000)
        
        runpod_tpm = runpod_config.get("tpm", 5000000)
        gemini_tpm = gemini_config.get("tpm", 10000000)
        openai_tpm = openai_config.get("tpm", 4000000)
        openrouter1_tpm = openrouter1_config.get("tpm", 10000000)
        openrouter2_tpm = openrouter2_config.get("tpm", 8000000)
        openrouter3_tpm = openrouter3_config.get("tpm", 5000000)
        
        runpod_weight = runpod_config.get("weight", 50)
        gemini_weight = gemini_config.get("weight", 29)
        openai_weight = openai_config.get("weight", 14)
        openrouter1_weight = openrouter1_config.get("weight", 30)
        openrouter2_weight = openrouter2_config.get("weight", 25)
        openrouter3_weight = openrouter3_config.get("weight", 20)
        
        # Calcular concorrência baseado em RPM (80% de segurança)
        # Hard cap evita oversubscription (degradação TTFT/latência, timeouts, retries)
        hard_cap = getattr(settings, "LLM_CONCURRENCY_HARD_CAP", 32)
        runpod_concurrent = min(
            hard_cap,
            max(800, int(runpod_rpm * safety_margin / 15)),
        )
        gemini_concurrent = min(hard_cap, max(600, int(gemini_rpm * safety_margin / 15)))
        openai_concurrent = min(hard_cap, max(150, int(openai_rpm * safety_margin / 30)))
        openrouter1_concurrent = min(hard_cap, max(300, int(openrouter1_rpm * safety_margin / 30)))
        openrouter2_concurrent = min(hard_cap, max(250, int(openrouter2_rpm * safety_margin / 30)))
        openrouter3_concurrent = min(hard_cap, max(200, int(openrouter3_rpm * safety_margin / 30)))
        
        logger.info(f"LLM Limits carregados:")
        logger.info(f"  SGLang: RPM={runpod_rpm}, TPM={runpod_tpm:,}, weight={runpod_weight}%")
        logger.info(f"  Google Gemini: RPM={gemini_rpm}, TPM={gemini_tpm:,}, weight={gemini_weight}%")
        logger.info(f"  OpenAI: RPM={openai_rpm}, TPM={openai_tpm:,}, weight={openai_weight}%")
        logger.info(f"  OpenRouter 1: RPM={openrouter1_rpm}, TPM={openrouter1_tpm:,}, weight={openrouter1_weight}%")
        logger.info(f"  OpenRouter 2: RPM={openrouter2_rpm}, TPM={openrouter2_tpm:,}, weight={openrouter2_weight}%")
        logger.info(f"  OpenRouter 3: RPM={openrouter3_rpm}, TPM={openrouter3_tpm:,}, weight={openrouter3_weight}%")
        
        # SGLang: base_url e model vêm de LLM_URL e MODEL_NAME (variáveis de ambiente)
        default_providers = [
            ProviderConfig(
                name="SGLang",
                api_key=settings.RUNPOD_API_KEY or settings.VLLM_API_KEY or "",
                base_url=settings.RUNPOD_BASE_URL,
                model=settings.RUNPOD_MODEL,
                max_concurrent=runpod_concurrent,
                priority=90,  # Prioridade mais alta (provider primário)
                weight=runpod_weight,
                enabled=True  # SGLang sempre habilitado quando LLM_URL definida
            ),
            ProviderConfig(
                name="Google Gemini",
                api_key=settings.GOOGLE_API_KEY or "",
                base_url=settings.GOOGLE_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/",
                model=settings.GOOGLE_MODEL or "gemini-2.0-flash",
                max_concurrent=gemini_concurrent,
                priority=70,
                weight=gemini_weight,
                enabled=provider_enabled.get("Google Gemini", False)
            ),
            ProviderConfig(
                name="OpenAI",
                api_key=settings.OPENAI_API_KEY or "",
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
                model=settings.OPENAI_MODEL or "gpt-4.1-nano",
                max_concurrent=openai_concurrent,
                priority=60,
                weight=openai_weight,
                enabled=provider_enabled.get("OpenAI", False)
            ),
            ProviderConfig(
                name="OpenRouter",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL,
                max_concurrent=openrouter1_concurrent,
                priority=80,
                weight=openrouter1_weight,
                enabled=provider_enabled.get("OpenRouter", False)
            ),
            ProviderConfig(
                name="OpenRouter2",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL_2,
                max_concurrent=openrouter2_concurrent,
                priority=75,
                weight=openrouter2_weight,
                enabled=provider_enabled.get("OpenRouter2", False)
            ),
            ProviderConfig(
                name="OpenRouter3",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL_3,
                max_concurrent=openrouter3_concurrent,
                priority=72,
                weight=openrouter3_weight,
                enabled=provider_enabled.get("OpenRouter3", False)
            ),
        ]
        
        for config in default_providers:
            # SGLang: só adiciona se BASE_URL definida (LLM_URL no Railway)
            # Outros providers só são adicionados se tiverem API key E estiverem habilitados
            if config.name == "SGLang":
                if config.api_key and config.base_url:
                    self.add_provider(config)
            else:
                if config.api_key and config.enabled:
                    self.add_provider(config)
                    logger.info(f"ProviderManager: {config.name} habilitado conforme configuração")
                elif config.api_key and not config.enabled:
                    logger.info(f"ProviderManager: {config.name} desabilitado conforme llm_providers.json")
                else:
                    logger.debug(f"ProviderManager: {config.name} não configurado (sem API key)")
    
    def _load_limits_from_file(self) -> dict:
        """Carrega limites a partir do config centralizado."""
        cfg = get_concurrency_section("llm_limits", {})
        if cfg:
            return cfg
        logger.warning("ProviderManager: Configuração llm_limits ausente; usando vazio.")
        return {}
    
    def _load_provider_enabled_config(self) -> dict:
        """Carrega configuração de quais providers estão habilitados."""
        try:
            # Usar o config_loader do concurrency_manager para carregar o arquivo
            from app.services.concurrency_manager.config_loader import load_config
            providers_config = load_config("llm_providers")
            enabled_providers = providers_config.get("enabled_providers", {})
            
            logger.info("ProviderManager: Configuração de providers carregada:")
            for provider, enabled in enabled_providers.items():
                status = "✅ habilitado" if enabled else "❌ desabilitado"
                logger.info(f"  {provider}: {status}")
            
            return enabled_providers
        except Exception as e:
            logger.warning(f"ProviderManager: Erro ao carregar llm_providers.json: {e}")
            # Padrão: apenas SGLang habilitado
            logger.info("ProviderManager: Usando configuração padrão (apenas SGLang habilitado)")
            return {
                "SGLang": True,
                "Google Gemini": False,
                "OpenAI": False,
                "OpenRouter": False,
                "OpenRouter2": False,
                "OpenRouter3": False
            }

    def _load_sglang_fixed_provider_only(self):
        """
        Registra apenas o provider SGLang da instância atual (SGLANG_BASE_URL).
        Sem outros providers e sem fallback. Usado quando o processo está pinado a uma GPU.
        """
        base_url_raw = os.environ.get("SGLANG_BASE_URL", "").strip()
        if not base_url_raw:
            return
        base_url = self._build_base_v1(base_url_raw)
        model = getattr(settings, "RUNPOD_MODEL", None) or getattr(settings, "VLLM_MODEL", None) or os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
        api_key = getattr(settings, "RUNPOD_API_KEY", None) or getattr(settings, "VLLM_API_KEY", None) or "buscafornecedor"

        limits = self._load_limits_from_file()
        runpod_config = limits.get("runpod", {})
        # Resolver modelo para limites (mesma lógica que rate_limiter: runpod/Qwen ou fallback)
        model_limits = runpod_config.get(model) or runpod_config.get("Qwen/Qwen2.5-3B-Instruct") or runpod_config.get("mistralai/Ministral-3-8B-Instruct-2512", {})
        rpm = model_limits.get("rpm", 30000)
        tpm = model_limits.get("tpm", 5000000)
        safety_margin = limits.get("config", {}).get("safety_margin", 0.8)
        hard_cap = getattr(settings, "LLM_CONCURRENCY_HARD_CAP", 32)
        runpod_concurrent = min(hard_cap, max(800, int(rpm * safety_margin / 15)))

        config = ProviderConfig(
            name="SGLang",
            api_key=api_key or "buscafornecedor",
            base_url=base_url,
            model=model,
            max_concurrent=runpod_concurrent,
            priority=90,
            weight=50,
            enabled=True,
        )
        self.add_provider(config)
        instance_name = os.environ.get("SGLANG_INSTANCE_NAME", "default")
        logger.info(
            "ProviderManager: modo instância SGLang — único provider registrado "
            "(instance=%s, base_url=%s)",
            instance_name,
            base_url,
        )

    def add_provider(self, config: ProviderConfig):
        """Adiciona um provider e categoriza por prioridade."""
        if not config.api_key:
            logger.warning(f"ProviderManager: {config.name} sem API key, ignorando")
            return
        
        self._configs[config.name] = config
        self._clients[config.name] = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout
        )
        self._semaphores[config.name] = asyncio.Semaphore(config.max_concurrent)
        
        # v3.4: Categorizar provider por prioridade
        # SGLang → HIGH e NORMAL (provider primário para todas as chamadas)
        # Google Gemini (direto) → HIGH priority (Discovery/LinkSelector) - Fallback
        # Outros → NORMAL priority (Profile Building) - Fallback
        if config.name == "SGLang":
            # SGLang disponível para ambas as prioridades (primário)
            self._high_priority_providers.append(config.name)
            self._normal_priority_providers.append(config.name)
            priority_label = "HIGH+NORMAL"
        elif config.name == "Google Gemini":
            self._high_priority_providers.append(config.name)
            priority_label = "HIGH"
        else:
            self._normal_priority_providers.append(config.name)
            priority_label = "NORMAL"
        
        logger.info(f"ProviderManager: {config.name} adicionado (model={config.model}, queue={priority_label})")
    
    def remove_provider(self, name: str):
        """Remove um provider."""
        self._configs.pop(name, None)
        self._clients.pop(name, None)
        self._semaphores.pop(name, None)
        
        # v3.3: Remover das listas de prioridade
        if name in self._high_priority_providers:
            self._high_priority_providers.remove(name)
        if name in self._normal_priority_providers:
            self._normal_priority_providers.remove(name)
        # SGLang está em ambas as listas, então remove de ambas se necessário
    
    @property
    def available_providers(self) -> List[str]:
        """Lista de providers disponíveis."""
        return [name for name, config in self._configs.items() if config.enabled]
    
    @property
    def provider_priorities(self) -> Dict[str, int]:
        """Dict de prioridades dos providers."""
        return {name: config.priority for name, config in self._configs.items()}
    
    @property
    def provider_weights(self) -> Dict[str, int]:
        """Dict de pesos dos providers para distribuição proporcional."""
        return {name: config.weight for name, config in self._configs.items()}
    
    def get_weighted_provider_list(self, count: int) -> List[str]:
        """Gera lista de providers distribuídos por peso."""
        providers = self.available_providers
        if not providers:
            return []
        
        weights = self.provider_weights
        total_weight = sum(weights.get(p, 10) for p in providers)
        
        distributed = []
        for provider in providers:
            weight = weights.get(provider, 10)
            provider_count = max(1, int(count * weight / total_weight))
            distributed.extend([provider] * provider_count)
        
        while len(distributed) < count:
            best_provider = max(providers, key=lambda p: weights.get(p, 10))
            distributed.append(best_provider)
        
        random.shuffle(distributed)
        
        return distributed[:count]
    
    def get_config(self, provider: str) -> Optional[ProviderConfig]:
        """Retorna configuração de um provider."""
        return self._configs.get(provider)
    
    def get_client(self, provider: str) -> Optional[AsyncOpenAI]:
        """Retorna cliente de um provider."""
        return self._clients.get(provider)
    
    def get_model(self, provider: str) -> Optional[str]:
        """Retorna modelo de um provider."""
        config = self._configs.get(provider)
        return config.model if config else None
    
    async def call(
        self,
        provider: str,
        messages: List[dict],
        timeout: float = None,
        temperature: float = 0.0,
        response_format: dict = None,
        ctx_label: str = "",
        priority: LLMPriority = LLMPriority.NORMAL
    ) -> Tuple[str, float]:
        """
        Faz chamada a um provider com controle de rate limiting.
        
        Args:
            provider: Nome do provider
            messages: Lista de mensagens
            timeout: Timeout opcional
            temperature: Temperatura da geração
            response_format: Formato de resposta
            ctx_label: Label de contexto para logs
            priority: HIGH (Discovery/LinkSelector) ou NORMAL (Profile)
        
        Returns:
            Tuple de (response_content, latency_ms)
        
        Raises:
            ProviderRateLimitError, ProviderTimeoutError, 
            ProviderBadRequestError, ProviderError
        """
        config = self._configs.get(provider)
        if not config:
            raise ProviderError(f"Provider '{provider}' não encontrado")
        
        client = self._clients.get(provider)
        if not client:
            raise ProviderError(f"Cliente não inicializado para '{provider}'")
        
        semaphore = self._semaphores.get(provider)
        actual_timeout = timeout or config.timeout
        
        # Estimar tokens da requisição
        estimated_tokens = estimate_tokens(messages)
        
        # Verificar se o conteúdo cabe no context window do provider
        safe_input_tokens = self._rate_limiter.get_safe_input_tokens(provider)
        context_window = self._rate_limiter.get_context_window(provider)

        # Validação conservadora para SGLang/vLLM: usar 80% do context window
        is_sglang = "sglang" in provider.lower()
        if is_sglang:
            safe_input_tokens = int(context_window * 0.8)  # 80% do context window

        if estimated_tokens > safe_input_tokens:
            logger.error(
                f"{ctx_label}❌ Conteúdo muito grande para {provider}! "
                f"Estimado: {estimated_tokens:,} tokens, "
                f"Limite seguro: {safe_input_tokens:,} tokens, "
                f"Context window: {context_window:,} tokens"
                f"{' (SGLang: usando 80% do context window)' if is_sglang else ''}"
            )
            raise ProviderBadRequestError(
                f"Conteúdo excede context window do {provider}. "
                f"Estimado: {estimated_tokens:,}, Limite: {safe_input_tokens:,}"
            )
        
        if priority == LLMPriority.HIGH:
            async with self._counter_lock:
                self._high_priority_active += 1
                self._high_priority_done.clear()
            
            try:
                return await self._execute_llm_call(
                    client, config, semaphore, messages,
                    actual_timeout, temperature, response_format,
                    ctx_label, provider, estimated_tokens
                )
            finally:
                async with self._counter_lock:
                    self._high_priority_active -= 1
                    if self._high_priority_active == 0:
                        self._high_priority_done.set()
        else:
            await self._high_priority_done.wait()
            
            return await self._execute_llm_call(
                client, config, semaphore, messages,
                actual_timeout, temperature, response_format,
                ctx_label, provider, estimated_tokens
            )
    
    async def _execute_llm_call(
        self,
        client: AsyncOpenAI,
        config: ProviderConfig,
        semaphore: asyncio.Semaphore,
        messages: List[dict],
        timeout: float,
        temperature: float,
        response_format: dict,
        ctx_label: str,
        provider: str,
        estimated_tokens: int
    ) -> Tuple[str, float]:
        """Executa a chamada LLM real com controle de rate limiting."""
        
        # 1. Adquirir permissão do rate limiter (RPM + TPM)
        # Timeout reduzido para 5s (fail fast) para evitar lock contenção
        rate_acquired = await self._rate_limiter.acquire(
            provider=provider,
            estimated_tokens=estimated_tokens,
            timeout=min(timeout, 5.0)
        )
        
        if not rate_acquired:
            logger.warning(
                f"{ctx_label}ProviderManager: {provider} rate limit local atingido "
                f"(tokens={estimated_tokens})"
            )
            raise ProviderRateLimitError(f"Rate limit local para {provider}")
        
        # 2. Usar semáforo de concorrência
        async with semaphore:
            start_time = time.perf_counter()
            
            try:
                # Detectar SGLang (suporta json_schema)
                is_sglang = "sglang" in provider.lower()
                
                # Obter max_output_tokens do provider para garantir valor válido
                max_output_tokens = self._rate_limiter.get_max_output_tokens(provider)
                
                request_params = {
                    "model": config.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_output_tokens  # Garantir valor explícito e válido
                }
                
                # SGLang suporta json_schema via response_format
                if response_format:
                    if response_format.get("type") == "json_schema":
                        request_params["response_format"] = response_format
                        logger.debug(f"{ctx_label}ProviderManager: {provider} usando json_schema (SGLang structured output)")
                    elif response_format.get("type") == "json_object":
                        if is_sglang:
                            request_params["response_format"] = response_format
                            logger.debug(f"{ctx_label}ProviderManager: {provider} usando json_object (fallback)")
                        else:
                            # Outros providers: usar response_format normalmente
                            request_params["response_format"] = response_format
                    else:
                        # Outros formatos: usar normalmente
                        request_params["response_format"] = response_format
                
                # Log dos parâmetros da requisição para debug
                logger.debug(
                    f"{ctx_label}ProviderManager: {provider} chamando com model={request_params.get('model')}, "
                    f"temperature={temperature}, stop={request_params.get('stop')}, "
                    f"response_format={request_params.get('response_format')}"
                )
                
                # Usar asyncio.wait_for para aplicar timeout se necessário
                try:
                    if timeout:
                        response = await asyncio.wait_for(
                            client.chat.completions.create(**request_params),
                            timeout=timeout
                        )
                    else:
                        response = await client.chat.completions.create(**request_params)
                except BadRequestError as bad_req:
                    # Se BadRequest com response_format, tentar sem ele
                    if response_format and "response_format" in request_params:
                        logger.warning(
                            f"{ctx_label}ProviderManager: {provider} BAD_REQUEST com response_format, "
                            f"tentando sem ele: {bad_req}"
                        )
                        request_params.pop("response_format", None)
                        # Adicionar reforço no prompt se ainda não tiver
                        if messages and messages[-1].get("role") == "user" and not is_sglang:
                            user_msg = messages[-1]["content"]
                            messages[-1]["content"] = f"""{user_msg}

IMPORTANTE: Retorne APENAS um objeto JSON válido. Sem markdown, sem explicações."""
                        # Não usar stop tokens para evitar resposta vazia
                        if timeout:
                            response = await asyncio.wait_for(
                                client.chat.completions.create(**request_params),
                                timeout=timeout
                            )
                        else:
                            response = await client.chat.completions.create(**request_params)
                    else:
                        raise
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                # Debug detalhado para resposta vazia
                if not response.choices:
                    logger.error(f"{ctx_label}ProviderManager: {provider} resposta sem choices. Response: {response}")
                    raise ProviderError(f"{provider} retornou resposta sem choices")
                
                if not response.choices[0]:
                    logger.error(f"{ctx_label}ProviderManager: {provider} choices[0] está None. Response: {response}")
                    raise ProviderError(f"{provider} retornou choices[0] None")
                
                if not hasattr(response.choices[0], 'message'):
                    logger.error(f"{ctx_label}ProviderManager: {provider} choices[0] sem atributo 'message'. Response: {response.choices[0]}")
                    raise ProviderError(f"{provider} retornou choices[0] sem message")
                
                message = response.choices[0].message
                if not hasattr(message, 'content') or not message.content:
                    # Log detalhado para debug
                    logger.error(
                        f"{ctx_label}ProviderManager: {provider} retornou resposta vazia. "
                        f"Response object: {type(response)}, "
                        f"Choices count: {len(response.choices) if response.choices else 0}, "
                        f"Message type: {type(message) if message else None}, "
                        f"Content attr exists: {hasattr(message, 'content') if message else False}, "
                        f"Content value: {repr(getattr(message, 'content', None))}"
                    )
                    raise ProviderError(f"{provider} retornou resposta vazia")
                
                content = message.content.strip()
                
                # Log com tokens reais e comparação com estimativa
                actual_tokens = getattr(response, 'usage', None)
                if actual_tokens and actual_tokens.prompt_tokens:
                    actual_prompt_tokens = actual_tokens.prompt_tokens
                    diff = actual_prompt_tokens - estimated_tokens
                    diff_percent = (diff / estimated_tokens * 100) if estimated_tokens > 0 else 0
                    
                    # Log detalhado para SGLang (comparação importante)
                    if is_sglang:
                        if abs(diff_percent) > 10:  # Diferença > 10%
                            logger.warning(
                                f"{ctx_label}ProviderManager: {provider} - Discrepância significativa de tokens: "
                                f"estimado={estimated_tokens:,}, real={actual_prompt_tokens:,}, "
                                f"diff={diff:+,} ({diff_percent:+.1f}%)"
                            )
                        else:
                            logger.debug(
                                f"{ctx_label}ProviderManager: {provider} - Tokens: estimado={estimated_tokens:,}, "
                                f"real={actual_prompt_tokens:,}, diff={diff:+,} ({diff_percent:+.1f}%)"
                            )
                    else:
                        logger.debug(
                            f"{ctx_label}ProviderManager: {provider} - {len(content)} chars em {latency_ms:.0f}ms "
                            f"(tokens: in={actual_prompt_tokens}, out={actual_tokens.completion_tokens})"
                        )
                else:
                    logger.debug(
                        f"{ctx_label}ProviderManager: {provider} - {len(content)} chars em {latency_ms:.0f}ms"
                    )
                
                return content, latency_ms
            
            except RateLimitError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(f"{ctx_label}ProviderManager: {provider} RATE_LIMIT (API) após {latency_ms:.0f}ms")
                raise ProviderRateLimitError(str(e))
            
            except APITimeoutError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(f"{ctx_label}ProviderManager: {provider} TIMEOUT após {latency_ms:.0f}ms")
                raise ProviderTimeoutError(str(e))
            
            except BadRequestError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"{ctx_label}ProviderManager: {provider} BAD_REQUEST: {e}")
                raise ProviderBadRequestError(str(e))
            
            except asyncio.TimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(f"{ctx_label}ProviderManager: {provider} ASYNC_TIMEOUT após {latency_ms:.0f}ms")
                raise ProviderTimeoutError("Async timeout")
            
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"{ctx_label}ProviderManager: {provider} ERROR: {type(e).__name__}: {e}")
                raise ProviderError(str(e))
    
    async def call_with_retry(
        self,
        provider: str,
        messages: List[dict],
        max_retries: int = 2,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Tuple[str, float]:
        """Faz chamada com retry automático."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.call(provider, messages, **kwargs)
            
            except ProviderBadRequestError:
                raise
            
            except (ProviderRateLimitError, ProviderTimeoutError, ProviderError) as e:
                last_error = e
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    logger.info(
                        f"ProviderManager: {provider} retry {attempt + 1}/{max_retries} "
                        f"após {delay:.1f}s ({type(e).__name__})"
                    )
                    await asyncio.sleep(delay)
        
        raise last_error
    
    def get_status(self) -> dict:
        """Retorna status de todos os providers."""
        status = {
            "_queues": {
                "high_priority_providers": self._high_priority_providers,
                "normal_priority_providers": self._normal_priority_providers
            }
        }
        for name, config in self._configs.items():
            semaphore = self._semaphores.get(name)
            rate_status = self._rate_limiter.get_status().get(name, {})
            queue = "HIGH" if name in self._high_priority_providers else "NORMAL"
            status[name] = {
                "enabled": config.enabled,
                "model": config.model,
                "priority": config.priority,
                "queue": queue,
                "max_concurrent": config.max_concurrent,
                "semaphore_locked": semaphore.locked() if semaphore else None,
                "rate_limiter": rate_status
            }
        return status
    
    def get_rate_limiter_status(self) -> dict:
        """Retorna status detalhado do rate limiter."""
        return self._rate_limiter.get_status()


# Instância singleton
provider_manager = ProviderManager()
