"""
Circuit Breaker para controle de falhas por domínio.
Previne tentativas excessivas em domínios que estão falhando.
"""

import logging
from urllib.parse import urlparse
from .constants import scraper_config

logger = logging.getLogger(__name__)

# Estado global do circuit breaker
_domain_failures: dict[str, int] = {}


def get_domain(url: str) -> str:
    """Extrai o domínio de uma URL."""
    try:
        return urlparse(url).netloc
    except:
        return "unknown"


def record_failure(url: str, is_protection: bool = False) -> None:
    """
    Registra falha de um domínio.
    
    Args:
        url: URL que falhou
        is_protection: Se True, é uma proteção (Cloudflare/WAF), não conta como falha
    """
    if is_protection:
        logger.debug(f"[CircuitBreaker] Proteção detectada em {url}, não contando como falha")
        return
        
    domain = get_domain(url)
    _domain_failures[domain] = _domain_failures.get(domain, 0) + 1
    
    threshold = scraper_config.circuit_breaker_threshold
    if _domain_failures[domain] >= threshold:
        logger.warning(
            f"🔌 CIRCUIT BREAKER ABERTO para {domain} após "
            f"{_domain_failures[domain]} falhas consecutivas"
        )


def record_success(url: str) -> None:
    """Registra sucesso de um domínio (reseta contador de falhas)."""
    domain = get_domain(url)
    if domain in _domain_failures:
        _domain_failures[domain] = 0


def is_circuit_open(url: str) -> bool:
    """Verifica se o circuit breaker está aberto para um domínio."""
    domain = get_domain(url)
    threshold = scraper_config.circuit_breaker_threshold
    return _domain_failures.get(domain, 0) >= threshold


def get_failure_count(url: str) -> int:
    """Retorna o número de falhas de um domínio."""
    domain = get_domain(url)
    return _domain_failures.get(domain, 0)


def reset_all() -> None:
    """Reseta todos os contadores de falha."""
    _domain_failures.clear()
    logger.info("🔄 Circuit breaker resetado para todos os domínios")


def reset_domain(url: str) -> None:
    """Reseta o contador de falha de um domínio específico."""
    domain = get_domain(url)
    if domain in _domain_failures:
        del _domain_failures[domain]
        logger.info(f"🔄 Circuit breaker resetado para {domain}")

