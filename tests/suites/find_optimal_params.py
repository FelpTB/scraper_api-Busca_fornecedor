"""
Encontra parâmetros ótimos para processamento paralelo.

Testa diferentes configurações e analisa qual a melhor combinação
para processar N empresas com N concorrências (cenário de produção).
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any

from tests.suites.stress_test_empresas import StressTestEmpresas

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """Configuração de teste."""
    empresas: int
    concorrencia: int
    timeout: float
    
    @property
    def nome(self) -> str:
        return f"E{self.empresas}_C{self.concorrencia}_T{int(self.timeout)}"


@dataclass
class TestResultado:
    """Resultado de um teste."""
    config: TestConfig
    taxa_sucesso: float
    tempo_medio: float
    completude: float
    tempo_total: float
    aprovado: bool
    erros: Dict[str, int]


class OptimalParamsFinder:
    """Encontra parâmetros ótimos através de testes."""
    
    def __init__(self):
        self.resultados: List[TestResultado] = []
    
    async def run_single_test(self, config: TestConfig) -> TestResultado:
        """Executa um único teste com a configuração especificada."""
        print(f"\n{'='*60}")
        print(f"🧪 Testando: {config.empresas} empresas | {config.concorrencia} conc. | {config.timeout}s timeout")
        print(f"{'='*60}")
        
        test = StressTestEmpresas(
            max_concurrent=config.concorrencia,
            timeout_per_empresa=config.timeout
        )
        
        metrics = await test.run_stress_test(limit=config.empresas, verbose=False)
        
        resultado = TestResultado(
            config=config,
            taxa_sucesso=metrics.taxa_sucesso,
            tempo_medio=metrics.tempo_medio_segundos,
            completude=metrics.completude_media,
            tempo_total=metrics.tempo_total_segundos,
            aprovado=metrics.aprovado,
            erros=metrics.erros_por_tipo
        )
        
        self.resultados.append(resultado)
        
        status = "✅ APROVADO" if resultado.aprovado else "❌ REPROVADO"
        print(f"\n{status}")
        print(f"  Taxa: {resultado.taxa_sucesso:.1f}% | Tempo médio: {resultado.tempo_medio:.1f}s | Completude: {resultado.completude:.1f}%")
        
        return resultado
    
    async def find_optimal_for_n_empresas(self, n: int) -> Dict[str, Any]:
        """
        Encontra parâmetros ótimos para N empresas com N concorrências.
        
        Testa diferentes valores de timeout para encontrar o melhor.
        """
        print(f"\n{'#'*60}")
        print(f"# BUSCANDO PARÂMETROS ÓTIMOS PARA {n} EMPRESAS")
        print(f"# Cenário: {n} empresas com {n} concorrências (produção)")
        print(f"{'#'*60}")
        
        # Testar diferentes timeouts
        timeouts = [60, 90, 120]
        
        for timeout in timeouts:
            config = TestConfig(
                empresas=n,
                concorrencia=n,
                timeout=timeout
            )
            await self.run_single_test(config)
        
        # Analisar resultados
        resultados_n = [r for r in self.resultados if r.config.empresas == n]
        
        # Encontrar melhor configuração
        aprovados = [r for r in resultados_n if r.aprovado]
        
        if aprovados:
            # Melhor aprovado por taxa de sucesso
            melhor = max(aprovados, key=lambda r: r.taxa_sucesso)
        else:
            # Se nenhum aprovado, pegar o melhor resultado
            melhor = max(resultados_n, key=lambda r: r.taxa_sucesso)
        
        return {
            "empresas": n,
            "melhor_timeout": melhor.config.timeout,
            "taxa_sucesso": melhor.taxa_sucesso,
            "tempo_medio": melhor.tempo_medio,
            "completude": melhor.completude,
            "aprovado": melhor.aprovado,
            "todos_resultados": [
                {
                    "timeout": r.config.timeout,
                    "taxa_sucesso": r.taxa_sucesso,
                    "tempo_medio": r.tempo_medio,
                    "completude": r.completude,
                    "aprovado": r.aprovado
                }
                for r in resultados_n
            ]
        }
    
    def print_summary(self):
        """Imprime resumo de todos os testes."""
        print("\n" + "="*80)
        print("📊 RESUMO DE TODOS OS TESTES")
        print("="*80)
        
        print(f"\n{'Config':<20} {'Taxa':<10} {'Tempo':<10} {'Complet.':<10} {'Status':<10}")
        print("-"*60)
        
        for r in sorted(self.resultados, key=lambda x: (x.config.empresas, x.config.timeout)):
            status = "✅" if r.aprovado else "❌"
            print(f"{r.config.nome:<20} {r.taxa_sucesso:>6.1f}%   {r.tempo_medio:>6.1f}s   {r.completude:>6.1f}%   {status}")
        
        print("-"*60)
        
        # Recomendações
        print("\n📋 RECOMENDAÇÕES:")
        
        # Agrupar por número de empresas
        empresas_testadas = sorted(set(r.config.empresas for r in self.resultados))
        
        for n in empresas_testadas:
            resultados_n = [r for r in self.resultados if r.config.empresas == n]
            aprovados = [r for r in resultados_n if r.aprovado]
            
            if aprovados:
                melhor = max(aprovados, key=lambda r: r.taxa_sucesso)
                print(f"\n  Para {n} empresas em paralelo:")
                print(f"    ✅ Timeout recomendado: {melhor.config.timeout}s")
                print(f"    Taxa esperada: {melhor.taxa_sucesso:.1f}%")
            else:
                melhor = max(resultados_n, key=lambda r: r.taxa_sucesso)
                print(f"\n  Para {n} empresas em paralelo:")
                print(f"    ⚠️ Nenhuma config aprovada. Melhor resultado:")
                print(f"    Timeout: {melhor.config.timeout}s → Taxa: {melhor.taxa_sucesso:.1f}%")
                print(f"    💡 Sugestão: Aumentar recursos ou processar em lotes menores")
    
    def save_report(self, filename: str = "tests/reports/optimal_params_report.json"):
        """Salva relatório dos testes."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_testes": len(self.resultados),
            "resultados": [
                {
                    "config": {
                        "empresas": r.config.empresas,
                        "concorrencia": r.config.concorrencia,
                        "timeout": r.config.timeout
                    },
                    "taxa_sucesso": r.taxa_sucesso,
                    "tempo_medio": r.tempo_medio,
                    "completude": r.completude,
                    "tempo_total": r.tempo_total,
                    "aprovado": r.aprovado,
                    "erros": r.erros
                }
                for r in self.resultados
            ]
        }
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Relatório salvo em: {filename}")


async def main():
    """Executa busca de parâmetros ótimos."""
    finder = OptimalParamsFinder()
    
    # Testar para diferentes tamanhos
    # Começar com 50, depois 100, depois 150
    tamanhos = [50, 100]
    
    for n in tamanhos:
        await finder.find_optimal_for_n_empresas(n)
    
    finder.print_summary()
    finder.save_report()


if __name__ == "__main__":
    asyncio.run(main())

