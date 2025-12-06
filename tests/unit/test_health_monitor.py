"""
Testes unitários para o Health Monitor.
"""

import pytest
import time
from app.services.llm.health_monitor import HealthMonitor, FailureType, ProviderMetrics


class TestProviderMetrics:
    """Testes para ProviderMetrics."""
    
    def test_success_rate_no_requests(self):
        """Success rate deve ser 1.0 sem requisições."""
        metrics = ProviderMetrics()
        assert metrics.success_rate == 1.0
    
    def test_success_rate_all_success(self):
        """Success rate deve ser 1.0 com 100% sucesso."""
        metrics = ProviderMetrics()
        metrics.requests_total = 10
        metrics.requests_success = 10
        assert metrics.success_rate == 1.0
    
    def test_success_rate_partial(self):
        """Success rate deve refletir proporção."""
        metrics = ProviderMetrics()
        metrics.requests_total = 10
        metrics.requests_success = 7
        assert metrics.success_rate == 0.7
    
    def test_avg_latency_empty(self):
        """Latência média deve ser 0 sem dados."""
        metrics = ProviderMetrics()
        assert metrics.avg_latency_ms == 0.0
    
    def test_avg_latency_with_data(self):
        """Latência média deve ser calculada corretamente."""
        metrics = ProviderMetrics()
        metrics.recent_latencies.extend([100, 200, 300])
        assert metrics.avg_latency_ms == 200.0


class TestHealthMonitor:
    """Testes para HealthMonitor."""
    
    def setup_method(self):
        self.monitor = HealthMonitor()
    
    def test_record_success_increments_counters(self):
        """Sucesso deve incrementar contadores."""
        self.monitor.record_success("TestProvider", 100.0)
        metrics = self.monitor._get_metrics("TestProvider")
        
        assert metrics.requests_total == 1
        assert metrics.requests_success == 1
        assert metrics.requests_failed == 0
    
    def test_record_success_updates_latency(self):
        """Sucesso deve registrar latência."""
        self.monitor.record_success("TestProvider", 150.0)
        metrics = self.monitor._get_metrics("TestProvider")
        
        assert 150.0 in metrics.recent_latencies
    
    def test_record_failure_timeout(self):
        """Falha de timeout deve incrementar timeouts."""
        self.monitor.record_failure("TestProvider", FailureType.TIMEOUT)
        metrics = self.monitor._get_metrics("TestProvider")
        
        assert metrics.requests_failed == 1
        assert metrics.timeouts == 1
    
    def test_record_failure_rate_limit(self):
        """Falha de rate limit deve incrementar rate_limits."""
        self.monitor.record_failure("TestProvider", FailureType.RATE_LIMIT)
        metrics = self.monitor._get_metrics("TestProvider")
        
        assert metrics.rate_limits_hit == 1
    
    def test_record_failure_error(self):
        """Falha genérica deve incrementar errors."""
        self.monitor.record_failure("TestProvider", FailureType.ERROR)
        metrics = self.monitor._get_metrics("TestProvider")
        
        assert metrics.errors == 1
    
    def test_health_score_starts_at_100(self):
        """Score inicial deve ser 100."""
        score = self.monitor.get_health_score("NewProvider")
        assert score == 100
    
    def test_health_score_decreases_on_failure(self):
        """Score deve diminuir após falhas."""
        # Primeiro sucesso
        self.monitor.record_success("TestProvider", 100.0)
        score_before = self.monitor.get_health_score("TestProvider")
        
        # Depois falha
        self.monitor.record_failure("TestProvider", FailureType.ERROR)
        score_after = self.monitor.get_health_score("TestProvider")
        
        assert score_after < score_before
    
    def test_health_score_decreases_more_on_rate_limit(self):
        """Rate limits devem impactar mais o score."""
        # Provider com sucesso
        self.monitor.record_success("P1", 100.0)
        self.monitor.record_failure("P1", FailureType.ERROR)
        score_error = self.monitor.get_health_score("P1")
        
        # Provider com rate limit
        self.monitor.record_success("P2", 100.0)
        self.monitor.record_failure("P2", FailureType.RATE_LIMIT)
        score_rate_limit = self.monitor.get_health_score("P2")
        
        # Rate limit deve impactar mais
        assert score_rate_limit <= score_error
    
    def test_is_healthy_true(self):
        """Provider novo deve ser saudável."""
        assert self.monitor.is_healthy("NewProvider") is True
    
    def test_is_healthy_false_after_many_failures(self):
        """Provider deve ter score baixo após muitas falhas consecutivas."""
        # Muitas falhas consecutivas devem resultar em score reduzido
        for _ in range(30):
            self.monitor.record_failure("BadProvider", FailureType.ERROR)
        
        score = self.monitor.get_health_score("BadProvider")
        # Com 100% de falhas, score deve estar abaixo do limiar de "saudável"
        assert score < 70  # Limiar de degradação
    
    def test_get_healthy_providers(self):
        """Deve retornar providers ordenados por health score."""
        providers = ["P1", "P2", "P3"]
        
        # P1 - muito saudável (muitos sucessos)
        for _ in range(10):
            self.monitor.record_success("P1", 100.0)
        
        # P2 - degradado (mistura de sucesso e falha)
        for _ in range(5):
            self.monitor.record_success("P2", 200.0)
        for _ in range(3):
            self.monitor.record_failure("P2", FailureType.ERROR)
        
        # P3 - saudável mas com mais latência
        for _ in range(8):
            self.monitor.record_success("P3", 500.0)
        
        healthy = self.monitor.get_healthy_providers(providers)
        
        # Todos devem estar na lista (acima do threshold)
        assert "P1" in healthy
        # P1 deve estar no topo (maior score)
        assert healthy[0] == "P1"
    
    def test_get_best_provider(self):
        """Deve retornar provider com melhor score."""
        providers = ["P1", "P2"]
        
        # P1 - score alto
        for _ in range(5):
            self.monitor.record_success("P1", 100.0)
        
        # P2 - score mais baixo
        self.monitor.record_success("P2", 100.0)
        self.monitor.record_failure("P2", FailureType.TIMEOUT)
        
        best = self.monitor.get_best_provider(providers)
        assert best == "P1"
    
    def test_get_metrics_returns_dict(self):
        """Deve retornar dict com métricas."""
        self.monitor.record_success("TestProvider", 100.0)
        metrics = self.monitor.get_metrics("TestProvider")
        
        assert isinstance(metrics, dict)
        assert "provider" in metrics
        assert "health_score" in metrics
        assert "status" in metrics
    
    def test_reset_specific_provider(self):
        """Deve resetar métricas de um provider."""
        self.monitor.record_success("TestProvider", 100.0)
        self.monitor.record_failure("TestProvider", FailureType.ERROR)
        
        self.monitor.reset("TestProvider")
        
        metrics = self.monitor._get_metrics("TestProvider")
        assert metrics.requests_total == 0
    
    def test_reset_all(self):
        """Deve resetar todas as métricas."""
        self.monitor.record_success("P1", 100.0)
        self.monitor.record_success("P2", 200.0)
        
        self.monitor.reset()
        
        assert len(self.monitor._metrics) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

