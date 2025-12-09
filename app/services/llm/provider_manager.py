"""
Gerenciador de provedores LLM.
Centraliza configuração e chamadas aos providers.

v2.1: Adicionado suporte a prioridades (HIGH para Discovery/LinkSelector, NORMAL para Profile)
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError, BadRequestError

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMPriority(IntEnum):
    """
    Níveis de prioridade para chamadas LLM.
    
    HIGH: Discovery e LinkSelector (etapas iniciais que desbloqueiam o scrape)
    NORMAL: Montagem de perfil (etapa final após scrape)
    """
    HIGH = 1    # Discovery, LinkSelector - prioridade máxima
    NORMAL = 2  # Profile building - prioridade normal


@dataclass
class ProviderConfig:
    """Configuração de um provider LLM."""
    name: str
    api_key: str
    base_url: str
    model: str
    max_concurrent: int = 100
    priority: int = 50  # 0-100, maior = melhor
    timeout: float = 90.0
    enabled: bool = True
    weight: int = 10  # Peso para distribuição proporcional (% da capacidade)


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
    
    v2.1: Suporte a prioridades - HIGH priority (Discovery/LinkSelector) é processado
          antes de NORMAL priority (Profile building).
    """
    
    def __init__(self, configs: List[ProviderConfig] = None):
        self._configs: Dict[str, ProviderConfig] = {}
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # Sistema de prioridade: HIGH priority passa na frente
        self._high_priority_waiting = 0
        self._priority_lock = asyncio.Lock()
        self._priority_event = asyncio.Event()
        self._priority_event.set()  # Inicialmente liberado
        
        if configs:
            for config in configs:
                self.add_provider(config)
        else:
            self._load_default_providers()
    
    def _load_default_providers(self):
        """Carrega providers das configurações do sistema com limites do llm_limits.json."""
        # Carregar limites reais do arquivo de configuração
        limits = self._load_limits_from_file()
        safety_margin = limits.get("config", {}).get("safety_margin", 0.8)
        
        # Obter limites por provider
        gemini_config = limits.get("google", {}).get("gemini-2.0-flash", {})
        openai_config = limits.get("openai", {}).get("gpt-4o-mini", {})
        openrouter1_config = limits.get("openrouter", {}).get("google/gemini-2.0-flash-lite-001", {})
        openrouter2_config = limits.get("openrouter", {}).get("google/gemini-2.5-flash-lite", {})
        openrouter3_config = limits.get("openrouter", {}).get("openai/gpt-4.1-nano", {})
        
        # Calcular max_concurrent baseado em RPM real (80% de segurança)
        gemini_rpm = gemini_config.get("rpm", 10000)
        openai_rpm = openai_config.get("rpm", 5000)
        openrouter1_rpm = openrouter1_config.get("rpm", 20000)
        openrouter2_rpm = openrouter2_config.get("rpm", 15000)
        openrouter3_rpm = openrouter3_config.get("rpm", 10000)
        
        # Obter pesos para distribuição proporcional
        gemini_weight = gemini_config.get("weight", 29)
        openai_weight = openai_config.get("weight", 14)
        openrouter1_weight = openrouter1_config.get("weight", 30)
        openrouter2_weight = openrouter2_config.get("weight", 25)
        openrouter3_weight = openrouter3_config.get("weight", 20)
        
        # Converter RPM para concorrência máxima razoável
        # Fórmula: (RPM * safety_margin) / 60 * avg_latency_seconds
        # Com avg_latency ~2s, dividir por 30 dá uma estimativa conservadora
        gemini_concurrent = max(200, int(gemini_rpm * safety_margin / 30))
        openai_concurrent = max(150, int(openai_rpm * safety_margin / 30))
        openrouter1_concurrent = max(300, int(openrouter1_rpm * safety_margin / 30))
        openrouter2_concurrent = max(250, int(openrouter2_rpm * safety_margin / 30))
        openrouter3_concurrent = max(200, int(openrouter3_rpm * safety_margin / 30))
        
        logger.info(f"LLM Limits carregados:")
        logger.info(f"  Google Gemini: RPM={gemini_rpm}, concurrent={gemini_concurrent}, weight={gemini_weight}%")
        logger.info(f"  OpenAI: RPM={openai_rpm}, concurrent={openai_concurrent}, weight={openai_weight}%")
        logger.info(f"  OpenRouter 1: RPM={openrouter1_rpm}, concurrent={openrouter1_concurrent}, weight={openrouter1_weight}%")
        logger.info(f"  OpenRouter 2: RPM={openrouter2_rpm}, concurrent={openrouter2_concurrent}, weight={openrouter2_weight}%")
        logger.info(f"  OpenRouter 3: RPM={openrouter3_rpm}, concurrent={openrouter3_concurrent}, weight={openrouter3_weight}%")
        
        default_providers = [
            # Google Gemini - API Nativa (alta prioridade, boa capacidade)
            ProviderConfig(
                name="Google Gemini",
                api_key=settings.GOOGLE_API_KEY or "",
                base_url=settings.GOOGLE_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/",
                model=settings.GOOGLE_MODEL or "gemini-2.0-flash",
                max_concurrent=gemini_concurrent,
                priority=70,
                weight=gemini_weight
            ),
            # OpenAI - API Nativa (prioridade média, capacidade moderada)
            ProviderConfig(
                name="OpenAI",
                api_key=settings.OPENAI_API_KEY or "",
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                max_concurrent=openai_concurrent,
                priority=60,
                weight=openai_weight
            ),
            # OpenRouter 1 - Gemini 2.0 Flash Lite (ALTA capacidade, prioridade alta)
            ProviderConfig(
                name="OpenRouter",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL,
                max_concurrent=openrouter1_concurrent,
                priority=80,  # Alta prioridade - maior capacidade
                weight=openrouter1_weight
            ),
            # OpenRouter 2 - Gemini 2.5 Flash Lite (boa capacidade, prioridade alta)
            ProviderConfig(
                name="OpenRouter2",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL_2,
                max_concurrent=openrouter2_concurrent,
                priority=75,  # Alta prioridade
                weight=openrouter2_weight
            ),
            # OpenRouter 3 - GPT-4.1 Nano (capacidade adicional)
            ProviderConfig(
                name="OpenRouter3",
                api_key=settings.OPENROUTER_API_KEY or "",
                base_url=settings.OPENROUTER_BASE_URL,
                model=settings.OPENROUTER_MODEL_3,
                max_concurrent=openrouter3_concurrent,
                priority=72,  # Prioridade boa
                weight=openrouter3_weight
            ),
        ]
        
        for config in default_providers:
            if config.api_key:
                self.add_provider(config)
    
    def _load_limits_from_file(self) -> dict:
        """Carrega limites do arquivo llm_limits.json."""
        import json
        from pathlib import Path
        
        limits_file = Path(__file__).parent.parent.parent / "core" / "llm_limits.json"
        
        try:
            if limits_file.exists():
                with open(limits_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Não foi possível carregar llm_limits.json: {e}")
        
        return {}
    
    def add_provider(self, config: ProviderConfig):
        """Adiciona um provider."""
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
        
        logger.info(f"ProviderManager: {config.name} adicionado (model={config.model})")
    
    def remove_provider(self, name: str):
        """Remove um provider."""
        self._configs.pop(name, None)
        self._clients.pop(name, None)
        self._semaphores.pop(name, None)
    
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
        """
        Gera lista de providers distribuídos por peso.
        
        Args:
            count: Número de itens a distribuir
        
        Returns:
            Lista de nomes de providers ordenados por peso
        
        Example:
            Com weights {A: 40, B: 30, C: 20, D: 10} e count=10:
            Retorna: [A, A, A, A, B, B, B, C, C, D]
        """
        providers = self.available_providers
        if not providers:
            return []
        
        # Obter pesos e calcular distribuição
        weights = self.provider_weights
        total_weight = sum(weights.get(p, 10) for p in providers)
        
        # Criar lista distribuída
        distributed = []
        for provider in providers:
            weight = weights.get(provider, 10)
            provider_count = max(1, int(count * weight / total_weight))
            distributed.extend([provider] * provider_count)
        
        # Ajustar para o tamanho exato se necessário
        while len(distributed) < count:
            # Adicionar do provider com maior peso
            best_provider = max(providers, key=lambda p: weights.get(p, 10))
            distributed.append(best_provider)
        
        # Embaralhar para não ter todos do mesmo provider seguidos
        import random
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
    
    async def _wait_for_priority(self, priority: LLMPriority):
        """
        Aguarda liberação baseada em prioridade.
        
        HIGH priority: passa direto
        NORMAL priority: aguarda se houver HIGH priority esperando
        """
        if priority == LLMPriority.HIGH:
            # HIGH priority: incrementa contador e passa
            async with self._priority_lock:
                self._high_priority_waiting += 1
                self._priority_event.clear()  # Bloqueia NORMAL
            return
        
        # NORMAL priority: aguarda até não haver HIGH priority esperando
        while True:
            async with self._priority_lock:
                if self._high_priority_waiting == 0:
                    return
            # Aguarda um pouco e verifica novamente
            await asyncio.sleep(0.05)
    
    async def _release_priority(self, priority: LLMPriority):
        """Libera slot de prioridade após conclusão."""
        if priority == LLMPriority.HIGH:
            async with self._priority_lock:
                self._high_priority_waiting = max(0, self._high_priority_waiting - 1)
                if self._high_priority_waiting == 0:
                    self._priority_event.set()  # Libera NORMAL
    
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
        Faz chamada a um provider.
        
        Args:
            provider: Nome do provider
            messages: Lista de mensagens
            timeout: Timeout opcional (usa padrão do provider se None)
            temperature: Temperatura da geração
            response_format: Formato de resposta (ex: {"type": "json_object"})
            ctx_label: Label de contexto para logs
            priority: Prioridade da chamada (HIGH para Discovery/LinkSelector, NORMAL para Profile)
        
        Returns:
            Tuple de (response_content, latency_ms)
        
        Raises:
            ProviderRateLimitError: Se rate limit
            ProviderTimeoutError: Se timeout
            ProviderBadRequestError: Se requisição inválida
            ProviderError: Para outros erros
        """
        config = self._configs.get(provider)
        if not config:
            raise ProviderError(f"Provider '{provider}' não encontrado")
        
        client = self._clients.get(provider)
        if not client:
            raise ProviderError(f"Cliente não inicializado para '{provider}'")
        
        semaphore = self._semaphores.get(provider)
        actual_timeout = timeout or config.timeout
        
        # Aguardar baseado em prioridade
        await self._wait_for_priority(priority)
        
        try:
            async with semaphore:
                start_time = time.perf_counter()
                
                try:
                    request_params = {
                        "model": config.model,
                        "messages": messages,
                        "temperature": temperature,
                        "timeout": actual_timeout
                    }
                    
                    if response_format:
                        request_params["response_format"] = response_format
                    
                    response = await client.chat.completions.create(**request_params)
                    
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    
                    if not response.choices or not response.choices[0].message.content:
                        raise ProviderError(f"{provider} retornou resposta vazia")
                    
                    content = response.choices[0].message.content.strip()
                    
                    logger.debug(
                        f"ProviderManager: {provider} - "
                        f"{len(content)} chars em {latency_ms:.0f}ms"
                    )
                    
                    return content, latency_ms
                
                except RateLimitError as e:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    logger.warning(f"{ctx_label}ProviderManager: {provider} RATE_LIMIT após {latency_ms:.0f}ms")
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
        finally:
            # Liberar slot de prioridade
            await self._release_priority(priority)
    
    async def call_with_retry(
        self,
        provider: str,
        messages: List[dict],
        max_retries: int = 2,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Tuple[str, float]:
        """
        Faz chamada com retry automático.
        
        Args:
            provider: Nome do provider
            messages: Lista de mensagens
            max_retries: Número máximo de retries
            retry_delay: Delay entre retries em segundos
            **kwargs: Argumentos adicionais para call()
        
        Returns:
            Tuple de (response_content, latency_ms)
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.call(provider, messages, **kwargs)
            
            except ProviderBadRequestError:
                # Não faz retry para bad request
                raise
            
            except (ProviderRateLimitError, ProviderTimeoutError, ProviderError) as e:
                last_error = e
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(
                        f"ProviderManager: {provider} retry {attempt + 1}/{max_retries} "
                        f"após {delay:.1f}s ({type(e).__name__})"
                    )
                    await asyncio.sleep(delay)
        
        raise last_error
    
    def get_status(self) -> dict:
        """Retorna status de todos os providers."""
        status = {}
        for name, config in self._configs.items():
            semaphore = self._semaphores.get(name)
            status[name] = {
                "enabled": config.enabled,
                "model": config.model,
                "priority": config.priority,
                "max_concurrent": config.max_concurrent,
                "semaphore_locked": semaphore.locked() if semaphore else None
            }
        return status


# Instância singleton
provider_manager = ProviderManager()

