"""
Analisador de Testes com LLM - Fase 6

Analisa logs de testes e usa LLM para sugerir otimizações de parâmetros.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TestAnalysisRequest:
    """Dados para análise de teste."""
    test_id: str
    timestamp: str
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    error_distribution: Dict[str, int]
    sample_failures: List[Dict[str, Any]]
    sample_successes: List[Dict[str, Any]]


@dataclass
class ParameterSuggestion:
    """Sugestão de parâmetro."""
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float
    expected_impact: str


@dataclass
class TestAnalysisResult:
    """Resultado da análise de teste."""
    test_id: str
    analysis_timestamp: str
    overall_assessment: str
    bottlenecks: List[str]
    suggestions: List[ParameterSuggestion]
    priority_actions: List[str]
    estimated_improvement: str


class TestAnalyzer:
    """
    Analisador de testes que usa LLM para sugerir otimizações.
    """
    
    ANALYSIS_PROMPT = """Você é um especialista em otimização de sistemas de web scraping e processamento de dados.

Analise os seguintes resultados de teste e forneça recomendações de otimização.

## DADOS DO TESTE

**Configuração:**
- Empresas processadas: {total_empresas}
- Concorrência máxima: {max_concurrent}
- Timeout por empresa: {timeout}s

**Métricas:**
- Taxa de sucesso: {taxa_sucesso:.1f}%
- Tempo médio (sucessos): {tempo_medio:.1f}s
- Tempo mínimo: {tempo_min:.1f}s
- Tempo máximo: {tempo_max:.1f}s
- Completude média: {completude:.1f}%

**Resultados por etapa:**
- Discovery: {discovery_sucesso}/{total_empresas} ({discovery_pct:.1f}%)
- Scrape: {scrape_sucesso}/{total_empresas} ({scrape_pct:.1f}%)
- LLM: {llm_sucesso}/{total_empresas} ({llm_pct:.1f}%)

**Distribuição de erros:**
{error_distribution}

**Exemplos de falhas:**
{sample_failures}

**Exemplos de sucessos:**
{sample_successes}

## PARÂMETROS ATUAIS DO SISTEMA

```json
{current_params}
```

## TAREFA

Analise os dados e forneça:

1. **AVALIAÇÃO GERAL**: Uma frase resumindo o estado atual do sistema
2. **GARGALOS**: Liste os principais gargalos identificados (máximo 3)
3. **SUGESTÕES DE PARÂMETROS**: Para cada parâmetro que deve ser ajustado:
   - Nome do parâmetro
   - Valor atual
   - Valor sugerido
   - Razão da mudança
   - Confiança (0-100%)
   - Impacto esperado

4. **AÇÕES PRIORITÁRIAS**: Liste as 3 ações mais importantes a tomar

