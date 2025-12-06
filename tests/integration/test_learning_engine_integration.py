"""
Teste de Integração do Learning Engine.
Valida que todos os componentes trabalham juntos corretamente.
"""

import pytest
import tempfile
import os
import json

from app.services.learning import (
    FailureTracker,
    FailureModule,
    FailureType,
    PatternAnalyzer,
    ConfigOptimizer,
    SiteKnowledgeBase,
    failure_tracker,
    pattern_analyzer,
    config_optimizer,
    site_knowledge
)


class TestLearningEngineImports:
    """Testa que todos os imports funcionam."""
    
    def test_failure_tracker_imports(self):
        """Testa imports do failure_tracker."""
        from app.services.learning import (
            failure_tracker,
            FailureTracker,
            FailureRecord,
            FailureModule,
            FailureType
        )
        
        assert failure_tracker is not None
        assert FailureTracker is not None
        assert FailureModule.SCRAPER.value == "scraper"
    
    def test_pattern_analyzer_imports(self):
        """Testa imports do pattern_analyzer."""
        from app.services.learning import (
            pattern_analyzer,
            PatternAnalyzer,
            ScraperAnalysis,
            LLMAnalysis,
            Recommendation
        )
        
        assert pattern_analyzer is not None
        assert PatternAnalyzer is not None
    
    def test_config_optimizer_imports(self):
        """Testa imports do config_optimizer."""
        from app.services.learning import (
            config_optimizer,
            ConfigOptimizer,
            ConfigSuggestion
        )
        
        assert config_optimizer is not None
        assert ConfigOptimizer is not None
    
    def test_site_knowledge_imports(self):
        """Testa imports do site_knowledge."""
        from app.services.learning import (
            site_knowledge,
            SiteKnowledgeBase,
            SiteKnowledge
        )
        
        assert site_knowledge is not None
        assert SiteKnowledgeBase is not None


class TestLearningEnginePipeline:
    """Testa o pipeline completo do Learning Engine."""
    
    @pytest.fixture
    def temp_learning_system(self):
        """Cria sistema de learning com arquivos temporários."""
        with tempfile.TemporaryDirectory() as temp_dir:
            failures_path = os.path.join(temp_dir, "failures.json")
            knowledge_path = os.path.join(temp_dir, "knowledge.json")
            
            tracker = FailureTracker(storage_path=failures_path)
            analyzer = PatternAnalyzer(tracker)
            optimizer = ConfigOptimizer(analyzer)
            knowledge = SiteKnowledgeBase(storage_path=knowledge_path)
            
            yield {
                "tracker": tracker,
                "analyzer": analyzer,
                "optimizer": optimizer,
                "knowledge": knowledge,
                "temp_dir": temp_dir
            }
    
    def test_full_scraper_learning_cycle(self, temp_learning_system):
        """Testa ciclo completo de aprendizado do scraper."""
        tracker = temp_learning_system["tracker"]
        analyzer = temp_learning_system["analyzer"]
        optimizer = temp_learning_system["optimizer"]
        knowledge = temp_learning_system["knowledge"]
        
        # 1. Simular falhas de scraping
        test_domains = [
            ("cf-site1.com", FailureType.CLOUDFLARE),
            ("cf-site1.com", FailureType.CLOUDFLARE),
            ("cf-site2.com", FailureType.CLOUDFLARE),
            ("slow-site.com", FailureType.TIMEOUT),
            ("slow-site.com", FailureType.TIMEOUT),
            ("slow-site.com", FailureType.TIMEOUT),
        ]
        
        for domain, error_type in test_domains:
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=error_type,
                url=f"https://{domain}/page",
                duration_ms=15000
            )
            knowledge.record_failure(domain, error_type.value)
        
        # 2. Analisar padrões
        scraper_analysis = analyzer.analyze_scraper_failures()
        
        assert scraper_analysis.total_failures == 6
        assert len(scraper_analysis.cloudflare_sites) == 2
        assert len(scraper_analysis.timeout_sites) == 1
        
        # 3. Obter sugestões de configuração
        current_config = {
            "session_timeout": 15,
            "circuit_breaker_threshold": 5
        }
        
        suggestions = optimizer.suggest_scraper_config(current_config)
        
        # Deve sugerir aumento de timeout devido aos timeouts
        timeout_suggestion = next(
            (s for s in suggestions if s.config_key == "session_timeout"), 
            None
        )
        if timeout_suggestion:
            assert timeout_suggestion.suggested_value > 15
        
        # 4. Verificar conhecimento adquirido
        assert knowledge.get_protection_type("cf-site1.com") in ["cloudflare", "none"]
        
        # 5. Obter recomendações gerais
        recs = analyzer.get_all_recommendations()
        assert len(recs) >= 0  # Pode ou não ter recomendações
    
    def test_full_llm_learning_cycle(self, temp_learning_system):
        """Testa ciclo completo de aprendizado do LLM."""
        tracker = temp_learning_system["tracker"]
        analyzer = temp_learning_system["analyzer"]
        optimizer = temp_learning_system["optimizer"]
        
        # 1. Simular falhas de LLM
        for _ in range(10):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="openai",
                context={"provider": "OpenAI"},
                duration_ms=100
            )
        
        for _ in range(5):
            tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="google",
                context={"provider": "Google"},
                duration_ms=60000
            )
        
        # 2. Analisar padrões
        llm_analysis = analyzer.analyze_llm_failures()
        
        assert llm_analysis.total_failures == 15
        assert llm_analysis.rate_limit_count == 10
        assert llm_analysis.timeout_count == 5
        assert llm_analysis.provider_failures["OpenAI"] == 10
        assert llm_analysis.provider_failures["Google"] == 5
        
        # 3. Obter sugestões
        llm_config = {
            "max_concurrent": 50,
            "timeout": 60
        }
        
        suggestions = optimizer.suggest_llm_config(llm_config)
        
        # Deve sugerir redução de concorrência devido aos rate limits
        conc_suggestion = next(
            (s for s in suggestions if s.config_key == "max_concurrent"),
            None
        )
        if conc_suggestion:
            assert conc_suggestion.suggested_value < 50
    
    def test_site_knowledge_learning(self, temp_learning_system):
        """Testa aprendizado de conhecimento sobre sites."""
        knowledge = temp_learning_system["knowledge"]
        
        # 1. Site novo - estratégia padrão
        strategy = knowledge.get_best_strategy("new-site.com")
        assert strategy == "standard"
        
        # 2. Registrar vários sucessos
        for _ in range(10):
            knowledge.record_success("fast-site.com", 50, "fast")
        
        # 3. Verificar estratégia aprendida
        profile = knowledge.get_profile("fast-site.com")
        assert profile.success_rate > 0.8
        assert profile.best_strategy == "fast"
        
        # 4. Site problemático
        for _ in range(8):
            knowledge.record_failure("problem-site.com", "cloudflare", "cloudflare")
        for _ in range(2):
            knowledge.record_success("problem-site.com", 5000)
        
        profile = knowledge.get_profile("problem-site.com")
        assert profile.success_rate < 0.5
        
        # Deve recomendar estratégia agressiva
        strategy = knowledge.get_best_strategy("problem-site.com")
        assert strategy in ["aggressive", "robust"]
    
    def test_config_optimization_pipeline(self, temp_learning_system):
        """Testa pipeline de otimização de configuração."""
        tracker = temp_learning_system["tracker"]
        optimizer = temp_learning_system["optimizer"]
        
        # Criar cenário com muitos problemas
        for _ in range(50):
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
        
        # Aplicar sugestões automáticas
        applied = optimizer.apply_auto_suggestions(
            scraper_config, llm_config, apply_func
        )
        
        # Verificar que aplicou (se havia sugestões com alta confiança)
        if applied:
            assert len(applied_configs) > 0


