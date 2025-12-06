"""
Teste de Integração End-to-End v2.0

Valida que todos os módulos refatorados trabalham juntos corretamente.
"""

import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, patch, MagicMock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestScraperModuleIntegration:
    """Testa integração dos componentes do scraper."""
    
    def test_scraper_imports(self):
        """Verifica que todos os módulos do scraper importam corretamente."""
        from app.services.scraper import (
            scraper_config,
            ScraperConfig,
            record_failure,
            record_success,
            is_circuit_open,
            parse_html,
            is_cloudflare_challenge,
            is_soft_404,
            normalize_url,
            SiteType,
            ProtectionType,
            ScrapingStrategy,
            SiteProfile,
            ScrapedPage,
            ScrapedContent,
            site_analyzer,
            protection_detector,
            strategy_selector,
            url_prober,
        )
        
        assert scraper_config is not None
        assert site_analyzer is not None
        assert protection_detector is not None
        assert strategy_selector is not None
        assert url_prober is not None
    
    def test_scrape_url_import(self):
        """Verifica que scrape_url importa corretamente."""
        from app.services.scraper import scrape_url
        assert scrape_url is not None
        assert asyncio.iscoroutinefunction(scrape_url)
    
    def test_scraper_config_access(self):
        """Verifica acesso às configurações do scraper."""
        from app.services.scraper import scraper_config
        
        assert hasattr(scraper_config, 'site_semaphore_limit')
        assert hasattr(scraper_config, 'circuit_breaker_threshold')
        assert hasattr(scraper_config, 'session_timeout')
    
    def test_strategy_selector_works(self):
        """Testa que o seletor de estratégias funciona."""
        from app.services.scraper import (
            strategy_selector, 
            SiteProfile, 
            SiteType, 
            ProtectionType,
            ScrapingStrategy
        )
        
        profile = SiteProfile(
            url="https://test.com",
            response_time_ms=100,
            site_type=SiteType.STATIC,
            protection_type=ProtectionType.NONE,
            best_strategy=ScrapingStrategy.FAST
        )
        
        strategies = strategy_selector.select(profile)
        assert len(strategies) > 0
        assert all(isinstance(s, ScrapingStrategy) for s in strategies)
    
    def test_protection_detector_works(self):
        """Testa que o detector de proteção funciona."""
        from app.services.scraper import protection_detector, ProtectionType
        
        # Testar detecção de Cloudflare (precisa ter 'cloudflare' e challenge)
        cf_body = "Please wait... cloudflare checking your browser Ray ID: abc123"
        result = protection_detector.detect(response_body=cf_body)
        assert result == ProtectionType.CLOUDFLARE
        
        # Testar detecção de rate limit via status 429
        result = protection_detector.detect(status_code=429)
        assert result == ProtectionType.RATE_LIMIT
        
        # Testar sem proteção
        normal_body = "<html><body>Normal website content</body></html>"
        result = protection_detector.detect(response_body=normal_body)
        assert result == ProtectionType.NONE


