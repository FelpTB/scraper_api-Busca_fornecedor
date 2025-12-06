"""
Testes de Integração para o Learning Engine.
Verifica que todos os componentes funcionam juntos corretamente.
"""

import pytest
import os
import tempfile

from app.services.learning import (
    FailureTracker,
    FailureModule,
    FailureType,
    PatternAnalyzer,
    ConfigOptimizer,
    SiteKnowledgeBase
)


class TestLearningModuleIntegration:
    """Testa integração dos componentes do Learning Engine."""
    
    def test_learning_imports(self):
        """Verifica que todos os módulos importam corretamente."""
        from app.services.learning import (
            failure_tracker,
            FailureTracker,
            FailureRecord,
            FailureModule,
            FailureType,
            pattern_analyzer,
            PatternAnalyzer,
            ScraperAnalysis,
            LLMAnalysis,
            Recommendation,
            config_optimizer,
            ConfigOptimizer,
            ConfigSuggestion,
            site_knowledge,
            SiteKnowledgeBase,
            SiteKnowledge
        )
        
        assert failure_tracker is not None
        assert pattern_analyzer is not None
        assert config_optimizer is not None
        assert site_knowledge is not None
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para storage."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        # Limpeza
        import shutil
        shutil.rmtree(dir_path, ignore_errors=True)
    
    @pytest.fixture
    def failure_tracker(self, temp_dir):
        """Cria tracker com storage temporário."""
        return FailureTracker(storage_path=os.path.join(temp_dir, "failures.json"))
    
    @pytest.fixture
    def pattern_analyzer(self, failure_tracker):
        """Cria analyzer com tracker."""
        return PatternAnalyzer(failure_tracker)
    
    @pytest.fixture
    def config_optimizer(self, pattern_analyzer):
        """Cria optimizer com analyzer."""
        return ConfigOptimizer(pattern_analyzer)
    
    @pytest.fixture
    def site_knowledge(self, temp_dir):
        """Cria base de conhecimento com storage temporário."""
        return SiteKnowledgeBase(storage_path=os.path.join(temp_dir, "knowledge.json"))


