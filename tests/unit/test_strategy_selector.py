"""
Testes unitários para o StrategySelector.
"""

import pytest
from app.services.scraper.strategy_selector import StrategySelector, strategy_selector
from app.services.scraper.models import (
    SiteProfile, SiteType, ProtectionType, ScrapingStrategy
)


class TestStrategySelector:
    """Testes para seleção de estratégias."""
    
    def setup_method(self):
        self.selector = StrategySelector()
    
    def test_select_for_static_site_no_protection(self):
        """Site estático sem proteção deve priorizar FAST."""
        profile = SiteProfile(
            url="https://example.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.NONE,
            response_time_ms=500
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.FAST
        assert len(strategies) >= 3
    
    def test_select_for_cloudflare(self):
        """Site com Cloudflare deve priorizar AGGRESSIVE."""
        profile = SiteProfile(
            url="https://protected.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.CLOUDFLARE,
            response_time_ms=1000
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.AGGRESSIVE
    
    def test_select_for_waf(self):
        """Site com WAF deve priorizar ROBUST."""
        profile = SiteProfile(
            url="https://waf-protected.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.WAF,
            response_time_ms=1000
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.ROBUST
    
    def test_select_for_spa(self):
        """Site SPA deve priorizar ROBUST."""
        profile = SiteProfile(
            url="https://spa-app.com",
            site_type=SiteType.SPA,
            protection_type=ProtectionType.NONE,
            response_time_ms=1000
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.ROBUST
    
    def test_select_for_slow_site(self):
        """Site lento deve priorizar ROBUST."""
        profile = SiteProfile(
            url="https://slow-site.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.NONE,
            response_time_ms=6000  # > 5000ms
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.ROBUST
    
    def test_select_for_fast_site(self):
        """Site rápido sem proteção deve priorizar FAST."""
        profile = SiteProfile(
            url="https://fast-site.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.NONE,
            response_time_ms=300  # < 500ms
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.FAST
    
    def test_select_for_rate_limit(self):
        """Site com rate limit deve usar STANDARD."""
        profile = SiteProfile(
            url="https://rate-limited.com",
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.RATE_LIMIT,
            response_time_ms=1000
        )
        strategies = self.selector.select(profile)
        assert strategies[0] == ScrapingStrategy.STANDARD
    
    def test_select_for_subpage(self):
        """Deve selecionar estratégias para subpágina baseado na main."""
        strategies = self.selector.select_for_subpage(
            ScrapingStrategy.FAST, 
            "https://example.com/about"
        )
        assert strategies[0] == ScrapingStrategy.FAST
        assert len(strategies) >= 2
    
    def test_get_strategy_config_fast(self):
        """Deve retornar config correta para FAST."""
        config = self.selector.get_strategy_config(ScrapingStrategy.FAST)
        assert config["timeout"] == 10
        assert config["use_proxy"] == False
        assert config["retry_count"] == 1
    
    def test_get_strategy_config_aggressive(self):
        """Deve retornar config correta para AGGRESSIVE."""
        config = self.selector.get_strategy_config(ScrapingStrategy.AGGRESSIVE)
        assert config["timeout"] == 25
        assert config["use_proxy"] == True
        assert config["rotate_ua"] == True
        assert config["rotate_proxy"] == True
    
    def test_all_strategies_have_config(self):
        """Todas as estratégias devem ter configuração."""
        for strategy in ScrapingStrategy:
            config = self.selector.get_strategy_config(strategy)
            assert "timeout" in config
            assert "use_proxy" in config
    
    def test_singleton_instance(self):
        """Deve ter instância singleton disponível."""
        assert strategy_selector is not None
        assert isinstance(strategy_selector, StrategySelector)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

