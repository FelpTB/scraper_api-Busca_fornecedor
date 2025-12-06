"""
Seletor de estratégias de scraping.
Decide qual estratégia usar baseado no perfil do site.
"""

import logging
from typing import List
from .models import SiteProfile, SiteType, ProtectionType, ScrapingStrategy

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Seleciona estratégias de scraping ordenadas por prioridade.
    Retorna lista de estratégias para tentar em cascata.
    """
    
    # Configuração de estratégias por tipo de proteção
    PROTECTION_STRATEGIES = {
        ProtectionType.NONE: [
            ScrapingStrategy.FAST,
            ScrapingStrategy.STANDARD,
            ScrapingStrategy.ROBUST
        ],
        ProtectionType.CLOUDFLARE: [
            ScrapingStrategy.AGGRESSIVE,
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.STANDARD
        ],
        ProtectionType.WAF: [
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.AGGRESSIVE,
            ScrapingStrategy.STANDARD
        ],
        ProtectionType.CAPTCHA: [
            ScrapingStrategy.AGGRESSIVE,
            ScrapingStrategy.ROBUST
        ],
        ProtectionType.RATE_LIMIT: [
            ScrapingStrategy.STANDARD,
            ScrapingStrategy.ROBUST
        ],
        ProtectionType.BOT_DETECTION: [
            ScrapingStrategy.AGGRESSIVE,
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.STANDARD
        ]
    }
    
    # Configuração de estratégias por tipo de site
    SITE_TYPE_STRATEGIES = {
        SiteType.STATIC: [
            ScrapingStrategy.FAST,
            ScrapingStrategy.STANDARD,
            ScrapingStrategy.ROBUST
        ],
        SiteType.SPA: [
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.AGGRESSIVE,
            ScrapingStrategy.STANDARD
        ],
        SiteType.HYBRID: [
            ScrapingStrategy.STANDARD,
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.AGGRESSIVE
        ],
        SiteType.UNKNOWN: [
            ScrapingStrategy.STANDARD,
            ScrapingStrategy.FAST,
            ScrapingStrategy.ROBUST,
            ScrapingStrategy.AGGRESSIVE
        ]
    }
    
    def select(self, site_profile: SiteProfile) -> List[ScrapingStrategy]:
        """
        Retorna lista de estratégias ordenadas por prioridade.
        
        Args:
            site_profile: Perfil do site analisado
        
        Returns:
            Lista de estratégias para tentar em ordem
        """
        protection = site_profile.protection_type
        site_type = site_profile.site_type
        
        # Se há proteção, priorizar estratégias para proteção
        if protection != ProtectionType.NONE:
            protection_strats = self.PROTECTION_STRATEGIES.get(
                protection, 
                self.PROTECTION_STRATEGIES[ProtectionType.NONE]
            )
            combined = list(protection_strats)
        else:
            # Sem proteção: priorizar baseado no tipo de site
            combined = list(self.SITE_TYPE_STRATEGIES.get(
                site_type,
                self.SITE_TYPE_STRATEGIES[SiteType.UNKNOWN]
            ))
        
        # Adicionar estratégias complementares
        all_strategies = [
            ScrapingStrategy.FAST, ScrapingStrategy.STANDARD,
            ScrapingStrategy.ROBUST, ScrapingStrategy.AGGRESSIVE
        ]
        for strat in all_strategies:
            if strat not in combined:
                combined.append(strat)
        
        # Ajustar baseado em tempo de resposta
        if site_profile.response_time_ms > 5000:
            # Site muito lento - priorizar ROBUST
            if ScrapingStrategy.ROBUST in combined:
                combined.remove(ScrapingStrategy.ROBUST)
                combined.insert(0, ScrapingStrategy.ROBUST)
        elif site_profile.response_time_ms < 500 and site_type == SiteType.STATIC:
            # Site estático rápido - priorizar FAST
            if ScrapingStrategy.FAST in combined:
                combined.remove(ScrapingStrategy.FAST)
                combined.insert(0, ScrapingStrategy.FAST)
        
        logger.debug(
            f"Estratégias selecionadas para {site_profile.url}: "
            f"{[s.value for s in combined]}"
        )
        
        return combined
    
    def select_for_subpage(
        self, 
        main_strategy: ScrapingStrategy, 
        subpage_url: str
    ) -> List[ScrapingStrategy]:
        """
        Seleciona estratégias para subpágina baseado na estratégia da main page.
        
        Args:
            main_strategy: Estratégia que funcionou na main page
            subpage_url: URL da subpágina
        
        Returns:
            Lista de estratégias para a subpágina
        """
        # Começar com a estratégia que funcionou
        strategies = [main_strategy]
        
        # Adicionar fallbacks
        if main_strategy == ScrapingStrategy.FAST:
            strategies.extend([ScrapingStrategy.STANDARD, ScrapingStrategy.ROBUST])
        elif main_strategy == ScrapingStrategy.STANDARD:
            strategies.extend([ScrapingStrategy.FAST, ScrapingStrategy.ROBUST])
        elif main_strategy == ScrapingStrategy.ROBUST:
            strategies.extend([ScrapingStrategy.STANDARD, ScrapingStrategy.AGGRESSIVE])
        elif main_strategy == ScrapingStrategy.AGGRESSIVE:
            strategies.extend([ScrapingStrategy.ROBUST, ScrapingStrategy.STANDARD])
        
        return strategies
    
    def get_strategy_config(self, strategy: ScrapingStrategy) -> dict:
        """
        Retorna configuração específica para cada estratégia.
        
        Args:
            strategy: Estratégia de scraping
        
        Returns:
            Dict com configurações (timeout, use_proxy, rotate_ua, etc)
        """
        configs = {
            ScrapingStrategy.FAST: {
                "timeout": 10,
                "use_proxy": False,
                "rotate_ua": False,
                "retry_count": 1,
                "delay_between_requests": 0.1
            },
            ScrapingStrategy.STANDARD: {
                "timeout": 15,
                "use_proxy": True,
                "rotate_ua": False,
                "retry_count": 2,
                "delay_between_requests": 0.5
            },
            ScrapingStrategy.ROBUST: {
                "timeout": 20,
                "use_proxy": True,
                "rotate_ua": True,
                "retry_count": 3,
                "delay_between_requests": 1.0
            },
            ScrapingStrategy.AGGRESSIVE: {
                "timeout": 25,
                "use_proxy": True,
                "rotate_ua": True,
                "rotate_proxy": True,
                "custom_headers": True,
                "retry_count": 3,
                "delay_between_requests": 2.0
            }
        }
        return configs.get(strategy, configs[ScrapingStrategy.STANDARD])


# Instância singleton
strategy_selector = StrategySelector()

