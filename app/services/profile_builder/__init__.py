"""
Módulo Profile Builder v3.0

Responsável por analisar conteúdo scraped e extrair perfis de empresas.

Este módulo contém:
- LLMService: Serviço principal de análise de conteúdo
- Processamento de conteúdo (chunking, normalização, merge)
- Configurações específicas de perfil

Para gerenciamento de chamadas LLM (rate limiting, health monitoring, etc),
use o módulo app.services.llm_manager
"""

# Serviço principal
from .llm_service import analyze_content, get_llm_service, LLMService

# Processamento de conteúdo
# NOTA: chunk_content e estimate_tokens foram movidos para app.core.chunking
# Use: from app.core.chunking import process_content
#      from app.core.token_utils import estimate_tokens
from .profile_merger import merge_profiles
from .response_normalizer import normalize_llm_response

# Configuração local
from .constants import llm_config, LLMConfig, SYSTEM_PROMPT

# Caller legado (para compatibilidade)
from .provider_caller import (
    call_llm,
    analyze_content_with_fallback,
    process_chunk_with_retry
)

__all__ = [
    # Função principal
    'analyze_content',
    'get_llm_service',
    'LLMService',
    
    # Configuração
    'llm_config',
    'LLMConfig',
    'SYSTEM_PROMPT',
    
    # Merge
    'merge_profiles',
    
    # Normalização
    'normalize_llm_response',
    
    # Caller legado
    'call_llm',
    'analyze_content_with_fallback',
    'process_chunk_with_retry',
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
