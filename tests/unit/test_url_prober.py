"""
Testes unitários para o URLProber.
"""

import pytest
from app.services.scraper.url_prober import URLProber


class TestURLProber:
    """Testes para geração de variações de URL."""
    
    def setup_method(self):
        self.prober = URLProber(timeout=5.0)
    
    def test_generate_variations_basic(self):
        """Deve gerar variações básicas."""
        variations = self.prober._generate_variations("example.com")
        assert len(variations) >= 4  # https/http x www/non-www
        assert "https://example.com" in variations
        assert "https://www.example.com" in variations
        assert "http://example.com" in variations
        assert "http://www.example.com" in variations
    
    def test_generate_variations_with_scheme(self):
        """Deve funcionar com URL que já tem scheme."""
        variations = self.prober._generate_variations("https://example.com")
        assert "https://example.com" in variations
        assert "https://www.example.com" in variations
    
    def test_generate_variations_with_www(self):
        """Deve funcionar com URL que já tem www."""
        variations = self.prober._generate_variations("https://www.example.com")
        assert "https://www.example.com" in variations
        assert "https://example.com" in variations
    
    def test_generate_variations_with_path(self):
        """Deve preservar path."""
        variations = self.prober._generate_variations("https://example.com/page")
        for var in variations:
            assert "/page" in var
    
    def test_generate_variations_no_double_www(self):
        """Não deve gerar www.www."""
        variations = self.prober._generate_variations("www.example.com")
        for var in variations:
            assert "www.www" not in var
    
    def test_generate_variations_order(self):
        """HTTPS deve vir primeiro."""
        variations = self.prober._generate_variations("example.com")
        assert variations[0].startswith("https://")
    
    def test_generate_variations_unique(self):
        """Todas as variações devem ser únicas."""
        variations = self.prober._generate_variations("example.com")
        assert len(variations) == len(set(variations))
    
    def test_generate_variations_subdomain(self):
        """Deve funcionar com subdomínio."""
        variations = self.prober._generate_variations("https://api.example.com")
        # Não deve adicionar www a subdomínio existente de forma incorreta
        assert any("api.example.com" in v for v in variations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

