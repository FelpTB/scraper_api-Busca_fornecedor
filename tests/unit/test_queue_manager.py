"""
Testes unitários para o Queue Manager.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.llm.queue_manager import QueueManager, ProviderSelection
from app.services.llm.rate_limiter import RateLimiter
from app.services.llm.health_monitor import HealthMonitor


class TestQueueManager:
    """Testes para QueueManager."""
    
    def setup_method(self):
        self.rate_limiter = RateLimiter()
        self.health_monitor = HealthMonitor()
        self.providers = ["Provider1", "Provider2", "Provider3"]
        self.priorities = {"Provider1": 80, "Provider2": 50, "Provider3": 30}
        
        self.manager = QueueManager(
            rate_limiter=self.rate_limiter,
            health_monitor=self.health_monitor,
            providers=self.providers,
            priorities=self.priorities
        )
    
    @pytest.mark.asyncio
    async def test_get_best_provider_returns_selection(self):
        """Deve retornar ProviderSelection."""
        selection = await self.manager.get_best_provider()
        
        assert selection is not None
        assert isinstance(selection, ProviderSelection)
        assert selection.provider in self.providers
    
    @pytest.mark.asyncio
    async def test_get_best_provider_prefers_healthy(self):
        """Deve preferir providers saudáveis."""
        # Tornar Provider1 não saudável
        for _ in range(15):
            self.health_monitor.record_failure("Provider1", MagicMock())
        
        selection = await self.manager.get_best_provider()
        
        # Deve escolher Provider2 ou Provider3 (saudáveis)
        assert selection.provider != "Provider1"
    
    @pytest.mark.asyncio
    async def test_get_best_provider_excludes_providers(self):
        """Deve excluir providers especificados."""
        selection = await self.manager.get_best_provider(exclude=["Provider1", "Provider2"])
        
        assert selection.provider == "Provider3"
    
    @pytest.mark.asyncio
    async def test_get_best_provider_returns_none_if_no_available(self):
        """Deve retornar None se nenhum provider disponível."""
        selection = await self.manager.get_best_provider(exclude=self.providers)
        
        assert selection is None
    
    @pytest.mark.asyncio
    async def test_acquire_slot(self):
        """Deve adquirir slot para provider."""
        result = await self.manager.acquire_slot("Provider1")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_and_acquire_success(self):
        """Deve selecionar e adquirir slot."""
        result = await self.manager.get_and_acquire()
        
        assert result is not None
        provider, selection = result
        assert provider in self.providers
    
    def test_get_next_provider_round_robin(self):
        """Deve alternar entre providers."""
        seen = set()
        for _ in range(len(self.providers)):
            provider = self.manager.get_next_provider_round_robin()
            seen.add(provider)
        
        # Deve ter visto todos os providers
        assert seen == set(self.providers)
    
    def test_get_next_provider_round_robin_with_exclude(self):
        """Round-robin deve excluir providers."""
        provider = self.manager.get_next_provider_round_robin(exclude=["Provider1"])
        assert provider != "Provider1"
    
    def test_get_status(self):
        """Deve retornar status completo."""
        status = self.manager.get_status()
        
        assert "providers" in status
        assert "total_providers" in status
        assert "healthy_providers" in status
        
        for provider in self.providers:
            assert provider in status["providers"]
            assert "health_score" in status["providers"][provider]
            assert "priority" in status["providers"][provider]


class TestProviderSelection:
    """Testes para ProviderSelection dataclass."""
    
    def test_creation(self):
        """Deve criar ProviderSelection com todos campos."""
        selection = ProviderSelection(
            provider="TestProvider",
            reason="best_score",
            health_score=95,
            estimated_wait=0.5
        )
        
        assert selection.provider == "TestProvider"
        assert selection.reason == "best_score"
        assert selection.health_score == 95
        assert selection.estimated_wait == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

