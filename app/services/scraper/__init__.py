"""
Módulo de Scraping v2.0

Responsável por extrair conteúdo de websites de forma adaptativa.
Inclui detecção automática de proteções, seleção de estratégias e fallback.
"""

from .constants import scraper_config, ScraperConfig
from .circuit_breaker import (
    record_failure,
    record_success,
    is_circuit_open,
    reset_all as reset_circuit_breaker
)
from .html_parser import (
    parse_html,
    is_cloudflare_challenge,
    is_soft_404,
    normalize_url
)
from .link_selector import (
    select_links_with_llm,
    prioritize_links,
    filter_non_html_links
)
from .models import (
    SiteType,
    ProtectionType,
    ScrapingStrategy,
    SiteProfile,
    ScrapedPage,
    ScrapedContent
)
from .site_analyzer import site_analyzer, SiteAnalyzer
from .protection_detector import protection_detector, ProtectionDetector
from .strategy_selector import strategy_selector, StrategySelector
from .url_prober import url_prober, URLProber, URLNotReachable

# Importação direta do scrape_url para compatibilidade
try:
    from .scraper_service import scrape_url
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"curl_cffi não disponível: {e}")
    
    async def scrape_url(url: str, max_subpages: int = 100):
        """Stub quando curl_cffi não está disponível."""
        return "", [], []


__all__ = [
    # Função principal
    'scrape_url',
    
    # Configuração
    'scraper_config',
    'ScraperConfig',
    
    # Circuit Breaker
    'record_failure',
    'record_success',
    'is_circuit_open',
    'reset_circuit_breaker',
    
    # HTML Parser
    'parse_html',
    'is_cloudflare_challenge',
    'is_soft_404',
    'normalize_url',
    
    # Link Selector
    'select_links_with_llm',
    'prioritize_links',
    'filter_non_html_links',
    
    # Modelos v2.0
    'SiteType',
    'ProtectionType',
    'ScrapingStrategy',
    'SiteProfile',
    'ScrapedPage',
    'ScrapedContent',
    
    # Analisadores v2.0
    'site_analyzer',
    'SiteAnalyzer',
    'protection_detector',
    'ProtectionDetector',
    'strategy_selector',
    'StrategySelector',
    'url_prober',
    'URLProber',
    'URLNotReachable',
]


def configure_scraper(**kwargs):
    """
    Configura dinamicamente os parâmetros do scraper.
    
    Parâmetros aceitos:
        site_semaphore_limit: int
        circuit_breaker_threshold: int
        page_timeout: int
        session_timeout: int
        chunk_size: int
        chunk_semaphore_limit: int
    """
    scraper_config.update(**kwargs)

