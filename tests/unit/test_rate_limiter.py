"""
Testes unitários para o Rate Limiter.
"""

import pytest
import asyncio
import time
from app.services.llm.rate_limiter import TokenBucket, RateLimiter, BucketConfig


class TestTokenBucket:
    """Testes para TokenBucket."""
    
    def test_init_default_max_tokens(self):
        """max_tokens deve ser igual a tpm se não especificado."""
        bucket = TokenBucket(tokens_per_minute=60)
        assert bucket.max_tokens == 60
        assert bucket.tokens == 60.0
    
    def test_init_custom_max_tokens(self):
        """Deve aceitar max_tokens customizado."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        assert bucket.max_tokens == 10
        assert bucket.tokens == 10.0
    
    @pytest.mark.asyncio
    async def test_acquire_immediate(self):
        """Deve adquirir token imediatamente se disponível."""
        bucket = TokenBucket(tokens_per_minute=60)
        
        start = time.perf_counter()
        result = await bucket.acquire(1)
        elapsed = time.perf_counter() - start
        
        assert result is True
        assert elapsed < 0.1  # Deve ser quase instantâneo
    
    @pytest.mark.asyncio
    async def test_acquire_depletes_tokens(self):
        """Adquirir deve reduzir tokens disponíveis."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        
        assert bucket.tokens == 10.0
        await bucket.acquire(3)
        assert bucket.tokens == 7.0
    
    @pytest.mark.asyncio
    async def test_acquire_timeout(self):
        """Deve retornar False se não conseguir tokens no timeout."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=1)
        
        # Consumir todos os tokens
        await bucket.acquire(1)
        
        # Tentar adquirir mais com timeout curto
        result = await bucket.acquire(1, timeout=0.1)
        assert result is False
    
    def test_get_wait_time_zero_if_available(self):
        """Tempo de espera deve ser 0 se tokens disponíveis."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        wait_time = bucket._get_wait_time(5)
        assert wait_time == 0.0
    
    def test_get_wait_time_positive_if_not_available(self):
        """Tempo de espera deve ser positivo se não há tokens."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=1)
        bucket.tokens = 0
        
        wait_time = bucket._get_wait_time(1)
        assert wait_time > 0
    
    def test_utilization(self):
        """Utilização deve refletir tokens usados."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        
        assert bucket.utilization == 0.0
        
        bucket.tokens = 5
        assert bucket.utilization == 0.5
        
        bucket.tokens = 0
        assert bucket.utilization == 1.0
    
    def test_get_status(self):
        """Status deve conter informações relevantes."""
        bucket = TokenBucket(tokens_per_minute=60, max_tokens=10)
        status = bucket.get_status()
        
        assert "tokens" in status
        assert "max_tokens" in status
        assert "tpm" in status
        assert "utilization" in status


class TestRateLimiter:
    """Testes para RateLimiter."""
    
    def test_get_or_create_bucket(self):
        """Deve criar bucket automaticamente para provider novo."""
        limiter = RateLimiter()
        
        tokens = limiter.get_available_tokens("NewProvider")
        assert tokens > 0  # Bucket foi criado
    
    @pytest.mark.asyncio
    async def test_acquire_for_provider(self):
        """Deve adquirir tokens para provider específico."""
        limiter = RateLimiter()
        
        result = await limiter.acquire("Google Gemini", 1)
        assert result is True
    
    def test_get_wait_time(self):
        """Deve retornar tempo de espera para provider."""
        limiter = RateLimiter()
        
        wait = limiter.get_wait_time("Google Gemini", 1)
        assert wait >= 0
    
    def test_get_best_provider(self):
        """Deve retornar provider com menor tempo de espera."""
        limiter = RateLimiter()
        providers = ["Google Gemini", "OpenAI"]
        
        best = limiter.get_best_provider(providers)
        assert best in providers
    
    def test_get_status(self):
        """Deve retornar status de todos os buckets."""
        limiter = RateLimiter()
        
        # Criar alguns buckets
        limiter.get_available_tokens("Provider1")
        limiter.get_available_tokens("Provider2")
        
        status = limiter.get_status()
        assert "Provider1" in status
        assert "Provider2" in status
    
    def test_reset_specific_provider(self):
        """Deve resetar apenas um provider."""
        limiter = RateLimiter()
        
        # Consumir tokens
        limiter._get_or_create_bucket("TestProvider").tokens = 0
        assert limiter.get_available_tokens("TestProvider") == 0
        
        limiter.reset("TestProvider")
        assert limiter.get_available_tokens("TestProvider") > 0
    
    def test_reset_all(self):
        """Deve resetar todos os providers."""
        limiter = RateLimiter()
        
        # Criar e consumir tokens
        limiter._get_or_create_bucket("P1").tokens = 0
        limiter._get_or_create_bucket("P2").tokens = 0
        
        limiter.reset()
        
        assert limiter.get_available_tokens("P1") > 0
        assert limiter.get_available_tokens("P2") > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

