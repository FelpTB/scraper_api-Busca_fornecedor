"""
Testes unitários para o PatternAnalyzer.
"""

import pytest
import tempfile
import os
from datetime import datetime

from app.services.learning.failure_tracker import (
    FailureTracker, FailureModule, FailureType
)
from app.services.learning.pattern_analyzer import (
    PatternAnalyzer,
    ScraperAnalysis,
    LLMAnalysis,
    Recommendation
)


class TestPatternAnalyzer:
    """Testes para PatternAnalyzer."""
    
    @pytest.fixture
    def analyzer_with_tracker(self):
        """Cria analyzer com tracker temporário."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        tracker = FailureTracker(storage_path=temp_path)
        analyzer = PatternAnalyzer(tracker)
        yield analyzer, tracker
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_analyze_scraper_no_failures(self, analyzer_with_tracker):
        """Testa análise sem falhas."""
        analyzer, _ = analyzer_with_tracker
        analysis = analyzer.analyze_scraper_failures()
        
        assert analysis.total_failures == 0
        assert len(analysis.cloudflare_sites) == 0
        assert len(analysis.recommendations) == 0
    
    def test_analyze_scraper_cloudflare_pattern(self, analyzer_with_tracker):
        """Testa detecção de padrão Cloudflare."""
        analyzer, tracker = analyzer_with_tracker
        
        # Adicionar muitas falhas de Cloudflare
        for i in range(10):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url=f"https://cf-site{i % 3}.com"
            )
        
        # Adicionar algumas outras falhas
        for _ in range(3):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
                url="https://slow-site.com"
        )
        
        analysis = analyzer.analyze_scraper_failures()
        
        assert analysis.total_failures == 13
        assert len(analysis.cloudflare_sites) == 3
        assert analysis.failure_rate_by_type.get("cloudflare", 0) > 70
    
    def test_analyze_scraper_timeout_pattern(self, analyzer_with_tracker):
        """Testa detecção de padrão de timeout."""
        analyzer, tracker = analyzer_with_tracker
        
        # Adicionar muitas falhas de timeout
        for i in range(8):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url=f"https://slow-site{i % 2}.com",
                duration_ms=15000
            )
        
        analysis = analyzer.analyze_scraper_failures()
        
        assert analysis.total_failures == 8
        assert len(analysis.timeout_sites) == 2
        assert analysis.avg_duration_ms == 15000
    
    def test_analyze_llm_rate_limit_pattern(self, analyzer_with_tracker):
        """Testa detecção de padrão de rate limit no LLM."""
        analyzer, tracker = analyzer_with_tracker
        
        # Adicionar falhas de rate limit
        for _ in range(5):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="openai",
                context={"provider": "OpenAI"}
            )
        
        for _ in range(2):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="google",
                context={"provider": "Google"}
            )
        
        analysis = analyzer.analyze_llm_failures()
        
        assert analysis.total_failures == 7
        assert analysis.rate_limit_count == 5
        assert analysis.timeout_count == 2
        assert analysis.provider_failures["OpenAI"] == 5
        assert analysis.provider_failures["Google"] == 2
    
    def test_recommendations_cloudflare_high_rate(self, analyzer_with_tracker):
        """Testa recomendação para alta taxa de Cloudflare."""
        analyzer, tracker = analyzer_with_tracker
        
        # 30% de Cloudflare
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url="https://cf.com"
            )
        for _ in range(70):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        analysis = analyzer.analyze_scraper_failures()
        
        cf_recs = [r for r in analysis.recommendations if "Cloudflare" in r.title]
        assert len(cf_recs) >= 1
        assert cf_recs[0].priority == 1
    
    def test_recommendations_timeout_high_rate(self, analyzer_with_tracker):
        """Testa recomendação para alta taxa de timeout."""
        analyzer, tracker = analyzer_with_tracker
        
        # 20% de timeout
        for _ in range(20):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        for _ in range(80):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.EMPTY_CONTENT,
                url="https://empty.com"
            )
        
        analysis = analyzer.analyze_scraper_failures()
        
        timeout_recs = [r for r in analysis.recommendations if "timeout" in r.title.lower()]
        assert len(timeout_recs) >= 1
    
    def test_recommendations_llm_rate_limit(self, analyzer_with_tracker):
        """Testa recomendação para rate limit do LLM."""
        analyzer, tracker = analyzer_with_tracker
        
        # 30% de rate limit
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="provider",
                context={"provider": "TestProvider"}
            )
        for _ in range(70):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="provider"
            )
        
        analysis = analyzer.analyze_llm_failures()
        
        rate_recs = [r for r in analysis.recommendations if "rate limit" in r.title.lower()]
        assert len(rate_recs) >= 1
    
    def test_get_all_recommendations_ordered(self, analyzer_with_tracker):
        """Testa ordenação de todas as recomendações."""
        analyzer, tracker = analyzer_with_tracker
        
        # Criar cenário com múltiplas recomendações
        for _ in range(30):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url="https://cf.com"
            )
        for _ in range(20):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="provider"
            )
        
        recs = analyzer.get_all_recommendations()
        
        # Verificar ordenação por prioridade
        for i in range(len(recs) - 1):
            assert recs[i].priority <= recs[i + 1].priority
    
    def test_get_summary(self, analyzer_with_tracker):
        """Testa resumo da análise."""
        analyzer, tracker = analyzer_with_tracker
        
        for _ in range(5):
        tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
                url="https://slow.com"
        )
        for _ in range(3):
        tracker.record_failure(
            module=FailureModule.LLM,
            error_type=FailureType.LLM_RATE_LIMIT,
                url="provider"
        )
        
        summary = analyzer.get_summary()
        
        assert summary["period_hours"] == 24
        assert summary["scraper"]["total_failures"] == 5
        assert summary["llm"]["total_failures"] == 3
        assert "recommendations_count" in summary
    
    def test_best_strategy_detection_protection(self, analyzer_with_tracker):
        """Testa detecção de melhor estratégia para sites com proteção."""
        analyzer, tracker = analyzer_with_tracker
        
        domain = "protected-site.com"
        
        # Muitas falhas de proteção
        for _ in range(8):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url=f"https://{domain}/page"
            )
        for _ in range(2):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url=f"https://{domain}/other"
            )
        
        analysis = analyzer.analyze_scraper_failures()
        
        assert analysis.best_strategy_by_site.get(domain) == "aggressive"


class TestRecommendation:
    """Testes para Recommendation."""
    
    def test_recommendation_creation(self):
        """Testa criação de recomendação."""
        rec = Recommendation(
            priority=1,
            module="scraper",
            title="Alta taxa de timeout",
            description="50% das falhas são timeouts",
            action="Aumentar timeout padrão",
            impact="Melhorar sucesso em 20 sites"
        )
        
        assert rec.priority == 1
        assert rec.module == "scraper"
        assert "timeout" in rec.title.lower()


class TestScraperAnalysis:
    """Testes para ScraperAnalysis."""
    
    def test_default_values(self):
        """Testa valores padrão."""
        analysis = ScraperAnalysis()
        
        assert analysis.total_failures == 0
        assert analysis.cloudflare_sites == []
        assert analysis.failure_rate_by_type == {}
        assert analysis.recommendations == []


class TestLLMAnalysis:
    """Testes para LLMAnalysis."""
    
    def test_default_values(self):
        """Testa valores padrão."""
        analysis = LLMAnalysis()
        
        assert analysis.total_failures == 0
        assert analysis.rate_limit_count == 0
        assert analysis.timeout_count == 0
        assert analysis.provider_failures == {}