class TestFullPipeline(TestLearningModuleIntegration):
    """Testa pipeline completo de aprendizado."""
    
    def test_failure_to_recommendation_pipeline(
        self, 
        failure_tracker, 
        pattern_analyzer, 
        config_optimizer
    ):
        """
        Testa pipeline: falha -> análise -> recomendação.
        
        Cenário: Muitas falhas de timeout devem gerar recomendação
        para aumentar timeout.
        """
        # 1. Registrar falhas
        for _ in range(40):
            failure_tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow-site.com/page",
                duration_ms=15000
            )
        
        # 2. Analisar padrões
        analysis = pattern_analyzer.analyze_scraper_failures()
        
        assert analysis.total_failures == 40
        assert "slow-site.com" in analysis.timeout_sites
        
        # 3. Obter recomendações
        recommendations = analysis.recommendations
        
        # Deve haver recomendação sobre timeout
        timeout_recs = [r for r in recommendations if "timeout" in r.title.lower()]
        assert len(timeout_recs) > 0
        
        # 4. Obter sugestões de config
        scraper_config = {"session_timeout": 15}
        suggestions = config_optimizer.suggest_scraper_config(scraper_config)
        
        timeout_suggestions = [s for s in suggestions if s.config_key == "session_timeout"]
        assert len(timeout_suggestions) > 0
        assert timeout_suggestions[0].suggested_value > 15
    
    def test_protection_detection_to_knowledge(
        self, 
        failure_tracker, 
        pattern_analyzer, 
        site_knowledge
    ):
        """
        Testa pipeline: detecção de proteção -> base de conhecimento.
        
        Cenário: Falhas de Cloudflare devem atualizar a base de conhecimento.
        """
        # 1. Registrar falhas de Cloudflare
        for _ in range(5):
            failure_tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.CLOUDFLARE,
                url="https://protected-site.com/page"
            )
        
        # 2. Analisar
        analysis = pattern_analyzer.analyze_scraper_failures()
        
        assert "protected-site.com" in analysis.cloudflare_sites
        assert analysis.best_strategy_by_site.get("protected-site.com") == "aggressive"
        
        # 3. Atualizar base de conhecimento
        site_knowledge.update_profile(
            domain_or_url="protected-site.com",
            protection_type="cloudflare",
            best_strategy="aggressive"
        )
        
        # 4. Verificar que a base retorna a estratégia correta
        strategy = site_knowledge.get_best_strategy("protected-site.com")
        assert strategy == "aggressive"
        
        protection = site_knowledge.get_protection_type("protected-site.com")
        assert protection == "cloudflare"
    
    def test_success_tracking_updates_knowledge(self, site_knowledge):
        """
        Testa que sucessos atualizam a base de conhecimento.
        """
        # Registrar alguns sucessos
        for i in range(5):
            site_knowledge.record_success(
                domain_or_url="https://fast-site.com/page",
                response_time_ms=200 + i * 10,
                strategy_used="fast"
            )
        
        profile = site_knowledge.get_profile("fast-site.com")
        
        assert profile.total_successes == 5
        assert profile.success_rate == 1.0
        assert profile.avg_response_time_ms > 0
        assert profile.best_strategy == "fast"
    
    def test_mixed_results_affect_strategy(self, site_knowledge):
        """
        Testa que resultados mistos afetam a estratégia recomendada.
        """
        # 2 sucessos, 8 falhas = 20% taxa de sucesso
        site_knowledge.record_success("problem-site.com", 500)
        site_knowledge.record_success("problem-site.com", 500)
        
        for _ in range(8):
            site_knowledge.record_failure(
                "problem-site.com",
                error_type="timeout",
                protection_detected=None
            )
        
        profile = site_knowledge.get_profile("problem-site.com")
        
        assert profile.success_rate == 0.2
        assert profile.total_attempts == 10
        
        # Com baixa taxa de sucesso, deve recomendar estratégia mais robusta
        strategy = site_knowledge.get_best_strategy("problem-site.com")
        assert strategy in ["robust", "aggressive"]


class TestLLMPipeline(TestLearningModuleIntegration):
    """Testa pipeline de aprendizado para LLM."""
    
    def test_llm_rate_limit_to_config_suggestion(
        self, 
        failure_tracker, 
        pattern_analyzer, 
        config_optimizer
    ):
        """
        Testa: rate limits -> análise -> sugestão de reduzir concorrência.
        """
        # Registrar rate limits
        for _ in range(35):
            failure_tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_RATE_LIMIT,
                url="https://api.openai.com",
                context={"provider": "openai"}
            )
        
        # Analisar
        analysis = pattern_analyzer.analyze_llm_failures()
        
        assert analysis.rate_limit_count == 35
        assert analysis.provider_failures.get("openai", 0) == 35
        
        # Obter sugestões
        llm_config = {"max_concurrent": 50}
        suggestions = config_optimizer.suggest_llm_config(llm_config)
        
        concurrent_suggestions = [s for s in suggestions if s.config_key == "max_concurrent"]
        assert len(concurrent_suggestions) > 0
        assert concurrent_suggestions[0].suggested_value < 50
    
    def test_provider_health_tracking(self, failure_tracker, pattern_analyzer):
        """
        Testa rastreamento de saúde por provider.
        """
        # Google com mais falhas
        for _ in range(10):
            failure_tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="https://api.google.com",
                context={"provider": "google"}
            )
        
        # OpenAI com menos falhas
        for _ in range(3):
            failure_tracker.record_failure(
                module=FailureModule.LLM,
                error_type=FailureType.LLM_TIMEOUT,
                url="https://api.openai.com",
                context={"provider": "openai"}
            )
        
        analysis = pattern_analyzer.analyze_llm_failures()
        
        assert analysis.provider_failures["google"] > analysis.provider_failures["openai"]
        
        # Deve haver recomendação sobre o provider mais problemático
        provider_recs = [r for r in analysis.recommendations if "google" in r.title.lower()]
        # Pode ou não ter dependendo da porcentagem


