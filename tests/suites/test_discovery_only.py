"""
Teste focado APENAS na etapa de Discovery.

Objetivo: Identificar gargalos no Discovery (Serper + LLM Decision)
sem custos de Scrape e LLM de análise.

Métricas coletadas:
- Tempo do Serper (busca Google)
- Tempo do LLM Decision (escolha do site)
- Tempo total do Discovery
- Taxa de sucesso
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Resultado de uma descoberta de site."""
    empresa_nome: str
    razao_social: str = ""
    municipio: str = ""
    
    # Resultado
    success: bool = False
    url_encontrada: str = ""
    error: str = ""
    
    # Tempos detalhados
    tempo_total_ms: float = 0
    tempo_serper_ms: float = 0
    tempo_llm_ms: float = 0
    
    # Metadados
    num_queries_serper: int = 0
    num_resultados_serper: int = 0
    provider_llm: str = ""


@dataclass
class DiscoveryTestMetrics:
    """Métricas agregadas do teste."""
    total: int = 0
    sucesso: int = 0
    falha_serper: int = 0
    falha_llm: int = 0
    timeout: int = 0
    
    tempo_total_medio_ms: float = 0
    tempo_serper_medio_ms: float = 0
    tempo_llm_medio_ms: float = 0


class DiscoveryOnlyTest:
    """Teste focado apenas no Discovery."""
    
    def __init__(
        self,
        data_file: str = "tests/data_empresas.json",
        max_concurrent: int = 50,
        timeout_per_empresa: float = 60.0
    ):
        self.data_file = data_file
        self.max_concurrent = max_concurrent
        self.timeout = timeout_per_empresa
        self.results: List[DiscoveryResult] = []
        self.metrics = DiscoveryTestMetrics()
    
    def load_empresas(self, limit: int = 50) -> List[Dict]:
        """Carrega empresas do arquivo."""
        with open(self.data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        empresas = []
        for e in data[:limit]:
            empresas.append({
                'nome_fantasia': e.get('nome_fantasia', ''),
                'razao_social': e.get('razao_social', ''),
                'municipio': e.get('municipio', ''),
                'cnpj': e.get('cnpj_basico', ''),
                'email': e.get('correio_eletronico', ''),
                'cnaes': [e.get('cnae_fiscal', '')] if e.get('cnae_fiscal') else None
            })
        
        logger.info(f"Carregadas {len(empresas)} empresas para teste de Discovery")
        return empresas
    
    async def test_discovery_single(self, empresa: Dict, idx: int) -> DiscoveryResult:
        """Testa Discovery para uma única empresa com métricas detalhadas."""
        from app.services.discovery import find_company_website
        
        result = DiscoveryResult(
            empresa_nome=empresa.get('nome_fantasia', '?'),
            razao_social=empresa.get('razao_social', ''),
            municipio=empresa.get('municipio', '')
        )
        
        start_total = time.perf_counter()
        
        try:
            url = await asyncio.wait_for(
                find_company_website(
                    razao_social=empresa.get('razao_social', ''),
                    nome_fantasia=empresa.get('nome_fantasia', ''),
                    cnpj=empresa.get('cnpj', ''),
                    email=empresa.get('email'),
                    municipio=empresa.get('municipio'),
                    cnaes=empresa.get('cnaes')
                ),
                timeout=self.timeout
            )
            
            result.tempo_total_ms = (time.perf_counter() - start_total) * 1000
            
            if url:
                result.success = True
                result.url_encontrada = url
                logger.info(f"[{idx}] ✅ {result.empresa_nome[:30]:30} | {result.tempo_total_ms:.0f}ms | {url}")
            else:
                result.error = "Site não encontrado"
                logger.info(f"[{idx}] ❌ {result.empresa_nome[:30]:30} | {result.tempo_total_ms:.0f}ms | Não encontrado")
                
        except asyncio.TimeoutError:
            result.tempo_total_ms = self.timeout * 1000
            result.error = "Timeout"
            logger.info(f"[{idx}] ⏱️ {result.empresa_nome[:30]:30} | TIMEOUT ({self.timeout}s)")
            
        except Exception as e:
            result.tempo_total_ms = (time.perf_counter() - start_total) * 1000
            result.error = str(e)
            logger.error(f"[{idx}] ❌ {result.empresa_nome[:30]:30} | ERRO: {e}")
        
        return result
    
    async def run_test(self, limit: int = 50):
        """Executa teste de Discovery em paralelo."""
        empresas = self.load_empresas(limit)
        self.metrics.total = len(empresas)
        
        logger.info("="*70)
        logger.info("TESTE DE DISCOVERY - APENAS SERPER + LLM DECISION")
        logger.info("="*70)
        logger.info(f"Empresas: {len(empresas)}")
        logger.info(f"Concorrência: {self.max_concurrent}")
        logger.info(f"Timeout: {self.timeout}s")
        logger.info("="*70)
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_test(empresa, idx):
            async with semaphore:
                return await self.test_discovery_single(empresa, idx)
        
        start_time = time.perf_counter()
        
        tasks = [
            bounded_test(emp, i+1) 
            for i, emp in enumerate(empresas)
        ]
        
        self.results = await asyncio.gather(*tasks)
        
        total_time = time.perf_counter() - start_time
        
        # Calcular métricas
        self._calculate_metrics()
        
        # Imprimir resultados
        self._print_results(total_time)
        
        # Salvar relatório
        self._save_report(total_time)
    
    def _calculate_metrics(self):
        """Calcula métricas agregadas."""
        self.metrics.sucesso = sum(1 for r in self.results if r.success)
        self.metrics.timeout = sum(1 for r in self.results if 'Timeout' in r.error)
        self.metrics.falha_serper = sum(1 for r in self.results if 'Serper' in r.error)
        self.metrics.falha_llm = sum(1 for r in self.results if 'LLM' in r.error or 'não encontrado' in r.error.lower())
        
        tempos = [r.tempo_total_ms for r in self.results if r.success]
        if tempos:
            self.metrics.tempo_total_medio_ms = sum(tempos) / len(tempos)
    
    def _print_results(self, total_time: float):
        """Imprime resultados do teste."""
        print()
        print("="*70)
        print("RESULTADOS - TESTE DE DISCOVERY")
        print("="*70)
        
        taxa_sucesso = self.metrics.sucesso / self.metrics.total * 100 if self.metrics.total > 0 else 0
        
        print(f"\n📊 RESUMO:")
        print(f"   Total empresas: {self.metrics.total}")
        print(f"   Sucesso: {self.metrics.sucesso} ({taxa_sucesso:.1f}%)")
        print(f"   Timeout: {self.metrics.timeout}")
        print(f"   Não encontrado: {self.metrics.total - self.metrics.sucesso - self.metrics.timeout}")
        
        print(f"\n⏱️ TEMPOS:")
        print(f"   Tempo total do teste: {total_time:.1f}s")
        print(f"   Tempo médio por empresa (sucesso): {self.metrics.tempo_total_medio_ms:.0f}ms")
        
        # Distribuição de tempos
        tempos = [r.tempo_total_ms for r in self.results if r.success]
        if tempos:
            rapidos = sum(1 for t in tempos if t < 5000)
            medios = sum(1 for t in tempos if 5000 <= t < 15000)
            lentos = sum(1 for t in tempos if t >= 15000)
            
            print(f"\n📈 DISTRIBUIÇÃO DE TEMPOS (sucessos):")
            print(f"   Rápidos (<5s): {rapidos} ({rapidos/len(tempos)*100:.1f}%)")
            print(f"   Médios (5-15s): {medios} ({medios/len(tempos)*100:.1f}%)")
            print(f"   Lentos (>15s): {lentos} ({lentos/len(tempos)*100:.1f}%)")
        
        # Análise de erros
        erros = {}
        for r in self.results:
            if r.error:
                erro_tipo = r.error.split(':')[0] if ':' in r.error else r.error
                erros[erro_tipo] = erros.get(erro_tipo, 0) + 1
        
        if erros:
            print(f"\n❌ TIPOS DE ERRO:")
            for erro, count in sorted(erros.items(), key=lambda x: -x[1]):
                print(f"   {count}x - {erro}")
        
        print("="*70)
    
    def _save_report(self, total_time: float):
        """Salva relatório detalhado."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"tests/reports/discovery_test_{timestamp}.json"
        
        report = {
            "timestamp": timestamp,
            "config": {
                "max_concurrent": self.max_concurrent,
                "timeout": self.timeout,
                "total_empresas": self.metrics.total
            },
            "metrics": {
                "total": self.metrics.total,
                "sucesso": self.metrics.sucesso,
                "timeout": self.metrics.timeout,
                "taxa_sucesso": self.metrics.sucesso / self.metrics.total * 100 if self.metrics.total > 0 else 0,
                "tempo_total_teste_s": total_time,
                "tempo_medio_sucesso_ms": self.metrics.tempo_total_medio_ms
            },
            "results": [
                {
                    "empresa": r.empresa_nome,
                    "razao_social": r.razao_social,
                    "municipio": r.municipio,
                    "success": r.success,
                    "url": r.url_encontrada,
                    "error": r.error,
                    "tempo_ms": r.tempo_total_ms
                }
                for r in self.results
            ]
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Relatório salvo em: {report_file}")


async def run_discovery_test(n: int = 50, concurrent: int = 50, timeout: float = 60.0):
    """Executa teste de Discovery."""
    test = DiscoveryOnlyTest(
        max_concurrent=concurrent,
        timeout_per_empresa=timeout
    )
    await test.run_test(limit=n)
    return test.metrics


if __name__ == "__main__":
    print("="*70)
    print("TESTE DE DISCOVERY - DIAGNÓSTICO DE GARGALOS")
    print("="*70)
    print("• Testa APENAS Serper + LLM Decision")
    print("• NÃO faz Scrape nem LLM de análise")
    print("• Economia de custos para diagnóstico")
    print("="*70)
    
    # Parâmetros
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    
    asyncio.run(run_discovery_test(n, concurrent, timeout))