class TestLLMModuleIntegration:
    """Testa integração dos componentes do LLM."""
    
    def test_llm_imports(self):
        """Verifica que todos os módulos do LLM importam corretamente."""
        from app.services.llm import (
            analyze_content,
            get_llm_service,
            LLMService,
            health_monitor,
            HealthMonitor,
            FailureType,
            rate_limiter,
            RateLimiter,
            create_queue_manager,
            provider_manager,
            ProviderManager,
            llm_config,
            chunk_content,
            estimate_tokens,
            merge_profiles,
        )
        
        assert analyze_content is not None
        assert health_monitor is not None
        assert rate_limiter is not None
        assert provider_manager is not None
    
    def test_analyze_content_import(self):
        """Verifica que analyze_content importa corretamente."""
        from app.services.llm import analyze_content
        assert analyze_content is not None
        assert asyncio.iscoroutinefunction(analyze_content)
    
    def test_llm_service_singleton(self):
        """Verifica que o LLMService é singleton."""
        from app.services.llm import get_llm_service
        
        service1 = get_llm_service()
        service2 = get_llm_service()
        
        assert service1 is service2
    
    def test_health_monitor_works(self):
        """Testa que o health monitor funciona."""
        from app.services.llm import health_monitor, FailureType
        
        provider = "test_provider_integration"
        
        # Registrar sucesso
        health_monitor.record_success(provider, latency_ms=100)
        metrics = health_monitor.get_metrics(provider)
        
        assert metrics is not None
        assert metrics['requests_total'] >= 1
        assert metrics['health_score'] >= 0
        
        # Registrar falha
        health_monitor.record_failure(provider, FailureType.TIMEOUT)
        metrics = health_monitor.get_metrics(provider)
        
        assert metrics['requests_total'] >= 2
    
    def test_content_chunker_works(self):
        """Testa que o chunker de conteúdo funciona."""
        from app.services.llm import chunk_content, estimate_tokens
        
        content = "Este é um conteúdo de teste. " * 100
        
        tokens = estimate_tokens(content)
        assert tokens > 0
        
        chunks = chunk_content(content, max_tokens=1000)
        assert len(chunks) >= 1
    
    def test_queue_manager_creation(self):
        """Testa criação do queue manager."""
        from app.services.llm import create_queue_manager
        
        manager = create_queue_manager(
            providers=["Test Provider A", "Test Provider B"],
            priorities={"Test Provider A": 1, "Test Provider B": 2}
        )
        
        assert manager is not None
        assert len(manager.providers) == 2


class TestMainIntegration:
    """Testa integração do main.py com os módulos."""
    
    def test_main_imports(self):
        """Verifica que os módulos principais importam corretamente."""
        from app.services.scraper import scrape_url
        from app.services.llm import analyze_content, start_health_monitor
        
        assert scrape_url is not None
        assert analyze_content is not None
        assert start_health_monitor is not None
    
    def test_discovery_imports(self):
        """Verifica que o discovery importa corretamente."""
        from app.services.discovery import find_company_website
        
        assert find_company_website is not None
        assert asyncio.iscoroutinefunction(find_company_website)
    
    def test_fastapi_app_creation(self):
        """Verifica que o app FastAPI é criado corretamente."""
        from app.main import app
        
        assert app is not None
        assert app.title == "B2B Flash Profiler"
    
    def test_endpoints_exist(self):
        """Verifica que os endpoints existem."""
        from app.main import app
        
        routes = [r.path for r in app.routes]
        assert "/" in routes
        assert "/analyze" in routes


class TestDiscoveryIntegration:
    """Testa integração do módulo de discovery."""
    
    def test_discovery_functions_exist(self):
        """Verifica que as funções do discovery existem."""
        from app.services.discovery import find_company_website, search_google_serper
        
        assert find_company_website is not None
        assert search_google_serper is not None
        assert asyncio.iscoroutinefunction(find_company_website)
        assert asyncio.iscoroutinefunction(search_google_serper)


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Testes assíncronos de integração."""
    
    async def test_url_prober_integration(self):
        """Testa URLProber de forma assíncrona."""
        from app.services.scraper import URLProber
        
        prober = URLProber(timeout=5.0, max_concurrent=2)
        
        # Gerar variações
        variations = prober._generate_variations("example.com")
        assert len(variations) >= 2
        assert any("https://" in v for v in variations)
    
    async def test_site_analyzer_mock(self):
        """Testa SiteAnalyzer com mock."""
        from app.services.scraper import SiteAnalyzer, SiteProfile, SiteType, ProtectionType, ScrapingStrategy
        
        analyzer = SiteAnalyzer()
        
        # Mock da resposta HTTP
        with patch.object(analyzer, '_make_request') as mock_request:
            mock_request.return_value = (
                200, 
                {"content-type": "text/html"},
                "<html><body>Test</body></html>",
                100
            )
            
            profile = await analyzer.analyze("https://example.com")
            
            assert isinstance(profile, SiteProfile)
            assert profile.url == "https://example.com"
    
    async def test_rate_limiter_async(self):
        """Testa rate limiter de forma assíncrona."""
        from app.services.llm import RateLimiter, TokenBucket
        
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        
        # Adquirir tokens
        success = await bucket.acquire(tokens=1, timeout=1.0)
        assert success
        
        # Verificar status
        status = bucket.get_status()
        assert status['current_tokens'] < 10


def run_all_integration_tests():
    """Executa todos os testes de integração."""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_all_integration_tests()

