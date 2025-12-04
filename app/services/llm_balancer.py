"""
Serviço centralizado de Load Balancing para chamadas LLM.

Responsável por:
- Gerenciar semáforos de concorrência por provedor
- Selecionar o provedor com distribuição round-robin + fallback
- Fornecer clientes configurados para cada provedor
- Registrar métricas de performance

Usado por: discovery.py e llm.py
"""

import asyncio
import logging
import time
import threading
import itertools
from typing import Optional, Tuple, List
from collections import defaultdict
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- ROUND-ROBIN STATE ---
# Contador thread-safe para distribuição round-robin
_round_robin_lock = threading.Lock()
_round_robin_index = 0

# --- CONFIGURAÇÃO DE PROVEDORES ---
# Limites de concorrência por provedor
LLM_CONFIG = {
    'global_semaphore_limit': 500,
    'google_gemini_semaphore_limit': 300,
    'openai_semaphore_limit': 250,
}

# Definição dos provedores disponíveis
# Formato: (nome, api_key, base_url, model)
_PROVIDER_DEFINITIONS = [
    ("Google Gemini", settings.GOOGLE_API_KEY, settings.GOOGLE_BASE_URL, settings.GOOGLE_MODEL),
    ("OpenAI", settings.OPENAI_API_KEY, settings.OPENAI_BASE_URL, settings.OPENAI_MODEL),
]

# Filtrar apenas provedores com chave configurada
AVAILABLE_PROVIDERS: List[Tuple[str, str, str, str]] = [
    (name, key, url, model) 
    for name, key, url, model in _PROVIDER_DEFINITIONS 
    if key
]

if not AVAILABLE_PROVIDERS:
    logger.error("CRITICAL: Nenhum provedor de LLM configurado! Defina pelo menos uma API key.")

# --- SEMÁFOROS ---
# Inicializados com base na configuração
llm_semaphores = {
    "Google Gemini": asyncio.Semaphore(LLM_CONFIG['google_gemini_semaphore_limit']),
    "OpenAI": asyncio.Semaphore(LLM_CONFIG['openai_semaphore_limit']),
}

llm_global_semaphore = asyncio.Semaphore(LLM_CONFIG['global_semaphore_limit'])


# --- PERFORMANCE TRACKER ---
class LLMPerformanceTracker:
    """
    Rastreia métricas de performance dos providers LLM.
    Thread-safe para uso em ambiente assíncrono.
    """
    def __init__(self):
        self.stats = defaultdict(lambda: {
            'requests': 0,
            'successes': 0,
            'timeouts': 0,
            'errors': 0,
            'rate_limits': 0,
            'total_response_time': 0,
            'last_reset': time.time(),
            'active_requests': 0,
            'max_concurrency': 0
        })
        self.lock = threading.Lock()

    def start_request(self, provider_name: str):
        """Registra início de uma requisição"""
        with self.lock:
            stats = self.stats[provider_name]
            stats['active_requests'] += 1
            if stats['active_requests'] > stats['max_concurrency']:
                stats['max_concurrency'] = stats['active_requests']

    def record_request(self, provider_name: str, success: bool = False, timeout: bool = False,
                      error: bool = False, rate_limit: bool = False, response_time: float = 0):
        """Registra resultado de uma requisição"""
        with self.lock:
            stats = self.stats[provider_name]
            stats['active_requests'] = max(0, stats['active_requests'] - 1)
            stats['requests'] += 1
            if success:
                stats['successes'] += 1
            if timeout:
                stats['timeouts'] += 1
            if error:
                stats['errors'] += 1
            if rate_limit:
                stats['rate_limits'] += 1
            if response_time > 0:
                stats['total_response_time'] += response_time

    def get_summary(self, provider_name: str = None) -> dict:
        """Retorna resumo de métricas"""
        with self.lock:
            if provider_name:
                return dict(self.stats[provider_name])
            return {k: dict(v) for k, v in self.stats.items()}

    def log_summary(self):
        """Log resumo de performance de todos os provedores"""
        with self.lock:
            for p_name, stats in self.stats.items():
                if stats['requests'] == 0:
                    continue
                success_rate = (stats['successes'] / stats['requests']) * 100
                avg_time = stats['total_response_time'] / max(stats['requests'], 1)
                logger.info(f"📊 [PROVIDER_SUMMARY] {p_name} - "
                           f"Requests: {stats['requests']}, "
                           f"Success: {success_rate:.1f}%, "
                           f"Avg Time: {avg_time:.2f}s")


# Instância global do tracker
performance_tracker = LLMPerformanceTracker()


# --- FUNÇÕES DE LOAD BALANCING ---

def _get_next_round_robin_index() -> int:
    """
    Retorna o próximo índice para round-robin de forma thread-safe.
    """
    global _round_robin_index
    with _round_robin_lock:
        idx = _round_robin_index
        _round_robin_index = (_round_robin_index + 1) % len(AVAILABLE_PROVIDERS)
        return idx


def _is_provider_available(provider_name: str) -> bool:
    """
    Verifica se um provedor está disponível (semáforo não está locked).
    
    Args:
        provider_name: Nome do provedor
        
    Returns:
        True se disponível, False se semáforo está locked
    """
    semaphore = llm_semaphores.get(provider_name)
    if semaphore is None:
        return False
    return not semaphore.locked()


