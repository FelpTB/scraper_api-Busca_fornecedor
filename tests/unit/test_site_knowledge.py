"""
Testes unitários para o SiteKnowledgeBase.
"""

import pytest
import tempfile
import os
import json
from datetime import datetime

from app.services.learning.site_knowledge import (
    SiteKnowledgeBase,
    SiteKnowledge
)


class TestSiteKnowledge:
    """Testes para SiteKnowledge."""
    
    def test_default_values(self):
        """Testa valores padrão."""
        knowledge = SiteKnowledge(domain="example.com")
        
        assert knowledge.domain == "example.com"
        assert knowledge.protection_type == "none"
        assert knowledge.best_strategy == "standard"
        assert knowledge.success_rate == 0.0
        assert knowledge.total_attempts == 0
    
    def test_update_success(self):
        """Testa atualização de sucesso."""
        knowledge = SiteKnowledge(domain="example.com")
        
        knowledge.update_success(100)
        
        assert knowledge.total_attempts == 1
        assert knowledge.total_successes == 1
        assert knowledge.success_rate == 1.0
        assert knowledge.avg_response_time_ms == 100
        assert knowledge.last_success != ""
    
    def test_update_failure(self):
        """Testa atualização de falha."""
        knowledge = SiteKnowledge(domain="example.com")
        
        knowledge.update_failure("timeout")
        
        assert knowledge.total_attempts == 1
        assert knowledge.total_successes == 0
        assert knowledge.success_rate == 0.0
        assert knowledge.last_failure != ""
    
    def test_success_rate_calculation(self):
        """Testa cálculo de taxa de sucesso."""
        knowledge = SiteKnowledge(domain="example.com")
        
        # 3 sucessos, 2 falhas = 60% sucesso
        knowledge.update_success(100)
        knowledge.update_success(150)
        knowledge.update_success(120)
        knowledge.update_failure("timeout")
        knowledge.update_failure("cloudflare")
        
        assert knowledge.total_attempts == 5
        assert knowledge.success_rate == 0.6
    
    def test_avg_response_time_moving_average(self):
        """Testa média móvel de tempo de resposta."""
        knowledge = SiteKnowledge(domain="example.com")
        
        knowledge.update_success(100)  # Primeiro: 100
        knowledge.update_success(200)  # (100 * 0.8) + (200 * 0.2) = 120
        
        assert 110 < knowledge.avg_response_time_ms < 130


