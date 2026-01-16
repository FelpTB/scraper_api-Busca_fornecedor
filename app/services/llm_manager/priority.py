"""
Níveis de prioridade para chamadas LLM.
"""

from enum import IntEnum


class LLMPriority(IntEnum):
    """
    Níveis de prioridade para chamadas LLM.
    
    HIGH: Discovery e LinkSelector - prioridade ABSOLUTA, executa imediatamente
    NORMAL: Profile building - ESPERA até que todos HIGH terminem
    
    Objetivo: Garantir que Discovery/LinkSelector alimentem o scraper o mais
    rápido possível. O único gargalo da aplicação deve ser o scraper.
    """
    HIGH = 1    # Discovery, LinkSelector - prioridade absoluta
    NORMAL = 2  # Profile building - espera HIGH terminar


