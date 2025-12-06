"""
Testes unitários para o ProtectionDetector.
"""

import pytest
from app.services.scraper.protection_detector import ProtectionDetector, protection_detector
from app.services.scraper.models import ProtectionType


class TestProtectionDetector:
    """Testes para detecção de proteções."""
    
    def setup_method(self):
        self.detector = ProtectionDetector()
    
    def test_detect_no_protection(self):
        """Deve retornar NONE para página sem proteção."""
        body = "<html><body><h1>Welcome</h1><p>Content here</p></body></html>"
        result = self.detector.detect(response_body=body, status_code=200)
        assert result == ProtectionType.NONE
    
    def test_detect_cloudflare_challenge(self):
        """Deve detectar Cloudflare challenge."""
        body = """
        <html>
        <title>Just a moment...</title>
        <body>
        Please wait while we verify your browser...
        Cloudflare Ray ID: abc123
        </body>
        </html>
        """
        result = self.detector.detect(response_body=body, status_code=403)
        assert result == ProtectionType.CLOUDFLARE
    
    def test_detect_cloudflare_with_headers(self):
        """Deve detectar Cloudflare via headers + body."""
        headers = {"cf-ray": "abc123", "cf-cache-status": "DYNAMIC"}
        body = "Please wait... checking your browser... cloudflare"
        result = self.detector.detect(response_headers=headers, response_body=body)
        assert result == ProtectionType.CLOUDFLARE
    
    def test_detect_waf(self):
        """Deve detectar WAF genérico."""
        body = """
        <html>
        <title>Access Denied</title>
        <body>
        Your request has been blocked by our firewall.
        This is a security check.
        </body>
        </html>
        """
        result = self.detector.detect(response_body=body, status_code=403)
        assert result == ProtectionType.WAF
    
    def test_detect_captcha_recaptcha(self):
        """Deve detectar reCAPTCHA."""
        body = """
        <html>
        <body>
        <div class="g-recaptcha" data-sitekey="xyz"></div>
        Please prove you're not a robot.
        </body>
        </html>
        """
        result = self.detector.detect(response_body=body)
        assert result == ProtectionType.CAPTCHA
    
    def test_detect_captcha_hcaptcha(self):
        """Deve detectar hCaptcha."""
        body = """
        <html>
        <body>
        <div class="h-captcha"></div>
        Verify you are human.
        </body>
        </html>
        """
        result = self.detector.detect(response_body=body)
        assert result == ProtectionType.CAPTCHA
    
    def test_detect_rate_limit_status_429(self):
        """Deve detectar rate limit via status 429."""
        result = self.detector.detect(response_body="", status_code=429)
        assert result == ProtectionType.RATE_LIMIT
    
    def test_detect_rate_limit_body(self):
        """Deve detectar rate limit via corpo."""
        body = "Too many requests. Please slow down and retry after a few seconds."
        result = self.detector.detect(response_body=body, status_code=200)
        assert result == ProtectionType.RATE_LIMIT
    
    def test_detect_bot_detection(self):
        """Deve detectar detecção de bot."""
        body = """
        <html>
        <body>
        <h1>Bot Detected</h1>
        We've detected automated access to our site. 
        Please verify you're not a robot.
        </body>
        </html>
        """
        result = self.detector.detect(response_body=body)
        assert result == ProtectionType.BOT_DETECTION
    
    def test_is_blocking_protection(self):
        """Deve identificar proteções que bloqueiam."""
        assert self.detector.is_blocking_protection(ProtectionType.CLOUDFLARE) == True
        assert self.detector.is_blocking_protection(ProtectionType.CAPTCHA) == True
        assert self.detector.is_blocking_protection(ProtectionType.BOT_DETECTION) == True
        assert self.detector.is_blocking_protection(ProtectionType.NONE) == False
        assert self.detector.is_blocking_protection(ProtectionType.WAF) == False
    
    def test_get_retry_recommendation_cloudflare(self):
        """Deve retornar recomendação para Cloudflare."""
        rec = self.detector.get_retry_recommendation(ProtectionType.CLOUDFLARE)
        assert rec["can_retry"] == True
        assert rec["delay_seconds"] == 5
        assert rec["change_strategy"] == True
    
    def test_get_retry_recommendation_captcha(self):
        """Deve retornar que não pode retry para captcha."""
        rec = self.detector.get_retry_recommendation(ProtectionType.CAPTCHA)
        assert rec["can_retry"] == False
    
    def test_singleton_instance(self):
        """Deve ter instância singleton disponível."""
        assert protection_detector is not None
        assert isinstance(protection_detector, ProtectionDetector)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