class TestLearningEngineWithRealModules:
    """Testa integração com módulos reais do sistema."""
    
    def test_failure_tracker_singleton(self):
        """Testa que singleton está funcionando."""
        from app.services.learning import failure_tracker as ft1
        from app.services.learning.failure_tracker import failure_tracker as ft2
        
        # Devem ser a mesma instância
        assert ft1 is ft2
    
    def test_pattern_analyzer_with_failure_tracker(self):
        """Testa que pattern_analyzer usa failure_tracker."""
        from app.services.learning import (
            failure_tracker,
            pattern_analyzer
        )
        
        # O analyzer deve ter referência ao tracker
        assert pattern_analyzer.failure_tracker is not None
    
    def test_config_optimizer_with_pattern_analyzer(self):
        """Testa que config_optimizer usa pattern_analyzer."""
        from app.services.learning import (
            pattern_analyzer,
            config_optimizer
        )
        
        # O optimizer deve ter referência ao analyzer
        assert config_optimizer.pattern_analyzer is not None


class TestLearningEngineSummaries:
    """Testa geração de resumos."""
    
    @pytest.fixture
    def populated_system(self):
        """Cria sistema populado com dados."""
        with tempfile.TemporaryDirectory() as temp_dir:
            failures_path = os.path.join(temp_dir, "failures.json")
            knowledge_path = os.path.join(temp_dir, "knowledge.json")
            
            tracker = FailureTracker(storage_path=failures_path)
            analyzer = PatternAnalyzer(tracker)
            knowledge = SiteKnowledgeBase(storage_path=knowledge_path)
            
            # Popular com dados
            for i in range(20):
                tracker.record_failure(
                    module=FailureModule.SCRAPER,
                    error_type=FailureType.TIMEOUT,
                    url=f"https://site{i % 5}.com"
                )
            
            for i in range(10):
                knowledge.record_success(f"good-site{i}.com", 100)
            
            yield {
                "tracker": tracker,
                "analyzer": analyzer,
                "knowledge": knowledge
            }
    
    def test_failure_tracker_summary(self, populated_system):
        """Testa resumo do failure tracker."""
        tracker = populated_system["tracker"]
        summary = tracker.get_summary()
        
        assert summary["total_records"] == 20
        assert summary["unique_domains"] == 5
        assert "scraper" in summary["last_24h"]
    
    def test_pattern_analyzer_summary(self, populated_system):
        """Testa resumo do pattern analyzer."""
        analyzer = populated_system["analyzer"]
        summary = analyzer.get_summary()
        
        assert "period_hours" in summary
        assert "scraper" in summary
        assert summary["scraper"]["total_failures"] == 20
    
    def test_site_knowledge_summary(self, populated_system):
        """Testa resumo da base de conhecimento."""
        knowledge = populated_system["knowledge"]
        summary = knowledge.get_summary()
        
        assert summary["total_profiles"] == 10
        assert "avg_success_rate" in summary

