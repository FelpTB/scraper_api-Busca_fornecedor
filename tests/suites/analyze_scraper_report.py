"""
Analisador de Relatórios do Teste de Scraping.

Gera análises detalhadas para identificar:
- Gargalos por etapa e subetapa
- Padrões de falha
- Subetapas que devem ser otimizadas, removidas ou melhoradas
- Correlação entre tipo de site/proteção e tempo
"""

import sys
from pathlib import Path
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@dataclass
class SubstepAnalysis:
    """Análise de uma subetapa."""
    name: str
    count: int = 0
    total_time_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    errors: Dict[str, int] = field(default_factory=dict)
    
    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.count if self.count > 0 else 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total * 100 if total > 0 else 0


@dataclass
class StepAnalysis:
    """Análise de uma etapa."""
    name: str
    step_number: int
    count: int = 0
    total_time_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    substeps: Dict[str, SubstepAnalysis] = field(default_factory=dict)
    
    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.count if self.count > 0 else 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total * 100 if total > 0 else 0


class ScraperReportAnalyzer:
    """Analisador de relatórios de scraping."""
    
    def __init__(self, report_path: str = None):
        self.report_path = report_path
        self.data = {}
        self.steps_analysis: Dict[int, StepAnalysis] = {}
    
    def load_report(self):
        """Carrega o relatório mais recente se não especificado."""
        if not self.report_path:
            reports_dir = Path("tests/reports")
            scraper_files = sorted(
                reports_dir.glob("scraper_test_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if scraper_files:
                self.report_path = str(scraper_files[0])
            else:
                raise FileNotFoundError("Nenhum relatório de scraping encontrado")
        
        with open(self.report_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        print(f"📄 Relatório carregado: {self.report_path}")
        print(f"   Timestamp: {self.data.get('timestamp', 'N/A')}")
    
    def analyze_steps(self):
        """Analisa cada etapa e subetapa."""
        results = self.data.get('results', [])
        
        for result in results:
            for step in result.get('steps', []):
                step_num = step['step_number']
                step_name = step['name']
                
                # Inicializar análise de etapa se necessário
                if step_num not in self.steps_analysis:
                    self.steps_analysis[step_num] = StepAnalysis(
                        name=step_name,
                        step_number=step_num
                    )
                
                analysis = self.steps_analysis[step_num]
                analysis.count += 1
                analysis.total_time_ms += step['duration_ms']
                
                if step.get('success', True):
                    analysis.success_count += 1
                else:
                    analysis.failure_count += 1
                
                # Analisar subetapas
                for substep in step.get('substeps', []):
                    ss_name = substep['name']
                    
                    if ss_name not in analysis.substeps:
                        analysis.substeps[ss_name] = SubstepAnalysis(name=ss_name)
                    
                    ss_analysis = analysis.substeps[ss_name]
                    ss_analysis.count += 1
                    ss_analysis.total_time_ms += substep['duration_ms']
                    
                    if substep.get('success', True):
                        ss_analysis.success_count += 1
                    else:
                        ss_analysis.failure_count += 1
                        error = substep.get('error', 'Unknown')
                        if error:
                            ss_analysis.errors[error] = ss_analysis.errors.get(error, 0) + 1
    
    def analyze_by_site_type(self) -> Dict[str, Dict]:
        """Analisa métricas por tipo de site."""
        by_type = defaultdict(lambda: {
            'count': 0, 'success': 0, 'total_time': 0,
            'avg_content': 0, 'avg_pages': 0
        })
        
        results = self.data.get('results', [])
        
        for r in results:
            site_type = r.get('site_type', 'unknown')
            by_type[site_type]['count'] += 1
            if r.get('success'):
                by_type[site_type]['success'] += 1
                by_type[site_type]['total_time'] += r.get('total_time_ms', 0)
                by_type[site_type]['avg_content'] += r.get('content_length', 0)
                by_type[site_type]['avg_pages'] += r.get('pages_scraped', 0)
        
        # Calcular médias
        for site_type, data in by_type.items():
            if data['success'] > 0:
                data['avg_time'] = data['total_time'] / data['success']
                data['avg_content'] = data['avg_content'] / data['success']
                data['avg_pages'] = data['avg_pages'] / data['success']
            else:
                data['avg_time'] = 0
        
        return dict(by_type)
    
    def analyze_by_protection(self) -> Dict[str, Dict]:
        """Analisa métricas por tipo de proteção."""
        by_protection = defaultdict(lambda: {
            'count': 0, 'success': 0, 'total_time': 0,
            'strategies_used': defaultdict(int)
        })
        
        results = self.data.get('results', [])
        
        for r in results:
            protection = r.get('protection_type', 'unknown')
            by_protection[protection]['count'] += 1
            if r.get('success'):
                by_protection[protection]['success'] += 1
                by_protection[protection]['total_time'] += r.get('total_time_ms', 0)
            strategy = r.get('strategy_used', 'unknown')
            by_protection[protection]['strategies_used'][strategy] += 1
        
        # Calcular médias
        for protection, data in by_protection.items():
            if data['success'] > 0:
                data['avg_time'] = data['total_time'] / data['success']
            else:
                data['avg_time'] = 0
        
        return dict(by_protection)
    
    def find_bottlenecks(self) -> List[Dict]:
        """Identifica os principais gargalos."""
        bottlenecks = []
        
        # Ordenar etapas por tempo médio
        for step_num, analysis in sorted(
            self.steps_analysis.items(),
            key=lambda x: -x[1].avg_time_ms
        ):
            bottleneck = {
                'step': analysis.name,
                'step_number': step_num,
                'avg_time_ms': analysis.avg_time_ms,
                'success_rate': analysis.success_rate,
                'substeps': []
            }
            
            # Ordenar subetapas por tempo
            for ss_name, ss_analysis in sorted(
                analysis.substeps.items(),
                key=lambda x: -x[1].avg_time_ms
            ):
                if ss_analysis.count > 0:
                    bottleneck['substeps'].append({
                        'name': ss_name,
                        'avg_time_ms': ss_analysis.avg_time_ms,
                        'count': ss_analysis.count,
                        'success_rate': ss_analysis.success_rate,
                        'errors': dict(ss_analysis.errors)
                    })
            
            bottlenecks.append(bottleneck)
        
        return bottlenecks
    
    def find_optimization_candidates(self) -> Dict[str, List[Dict]]:
        """Identifica subetapas candidatas a otimização."""
        candidates = {
            'otimizar': [],      # Muito lentas mas com bom sucesso
            'remover': [],       # Baixo impacto, pouco valor
            'melhorar': [],      # Alta taxa de falha
            'manter': []         # Bom desempenho
        }
        
        total_avg_time = sum(s.avg_time_ms for s in self.steps_analysis.values())
        
        for step_num, analysis in self.steps_analysis.items():
            step_pct = analysis.avg_time_ms / total_avg_time * 100 if total_avg_time > 0 else 0
            
            for ss_name, ss_analysis in analysis.substeps.items():
                ss_pct = ss_analysis.avg_time_ms / analysis.avg_time_ms * 100 if analysis.avg_time_ms > 0 else 0
                
                item = {
                    'step': analysis.name,
                    'substep': ss_name,
                    'avg_time_ms': ss_analysis.avg_time_ms,
                    'count': ss_analysis.count,
                    'success_rate': ss_analysis.success_rate,
                    'pct_of_step': ss_pct,
                    'errors': list(ss_analysis.errors.keys())[:3]
                }
                
                # Classificar
                if ss_analysis.success_rate < 50 and ss_analysis.failure_count > 3:
                    candidates['melhorar'].append(item)
                elif ss_analysis.avg_time_ms > 5000 and ss_analysis.success_rate > 70:
                    candidates['otimizar'].append(item)
                elif ss_pct < 5 and ss_analysis.avg_time_ms < 100:
                    candidates['remover'].append(item)
                else:
                    candidates['manter'].append(item)
        
        # Ordenar por tempo
        for category in candidates:
            candidates[category].sort(key=lambda x: -x['avg_time_ms'])
        
        return candidates
    
    def generate_report(self):
        """Gera relatório de análise completo."""
        print("\n" + "=" * 80)
        print("ANÁLISE DETALHADA DO RELATÓRIO DE SCRAPING")
        print("=" * 80)
        
        # Métricas gerais
        metrics = self.data.get('metrics', {})
        print(f"\n📊 RESUMO GERAL:")
        print(f"   Total: {metrics.get('total', 0)}")
        print(f"   Sucesso: {metrics.get('success', 0)} ({metrics.get('taxa_sucesso', 0):.1f}%)")
        print(f"   Falhas: {metrics.get('failed', 0)}")
        print(f"   Timeout: {metrics.get('timeout', 0)}")
        
        # Análise por etapa
        print(f"\n🔍 ANÁLISE POR ETAPA:")
        print("-" * 80)
        
        bottlenecks = self.find_bottlenecks()
        total_time = sum(b['avg_time_ms'] for b in bottlenecks)
        
        for b in bottlenecks:
            pct = b['avg_time_ms'] / total_time * 100 if total_time > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"\n   ETAPA {b['step_number']}: {b['step']}")
            print(f"   ├─ Tempo médio: {b['avg_time_ms']:.0f}ms ({pct:.1f}%) {bar}")
            print(f"   ├─ Taxa de sucesso: {b['success_rate']:.1f}%")
            print(f"   └─ Subetapas mais lentas:")
            
            for ss in b['substeps'][:5]:  # Top 5
                ss_pct = ss['avg_time_ms'] / b['avg_time_ms'] * 100 if b['avg_time_ms'] > 0 else 0
                ss_bar = "▓" * int(ss_pct / 5)
                status = "✅" if ss['success_rate'] >= 90 else "⚠️" if ss['success_rate'] >= 50 else "❌"
                print(f"      {status} {ss['name'][:35]:35} | {ss['avg_time_ms']:>7.0f}ms ({ss_pct:5.1f}%) {ss_bar}")
                
                if ss['errors']:
                    errors_list = list(ss['errors'].keys()) if isinstance(ss['errors'], dict) else ss['errors']
                    print(f"         Erros: {', '.join(errors_list[:2])}")
        
        # Análise por tipo de site
        print(f"\n\n🌐 ANÁLISE POR TIPO DE SITE:")
        print("-" * 80)
        
        by_type = self.analyze_by_site_type()
        for site_type, data in sorted(by_type.items()):
            success_rate = data['success'] / data['count'] * 100 if data['count'] > 0 else 0
            print(f"   {site_type.upper():10} | {data['count']:3} sites | {success_rate:5.1f}% sucesso | "
                  f"~{data.get('avg_time', 0):.0f}ms | ~{data.get('avg_content', 0):.0f} chars")
        
        # Análise por proteção
        print(f"\n🛡️ ANÁLISE POR PROTEÇÃO:")
        print("-" * 80)
        
        by_protection = self.analyze_by_protection()
        for protection, data in sorted(by_protection.items()):
            success_rate = data['success'] / data['count'] * 100 if data['count'] > 0 else 0
            strategies = ", ".join(f"{k}:{v}" for k, v in data['strategies_used'].items() if v > 0)
            print(f"   {protection.upper():15} | {data['count']:3} sites | {success_rate:5.1f}% sucesso | "
                  f"~{data.get('avg_time', 0):.0f}ms")
            print(f"      Estratégias: {strategies}")
        
        # Candidatos a otimização
        print(f"\n\n🎯 RECOMENDAÇÕES DE OTIMIZAÇÃO:")
        print("-" * 80)
        
        candidates = self.find_optimization_candidates()
        
        if candidates['otimizar']:
            print(f"\n   ⚡ SUBETAPAS A OTIMIZAR (lentas mas funcionais):")
            for c in candidates['otimizar'][:5]:
                print(f"      • {c['step']} → {c['substep'][:40]}")
                print(f"        {c['avg_time_ms']:.0f}ms | {c['success_rate']:.0f}% sucesso | {c['pct_of_step']:.0f}% da etapa")
        
        if candidates['melhorar']:
            print(f"\n   🔧 SUBETAPAS A MELHORAR (alta taxa de falha):")
            for c in candidates['melhorar'][:5]:
                print(f"      • {c['step']} → {c['substep'][:40]}")
                print(f"        {c['avg_time_ms']:.0f}ms | {c['success_rate']:.0f}% sucesso")
                if c['errors']:
                    print(f"        Erros: {', '.join(c['errors'])}")
        
        if candidates['remover']:
            print(f"\n   🗑️ SUBETAPAS CANDIDATAS A REMOÇÃO (baixo impacto):")
            for c in candidates['remover'][:5]:
                print(f"      • {c['step']} → {c['substep'][:40]}")
                print(f"        {c['avg_time_ms']:.0f}ms | {c['pct_of_step']:.0f}% da etapa")
        
        # Resumo de ações
        print(f"\n\n📋 RESUMO DE AÇÕES SUGERIDAS:")
        print("-" * 80)
        
        # Identificar maiores gargalos
        if bottlenecks:
            top_bottleneck = bottlenecks[0]
            top_pct = top_bottleneck['avg_time_ms'] / total_time * 100 if total_time > 0 else 0
            
            print(f"\n   1. PRINCIPAL GARGALO: {top_bottleneck['step']} ({top_pct:.1f}% do tempo total)")
            if top_bottleneck['substeps']:
                top_ss = top_bottleneck['substeps'][0]
                print(f"      → Subetapa crítica: {top_ss['name']}")
                print(f"      → Ação sugerida: Paralelizar ou otimizar")
        
        # Verificar taxa de sucesso
        overall_success = metrics.get('taxa_sucesso', 0)
        if overall_success < 80:
            print(f"\n   2. TAXA DE SUCESSO BAIXA ({overall_success:.1f}%)")
            print(f"      → Revisar estratégias de fallback")
            print(f"      → Aumentar timeouts ou retries")
        
        # Verificar proteções problemáticas
        for protection, data in by_protection.items():
            success_rate = data['success'] / data['count'] * 100 if data['count'] > 0 else 0
            if success_rate < 70 and data['count'] > 5:
                print(f"\n   3. PROTEÇÃO PROBLEMÁTICA: {protection.upper()}")
                print(f"      → Taxa de sucesso: {success_rate:.1f}%")
                print(f"      → Considerar estratégias mais agressivas")
        
        print("\n" + "=" * 80)
    
    def run(self):
        """Executa análise completa."""
        self.load_report()
        self.analyze_steps()
        self.generate_report()


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    analyzer = ScraperReportAnalyzer(report_path)
    analyzer.run()

