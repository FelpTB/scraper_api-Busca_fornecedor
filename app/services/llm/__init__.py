"""
Módulo de LLM v2.0

Responsável por analisar conteúdo scraped e extrair perfis de empresas.
Suporta múltiplos provedores com balanceamento de carga e fallback.
"""

from .llm_service import analyze_content, get_llm_service, LLMService
from .health_monitor import (
    health_monitor,
    HealthMonitor,
    FailureType,
    start_health_monitor,
    stop_health_monitor
)
from .rate_limiter import rate_limiter, RateLimiter, TokenBucket
from .queue_manager import create_queue_manager, QueueManager
from .provider_manager import (
    provider_manager,
    ProviderManager,
    ProviderConfig,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderBadRequestError
)
from .constants import llm_config, LLMConfig, SYSTEM_PROMPT
from .content_chunker import chunk_content, estimate_tokens
from .profile_merger import merge_profiles
from .response_normalizer import normalize_llm_response

__all__ = [
    # Função principal
    'analyze_content',
    'get_llm_service',
    'LLMService',
    
    # Health Monitor v2.0
    'health_monitor',
    'HealthMonitor',
    'FailureType',
    'start_health_monitor',
    'stop_health_monitor',
    
    # Rate Limiter v2.0
    'rate_limiter',
    'RateLimiter',
    'TokenBucket',
    
    # Queue Manager v2.0
    'create_queue_manager',
    'QueueManager',
    
    # Provider Manager v2.0
    'provider_manager',
    'ProviderManager',
    'ProviderConfig',
    'ProviderError',
    'ProviderRateLimitError',
    'ProviderTimeoutError',
    'ProviderBadRequestError',
    
    # Configuração
    'llm_config',
    'LLMConfig',
    'SYSTEM_PROMPT',
    
    # Chunking
    'chunk_content',
    'estimate_tokens',
    
    # Merge
    'merge_profiles',
    
    # Normalização
    'normalize_llm_response',
]


def configure_llm(**kwargs):
    """
    Configura dinamicamente os parâmetros do LLM.
    
    Parâmetros aceitos:
        max_chunk_tokens: int
        chars_per_token: int
        group_target_tokens: int
        min_chunk_chars: int
        similarity_threshold: float
    """
    llm_config.update(**kwargs)
