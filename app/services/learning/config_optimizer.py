"""
Config Optimizer - Sugere e aplica otimizações de configuração.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime

from .pattern_analyzer import PatternAnalyzer, ScraperAnalysis, LLMAnalysis

logger = logging.getLogger(__name__)


@dataclass
class ConfigSuggestion:
    """Sugestão de alteração de configuração."""
    module: str
    config_key: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0.0 a 1.0
    auto_apply: bool = False  # Se pode ser aplicado automaticamente


class ConfigOptimizer:
    """
    Otimizador de configurações baseado em análise de padrões.
    
    Analisa falhas e sugere ajustes nas configurações do scraper e LLM.
    """
    
    # Limites de configuração
    SCRAPER_LIMITS = {
        "timeout": (5, 60),  # segundos
        "chunk_size": (5, 50),
        "max_concurrent": (5, 100),
        "retry_count": (1, 5)
    }
    
    LLM_LIMITS = {
        "timeout": (30, 300),  # segundos
        "max_chunk_tokens": (10000, 500000),
        "max_concurrent": (5, 100)
    }
    
    def __init__(self, pattern_analyzer: PatternAnalyzer):
        self.pattern_analyzer = pattern_analyzer
        self._applied_suggestions: List[ConfigSuggestion] = []
    
    def suggest_scraper_config(
        self, 
        current_config: Dict[str, Any],
        period_hours: int = 24
    ) -> List[ConfigSuggestion]:
        """
        Sugere otimizações para configuração do scraper.
        
        Args:
            current_config: Configuração atual do scraper
            period_hours: Período de análise
        
        Returns:
            Lista de sugestões
        """
        suggestions = []
        analysis = self.pattern_analyzer.analyze_scraper_failures(period_hours)
        
        if analysis.total_failures == 0:
            return suggestions
        
        # Analisar timeout
        timeout_rate = analysis.failure_rate_by_type.get("timeout", 0)
        current_timeout = current_config.get("session_timeout", 15)
        
        if timeout_rate > 20:
            # Muitos timeouts - aumentar timeout
            new_timeout = min(current_timeout * 1.5, self.SCRAPER_LIMITS["timeout"][1])
            if new_timeout != current_timeout:
                suggestions.append(ConfigSuggestion(
                    module="scraper",
                    config_key="session_timeout",
                    current_value=current_timeout,
                    suggested_value=int(new_timeout),
                    reason=f"Taxa de timeout alta ({timeout_rate:.1f}%)",
                    confidence=min(0.9, timeout_rate / 100 + 0.5),
                    auto_apply=timeout_rate > 30
                ))
        elif timeout_rate < 5 and analysis.avg_duration_ms > 8000:
            # Poucos timeouts mas duração alta - pode reduzir timeout
            new_timeout = max(current_timeout * 0.8, self.SCRAPER_LIMITS["timeout"][0])
            if new_timeout != current_timeout:
                suggestions.append(ConfigSuggestion(
                    module="scraper",
                    config_key="session_timeout",
                    current_value=current_timeout,
                    suggested_value=int(new_timeout),
                    reason="Duração alta com poucos timeouts - pode otimizar",
                    confidence=0.6,
                    auto_apply=False
                ))
        
        # Analisar chunk_size baseado em empty_content
        empty_rate = analysis.failure_rate_by_type.get("empty_content", 0)
        current_chunk = current_config.get("chunk_size", 20)
        
        if empty_rate > 30:
            # Muitos vazios - reduzir chunk para processar menos URLs por vez
            new_chunk = max(current_chunk - 5, self.SCRAPER_LIMITS["chunk_size"][0])
            if new_chunk != current_chunk:
                suggestions.append(ConfigSuggestion(
                    module="scraper",
                    config_key="chunk_size",
                    current_value=current_chunk,
                    suggested_value=new_chunk,
                    reason=f"Taxa alta de conteúdo vazio ({empty_rate:.1f}%)",
                    confidence=0.7,
                    auto_apply=False
                ))
        
        # Analisar circuit breaker baseado em proteções
        protection_failures = sum(
            analysis.failure_rate_by_type.get(t, 0)
            for t in ["cloudflare", "waf", "captcha"]
        )
        current_cb = current_config.get("circuit_breaker_threshold", 5)
        
        if protection_failures > 40:
            # Muitas proteções - aumentar threshold do circuit breaker
            new_cb = min(current_cb + 3, 15)
            if new_cb != current_cb:
                suggestions.append(ConfigSuggestion(
                    module="scraper",
                    config_key="circuit_breaker_threshold",
                    current_value=current_cb,
                    suggested_value=new_cb,
                    reason=f"Muitas proteções detectadas ({protection_failures:.1f}%)",
                    confidence=0.8,
                    auto_apply=protection_failures > 50
                ))
        
        return suggestions
    
    def suggest_llm_config(
        self,
        current_config: Dict[str, Any],
        period_hours: int = 24
    ) -> List[ConfigSuggestion]:
        """
        Sugere otimizações para configuração do LLM.
        
        Args:
            current_config: Configuração atual do LLM
            period_hours: Período de análise
        
        Returns:
            Lista de sugestões
        """
        suggestions = []
        analysis = self.pattern_analyzer.analyze_llm_failures(period_hours)
        
        if analysis.total_failures == 0:
            return suggestions
        
        # Analisar rate limits
        if analysis.total_failures > 0:
            rate_limit_pct = (analysis.rate_limit_count / analysis.total_failures) * 100
            current_concurrent = current_config.get("max_concurrent", 50)
            
            if rate_limit_pct > 25:
                # Muitos rate limits - reduzir concorrência
                new_concurrent = max(
                    int(current_concurrent * 0.7),
                    self.LLM_LIMITS["max_concurrent"][0]
                )
                if new_concurrent != current_concurrent:
                    suggestions.append(ConfigSuggestion(
                        module="llm",
                        config_key="max_concurrent",
                        current_value=current_concurrent,
                        suggested_value=new_concurrent,
                        reason=f"Taxa alta de rate limit ({rate_limit_pct:.1f}%)",
                        confidence=min(0.9, rate_limit_pct / 100 + 0.5),
                        auto_apply=rate_limit_pct > 35
                    ))
        
        # Analisar timeouts LLM
        if analysis.total_failures > 0:
            timeout_pct = (analysis.timeout_count / analysis.total_failures) * 100
            current_timeout = current_config.get("timeout", 60)
            
            if timeout_pct > 20:
                # Muitos timeouts - aumentar timeout
                new_timeout = min(
                    int(current_timeout * 1.5),
                    self.LLM_LIMITS["timeout"][1]
                )
                if new_timeout != current_timeout:
                    suggestions.append(ConfigSuggestion(
                        module="llm",
                        config_key="timeout",
                        current_value=current_timeout,
                        suggested_value=new_timeout,
                        reason=f"Taxa alta de timeout LLM ({timeout_pct:.1f}%)",
                        confidence=min(0.85, timeout_pct / 100 + 0.5),
                        auto_apply=timeout_pct > 30
                    ))
        
        # Analisar erros de parse - pode indicar chunk muito grande
        if analysis.total_failures > 0:
            parse_pct = (analysis.parse_error_count / analysis.total_failures) * 100
            current_chunk_tokens = current_config.get("max_chunk_tokens", 500000)
            
            if parse_pct > 15:
                # Muitos erros de parse - reduzir tamanho do chunk
                new_chunk_tokens = max(
                    int(current_chunk_tokens * 0.8),
                    self.LLM_LIMITS["max_chunk_tokens"][0]
                )
                if new_chunk_tokens != current_chunk_tokens:
                    suggestions.append(ConfigSuggestion(
                        module="llm",
                        config_key="max_chunk_tokens",
                        current_value=current_chunk_tokens,
                        suggested_value=new_chunk_tokens,
                        reason=f"Taxa alta de erros de parse ({parse_pct:.1f}%)",
                        confidence=0.7,
                        auto_apply=False
                    ))
        
        return suggestions
    
    def get_all_suggestions(
        self,
        scraper_config: Dict[str, Any],
        llm_config: Dict[str, Any],
        period_hours: int = 24
    ) -> List[ConfigSuggestion]:
        """
        Retorna todas as sugestões ordenadas por confiança.
        
        Args:
            scraper_config: Configuração atual do scraper
            llm_config: Configuração atual do LLM
            period_hours: Período de análise
        
        Returns:
            Lista de sugestões ordenadas
        """
        scraper_suggestions = self.suggest_scraper_config(scraper_config, period_hours)
        llm_suggestions = self.suggest_llm_config(llm_config, period_hours)
        
        all_suggestions = scraper_suggestions + llm_suggestions
        return sorted(all_suggestions, key=lambda s: s.confidence, reverse=True)
    
    def apply_suggestion(
        self,
        suggestion: ConfigSuggestion,
        apply_func: Callable[[str, str, Any], bool]
    ) -> bool:
        """
        Aplica uma sugestão de configuração.
        
        Args:
            suggestion: Sugestão a aplicar
            apply_func: Função que aplica a configuração (module, key, value) -> success
        
        Returns:
            True se aplicado com sucesso
        """
        try:
            success = apply_func(
                suggestion.module,
                suggestion.config_key,
                suggestion.suggested_value
            )
            
            if success:
                self._applied_suggestions.append(suggestion)
                logger.info(
                    f"ConfigOptimizer: Aplicada sugestão {suggestion.module}.{suggestion.config_key} "
                    f"= {suggestion.suggested_value}"
                )
            
            return success
        except Exception as e:
            logger.error(f"ConfigOptimizer: Erro ao aplicar sugestão: {e}")
            return False
    
    def apply_auto_suggestions(
        self,
        scraper_config: Dict[str, Any],
        llm_config: Dict[str, Any],
        apply_func: Callable[[str, str, Any], bool],
        period_hours: int = 24
    ) -> List[ConfigSuggestion]:
        """
        Aplica automaticamente sugestões marcadas como auto_apply.
        
        Args:
            scraper_config: Configuração atual do scraper
            llm_config: Configuração atual do LLM
            apply_func: Função para aplicar configuração
            period_hours: Período de análise
        
        Returns:
            Lista de sugestões aplicadas
        """
        applied = []
        suggestions = self.get_all_suggestions(scraper_config, llm_config, period_hours)
        
        for suggestion in suggestions:
            if suggestion.auto_apply and suggestion.confidence >= 0.8:
                if self.apply_suggestion(suggestion, apply_func):
                    applied.append(suggestion)
        
        return applied
    
    def get_applied_suggestions(self) -> List[ConfigSuggestion]:
        """Retorna lista de sugestões já aplicadas."""
        return self._applied_suggestions.copy()
    
    def get_summary(
        self,
        scraper_config: Dict[str, Any],
        llm_config: Dict[str, Any],
        period_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Retorna resumo das sugestões.
        
        Args:
            scraper_config: Configuração atual do scraper
            llm_config: Configuração atual do LLM
            period_hours: Período de análise
        
        Returns:
            Dict com resumo
        """
        suggestions = self.get_all_suggestions(scraper_config, llm_config, period_hours)
        
        return {
            "total_suggestions": len(suggestions),
            "auto_apply_count": sum(1 for s in suggestions if s.auto_apply),
            "high_confidence_count": sum(1 for s in suggestions if s.confidence >= 0.8),
            "by_module": {
                "scraper": sum(1 for s in suggestions if s.module == "scraper"),
                "llm": sum(1 for s in suggestions if s.module == "llm")
            },
            "applied_count": len(self._applied_suggestions)
        }


# Instância singleton
def create_config_optimizer():
    from .pattern_analyzer import pattern_analyzer
    return ConfigOptimizer(pattern_analyzer)

config_optimizer = create_config_optimizer()