class TestSiteKnowledgeBase:
    """Testes para SiteKnowledgeBase."""
    
    @pytest.fixture
    def temp_knowledge(self):
        """Cria knowledge base com arquivo temporário."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        kb = SiteKnowledgeBase(storage_path=temp_path)
        yield kb
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_get_profile_not_exists(self, temp_knowledge):
        """Testa busca de perfil inexistente."""
        profile = temp_knowledge.get_profile("nonexistent.com")
        assert profile is None
    
    def test_get_or_create_profile(self, temp_knowledge):
        """Testa criação automática de perfil."""
        profile = temp_knowledge.get_or_create_profile("new-site.com")
        
        assert profile is not None
        assert profile.domain == "new-site.com"
        assert profile.best_strategy == "standard"
    
    def test_add_profile(self, temp_knowledge):
        """Testa adição de perfil."""
        profile = SiteKnowledge(
            domain="custom-site.com",
            protection_type="cloudflare",
            best_strategy="aggressive"
        )
        
        temp_knowledge.add_profile(profile)
        
        retrieved = temp_knowledge.get_profile("custom-site.com")
        assert retrieved is not None
        assert retrieved.protection_type == "cloudflare"
        assert retrieved.best_strategy == "aggressive"
    
    def test_update_profile(self, temp_knowledge):
        """Testa atualização de perfil."""
        temp_knowledge.get_or_create_profile("example.com")
        
        temp_knowledge.update_profile(
            "example.com",
            protection_type="waf",
            best_strategy="robust"
        )
        
        profile = temp_knowledge.get_profile("example.com")
        assert profile.protection_type == "waf"
        assert profile.best_strategy == "robust"
    
    def test_record_success(self, temp_knowledge):
        """Testa registro de sucesso."""
        temp_knowledge.record_success(
            "https://example.com/page",
            response_time_ms=150,
            strategy_used="fast"
        )
        
        profile = temp_knowledge.get_profile("example.com")
        assert profile is not None
        assert profile.total_successes == 1
        assert profile.avg_response_time_ms == 150
    
    def test_record_failure(self, temp_knowledge):
        """Testa registro de falha."""
        temp_knowledge.record_failure(
            "https://example.com/page",
            error_type="timeout",
            protection_detected="cloudflare"
        )
        
        profile = temp_knowledge.get_profile("example.com")
        assert profile is not None
        assert profile.total_attempts == 1
        assert profile.success_rate == 0.0
        assert profile.protection_type == "cloudflare"
    
    def test_get_best_strategy_unknown_site(self, temp_knowledge):
        """Testa estratégia para site desconhecido."""
        strategy = temp_knowledge.get_best_strategy("unknown.com")
        assert strategy == "standard"
    
    def test_get_best_strategy_known_site(self, temp_knowledge):
        """Testa estratégia para site conhecido."""
        temp_knowledge.update_profile(
            "fast-site.com",
            best_strategy="fast"
        )
        
        strategy = temp_knowledge.get_best_strategy("fast-site.com")
        assert strategy == "fast"
    
    def test_get_best_strategy_low_success_protection(self, temp_knowledge):
        """Testa estratégia agressiva para site com baixo sucesso e proteção."""
        profile = temp_knowledge.get_or_create_profile("protected.com")
        profile.protection_type = "cloudflare"
        profile.total_attempts = 10
        profile.total_successes = 2  # 20% sucesso
        profile._recalculate_success_rate()
        temp_knowledge.add_profile(profile)
        
        strategy = temp_knowledge.get_best_strategy("protected.com")
        assert strategy == "aggressive"
    
    def test_get_protection_type(self, temp_knowledge):
        """Testa obtenção de tipo de proteção."""
        temp_knowledge.update_profile(
            "waf-site.com",
            protection_type="waf"
        )
        
        protection = temp_knowledge.get_protection_type("waf-site.com")
        assert protection == "waf"
        
        # Site desconhecido
        protection = temp_knowledge.get_protection_type("unknown.com")
        assert protection == "none"
    
    def test_get_problematic_domains(self, temp_knowledge):
        """Testa obtenção de domínios problemáticos."""
        # Site problemático (baixo sucesso)
        profile1 = temp_knowledge.get_or_create_profile("problem1.com")
        profile1.total_attempts = 10
        profile1.total_successes = 3
        profile1._recalculate_success_rate()
        temp_knowledge.add_profile(profile1)
        
        # Site OK (alto sucesso)
        profile2 = temp_knowledge.get_or_create_profile("ok-site.com")
        profile2.total_attempts = 10
        profile2.total_successes = 9
        profile2._recalculate_success_rate()
        temp_knowledge.add_profile(profile2)
        
        problematic = temp_knowledge.get_problematic_domains(min_failures=3)
        
        assert len(problematic) == 1
        assert problematic[0].domain == "problem1.com"
    
    def test_get_protected_domains(self, temp_knowledge):
        """Testa obtenção de domínios protegidos."""
        temp_knowledge.update_profile("cf1.com", protection_type="cloudflare")
        temp_knowledge.update_profile("cf2.com", protection_type="cloudflare")
        temp_knowledge.update_profile("waf1.com", protection_type="waf")
        temp_knowledge.update_profile("normal.com", protection_type="none")
        
        protected = temp_knowledge.get_protected_domains()
        
        assert "cloudflare" in protected
        assert len(protected["cloudflare"]) == 2
        assert "waf" in protected
        assert len(protected["waf"]) == 1
        assert "none" not in protected
    
    def test_get_summary(self, temp_knowledge):
        """Testa resumo da base."""
        temp_knowledge.update_profile("site1.com", protection_type="cloudflare")
        temp_knowledge.record_success("site2.com", 100)
        
        summary = temp_knowledge.get_summary()
        
        assert summary["total_profiles"] == 2
        assert "protected_sites" in summary
        assert "avg_success_rate" in summary
    
    def test_persistence(self, temp_knowledge):
        """Testa persistência em disco."""
        temp_knowledge.update_profile(
            "persist-test.com",
            protection_type="waf",
            best_strategy="robust"
        )
        
        # Criar nova instância
        new_kb = SiteKnowledgeBase(storage_path=temp_knowledge.storage_path)
        
        profile = new_kb.get_profile("persist-test.com")
        assert profile is not None
        assert profile.protection_type == "waf"
    
    def test_domain_extraction_from_url(self, temp_knowledge):
        """Testa extração de domínio de URL."""
        temp_knowledge.record_success(
            "https://www.example.com/path/to/page.html?query=1",
            response_time_ms=100
        )
        
        profile = temp_knowledge.get_profile("www.example.com")
        assert profile is not None
    
    def test_update_best_strategy_high_success(self, temp_knowledge):
        """Testa atualização de estratégia com alto sucesso."""
        # Simular múltiplos sucessos com uma estratégia
        for _ in range(10):
            temp_knowledge.record_success(
                "consistent-site.com",
                response_time_ms=100,
                strategy_used="fast"
            )
        
        profile = temp_knowledge.get_profile("consistent-site.com")
        assert profile.best_strategy == "fast"
        assert profile.success_rate > 0.8


class TestSiteKnowledgeEdgeCases:
    """Testes de casos extremos."""
    
    @pytest.fixture
    def temp_knowledge(self):
        """Cria knowledge base com arquivo temporário."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        kb = SiteKnowledgeBase(storage_path=temp_path)
        yield kb
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_empty_url(self, temp_knowledge):
        """Testa URL vazia."""
        profile = temp_knowledge.get_or_create_profile("")
        assert profile.domain == ""
    
    def test_special_characters_in_domain(self, temp_knowledge):
        """Testa caracteres especiais em domínio."""
        temp_knowledge.record_success(
            "https://sub-domain.example-site.co.uk",
            response_time_ms=100
        )
        
        profile = temp_knowledge.get_profile("sub-domain.example-site.co.uk")
        assert profile is not None
    
    def test_concurrent_updates(self, temp_knowledge):
        """Testa múltiplas atualizações."""
        for i in range(100):
            if i % 2 == 0:
                temp_knowledge.record_success(f"site{i % 10}.com", 100)
            else:
                temp_knowledge.record_failure(f"site{i % 10}.com", "timeout")
        
        # Verificar que não perdeu dados
        assert temp_knowledge.get_profile("site0.com") is not None
