"""
Testes unitários para o ConfigOptimizer.
"""

import pytest
import tempfile
import os

from app.services.learning.failure_tracker import (
    FailureTracker, FailureModule, FailureType
)
from app.services.learning.pattern_analyzer import PatternAnalyzer
from app.services.learning.config_optimizer import (
    ConfigOptimizer,
    ConfigSuggestion
)


class TestConfigOptimizer:
    """Testes para ConfigOptimizer."""
    
    @pytest.fixture
    def optimizer_setup(self):
        """Cria optimizer com dependências temporárias."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        tracker = FailureTracker(storage_path=temp_path)
        analyzer = PatternAnalyzer(tracker)
        optimizer = ConfigOptimizer(analyzer)
        
        yield optimizer, tracker
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_no_suggestions_without_failures(self, optimizer_setup):
        """Testa que não há sugestões sem falhas."""
        optimizer, _ = optimizer_setup
        
        scraper_config = {"session_timeout": 15, "chunk_size": 20}
        suggestions = optimizer.suggest_scraper_config(scraper_config)
        
        assert len(suggestions) == 0
    
    def test_suggest_increase_timeout_high_timeout_rate(self, optimizer_setup):
        """Testa sugestão de aumento de timeout."""
        optimizer, tracker = optimizer_setup
        
        # 25% de timeouts
        for _ in range(25):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        for _ in range(75):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.EMPTY_CONTENT,
                url="https://empty.com"
            )
        
        scraper_config = {"session_timeout": 15, "chunk_size": 20}
        suggestions = optimizer.suggest_scraper_config(scraper_config)
        
        timeout_suggestions = [s for s in suggestions if s.config_key == "session_timeout"]
        assert len(timeout_suggestions) >= 1
        assert timeout_suggestions[0].suggested_value > 15
    
    def test_suggest_increase_circuit_breaker_protection(self, optimizer_setup):
        """Testa sugestão de aumento de circuit breaker."""
        optimizer, tracker = optimizer_setup
        
        # 50% de proteções
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url="https://cf.com"
            )
        for _ in range(20):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.WAF,
                url="https://waf.com"
            )
        for _ in range(50):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        scraper_config = {"circuit_breaker_threshold": 5}
        suggestions = optimizer.suggest_scraper_config(scraper_config)
        
        cb_suggestions = [s for s in suggestions if s.config_key == "circuit_breaker_threshold"]
        assert len(cb_suggestions) >= 1
        assert cb_suggestions[0].suggested_value > 5
    
    def test_suggest_reduce_llm_concurrency_rate_limit(self, optimizer_setup):
        """Testa sugestão de redução de concorrência LLM."""
        optimizer, tracker = optimizer_setup
        
        # 30% de rate limit
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="provider"
            )
        for _ in range(70):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="provider"
            )
        
        llm_config = {"max_concurrent": 50}
        suggestions = optimizer.suggest_llm_config(llm_config)
        
        conc_suggestions = [s for s in suggestions if s.config_key == "max_concurrent"]
        assert len(conc_suggestions) >= 1
        assert conc_suggestions[0].suggested_value < 50
    
    def test_suggest_increase_llm_timeout(self, optimizer_setup):
        """Testa sugestão de aumento de timeout LLM."""
        optimizer, tracker = optimizer_setup
        
        # 25% de timeout
        for _ in range(25):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="provider"
            )
        for _ in range(75):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="provider"
            )
        
        llm_config = {"timeout": 60}
        suggestions = optimizer.suggest_llm_config(llm_config)
        
        timeout_suggestions = [s for s in suggestions if s.config_key == "timeout"]
        assert len(timeout_suggestions) >= 1
        assert timeout_suggestions[0].suggested_value > 60
    
    def test_get_all_suggestions_ordered(self, optimizer_setup):
        """Testa ordenação de todas as sugestões."""
        optimizer, tracker = optimizer_setup
        
        # Criar cenário com múltiplas sugestões
        for _ in range(50):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        for _ in range(50):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="provider"
            )
        
        scraper_config = {"session_timeout": 15}
        llm_config = {"max_concurrent": 50}
        
        suggestions = optimizer.get_all_suggestions(scraper_config, llm_config)
        
        # Verificar ordenação por confiança (decrescente)
        for i in range(len(suggestions) - 1):
            assert suggestions[i].confidence >= suggestions[i + 1].confidence
    
    def test_apply_suggestion(self, optimizer_setup):
        """Testa aplicação de sugestão."""
        optimizer, tracker = optimizer_setup
        
        applied_configs = {}
        
        def apply_func(module, key, value):
            applied_configs[f"{module}.{key}"] = value
            return True
        
        suggestion = ConfigSuggestion(
            module="scraper",
            config_key="session_timeout",
            current_value=15,
            suggested_value=25,
            reason="Test",
            confidence=0.9,
            auto_apply=True
        )
        
        result = optimizer.apply_suggestion(suggestion, apply_func)
        
        assert result is True
        assert applied_configs["scraper.session_timeout"] == 25
        assert suggestion in optimizer.get_applied_suggestions()
    
    def test_apply_auto_suggestions(self, optimizer_setup):
        """Testa aplicação automática de sugestões."""
        optimizer, tracker = optimizer_setup
        
        # Criar cenário com sugestões auto_apply
        for _ in range(40):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        applied_configs = {}
        
        def apply_func(module, key, value):
            applied_configs[f"{module}.{key}"] = value
            return True
        
        scraper_config = {"session_timeout": 15}
        llm_config = {}
        
        applied = optimizer.apply_auto_suggestions(
            scraper_config, llm_config, apply_func
        )
        
        # Pode ou não ter aplicado dependendo da confiança
        assert isinstance(applied, list)
    
    def test_get_summary(self, optimizer_setup):
        """Testa resumo das sugestões."""
        optimizer, tracker = optimizer_setup
        
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        scraper_config = {"session_timeout": 15}
        llm_config = {"max_concurrent": 50}
        
        summary = optimizer.get_summary(scraper_config, llm_config)
        
        assert "total_suggestions" in summary
        assert "by_module" in summary
        assert "applied_count" in summary
    
    def test_respects_limits(self, optimizer_setup):
        """Testa que sugestões respeitam limites."""
        optimizer, tracker = optimizer_setup
        
        # Muitos timeouts para forçar aumento
        for _ in range(90):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        # Começar com timeout já alto
        scraper_config = {"session_timeout": 55}
        suggestions = optimizer.suggest_scraper_config(scraper_config)
        
        timeout_suggestions = [s for s in suggestions if s.config_key == "session_timeout"]
        if timeout_suggestions:
            # Não deve exceder o limite máximo de 60
            assert timeout_suggestions[0].suggested_value <= 60


class TestConfigSuggestion:
    """Testes para ConfigSuggestion."""
    
    def test_creation(self):
        """Testa criação de sugestão."""
        suggestion = ConfigSuggestion(
            module="scraper",
            config_key="session_timeout",
            current_value=15,
            suggested_value=25,
            reason="Alta taxa de timeout",
            confidence=0.85,
            auto_apply=True
        )
        
        assert suggestion.module == "scraper"
        assert suggestion.config_key == "session_timeout"
        assert suggestion.suggested_value == 25
        assert suggestion.confidence == 0.85
        assert suggestion.auto_apply is True
    
    def test_default_auto_apply(self):
        """Testa valor padrão de auto_apply."""
        suggestion = ConfigSuggestion(
            module="llm",
            config_key="timeout",
            current_value=60,
            suggested_value=90,
            reason="Test",
            confidence=0.5
        )
        
        assert suggestion.auto_apply is False