def select_least_loaded_provider() -> str:
    """
    Seleciona o provedor LLM usando estratégia HÍBRIDA:
    
    1. ROUND-ROBIN: Alterna entre provedores para distribuição uniforme (50/50)
    2. FALLBACK: Se o provedor selecionado estiver com semáforo locked,
       usa o próximo disponível
    
    Estratégia:
    - Garante distribuição uniforme quando ambos provedores estão disponíveis
    - Evita espera desnecessária quando um provedor está sobrecarregado
    
    Performance: ~1μs por chamada (thread-safe com lock mínimo)
    
    Returns:
        str: Nome do provedor selecionado
    """
    if len(AVAILABLE_PROVIDERS) == 1:
        return AVAILABLE_PROVIDERS[0][0]
    
    # 1. Obter próximo provedor via round-robin
    idx = _get_next_round_robin_index()
    primary_provider = AVAILABLE_PROVIDERS[idx][0]
    
    # 2. Verificar se o provedor está disponível (semáforo não locked)
    if _is_provider_available(primary_provider):
        logger.info(f"🔄 [ROUND_ROBIN] Selecionado: {primary_provider} (índice {idx})")
        return primary_provider
    
    # 3. Fallback: tentar outros provedores
    for i in range(len(AVAILABLE_PROVIDERS)):
        fallback_idx = (idx + i + 1) % len(AVAILABLE_PROVIDERS)
        fallback_provider = AVAILABLE_PROVIDERS[fallback_idx][0]
        
        if _is_provider_available(fallback_provider):
            logger.info(f"🔄 [ROUND_ROBIN] Fallback: {fallback_provider} "
                       f"({primary_provider} está com semáforo locked)")
            return fallback_provider
    
    # 4. Todos locked: retornar o primário mesmo assim (vai esperar no semáforo)
    logger.warning(f"⚠️ [ROUND_ROBIN] Todos provedores com semáforo locked, "
                  f"usando {primary_provider} (vai aguardar)")
    return primary_provider


def select_provider_by_load() -> str:
    """
    Seleciona o provedor LLM com menor carga no momento.
    Método alternativo ao round-robin para casos específicos.
    
    Estratégia de seleção (O(n) onde n = número de provedores):
    1. Calcula score de carga: locked (1000) + waiters (quantidade na fila)
    2. Retorna provedor com menor score
    
    Returns:
        str: Nome do provedor com menor carga
    """
    if len(AVAILABLE_PROVIDERS) == 1:
        return AVAILABLE_PROVIDERS[0][0]
    
    min_load = float('inf')
    selected_provider = AVAILABLE_PROVIDERS[0][0]
    
    for provider_name, _, _, _ in AVAILABLE_PROVIDERS:
        semaphore = llm_semaphores.get(provider_name)
        if semaphore is None:
            continue
        
        load_score = 0
        
        if semaphore.locked():
            load_score += 1000
        
        if hasattr(semaphore, '_waiters') and semaphore._waiters is not None:
            load_score += len(semaphore._waiters)
        
        if load_score < min_load:
            min_load = load_score
            selected_provider = provider_name
    
    return selected_provider


def get_round_robin_stats() -> dict:
    """
    Retorna estatísticas do round-robin para monitoramento.
    
    Returns:
        dict com índice atual e total de provedores
    """
    with _round_robin_lock:
        return {
            'current_index': _round_robin_index,
            'total_providers': len(AVAILABLE_PROVIDERS),
            'providers': [p[0] for p in AVAILABLE_PROVIDERS]
        }


def get_provider_config(provider_name: str) -> Optional[Tuple[str, str, str]]:
    """
    Retorna configuração de um provedor específico.
    
    Args:
        provider_name: Nome do provedor
        
    Returns:
        Tuple[api_key, base_url, model] ou None se não encontrado
    """
    for name, key, url, model in AVAILABLE_PROVIDERS:
        if name == provider_name:
            return (key, url, model)
    return None


def get_client_for_provider(provider_name: str) -> Optional[AsyncOpenAI]:
    """
    Cria e retorna um cliente AsyncOpenAI para o provedor especificado.
    
    Args:
        provider_name: Nome do provedor
        
    Returns:
        AsyncOpenAI client ou None se provedor não encontrado
    """
    config = get_provider_config(provider_name)
    if config is None:
        logger.error(f"❌ Provedor '{provider_name}' não encontrado")
        return None
    
    api_key, base_url, _ = config
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_model_for_provider(provider_name: str) -> Optional[str]:
    """
    Retorna o modelo configurado para um provedor.
    
    Args:
        provider_name: Nome do provedor
        
    Returns:
        Nome do modelo ou None se provedor não encontrado
    """
    config = get_provider_config(provider_name)
    if config is None:
        return None
    return config[2]


def get_semaphore_for_provider(provider_name: str) -> asyncio.Semaphore:
    """
    Retorna o semáforo de concorrência para um provedor.
    
    Args:
        provider_name: Nome do provedor
        
    Returns:
        Semáforo do provedor ou semáforo padrão com limite 3
    """
    return llm_semaphores.get(provider_name, asyncio.Semaphore(3))


def get_global_semaphore() -> asyncio.Semaphore:
    """Retorna o semáforo global de concorrência."""
    return llm_global_semaphore


def log_load_balance_decision(context: str, provider: str):
    """
    Log da decisão de load balancing (nível DEBUG para reduzir ruído).
    
    Args:
        context: Contexto da decisão (ex: "discovery", "profile_single_chunk")
        provider: Provedor selecionado
    """
    logger.debug(f"🔄 [LOAD_BALANCE] {context}: selecionado {provider}")

