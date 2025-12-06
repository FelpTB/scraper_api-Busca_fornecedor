"""
Pattern Analyzer - Analisa padrões de falhas e gera recomendações.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from collections import defaultdict
from datetime import datetime

from .failure_tracker import FailureTracker, FailureModule, FailureType

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """Recomendação de otimização."""
    priority: int  # 1 = Alta, 2 = Média, 3 = Baixa
    module: str
    title: str
    description: str
    action: str
    impact: str


@dataclass
class ScraperAnalysis:
    """Análise de falhas do scraper."""
    total_failures: int = 0
    cloudflare_sites: List[str] = field(default_factory=list)
    waf_sites: List[str] = field(default_factory=list)
    captcha_sites: List[str] = field(default_factory=list)
    timeout_sites: List[str] = field(default_factory=list)
    empty_content_sites: List[str] = field(default_factory=list)
    best_strategy_by_site: Dict[str, str] = field(default_factory=dict)
    failure_rate_by_type: Dict[str, float] = field(default_factory=dict)
    avg_duration_ms: float = 0.0
    recommendations: List[Recommendation] = field(default_factory=list)


@dataclass
class LLMAnalysis:
    """Análise de falhas do LLM."""
    total_failures: int = 0
    rate_limit_count: int = 0
    timeout_count: int = 0
    parse_error_count: int = 0
    provider_failures: Dict[str, int] = field(default_factory=dict)
    avg_duration_ms: float = 0.0
    peak_failure_hours: List[int] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)


class PatternAnalyzer:
    """
    Analisador de padrões de falha.
    
    Identifica tendências e gera recomendações de otimização.
    """
    
    def __init__(self, failure_tracker: FailureTracker):
        self.failure_tracker = failure_tracker
    
    def analyze_scraper_failures(self, period_hours: int = 24) -> ScraperAnalysis:
        """
        Analisa falhas do scraper e identifica padrões.
        
        Args:
            period_hours: Período de análise em horas
        
        Returns:
            ScraperAnalysis com dados e recomendações
        """
        analysis = ScraperAnalysis()
        
        failures = self.failure_tracker.get_by_module(FailureModule.SCRAPER)
        
        if not failures:
            return analysis
        
        # Filtrar por período
        cutoff = datetime.utcnow().timestamp() - (period_hours * 3600)
        failures = [
            f for f in failures
            if datetime.fromisoformat(f.timestamp).timestamp() >= cutoff
        ]
        
        analysis.total_failures = len(failures)
        
        if not failures:
            return analysis
        
        # Categorizar por tipo de erro
        type_counts = defaultdict(int)
        domain_errors = defaultdict(lambda: defaultdict(int))
        durations = []
        
        for f in failures:
            type_counts[f.error_type] += 1
            domain_errors[f.domain][f.error_type] += 1
            
            if f.duration_ms > 0:
                durations.append(f.duration_ms)
            
            # Classificar sites por proteção
            if f.error_type == FailureType.CLOUDFLARE.value:
                if f.domain not in analysis.cloudflare_sites:
                    analysis.cloudflare_sites.append(f.domain)
            elif f.error_type == FailureType.WAF.value:
                if f.domain not in analysis.waf_sites:
                    analysis.waf_sites.append(f.domain)
            elif f.error_type == FailureType.CAPTCHA.value:
                if f.domain not in analysis.captcha_sites:
                    analysis.captcha_sites.append(f.domain)
            elif f.error_type == FailureType.TIMEOUT.value:
                if f.domain not in analysis.timeout_sites:
                    analysis.timeout_sites.append(f.domain)
            elif f.error_type == FailureType.EMPTY_CONTENT.value:
                if f.domain not in analysis.empty_content_sites:
                    analysis.empty_content_sites.append(f.domain)
        
        # Calcular taxas
        total = sum(type_counts.values())
        analysis.failure_rate_by_type = {
            k: (v / total) * 100 for k, v in type_counts.items()
        }
        
        # Média de duração
        if durations:
            analysis.avg_duration_ms = sum(durations) / len(durations)
        
        # Determinar melhor estratégia por site
        for domain, errors in domain_errors.items():
            # Se site tem muitos erros de proteção, recomendar estratégia agressiva
            protection_errors = sum(
                errors.get(t.value, 0) 
                for t in [FailureType.CLOUDFLARE, FailureType.WAF, FailureType.CAPTCHA]
            )
            total_domain_errors = sum(errors.values())
            
            if protection_errors > total_domain_errors * 0.5:
                analysis.best_strategy_by_site[domain] = "aggressive"
            elif errors.get(FailureType.TIMEOUT.value, 0) > total_domain_errors * 0.5:
                analysis.best_strategy_by_site[domain] = "robust"
            else:
                analysis.best_strategy_by_site[domain] = "standard"
        
        # Gerar recomendações
        analysis.recommendations = self._generate_scraper_recommendations(analysis)
        
        return analysis
    
    def analyze_llm_failures(self, period_hours: int = 24) -> LLMAnalysis:
        """
        Analisa falhas do LLM e identifica padrões.
        
        Args:
            period_hours: Período de análise em horas
        
        Returns:
            LLMAnalysis com dados e recomendações
        """
        analysis = LLMAnalysis()
        
        failures = self.failure_tracker.get_by_module(FailureModule.LLM)
        
        if not failures:
            return analysis
        
        # Filtrar por período
        cutoff = datetime.utcnow().timestamp() - (period_hours * 3600)
        failures = [
            f for f in failures
            if datetime.fromisoformat(f.timestamp).timestamp() >= cutoff
        ]
        
        analysis.total_failures = len(failures)
        
        if not failures:
            return analysis
        
        # Categorizar
        durations = []
        hour_counts = defaultdict(int)
        
        for f in failures:
            if f.error_type == FailureType.LLM_RATE_LIMIT.value:
                analysis.rate_limit_count += 1
            elif f.error_type == FailureType.LLM_TIMEOUT.value:
                analysis.timeout_count += 1
            elif f.error_type == FailureType.LLM_PARSE_ERROR.value:
                analysis.parse_error_count += 1
            
            # Contar por provider
            provider = f.context.get("provider", "unknown")
            analysis.provider_failures[provider] = analysis.provider_failures.get(provider, 0) + 1
            
            if f.duration_ms > 0:
                durations.append(f.duration_ms)
            
            # Contar por hora
            try:
                hour = datetime.fromisoformat(f.timestamp).hour
                hour_counts[hour] += 1
            except:
                pass
        
        # Média de duração
        if durations:
            analysis.avg_duration_ms = sum(durations) / len(durations)
        
        # Horas de pico
        if hour_counts:
            avg_per_hour = sum(hour_counts.values()) / len(hour_counts)
            analysis.peak_failure_hours = [
                h for h, c in hour_counts.items() if c > avg_per_hour * 1.5
            ]
        
        # Gerar recomendações
        analysis.recommendations = self._generate_llm_recommendations(analysis)
        
        return analysis
    
    def _generate_scraper_recommendations(self, analysis: ScraperAnalysis) -> List[Recommendation]:
        """Gera recomendações baseadas na análise do scraper."""
        recommendations = []
        
        # Alta taxa de Cloudflare
        cf_rate = analysis.failure_rate_by_type.get(FailureType.CLOUDFLARE.value, 0)
        if cf_rate > 20:
            recommendations.append(Recommendation(
                priority=1,
                module="scraper",
                title="Alta taxa de bloqueio Cloudflare",
                description=f"{cf_rate:.1f}% das falhas são bloqueios Cloudflare",
                action="Usar estratégia AGGRESSIVE como padrão para sites conhecidos",
                impact=f"Pode melhorar sucesso em {len(analysis.cloudflare_sites)} sites"
            ))
        
        # Alta taxa de timeout
        timeout_rate = analysis.failure_rate_by_type.get(FailureType.TIMEOUT.value, 0)
        if timeout_rate > 15:
            recommendations.append(Recommendation(
                priority=1,
                module="scraper",
                title="Alta taxa de timeout",
                description=f"{timeout_rate:.1f}% das falhas são timeouts",
                action="Aumentar timeout padrão ou usar timeout adaptativo",
                impact=f"Pode melhorar sucesso em {len(analysis.timeout_sites)} sites"
            ))
        
        # Muitos sites com conteúdo vazio
        empty_rate = analysis.failure_rate_by_type.get(FailureType.EMPTY_CONTENT.value, 0)
        if empty_rate > 25:
            recommendations.append(Recommendation(
                priority=2,
                module="scraper",
                title="Alta taxa de conteúdo vazio",
                description=f"{empty_rate:.1f}% das falhas são conteúdo vazio",
                action="Revisar seleção de links e validação de conteúdo",
                impact="Melhorar qualidade do conteúdo extraído"
            ))
        
        # Duração média alta
        if analysis.avg_duration_ms > 10000:
            recommendations.append(Recommendation(
                priority=2,
                module="scraper",
                title="Tempo médio de scrape alto",
                description=f"Média de {analysis.avg_duration_ms/1000:.1f}s por falha",
                action="Reduzir timeout ou melhorar seleção de estratégia",
                impact="Reduzir tempo total de processamento"
            ))
        
        return recommendations
    
    def _generate_llm_recommendations(self, analysis: LLMAnalysis) -> List[Recommendation]:
        """Gera recomendações baseadas na análise do LLM."""
        recommendations = []
        
        # Alta taxa de rate limit
        if analysis.total_failures > 0:
            rate_limit_pct = (analysis.rate_limit_count / analysis.total_failures) * 100
            if rate_limit_pct > 20:
                recommendations.append(Recommendation(
                    priority=1,
                    module="llm",
                    title="Alta taxa de rate limit",
                    description=f"{rate_limit_pct:.1f}% das falhas são rate limits",
                    action="Reduzir concorrência ou adicionar mais providers",
                    impact="Melhorar estabilidade e throughput"
                ))
        
        # Alta taxa de timeout
        if analysis.total_failures > 0:
            timeout_pct = (analysis.timeout_count / analysis.total_failures) * 100
            if timeout_pct > 15:
                recommendations.append(Recommendation(
                    priority=1,
                    module="llm",
                    title="Alta taxa de timeout LLM",
                    description=f"{timeout_pct:.1f}% das falhas são timeouts",
                    action="Aumentar timeout ou reduzir tamanho do chunk",
                    impact="Reduzir falhas por timeout"
                ))
        
        # Provider com muitas falhas
        for provider, count in analysis.provider_failures.items():
            if analysis.total_failures > 0:
                provider_pct = (count / analysis.total_failures) * 100
                if provider_pct > 50:
                    recommendations.append(Recommendation(
                        priority=2,
                        module="llm",
                        title=f"Provider {provider} com muitas falhas",
                        description=f"{provider_pct:.1f}% das falhas são deste provider",
                        action=f"Verificar configuração de {provider} ou reduzir prioridade",
                        impact="Melhorar distribuição de carga"
                    ))
        
        # Horários de pico
        if analysis.peak_failure_hours:
            hours_str = ", ".join(f"{h}h" for h in analysis.peak_failure_hours)
            recommendations.append(Recommendation(
                priority=3,
                module="llm",
                title="Picos de falha em horários específicos",
                description=f"Mais falhas nos horários: {hours_str}",
                action="Considerar ajustar concorrência nesses horários",
                impact="Melhorar estabilidade em horários de pico"
            ))
        
        return recommendations
    
    def get_all_recommendations(self, period_hours: int = 24) -> List[Recommendation]:
        """
        Retorna todas as recomendações ordenadas por prioridade.
        
        Args:
            period_hours: Período de análise em horas
        
        Returns:
            Lista de recomendações ordenadas
        """
        scraper_analysis = self.analyze_scraper_failures(period_hours)
        llm_analysis = self.analyze_llm_failures(period_hours)
        
        all_recs = scraper_analysis.recommendations + llm_analysis.recommendations
        return sorted(all_recs, key=lambda r: r.priority)
    
    def get_summary(self, period_hours: int = 24) -> Dict[str, Any]:
        """
        Retorna resumo da análise de padrões.
        
        Args:
            period_hours: Período de análise em horas
        
        Returns:
            Dict com resumo
        """
        scraper = self.analyze_scraper_failures(period_hours)
        llm = self.analyze_llm_failures(period_hours)
        recs = self.get_all_recommendations(period_hours)
        
        return {
            "period_hours": period_hours,
            "scraper": {
                "total_failures": scraper.total_failures,
                "cloudflare_sites": len(scraper.cloudflare_sites),
                "timeout_sites": len(scraper.timeout_sites),
                "avg_duration_ms": scraper.avg_duration_ms
            },
            "llm": {
                "total_failures": llm.total_failures,
                "rate_limit_count": llm.rate_limit_count,
                "timeout_count": llm.timeout_count,
                "provider_failures": llm.provider_failures
            },
            "recommendations_count": len(recs),
            "high_priority_count": sum(1 for r in recs if r.priority == 1)
        }


# Instância singleton (importa failure_tracker para criar)
def create_pattern_analyzer():
    from .failure_tracker import failure_tracker
    return PatternAnalyzer(failure_tracker)

pattern_analyzer = create_pattern_analyzer()

