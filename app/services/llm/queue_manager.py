"""
Gerenciador de filas para requisições LLM.
Seleciona o melhor provider baseado em saúde e disponibilidade.
"""

import asyncio
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .rate_limiter import RateLimiter, rate_limiter
from .health_monitor import HealthMonitor, health_monitor

logger = logging.getLogger(__name__)


@dataclass
class ProviderSelection:
    """Resultado da seleção de provider."""
    provider: str
    reason: str
    health_score: int
    estimated_wait: float


class QueueManager:
    """
    Gerencia seleção de providers para requisições LLM.
    
    Critérios de seleção (em ordem):
    1. Saúde (health_score > threshold)
    2. Disponibilidade (tokens no bucket)
    3. Prioridade configurada
    """
    
    def __init__(
        self,
        rate_limiter: RateLimiter,
        health_monitor: HealthMonitor,
        providers: List[str],
        priorities: dict = None
    ):
        self.rate_limiter = rate_limiter
        self.health_monitor = health_monitor
        self.providers = providers
        self.priorities = priorities or {}
        self._round_robin_index = 0
        self._lock = asyncio.Lock()
    
    async def get_best_provider(
        self,
        estimated_tokens: int = 1,
        exclude: List[str] = None
    ) -> Optional[ProviderSelection]:
        """
        Seleciona o melhor provider disponível.
        
        Args:
            estimated_tokens: Tokens estimados para a requisição
            exclude: Providers a excluir da seleção
        
        Returns:
            ProviderSelection ou None se nenhum disponível
        """
        exclude = exclude or []
        available_providers = [p for p in self.providers if p not in exclude]
        
        if not available_providers:
            logger.warning("QueueManager: Nenhum provider disponível")
            return None
        
        # 1. Filtrar providers saudáveis
        healthy_providers = self.health_monitor.get_healthy_providers(available_providers)
        
        if not healthy_providers:
            # Fallback: usar qualquer provider mesmo não saudável
            logger.warning("QueueManager: Nenhum provider saudável, usando fallback")
            healthy_providers = available_providers
        
        # 2. Ordenar por disponibilidade (menor tempo de espera)
        provider_scores = []
        for provider in healthy_providers:
            health_score = self.health_monitor.get_health_score(provider)
            wait_time = self.rate_limiter.get_wait_time(provider, estimated_tokens)
            priority = self.priorities.get(provider, 50)  # 0-100, maior = melhor
            
            # Score combinado (maior = melhor)
            combined_score = (health_score * 0.5) + (priority * 0.3) + ((100 - min(wait_time * 10, 100)) * 0.2)
            provider_scores.append((provider, combined_score, health_score, wait_time))
        
        # Ordenar por score combinado
        provider_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not provider_scores:
            return None
        
        best = provider_scores[0]
        selection = ProviderSelection(
            provider=best[0],
            reason=self._get_selection_reason(best[0], healthy_providers),
            health_score=best[2],
            estimated_wait=best[3]
        )
        
        logger.debug(
            f"QueueManager: Selecionado {selection.provider} "
            f"(score={selection.health_score}, wait={selection.estimated_wait:.2f}s, "
            f"reason={selection.reason})"
        )
        
        return selection
    
    def _get_selection_reason(self, provider: str, healthy_providers: List[str]) -> str:
        """Gera razão da seleção para logging."""
        if provider == healthy_providers[0]:
            return "best_health_score"
        elif self.priorities.get(provider, 0) == max(self.priorities.values(), default=0):
            return "highest_priority"
        else:
            return "best_combined_score"
    
    async def acquire_slot(
        self,
        provider: str,
        tokens: int = 1,
        timeout: float = 30.0
    ) -> bool:
        """
        Adquire um slot para fazer requisição a um provider.
        
        Args:
            provider: Nome do provider
            tokens: Tokens necessários
            timeout: Tempo máximo de espera
        
        Returns:
            True se conseguiu slot, False se timeout
        """
        return await self.rate_limiter.acquire(provider, tokens, timeout)
    
    async def get_and_acquire(
        self,
        estimated_tokens: int = 1,
        timeout: float = 30.0,
        exclude: List[str] = None
    ) -> Optional[Tuple[str, ProviderSelection]]:
        """
        Seleciona melhor provider e adquire slot.
        
        Args:
            estimated_tokens: Tokens estimados
            timeout: Timeout para aquisição
            exclude: Providers a excluir
        
        Returns:
            Tuple de (provider_name, selection) ou None
        """
        selection = await self.get_best_provider(estimated_tokens, exclude)
        
        if not selection:
            return None
        
        acquired = await self.acquire_slot(selection.provider, estimated_tokens, timeout)
        
        if acquired:
            return selection.provider, selection
        
        # Se falhou, tentar próximo provider
        new_exclude = (exclude or []) + [selection.provider]
        return await self.get_and_acquire(estimated_tokens, timeout, new_exclude)
    
    def get_next_provider_round_robin(self, exclude: List[str] = None) -> Optional[str]:
        """
        Retorna próximo provider usando round-robin.
        Útil para distribuição uniforme de carga.
        """
        exclude = exclude or []
        available = [p for p in self.providers if p not in exclude]
        
        if not available:
            return None
        
        provider = available[self._round_robin_index % len(available)]
        self._round_robin_index += 1
        
        return provider
    
    def get_status(self) -> dict:
        """Retorna status atual do gerenciador."""
        return {
            "providers": {
                provider: {
                    "health_score": self.health_monitor.get_health_score(provider),
                    "is_healthy": self.health_monitor.is_healthy(provider),
                    "priority": self.priorities.get(provider, 50),
                    "rate_limit_status": self.rate_limiter.get_status().get(provider, {})
                }
                for provider in self.providers
            },
            "total_providers": len(self.providers),
            "healthy_providers": len(self.health_monitor.get_healthy_providers(self.providers))
        }


# Factory function para criar instância configurada
def create_queue_manager(providers: List[str], priorities: dict = None) -> QueueManager:
    """
    Cria QueueManager com rate_limiter e health_monitor globais.
    
    Args:
        providers: Lista de providers disponíveis
        priorities: Dict de prioridades {provider: score}
    
    Returns:
        QueueManager configurado
    """
    return QueueManager(
        rate_limiter=rate_limiter,
        health_monitor=health_monitor,
        providers=providers,
        priorities=priorities
    )

