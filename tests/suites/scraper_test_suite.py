"""
Suite de Testes do Scraper v2.0

Testa o scraper contra uma variedade de sites reais para medir:
- Taxa de sucesso
- Tempo de resposta
- Detecção de proteções
- Seleção de estratégias
"""

import asyncio
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Resultado de um teste individual."""
    url: str
    success: bool
    content_length: int = 0
    response_time_ms: float = 0.0
    protection_detected: str = "none"
    strategy_used: str = "unknown"
    pages_scraped: int = 0
    error: Optional[str] = None


@dataclass
class SuiteResults:
    """Resultados consolidados da suite."""
    total_tests: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    total_time_seconds: float = 0.0
    results: List[TestResult] = field(default_factory=list)
    protections_found: Dict[str, int] = field(default_factory=dict)
    strategies_used: Dict[str, int] = field(default_factory=dict)
    timestamp: str = ""
    
    def calculate_metrics(self):
        """Calcula métricas consolidadas."""
        self.total_tests = len(self.results)
        self.successful = sum(1 for r in self.results if r.success)
        self.failed = self.total_tests - self.successful
        self.success_rate = self.successful / self.total_tests if self.total_tests > 0 else 0.0
        
        response_times = [r.response_time_ms for r in self.results if r.response_time_ms > 0]
        self.avg_response_time_ms = sum(response_times) / len(response_times) if response_times else 0.0
        
        # Contagem de proteções
        self.protections_found = {}
        for r in self.results:
            protection = r.protection_detected
            self.protections_found[protection] = self.protections_found.get(protection, 0) + 1
        
        # Contagem de estratégias
        self.strategies_used = {}
        for r in self.results:
            strategy = r.strategy_used
            self.strategies_used[strategy] = self.strategies_used.get(strategy, 0) + 1


# URLs de teste categorizadas
TEST_URLS = {
    "static_simple": [
        "https://example.com",
        "https://httpbin.org",
        "https://jsonplaceholder.typicode.com",
    ],
    "static_corporate": [
        "https://www.apple.com",
        "https://www.microsoft.com",
        "https://www.ibm.com",
    ],
    "spa_apps": [
        "https://react.dev",
        "https://vuejs.org",
        "https://angular.io",
    ],
    "protected_cloudflare": [
        # Sites conhecidos por usar Cloudflare
        "https://www.cloudflare.com",
    ],
    "brazilian_corporate": [
        "https://www.petrobras.com.br",
        "https://www.vale.com",
        "https://www.itau.com.br",
        "https://www.bradesco.com.br",
    ]
}


class ScraperTestSuite:
    """Suite de testes para o scraper."""
    
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.results = SuiteResults()
    
    async def run_single_test(self, url: str) -> TestResult:
        """Executa teste em uma única URL."""
        from app.services.scraper import site_analyzer, scrape_url
        
        result = TestResult(url=url, success=False)
        
        try:
            start = time.perf_counter()
            
            # Analisar site primeiro
            profile = await site_analyzer.analyze(url)
            result.protection_detected = profile.protection_type.value
            result.strategy_used = profile.best_strategy.value
            
            # Fazer scrape
            content, docs, visited = await asyncio.wait_for(
                scrape_url(url, max_subpages=5),  # Limitado para testes
                timeout=self.timeout
            )
            
            elapsed = (time.perf_counter() - start) * 1000
            
            result.success = bool(content) and len(content) >= 100
            result.content_length = len(content) if content else 0
            result.response_time_ms = elapsed
            result.pages_scraped = len(visited)
            
            logger.info(f"✅ {url}: {result.content_length} chars, {result.pages_scraped} pages")
            
        except asyncio.TimeoutError:
            result.error = "Timeout"
            logger.warning(f"⏰ {url}: Timeout após {self.timeout}s")
        except Exception as e:
            result.error = str(e)
            logger.error(f"❌ {url}: {e}")
        
        return result
    
    async def run_category(self, category: str, urls: List[str]) -> List[TestResult]:
        """Executa testes em uma categoria de URLs."""
        logger.info(f"\n📁 Testando categoria: {category} ({len(urls)} URLs)")
        
        results = []
        for url in urls:
            result = await self.run_single_test(url)
            results.append(result)
            await asyncio.sleep(1)  # Delay entre testes
        
        return results
    
    async def run_full_suite(self, categories: List[str] = None) -> SuiteResults:
        """
        Executa a suite completa de testes.
        
        Args:
            categories: Lista de categorias para testar (None = todas)
        
        Returns:
            SuiteResults com métricas consolidadas
        """
        start_time = time.perf_counter()
        self.results = SuiteResults(timestamp=datetime.now().isoformat())
        
        test_categories = categories or list(TEST_URLS.keys())
        
        logger.info(f"\n🚀 Iniciando Scraper Test Suite")
        logger.info(f"📋 Categorias: {test_categories}")
        
        for category in test_categories:
            if category in TEST_URLS:
                results = await self.run_category(category, TEST_URLS[category])
                self.results.results.extend(results)
        
        self.results.total_time_seconds = time.perf_counter() - start_time
        self.results.calculate_metrics()
        
        return self.results
    
    def print_report(self):
        """Imprime relatório formatado."""
        r = self.results
        
        print("\n" + "="*60)
        print("📊 RELATÓRIO DO SCRAPER TEST SUITE")
        print("="*60)
        print(f"⏱️  Data/Hora: {r.timestamp}")
        print(f"⏱️  Tempo total: {r.total_time_seconds:.1f}s")
        print()
        print(f"📈 MÉTRICAS GERAIS:")
        print(f"   Total de testes: {r.total_tests}")
        print(f"   ✅ Sucesso: {r.successful}")
        print(f"   ❌ Falha: {r.failed}")
        print(f"   📊 Taxa de sucesso: {r.success_rate:.1%}")
        print(f"   ⏱️  Tempo médio: {r.avg_response_time_ms:.0f}ms")
        print()
        print("🛡️  PROTEÇÕES DETECTADAS:")
        for protection, count in r.protections_found.items():
            print(f"   - {protection}: {count}")
        print()
        print("🎯 ESTRATÉGIAS UTILIZADAS:")
        for strategy, count in r.strategies_used.items():
            print(f"   - {strategy}: {count}")
        print()
        
        # URLs com falha
        failures = [res for res in r.results if not res.success]
        if failures:
            print("❌ URLs COM FALHA:")
            for f in failures:
                print(f"   - {f.url}: {f.error or 'Unknown error'}")
        
        print("="*60)
    
    def save_report(self, filepath: str = "scraper_test_results.json"):
        """Salva relatório em JSON."""
        data = {
            "summary": {
                "total_tests": self.results.total_tests,
                "successful": self.results.successful,
                "failed": self.results.failed,
                "success_rate": self.results.success_rate,
                "avg_response_time_ms": self.results.avg_response_time_ms,
                "total_time_seconds": self.results.total_time_seconds,
                "timestamp": self.results.timestamp
            },
            "protections_found": self.results.protections_found,
            "strategies_used": self.results.strategies_used,
            "results": [asdict(r) for r in self.results.results]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Relatório salvo em {filepath}")


async def run_quick_test():
    """Executa teste rápido com poucas URLs."""
    suite = ScraperTestSuite(timeout=30.0)
    results = await suite.run_full_suite(categories=["static_simple"])
    suite.print_report()
    return results


async def run_full_test():
    """Executa suite completa."""
    suite = ScraperTestSuite(timeout=60.0)
    results = await suite.run_full_suite()
    suite.print_report()
    suite.save_report()
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(run_quick_test())
    else:
        asyncio.run(run_full_test())

