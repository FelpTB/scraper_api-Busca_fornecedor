"""
Módulo de Discovery v2.0

Responsável por encontrar o site oficial de uma empresa
usando busca no Google e análise por LLM.
"""

from .discovery_service import find_company_website, search_google_serper, search_google

__all__ = [
    'find_company_website',
    'search_google_serper',
    'search_google',
]

