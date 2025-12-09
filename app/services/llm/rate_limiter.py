"""
Rate Limiter usando algoritmo Token Bucket.
Controla a taxa de requisições por provider de forma assíncrona.
"""

import asyncio
import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BucketConfig:
    """Configuração de um bucket."""
    tokens_per_minute: int
    max_tokens: int = None
    
    def __post_init__(self):
        if self.max_tokens is None:
            self.max_tokens = self.tokens_per_minute


class TokenBucket:
    """
    Implementa algoritmo Token Bucket para rate limiting.
    Thread-safe para uso assíncrono.
    """
    
    def __init__(self, tokens_per_minute: int, max_tokens: int = None):
        self.tpm = tokens_per_minute
        self.max_tokens = max_tokens or tokens_per_minute
        self.tokens = float(self.max_tokens)
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
        self._refill_rate = self.tpm / 60.0  # tokens por segundo
    
    async def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Aguarda até ter tokens disponíveis ou timeout.
        
        Args:
            tokens: Quantidade de tokens necessários
            timeout: Tempo máximo de espera em segundos
        
        Returns:
            True se adquiriu tokens, False se timeout
        """
        start_time = time.monotonic()
        
        while True:
            async with self.lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # Verificar timeout
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                logger.warning(f"TokenBucket: Timeout após {elapsed:.1f}s aguardando {tokens} tokens")
                return False
            
            # Calcular tempo de espera
            wait_time = self._get_wait_time(tokens)
            remaining_timeout = timeout - elapsed
            actual_wait = min(wait_time, remaining_timeout, 1.0)
            
            await asyncio.sleep(actual_wait)
    
    def _refill(self):
        """Reabastece tokens baseado no tempo passado."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        
        # Adicionar tokens proporcionalmente ao tempo
        tokens_to_add = elapsed * self._refill_rate
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def _get_wait_time(self, tokens: int) -> float:
        """
        Calcula tempo estimado de espera para conseguir tokens.
        
        Args:
            tokens: Quantidade de tokens necessários
        
        Returns:
            Tempo estimado em segundos
        """
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self._refill_rate
    
    @property
    def available_tokens(self) -> float:
        """Retorna quantidade atual de tokens (sem refill)."""
        return self.tokens
    
    @property
    def utilization(self) -> float:
        """Retorna taxa de utilização (0.0 a 1.0)."""
        return 1.0 - (self.tokens / self.max_tokens)
    
    def get_status(self) -> dict:
        """Retorna status atual do bucket."""
        return {
            "tokens": round(self.tokens, 2),
            "max_tokens": self.max_tokens,
            "tpm": self.tpm,
            "utilization": f"{self.utilization:.1%}",
            "wait_time_1_token": f"{self._get_wait_time(1):.2f}s"
        }