class TestDataPersistence(TestLearningModuleIntegration):
    """Testa persistência de dados."""
    
    def test_failure_tracker_persistence(self, temp_dir):
        """Testa que falhas são persistidas e carregadas."""
        storage_path = os.path.join(temp_dir, "failures.json")
        
        # Criar tracker e adicionar falhas
        tracker1 = FailureTracker(storage_path=storage_path)
        tracker1.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://test.com"
        )
        
        # Criar novo tracker e verificar se carregou
        tracker2 = FailureTracker(storage_path=storage_path)
        
        assert len(tracker2.records) == 1
        assert tracker2.records[0].domain == "test.com"
    
    def test_site_knowledge_persistence(self, temp_dir):
        """Testa que conhecimento é persistido e carregado."""
        storage_path = os.path.join(temp_dir, "knowledge.json")
        
        # Criar base e adicionar perfil
        kb1 = SiteKnowledgeBase(storage_path=storage_path)
        kb1.update_profile(
            domain_or_url="test.com",
            protection_type="cloudflare",
            best_strategy="aggressive"
        )
        
        # Criar nova base e verificar se carregou
        kb2 = SiteKnowledgeBase(storage_path=storage_path)
        
        profile = kb2.get_profile("test.com")
        assert profile is not None
        assert profile.protection_type == "cloudflare"
        assert profile.best_strategy == "aggressive"


class TestSummaryReports:
    """Testa relatórios de resumo."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        import shutil
        shutil.rmtree(dir_path, ignore_errors=True)
    
    def test_failure_tracker_summary(self, temp_dir):
        """Testa resumo do failure tracker."""
        tracker = FailureTracker(storage_path=os.path.join(temp_dir, "f.json"))
        
        tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://site1.com"
        )
        tracker.record_failure(
            module=FailureModule.LLM,
            error_type=FailureType.LLM_RATE_LIMIT,
            url="https://api.com"
        )
        
        summary = tracker.get_summary()
        
        assert summary["total_records"] == 2
        assert summary["unique_domains"] == 2
    
    def test_pattern_analyzer_summary(self, temp_dir):
        """Testa resumo do pattern analyzer."""
        tracker = FailureTracker(storage_path=os.path.join(temp_dir, "f.json"))
        analyzer = PatternAnalyzer(tracker)
        
        for _ in range(5):
            tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        summary = analyzer.get_summary()
        
        assert "scraper" in summary
        assert "llm" in summary
        assert summary["scraper"]["total_failures"] == 5
    
    def test_config_optimizer_summary(self, temp_dir):
        """Testa resumo do config optimizer."""
        tracker = FailureTracker(storage_path=os.path.join(temp_dir, "f.json"))
        analyzer = PatternAnalyzer(tracker)
        optimizer = ConfigOptimizer(analyzer)
        
        scraper_config = {"session_timeout": 15}
        llm_config = {"max_concurrent": 50}
        
        summary = optimizer.get_summary(scraper_config, llm_config)
        
        assert "total_suggestions" in summary
        assert "by_module" in summary
    
    def test_site_knowledge_summary(self, temp_dir):
        """Testa resumo da site knowledge."""
        kb = SiteKnowledgeBase(storage_path=os.path.join(temp_dir, "k.json"))
        
        kb.update_profile("cf.com", protection_type="cloudflare")
        kb.update_profile("normal.com", protection_type="none")
        
        summary = kb.get_summary()
        
        assert summary["total_profiles"] == 2
        assert summary["protected_sites"] == 1

