"""
Testes unitários para o FailureTracker.
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from app.services.learning.failure_tracker import (
    FailureTracker,
    FailureRecord,
    FailureModule,
    FailureType
)


class TestFailureRecord:
    """Testes para FailureRecord."""
    
    def test_create_basic_record(self):
        """Testa criação básica de registro."""
        record = FailureRecord.create(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://example.com",
            error_message="Connection timed out"
        )
        
        assert record.module == "scraper"
        assert record.error_type == "timeout"
        assert record.url == "https://example.com"
        assert record.domain == "example.com"
        assert record.error_message == "Connection timed out"
        assert record.timestamp
    
    def test_create_with_context(self):
        """Testa criação com contexto adicional."""
        record = FailureRecord.create(
            module=FailureModule.LLM,
            error_type=FailureType.LLM_RATE_LIMIT,
            url="openai",
            context={"provider": "OpenAI", "tokens": 1000},
            retry_count=2
        )
        
        assert record.module == "llm"
        assert record.context["provider"] == "OpenAI"
        assert record.context["tokens"] == 1000
        assert record.retry_count == 2
    
    def test_domain_extraction(self):
        """Testa extração de domínio."""
        record = FailureRecord.create(
            module=FailureModule.SCRAPER,
            error_type=FailureType.CLOUDFLARE,
            url="https://www.sub.example.com/path/page.html?query=1"
        )
        
        assert record.domain == "www.sub.example.com"


class TestFailureTracker:
    """Testes para FailureTracker."""
    
    @pytest.fixture
    def temp_tracker(self):
        """Cria tracker com arquivo temporário."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        tracker = FailureTracker(storage_path=temp_path)
        yield tracker
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_record_and_retrieve(self, temp_tracker):
        """Testa gravar e recuperar registros."""
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://slow-site.com",
            error_message="Timed out after 30s"
        )
        
        records = temp_tracker.get_by_domain("slow-site.com")
        assert len(records) == 1
        assert records[0].error_type == "timeout"
    
    def test_get_by_module(self, temp_tracker):
        """Testa busca por módulo."""
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://example1.com"
        )
        temp_tracker.record_failure(
            module=FailureModule.LLM,
            error_type=FailureType.LLM_TIMEOUT,
            url="openai"
        )
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.CLOUDFLARE,
            url="https://example2.com"
        )
        
        scraper_failures = temp_tracker.get_by_module(FailureModule.SCRAPER)
        assert len(scraper_failures) == 2
        
        llm_failures = temp_tracker.get_by_module(FailureModule.LLM)
        assert len(llm_failures) == 1
    
    def test_get_by_type(self, temp_tracker):
        """Testa busca por tipo de erro."""
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.CLOUDFLARE,
            url="https://cf-site1.com"
        )
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.CLOUDFLARE,
            url="https://cf-site2.com"
        )
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.WAF,
            url="https://waf-site.com"
        )
        
        cf_failures = temp_tracker.get_by_type(FailureType.CLOUDFLARE)
        assert len(cf_failures) == 2
    
    def test_get_patterns(self, temp_tracker):
        """Testa obtenção de padrões."""
        # Adicionar várias falhas
        for _ in range(3):
            temp_tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url="https://slow.com"
            )
        
        for _ in range(2):
            temp_tracker.record_failure(
            module=FailureModule.LLM,
            error_type=FailureType.LLM_RATE_LIMIT,
                url="openai"
        )
        
        patterns = temp_tracker.get_patterns(period_hours=24)
        
        assert "scraper" in patterns
        assert patterns["scraper"]["timeout"] == 3
        assert "llm" in patterns
        assert patterns["llm"]["llm_rate_limit"] == 2
    
    def test_get_domain_stats(self, temp_tracker):
        """Testa estatísticas por domínio."""
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://problem-site.com/page1",
            strategy_used="fast",
            retry_count=2
        )
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.CLOUDFLARE,
            url="https://problem-site.com/page2",
            strategy_used="robust",
            retry_count=3
        )
        
        stats = temp_tracker.get_domain_stats("problem-site.com")
        
        assert stats["total_failures"] == 2
        assert "timeout" in stats["error_types"]
        assert "cloudflare" in stats["error_types"]
        assert stats["avg_retry_count"] == 2.5
    
    def test_persistence(self, temp_tracker):
        """Testa persistência em disco."""
        temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
            url="https://test.com"
        )
        
        # Criar novo tracker com mesmo arquivo
        new_tracker = FailureTracker(storage_path=temp_tracker.storage_path)
        
        assert len(new_tracker.records) == 1
        assert new_tracker.records[0].domain == "test.com"
    
    def test_max_records_limit(self, temp_tracker):
        """Testa limite máximo de registros."""
        temp_tracker.MAX_RECORDS = 10  # Reduzir para teste
        
        for i in range(15):
            temp_tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url=f"https://site{i}.com"
            )
        
        assert len(temp_tracker.records) == 10
    
    def test_get_summary(self, temp_tracker):
        """Testa resumo geral."""
        for i in range(5):
            temp_tracker.record_failure(
            module=FailureModule.SCRAPER,
            error_type=FailureType.TIMEOUT,
                url=f"https://site{i}.com"
            )
        
        summary = temp_tracker.get_summary()
        
        assert summary["total_records"] == 5
        assert summary["unique_domains"] == 5
        assert "scraper" in summary["total_by_module_24h"]
    
    def test_get_recent_failures(self, temp_tracker):
        """Testa obtenção de falhas recentes."""
        for i in range(20):
            temp_tracker.record_failure(
                module=FailureModule.SCRAPER,
                error_type=FailureType.TIMEOUT,
                url=f"https://site{i}.com"
        )
        
        recent = temp_tracker.get_recent_failures(limit=5)
        assert len(recent) == 5
        assert recent[-1].domain == "site19.com"


class TestFailureEnums:
    """Testes para enums de falha."""
    
    def test_failure_modules(self):
        """Testa módulos de falha."""
        assert FailureModule.SCRAPER.value == "scraper"
        assert FailureModule.LLM.value == "llm"
        assert FailureModule.DISCOVERY.value == "discovery"
    
    def test_scraper_failure_types(self):
        """Testa tipos de falha do scraper."""
        scraper_types = [
            FailureType.TIMEOUT,
            FailureType.CONNECTION_ERROR,
            FailureType.CLOUDFLARE,
            FailureType.WAF,
            FailureType.CAPTCHA,
            FailureType.RATE_LIMIT,
            FailureType.EMPTY_CONTENT,
            FailureType.SOFT_404,
            FailureType.SSL_ERROR,
            FailureType.DNS_ERROR
        ]
        
        for ft in scraper_types:
            assert ft.value is not None
    
    def test_llm_failure_types(self):
        """Testa tipos de falha do LLM."""
        llm_types = [
            FailureType.LLM_TIMEOUT,
            FailureType.LLM_RATE_LIMIT,
            FailureType.LLM_BAD_REQUEST,
            FailureType.LLM_PARSE_ERROR,
            FailureType.LLM_PROVIDER_ERROR
        ]
        
        for ft in llm_types:
            assert ft.value is not None
