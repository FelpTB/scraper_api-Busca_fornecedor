"""
LLM Manager v2.0

Módulo centralizado para gerenciamento de chamadas LLM.
Responsável por:
- Rate limiting separado por RPM (Requests/min) e TPM (Tokens/min)
- Balanceamento de carga (weighted distribution)
- Health monitoring
- Sistema de prioridades (HIGH para Discovery/LinkSelector, NORMAL para Profile)
- Fallback automático entre providers

Todos os serviços devem usar este módulo para fazer chamadas LLM.

Limites configurados na seção llm_limits do concurrency_config.json:
- RPM: Quantidade de chamadas à API por minuto
- TPM: Quantidade de tokens processados por minuto
"""

from .priority import LLMPriority
from .rate_limiter import (
    rate_limiter,
    RateLimiter,
    TokenBucket,
    BucketConfig,
    ProviderLimits,
    ProviderRateLimiter
)
from .health_monitor import (
    health_monitor,
    HealthMonitor,
    FailureType,
    start_health_monitor,
    stop_health_monitor
)
from .queue_manager import create_queue_manager, QueueManager, ProviderSelection
from .provider_manager import (
    provider_manager,
    ProviderManager,
    ProviderConfig,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderBadRequestError,
    estimate_tokens
)
from .manager import LLMCallManager, get_llm_manager

__all__ = [
    # Manager principal
    'LLMCallManager',
    'get_llm_manager',
    
    # Prioridade
    'LLMPriority',
    
    # Rate Limiter v2.0 (RPM + TPM)
    'rate_limiter',
    'RateLimiter',
    'TokenBucket',
    'BucketConfig',
    'ProviderLimits',
    'ProviderRateLimiter',
    
    # Health Monitor
    'health_monitor',
    'HealthMonitor',
    'FailureType',
    'start_health_monitor',
    'stop_health_monitor',
    
    # Queue Manager
    'create_queue_manager',
    'QueueManager',
    'ProviderSelection',
    
    # Provider Manager
    'provider_manager',
    'ProviderManager',
    'ProviderConfig',
    'ProviderError',
    'ProviderRateLimitError',
    'ProviderTimeoutError',
    'ProviderBadRequestError',
    'estimate_tokens',
]
