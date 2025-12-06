"""
Testes unitários para o AdaptiveConfigManager.
"""

import pytest
import tempfile
import os

from app.services.learning.failure_tracker import (
    FailureTracker, FailureModule, FailureType
)
from app.services.learning.adaptive_config import (
    AdaptiveConfigManager,
    AdaptiveState
)


class TestAdaptiveState:
    """Testes para AdaptiveState."""
    
    def test_default_values(self):
        """Testa valores padrão."""
        state = AdaptiveState()
        
        assert state.default_strategy == "standard"
        assert state.scraper_timeout == 15
        assert state.llm_max_concurrent == 50
        assert state.total_sites_processed == 0
        assert state.optimizations_applied == 0


class TestAdaptiveConfigManager:
    """Testes para AdaptiveConfigManager."""
    
    @pytest.fixture
    def temp_tracker(self):
        """Cria tracker com arquivo temporário."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        tracker = FailureTracker(storage_path=temp_path)
        yield tracker
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_initial_state(self):
        """Testa estado inicial."""
        manager = AdaptiveConfigManager()
        
        assert manager.state.default_strategy == "standard"
        assert manager.get_default_strategy_for_new_site() == "standard"
    
    def test_get_scraper_config(self):
        """Testa obtenção de config do scraper."""
        manager = AdaptiveConfigManager()
        config = manager.get_scraper_config()
        
        assert "session_timeout" in config
        assert "chunk_size" in config
        assert "default_strategy" in config
    
    def test_get_llm_config(self):
        """Testa obtenção de config do LLM."""
        manager = AdaptiveConfigManager()
        config = manager.get_llm_config()
        
        assert "max_concurrent" in config
        assert "timeout" in config
    
    def test_get_status(self):
        """Testa obtenção de status completo."""
        manager = AdaptiveConfigManager()
        status = manager.get_status()
        
        assert "default_strategy" in status
        assert "scraper_config" in status
        assert "llm_config" in status
        assert "learning_stats" in status
    
    def test_reset(self):
        """Testa reset de estado."""
        manager = AdaptiveConfigManager()
        manager.state.default_strategy = "aggressive"
        manager.state.scraper_timeout = 30
        
        manager.reset()
        
        assert manager.state.default_strategy == "standard"
        assert manager.state.scraper_timeout == 15
    
    def test_adapt_strategy_high_cloudflare(self, temp_tracker):
        """Testa adaptação de estratégia com alta taxa de Cloudflare."""
        manager = AdaptiveConfigManager()
        
        # Simular padrões com 40% de Cloudflare
        patterns = {
            "cloudflare": 40,
            "timeout": 30,
            "empty_content": 30
        }
        
        manager._analyze_and_adapt(patterns, 100)
        
        # Deve mudar para estratégia mais robusta
        assert manager.state.default_strategy in ["robust", "aggressive"]
    
    def test_adapt_timeout_high_timeout_rate(self, temp_tracker):
        """Testa adaptação de timeout com alta taxa de timeout."""
        manager = AdaptiveConfigManager()
        initial_timeout = manager.state.scraper_timeout
        
        # Simular padrões com 25% de timeout
        patterns = {
            "timeout": 25,
            "empty_content": 75
        }
        
        manager._analyze_and_adapt(patterns, 100)
        
        # Timeout deve ter aumentado
        assert manager.state.timeout_rate > 20
        assert manager.state.scraper_timeout >= initial_timeout
    
    def test_optimize_after_batch_increments_count(self, temp_tracker):
        """Testa que optimize_after_batch incrementa contador."""
        manager = AdaptiveConfigManager()
        initial_count = manager.state.total_sites_processed
        
        manager.optimize_after_batch(batch_size=10)
        
        assert manager.state.total_sites_processed == initial_count + 10
    
    def test_should_use_aggressive_strategy(self):
        """Testa flag de estratégia agressiva."""
        manager = AdaptiveConfigManager()
        
        # Inicialmente não deve usar agressiva
        assert manager.should_use_aggressive_strategy() is False
        
        # Simular alta taxa de CF
        manager.state.cloudflare_rate = 50
        assert manager.should_use_aggressive_strategy() is True
    
    def test_get_recommended_values(self):
        """Testa obtenção de valores recomendados."""
        manager = AdaptiveConfigManager()
        
        timeout = manager.get_recommended_timeout()
        concurrent = manager.get_recommended_llm_concurrent()
        
        assert isinstance(timeout, int)
        assert isinstance(concurrent, int)
        assert timeout > 0
        assert concurrent > 0


class TestAdaptiveConfigIntegration:
    """Testes de integração do adaptive config."""
    
    def test_import_from_learning_module(self):
        """Testa import do módulo learning."""
        from app.services.learning import (
            adaptive_config,
            AdaptiveConfigManager,
            AdaptiveState
        )
        
        assert adaptive_config is not None
        assert AdaptiveConfigManager is not None
        assert AdaptiveState is not None
    
    def test_singleton_instance(self):
        """Testa que é singleton."""
        from app.services.learning import adaptive_config as ac1
        from app.services.learning.adaptive_config import adaptive_config as ac2
        
        assert ac1 is ac2
    
    def test_full_learning_cycle(self):
        """Testa ciclo completo de aprendizado."""
        manager = AdaptiveConfigManager()
        
        # 1. Estado inicial
        assert manager.get_default_strategy_for_new_site() == "standard"
        
        # 2. Simular aprendizado com muitos Cloudflare
        patterns = {
            "cloudflare": 50,
            "waf": 10,
            "timeout": 20,
            "empty_content": 20
        }
        
        manager._analyze_and_adapt(patterns, 100)
        
        # 3. Verificar adaptação
        # Com 60% de proteções, deve ter mudado estratégia
        assert manager.state.cloudflare_rate > 50
        
        # 4. Estratégia para site novo deve refletir aprendizado
        new_strategy = manager.get_default_strategy_for_new_site()
        assert new_strategy in ["robust", "aggressive"]

