"""
Monitor de saúde dos provedores LLM v2.0.
Rastreia métricas de performance e calcula health score.
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Tipos de falha para registro."""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    ERROR = "error"
    BAD_REQUEST = "bad_request"


@dataclass
class ProviderMetrics:
    """Métricas de um provider."""
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    rate_limits_hit: int = 0
    timeouts: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    health_score: int = 100
    recent_latencies: deque = field(default_factory=lambda: deque(maxlen=50))
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso (0.0 a 1.0)."""
        if self.requests_total == 0:
            return 1.0
        return self.requests_success / self.requests_total
    
    @property
    def avg_latency_ms(self) -> float:
        """Latência média em ms."""
        if not self.recent_latencies:
            return 0.0
        return sum(self.recent_latencies) / len(self.recent_latencies)


class HealthMonitor:
    """
    Monitora saúde dos providers LLM e calcula scores.
    
    Health Score (0-100):
    - success_rate: 40% do peso
    - latency_score: 30% do peso  
    - rate_limit_score: 20% do peso
    - recency_score: 10% do peso
    """
    
    SCORE_WEIGHTS = {
        "success_rate": 0.40,
        "latency": 0.30,
        "rate_limit": 0.20,
        "recency": 0.10
    }
    
    # Limiares
    UNHEALTHY_THRESHOLD = 30
    DEGRADED_THRESHOLD = 60
    LATENCY_IDEAL_MS = 2000
    LATENCY_MAX_MS = 30000
    
    def __init__(self):
        self._metrics: Dict[str, ProviderMetrics] = {}
        self._lock = asyncio.Lock()
    
    def _get_metrics(self, provider: str) -> ProviderMetrics:
        """Obtém ou cria métricas para um provider."""
        if provider not in self._metrics:
            self._metrics[provider] = ProviderMetrics()
        return self._metrics[provider]
    
    def record_success(self, provider: str, latency_ms: float):
        """
        Registra uma requisição bem-sucedida.
        
        Args:
            provider: Nome do provider
            latency_ms: Tempo de resposta em milissegundos
        """
        metrics = self._get_metrics(provider)
        metrics.requests_total += 1
        metrics.requests_success += 1
        metrics.total_latency_ms += latency_ms
        metrics.recent_latencies.append(latency_ms)
        metrics.last_success_time = time.time()
        
        # Recalcular score
        metrics.health_score = self._calculate_score(metrics)
        
        logger.debug(f"HealthMonitor: {provider} SUCCESS - {latency_ms:.0f}ms, score={metrics.health_score}")
    
    def record_failure(self, provider: str, failure_type: FailureType, latency_ms: float = 0):
        """
        Registra uma falha.
        
        Args:
            provider: Nome do provider
            failure_type: Tipo de falha
            latency_ms: Tempo até a falha
        """
        metrics = self._get_metrics(provider)
        metrics.requests_total += 1
        metrics.requests_failed += 1
        metrics.last_failure_time = time.time()
        
        if latency_ms > 0:
            metrics.recent_latencies.append(latency_ms)
        
        if failure_type == FailureType.TIMEOUT:
            metrics.timeouts += 1
        elif failure_type == FailureType.RATE_LIMIT:
            metrics.rate_limits_hit += 1
        else:
            metrics.errors += 1
        
        # Recalcular score
        metrics.health_score = self._calculate_score(metrics)
        
        logger.debug(f"HealthMonitor: {provider} FAILURE ({failure_type.value}) - score={metrics.health_score}")
    
    def _calculate_score(self, metrics: ProviderMetrics) -> int:
        """
        Calcula health score baseado nas métricas.
        
        Returns:
            Score de 0 a 100
        """
        # 1. Success Rate Score (0-100)
        success_score = metrics.success_rate * 100
        
        # 2. Latency Score (0-100)
        avg_latency = metrics.avg_latency_ms
        if avg_latency <= self.LATENCY_IDEAL_MS:
            latency_score = 100
        elif avg_latency >= self.LATENCY_MAX_MS:
            latency_score = 0
        else:
            ratio = (avg_latency - self.LATENCY_IDEAL_MS) / (self.LATENCY_MAX_MS - self.LATENCY_IDEAL_MS)
            latency_score = 100 * (1 - ratio)
        
        # 3. Rate Limit Score (0-100)
        if metrics.requests_total == 0:
            rate_limit_score = 100
        else:
            rate_limit_ratio = metrics.rate_limits_hit / metrics.requests_total
            rate_limit_score = 100 * (1 - min(rate_limit_ratio * 5, 1.0))  # 20% rate limits = 0
        
        # 4. Recency Score (0-100) - Penaliza se última falha foi recente
        now = time.time()
        if metrics.last_failure_time == 0:
            recency_score = 100
        else:
            time_since_failure = now - metrics.last_failure_time
            if time_since_failure < 10:  # < 10s
                recency_score = 30
            elif time_since_failure < 60:  # < 1min
                recency_score = 60
            elif time_since_failure < 300:  # < 5min
                recency_score = 80
            else:
                recency_score = 100
        
        # Calcular score final ponderado
        final_score = (
            success_score * self.SCORE_WEIGHTS["success_rate"] +
            latency_score * self.SCORE_WEIGHTS["latency"] +
            rate_limit_score * self.SCORE_WEIGHTS["rate_limit"] +
            recency_score * self.SCORE_WEIGHTS["recency"]
        )
        
        return max(0, min(100, int(final_score)))
    
    def get_health_score(self, provider: str) -> int:
        """Retorna health score de um provider."""
        metrics = self._get_metrics(provider)
        return metrics.health_score
    
    def is_healthy(self, provider: str) -> bool:
        """Verifica se provider está saudável (score > threshold)."""
        return self.get_health_score(provider) > self.UNHEALTHY_THRESHOLD
    
    def is_degraded(self, provider: str) -> bool:
        """Verifica se provider está degradado."""
        score = self.get_health_score(provider)
        return self.UNHEALTHY_THRESHOLD < score <= self.DEGRADED_THRESHOLD
    
    def get_healthy_providers(self, providers: List[str]) -> List[str]:
        """
        Retorna providers saudáveis ordenados por score.
        
        Args:
            providers: Lista de providers a considerar
        
        Returns:
            Lista de providers saudáveis ordenados (melhor primeiro)
        """
        healthy = [p for p in providers if self.is_healthy(p)]
        return sorted(healthy, key=lambda p: self.get_health_score(p), reverse=True)
    
    def get_best_provider(self, providers: List[str]) -> Optional[str]:
        """Retorna provider com melhor score."""
        healthy = self.get_healthy_providers(providers)
        return healthy[0] if healthy else None
    
    def get_metrics(self, provider: str) -> dict:
        """Retorna métricas detalhadas de um provider."""
        metrics = self._get_metrics(provider)
        return {
            "provider": provider,
            "health_score": metrics.health_score,
            "status": self._get_status_label(metrics.health_score),
            "requests_total": metrics.requests_total,
            "success_rate": f"{metrics.success_rate:.1%}",
            "avg_latency_ms": f"{metrics.avg_latency_ms:.0f}",
            "rate_limits": metrics.rate_limits_hit,
            "timeouts": metrics.timeouts,
            "errors": metrics.errors,
        }
    
    def _get_status_label(self, score: int) -> str:
        """Retorna label de status baseado no score."""
        if score > self.DEGRADED_THRESHOLD:
            return "HEALTHY"
        elif score > self.UNHEALTHY_THRESHOLD:
            return "DEGRADED"
        else:
            return "UNHEALTHY"
    
    def get_all_metrics(self) -> Dict[str, dict]:
        """Retorna métricas de todos os providers."""
        return {
            provider: self.get_metrics(provider)
            for provider in self._metrics
        }
    
    def reset(self, provider: str = None):
        """
        Reseta métricas de provider(s).
        
        Args:
            provider: Provider específico ou None para todos
        """
        if provider:
            if provider in self._metrics:
                self._metrics[provider] = ProviderMetrics()
                logger.info(f"HealthMonitor: Reset {provider}")
        else:
            self._metrics.clear()
            logger.info("HealthMonitor: Reset all metrics")


# Instância singleton
health_monitor = HealthMonitor()


# Background monitor task
_monitor_task = None


async def periodic_health_log():
    """Log periódico de métricas de saúde."""
    await asyncio.sleep(30)
    
    while True:
        try:
            metrics = health_monitor.get_all_metrics()
            if metrics:
                for provider, data in metrics.items():
                    logger.info(
                        f"📊 [HEALTH] {provider}: "
                        f"score={data['health_score']}, "
                        f"status={data['status']}, "
                        f"success={data['success_rate']}, "
                        f"latency={data['avg_latency_ms']}ms"
                    )
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"HealthMonitor: Erro no log periódico: {e}")
            await asyncio.sleep(30)


def start_health_monitor():
    """Inicia o monitor de saúde em background."""
    global _monitor_task
    _monitor_task = asyncio.create_task(periodic_health_log())
    logger.info("🏥 HealthMonitor: Background logging iniciado")


def stop_health_monitor():
    """Para o monitor de saúde."""
    global _monitor_task
    if _monitor_task:
        _monitor_task.cancel()
        _monitor_task = None
        logger.info("🏥 HealthMonitor: Background logging parado")