Responda APENAS em JSON válido no formato:
```json
{{
  "overall_assessment": "string",
  "bottlenecks": ["string", "string"],
  "suggestions": [
    {{
      "parameter": "nome_do_parametro",
      "current_value": valor_atual,
      "suggested_value": valor_sugerido,
      "reason": "razão",
      "confidence": 0.85,
      "expected_impact": "impacto esperado"
    }}
  ],
  "priority_actions": ["ação 1", "ação 2", "ação 3"],
  "estimated_improvement": "estimativa de melhoria geral"
}}
```"""

    def __init__(self, reports_dir: str = "tests/reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_history: List[TestAnalysisResult] = []
    
    def save_detailed_log(
        self,
        test_id: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Salva log detalhado do teste para análise futura.
        
        Returns:
            Caminho do arquivo salvo
        """
        log_data = {
            "test_id": test_id,
            "timestamp": datetime.utcnow().isoformat(),
            "config": config,
            "metrics": metrics,
            "results": results,
            "error_analysis": self._analyze_errors(results),
            "timing_analysis": self._analyze_timing(results),
            "stage_analysis": self._analyze_stages(results)
        }
        
        filename = f"test_log_{test_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"TestAnalyzer: Log detalhado salvo em {filepath}")
        return str(filepath)
    
    def _analyze_errors(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Análise detalhada de erros."""
        errors = {}
        error_by_stage = {"discovery": 0, "scrape": 0, "llm": 0, "timeout": 0}
        
        for r in results:
            if not r.get("success") and r.get("error"):
                err = r["error"]
                errors[err] = errors.get(err, 0) + 1
                
                if "Discovery" in err:
                    error_by_stage["discovery"] += 1
                elif "Scrape" in err:
                    error_by_stage["scrape"] += 1
                elif "LLM" in err:
                    error_by_stage["llm"] += 1
                elif "Timeout" in err or "timeout" in err.lower():
                    error_by_stage["timeout"] += 1
        
        return {
            "total_errors": len([r for r in results if not r.get("success")]),
            "unique_errors": len(errors),
            "error_counts": errors,
            "errors_by_stage": error_by_stage
        }
    
    def _analyze_timing(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Análise de tempos."""
        success_times = [r["duration_seconds"] for r in results if r.get("success")]
        all_times = [r["duration_seconds"] for r in results]
        
        if not success_times:
            return {"no_successes": True}
        
        return {
            "success_avg": sum(success_times) / len(success_times),
            "success_min": min(success_times),
            "success_max": max(success_times),
            "success_median": sorted(success_times)[len(success_times)//2],
            "all_avg": sum(all_times) / len(all_times),
            "under_30s": len([t for t in success_times if t < 30]),
            "under_60s": len([t for t in success_times if t < 60]),
            "under_90s": len([t for t in success_times if t < 90]),
            "over_90s": len([t for t in all_times if t >= 90])
        }
    
    def _analyze_stages(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Análise por estágio."""
        total = len(results)
        discovery_ok = sum(1 for r in results if r.get("discovery_url"))
        scrape_ok = sum(1 for r in results if r.get("scrape_chars", 0) > 100)
        llm_ok = sum(1 for r in results if r.get("success"))
        
        return {
            "total": total,
            "discovery": {"success": discovery_ok, "rate": discovery_ok/total*100 if total else 0},
            "scrape": {"success": scrape_ok, "rate": scrape_ok/total*100 if total else 0},
            "llm": {"success": llm_ok, "rate": llm_ok/total*100 if total else 0},
            "conversion_funnel": {
                "discovery_to_scrape": scrape_ok/discovery_ok*100 if discovery_ok else 0,
                "scrape_to_llm": llm_ok/scrape_ok*100 if scrape_ok else 0
            }
        }
    
    async def analyze_with_llm(
        self,
        test_log_path: str,
        current_params: Dict[str, Any] = None
    ) -> TestAnalysisResult:
        """
        Analisa um teste usando LLM e retorna sugestões.
        
        Args:
            test_log_path: Caminho do arquivo de log
            current_params: Parâmetros atuais do sistema
        
        Returns:
            TestAnalysisResult com sugestões
        """
        # Carregar log
        with open(test_log_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        # Preparar dados para o prompt
        metrics = log_data.get("metrics", {})
        config = log_data.get("config", {})
        error_analysis = log_data.get("error_analysis", {})
        results = log_data.get("results", [])
        
        # Parâmetros atuais do sistema
        if current_params is None:
            current_params = self._get_current_system_params()
        
        # Amostras de falhas e sucessos
        failures = [r for r in results if not r.get("success")][:5]
        successes = [r for r in results if r.get("success")][:5]
        
        # Formatar prompt
        prompt = self.ANALYSIS_PROMPT.format(
            total_empresas=config.get("total_empresas", metrics.get("total_processadas", 0)),
            max_concurrent=config.get("max_concurrent", "N/A"),
            timeout=config.get("timeout_per_empresa", 90),
            taxa_sucesso=metrics.get("taxa_sucesso", 0),
            tempo_medio=metrics.get("tempo_medio_segundos", 0),
            tempo_min=metrics.get("tempo_minimo_segundos", 0),
            tempo_max=metrics.get("tempo_maximo_segundos", 0),
            completude=metrics.get("completude_media", 0),
            discovery_sucesso=metrics.get("discovery_sucesso", 0),
            discovery_pct=metrics.get("discovery_sucesso", 0) / max(metrics.get("total_processadas", 1), 1) * 100,
            scrape_sucesso=metrics.get("scrape_sucesso", 0),
            scrape_pct=metrics.get("scrape_sucesso", 0) / max(metrics.get("total_processadas", 1), 1) * 100,
            llm_sucesso=metrics.get("llm_sucesso", 0),
            llm_pct=metrics.get("llm_sucesso", 0) / max(metrics.get("total_processadas", 1), 1) * 100,
            error_distribution=json.dumps(error_analysis.get("error_counts", {}), indent=2),
            sample_failures=json.dumps([{
                "empresa": f.get("empresa", {}).get("nome_fantasia", "N/A"),
                "erro": f.get("error", "N/A"),
                "tempo": f.get("duration_seconds", 0)
            } for f in failures], indent=2),
            sample_successes=json.dumps([{
                "empresa": s.get("empresa", {}).get("nome_fantasia", "N/A"),
                "tempo": s.get("duration_seconds", 0),
                "completude": s.get("profile_completeness", 0)
            } for s in successes], indent=2),
            current_params=json.dumps(current_params, indent=2)
        )
        
        # Chamar LLM usando OpenAI API diretamente
        import httpx
        import os
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY não configurada")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "gpt-4.1-nano",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3
                    }
                )
                resp.raise_for_status()
                response = resp.json()["choices"][0]["message"]["content"]
            
            # Parse resposta
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            import json_repair
            analysis_data = json_repair.loads(content)
            
            # Criar resultado
            result = TestAnalysisResult(
                test_id=log_data.get("test_id", "unknown"),
                analysis_timestamp=datetime.utcnow().isoformat(),
                overall_assessment=analysis_data.get("overall_assessment", ""),
                bottlenecks=analysis_data.get("bottlenecks", []),
                suggestions=[
                    ParameterSuggestion(**s) for s in analysis_data.get("suggestions", [])
                ],
                priority_actions=analysis_data.get("priority_actions", []),
                estimated_improvement=analysis_data.get("estimated_improvement", "")
            )
            
            # Salvar análise
            self._save_analysis(result)
            self.analysis_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"TestAnalyzer: Erro na análise LLM: {e}")
            return TestAnalysisResult(
                test_id=log_data.get("test_id", "unknown"),
                analysis_timestamp=datetime.utcnow().isoformat(),
                overall_assessment=f"Erro na análise: {e}",
                bottlenecks=[],
                suggestions=[],
                priority_actions=[],
                estimated_improvement=""
            )
    
    def _get_current_system_params(self) -> Dict[str, Any]:
        """Obtém parâmetros atuais do sistema."""
        try:
            from app.services.scraper.constants import scraper_config
            from app.services.llm.constants import llm_config
            
            return {
                "scraper": {
                    "session_timeout": scraper_config.session_timeout,
                    "chunk_size": scraper_config.chunk_size,
                    "max_subpages": scraper_config.max_subpages,
                    "circuit_breaker_threshold": scraper_config.circuit_breaker_threshold,
                    "default_strategy": scraper_config.default_strategy
                },
                "llm": {
                    "max_concurrent_requests": llm_config.max_concurrent_requests,
                    "default_timeout": llm_config.default_timeout,
                    "max_chunk_tokens": llm_config.max_chunk_tokens
                }
            }
        except:
            return {"error": "Não foi possível carregar parâmetros"}
    
    def _save_analysis(self, result: TestAnalysisResult):
        """Salva resultado da análise."""
        filename = f"analysis_{result.test_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        
        logger.info(f"TestAnalyzer: Análise salva em {filepath}")
    
    async def apply_suggestions_to_learning_engine(
        self,
        analysis: TestAnalysisResult
    ) -> Dict[str, Any]:
        """
        Aplica sugestões ao Learning Engine.
        
        Args:
            analysis: Resultado da análise com sugestões
        
        Returns:
            Dict com status das aplicações
        """
        from app.services.learning import adaptive_config_manager
        
        applied = []
        skipped = []
        
        for suggestion in analysis.suggestions:
            if suggestion.confidence >= 0.7:
                try:
                    # Determinar módulo
                    if "scraper" in suggestion.parameter.lower() or suggestion.parameter in [
                        "session_timeout", "chunk_size", "circuit_breaker_threshold"
                    ]:
                        module = "scraper"
                    else:
                        module = "llm"
                    
                    # Aplicar via adaptive_config_manager
                    success = adaptive_config_manager._apply_single_suggestion(
                        module, 
                        suggestion.parameter, 
                        suggestion.suggested_value
                    )
                    
                    if success:
                        applied.append({
                            "parameter": suggestion.parameter,
                            "old_value": suggestion.current_value,
                            "new_value": suggestion.suggested_value,
                            "reason": suggestion.reason
                        })
                    else:
                        skipped.append({
                            "parameter": suggestion.parameter,
                            "reason": "Falha ao aplicar"
                        })
                        
                except Exception as e:
                    skipped.append({
                        "parameter": suggestion.parameter,
                        "reason": str(e)
                    })
            else:
                skipped.append({
                    "parameter": suggestion.parameter,
                    "reason": f"Confiança baixa ({suggestion.confidence:.0%})"
                })
        
        return {
            "applied": applied,
            "skipped": skipped,
            "total_applied": len(applied),
            "total_skipped": len(skipped)
        }
    
    def print_analysis(self, result: TestAnalysisResult):
        """Imprime análise formatada."""
        print("\n" + "="*60)
        print("📊 ANÁLISE DO TESTE COM IA")
        print("="*60)
        print(f"\n📋 Avaliação Geral: {result.overall_assessment}")
        
        if result.bottlenecks:
            print("\n🚧 Gargalos Identificados:")
            for i, b in enumerate(result.bottlenecks, 1):
                print(f"   {i}. {b}")
        
        if result.suggestions:
            print("\n💡 Sugestões de Parâmetros:")
            for s in result.suggestions:
                print(f"\n   📌 {s.parameter}")
                print(f"      Atual: {s.current_value} → Sugerido: {s.suggested_value}")
                print(f"      Razão: {s.reason}")
                print(f"      Confiança: {s.confidence:.0%} | Impacto: {s.expected_impact}")
        
        if result.priority_actions:
            print("\n🎯 Ações Prioritárias:")
            for i, a in enumerate(result.priority_actions, 1):
                print(f"   {i}. {a}")
        
        print(f"\n📈 Melhoria Estimada: {result.estimated_improvement}")
        print("="*60 + "\n")


# Instância singleton
test_analyzer = TestAnalyzer()


async def analyze_last_test():
    """Analisa o último teste executado."""
    reports_dir = Path("tests/reports")
    
    # Encontrar último relatório
    reports = list(reports_dir.glob("parallel_test_report.json"))
    if not reports:
        print("Nenhum relatório encontrado")
        return
    
    latest = max(reports, key=lambda p: p.stat().st_mtime)
    print(f"Analisando: {latest}")
    
    # Carregar e salvar log detalhado
    with open(latest) as f:
        data = json.load(f)
    
    test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_path = test_analyzer.save_detailed_log(
        test_id=test_id,
        config=data.get("config", {}),
        metrics=data.get("metrics", {}),
        results=data.get("results", [])
    )
    
    # Analisar com LLM
    print("Analisando com LLM...")
    result = await test_analyzer.analyze_with_llm(log_path)
    
    # Mostrar resultados
    test_analyzer.print_analysis(result)
    
    return result


if __name__ == "__main__":
    asyncio.run(analyze_last_test())