class RateLimiter:
    """
    Gerencia múltiplos buckets de tokens por provider.
    Carrega limites reais do arquivo llm_limits.json.
    """
    
    # Configurações padrão por provider (RPM - requests per minute)
    # Valores baseados em 80% dos limites reais para segurança
    DEFAULT_CONFIGS = {
        "Google Gemini": BucketConfig(tokens_per_minute=8000, max_tokens=400),   # 80% de 10k RPM
        "OpenAI": BucketConfig(tokens_per_minute=4000, max_tokens=200),           # 80% de 5k RPM
        "OpenRouter": BucketConfig(tokens_per_minute=16000, max_tokens=600),      # 80% de 20k RPM
        "OpenRouter2": BucketConfig(tokens_per_minute=12000, max_tokens=500),     # 80% de 15k RPM
        "OpenRouter3": BucketConfig(tokens_per_minute=8000, max_tokens=350),      # 80% de 10k RPM (GPT-4.1 Nano)
    }
    
    def __init__(self, configs: Dict[str, BucketConfig] = None):
        self._configs = configs or self._load_configs_from_file()
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    def _load_configs_from_file(self) -> Dict[str, BucketConfig]:
        """Carrega configurações do arquivo llm_limits.json."""
        import json
        from pathlib import Path
        
        limits_file = Path(__file__).parent.parent.parent / "core" / "llm_limits.json"
        
        try:
            if limits_file.exists():
                with open(limits_file, 'r') as f:
                    limits = json.load(f)
                
                safety_margin = limits.get("config", {}).get("safety_margin", 0.8)
                
                # Mapear providers para seus limites
                configs = {}
                
                # Google Gemini
                gemini_rpm = limits.get("google", {}).get("gemini-2.0-flash", {}).get("rpm", 10000)
                configs["Google Gemini"] = BucketConfig(
                    tokens_per_minute=int(gemini_rpm * safety_margin),
                    max_tokens=int(gemini_rpm * safety_margin / 20)
                )
                
                # OpenAI
                openai_rpm = limits.get("openai", {}).get("gpt-4o-mini", {}).get("rpm", 5000)
                configs["OpenAI"] = BucketConfig(
                    tokens_per_minute=int(openai_rpm * safety_margin),
                    max_tokens=int(openai_rpm * safety_margin / 20)
                )
                
                # OpenRouter 1
                or1_rpm = limits.get("openrouter", {}).get("google/gemini-2.0-flash-lite-001", {}).get("rpm", 20000)
                configs["OpenRouter"] = BucketConfig(
                    tokens_per_minute=int(or1_rpm * safety_margin),
                    max_tokens=int(or1_rpm * safety_margin / 20)
                )
                
                # OpenRouter 2
                or2_rpm = limits.get("openrouter", {}).get("google/gemini-2.5-flash-lite", {}).get("rpm", 15000)
                configs["OpenRouter2"] = BucketConfig(
                    tokens_per_minute=int(or2_rpm * safety_margin),
                    max_tokens=int(or2_rpm * safety_margin / 20)
                )
                
                # OpenRouter 3 (GPT-4.1 Nano)
                or3_rpm = limits.get("openrouter", {}).get("openai/gpt-4.1-nano", {}).get("rpm", 10000)
                configs["OpenRouter3"] = BucketConfig(
                    tokens_per_minute=int(or3_rpm * safety_margin),
                    max_tokens=int(or3_rpm * safety_margin / 20)
                )
                
                logger.info(f"RateLimiter: Carregou limites do arquivo - {len(configs)} providers")
                for name, cfg in configs.items():
                    logger.debug(f"  {name}: {cfg.tokens_per_minute} RPM, max_burst={cfg.max_tokens}")
                
                return configs
                
        except Exception as e:
            logger.warning(f"RateLimiter: Erro ao carregar llm_limits.json: {e}, usando defaults")
        
        return self.DEFAULT_CONFIGS
    
    def _get_or_create_bucket(self, provider: str) -> TokenBucket:
        """Obtém ou cria bucket para um provider."""
        if provider not in self._buckets:
            config = self._configs.get(provider, BucketConfig(tokens_per_minute=60))
            self._buckets[provider] = TokenBucket(
                tokens_per_minute=config.tokens_per_minute,
                max_tokens=config.max_tokens
            )
        return self._buckets[provider]
    
    async def acquire(self, provider: str, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Adquire tokens para um provider específico.
        
        Args:
            provider: Nome do provider
            tokens: Quantidade de tokens
            timeout: Timeout máximo
        
        Returns:
            True se adquiriu, False se timeout
        """
        bucket = self._get_or_create_bucket(provider)
        result = await bucket.acquire(tokens, timeout)
        
        if result:
            logger.debug(f"RateLimiter: {provider} - Adquirido {tokens} token(s)")
        else:
            logger.warning(f"RateLimiter: {provider} - Falha ao adquirir {tokens} token(s)")
        
        return result
    
    def get_wait_time(self, provider: str, tokens: int = 1) -> float:
        """Retorna tempo de espera estimado para um provider."""
        bucket = self._get_or_create_bucket(provider)
        return bucket._get_wait_time(tokens)
    
    def get_available_tokens(self, provider: str) -> float:
        """Retorna tokens disponíveis para um provider."""
        bucket = self._get_or_create_bucket(provider)
        return bucket.available_tokens
    
    def get_best_provider(self, providers: list, tokens: int = 1) -> Optional[str]:
        """
        Retorna o provider com menor tempo de espera.
        
        Args:
            providers: Lista de providers a considerar
            tokens: Tokens necessários
        
        Returns:
            Nome do provider ou None se nenhum disponível
        """
        best_provider = None
        min_wait = float('inf')
        
        for provider in providers:
            wait = self.get_wait_time(provider, tokens)
            if wait < min_wait:
                min_wait = wait
                best_provider = provider
        
        return best_provider
    
    def get_status(self) -> dict:
        """Retorna status de todos os buckets."""
        return {
            provider: bucket.get_status()
            for provider, bucket in self._buckets.items()
        }
    
    def reset(self, provider: str = None):
        """
        Reseta bucket(s) para capacidade máxima.
        
        Args:
            provider: Provider específico ou None para todos
        """
        if provider:
            if provider in self._buckets:
                bucket = self._buckets[provider]
                bucket.tokens = bucket.max_tokens
                logger.info(f"RateLimiter: Reset {provider}")
        else:
            for name, bucket in self._buckets.items():
                bucket.tokens = bucket.max_tokens
            logger.info("RateLimiter: Reset all buckets")


# Instância singleton
rate_limiter = RateLimiter()

