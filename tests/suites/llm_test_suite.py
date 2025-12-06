"""
Suite de Testes do LLM v2.0

Testa o sistema LLM contra uma variedade de conteúdos para medir:
- Taxa de sucesso
- Tempo de resposta
- Distribuição de carga entre providers
- Comportamento sob carga
"""

import asyncio
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LLMTestResult:
    """Resultado de um teste individual."""
    test_id: int
    content_size: int
    success: bool
    response_time_ms: float = 0.0
    provider_used: str = "unknown"
    chunks_processed: int = 0
    error: Optional[str] = None


@dataclass
class LLMSuiteResults:
    """Resultados consolidados da suite."""
    total_tests: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    total_time_seconds: float = 0.0
    results: List[LLMTestResult] = field(default_factory=list)
    providers_distribution: Dict[str, int] = field(default_factory=dict)
    rate_limit_count: int = 0
    timeout_count: int = 0
    timestamp: str = ""
    
    def calculate_metrics(self):
        """Calcula métricas consolidadas."""
        self.total_tests = len(self.results)
        self.successful = sum(1 for r in self.results if r.success)
        self.failed = self.total_tests - self.successful
        self.success_rate = self.successful / self.total_tests if self.total_tests > 0 else 0.0
        
        response_times = [r.response_time_ms for r in self.results if r.response_time_ms > 0]
        self.avg_response_time_ms = sum(response_times) / len(response_times) if response_times else 0.0
        
        # Contagem por provider
        self.providers_distribution = {}
        for r in self.results:
            provider = r.provider_used
            self.providers_distribution[provider] = self.providers_distribution.get(provider, 0) + 1
        
        # Contagem de erros específicos
        self.rate_limit_count = sum(1 for r in self.results if r.error and "rate" in r.error.lower())
        self.timeout_count = sum(1 for r in self.results if r.error and "timeout" in r.error.lower())


# Conteúdos de teste de diferentes tamanhos
SAMPLE_CONTENTS = {
    "small": """
    Empresa ABC Tecnologia Ltda
    CNPJ: 12.345.678/0001-90
    Endereço: Rua das Flores, 123 - São Paulo/SP
    Telefone: (11) 1234-5678
    Email: contato@abc.com.br
    
    Sobre: Desenvolvemos soluções de software para empresas de médio porte.
    Nossos principais produtos incluem sistemas de gestão empresarial e CRM.
    """,
    
    "medium": """
    DELTA INDÚSTRIA E COMÉRCIO S.A.
    CNPJ: 98.765.432/0001-10
    Inscrição Estadual: 123.456.789
    
    Sede: Av. Industrial, 5000 - Campinas/SP
    Filial: Rua do Comércio, 200 - Belo Horizonte/MG
    
    SOBRE A EMPRESA:
    A Delta é uma empresa brasileira fundada em 1990, especializada na 
    fabricação de equipamentos industriais para os setores automotivo, 
    alimentício e farmacêutico.
    
    PRODUTOS E SERVIÇOS:
    - Máquinas de envase automático
    - Equipamentos de embalagem
    - Sistemas de automação industrial
    - Manutenção preventiva e corretiva
    - Treinamento técnico especializado
    
    CERTIFICAÇÕES:
    - ISO 9001:2015
    - ISO 14001:2015
    - ANVISA - Boas Práticas de Fabricação
    
    CONTATO:
    Comercial: vendas@delta.com.br | (19) 3456-7890
    Suporte: suporte@delta.com.br | 0800 123 4567
    """,
    
    "large": """
    MEGA CORPORATION BRASIL S.A.
    
    DADOS CADASTRAIS:
    CNPJ: 11.222.333/0001-44
    Razão Social: MEGA CORPORATION DO BRASIL S.A.
    Nome Fantasia: MEGA CORP
    Fundação: 15 de março de 1985
    Capital Social: R$ 500.000.000,00
    
    LOCALIZAÇÃO:
    Matriz: Av. Paulista, 1000 - 20º andar - São Paulo/SP - CEP 01310-100
    Fábrica 1: Rodovia BR-101, Km 500 - Joinville/SC
    Fábrica 2: Distrito Industrial - Manaus/AM
    Centro de Distribuição: Rod. Anhanguera, Km 30 - Jundiaí/SP
    
    GOVERNANÇA:
    CEO: João da Silva
    CFO: Maria Santos
    CTO: Pedro Oliveira
    Diretor Comercial: Ana Costa
    
    HISTÓRIA:
    A Mega Corporation foi fundada em 1985 como uma pequena fábrica de 
    componentes eletrônicos. Ao longo de quase 40 anos, a empresa cresceu
    e se tornou uma das maiores corporações do Brasil no setor de tecnologia.
    
    Em 1995, abriu capital na B3 (antiga Bovespa) e iniciou processo de
    internacionalização. Hoje possui operações em 15 países e mais de
    50.000 colaboradores diretos.
    
    DIVISÕES DE NEGÓCIO:
    
    1. Mega Electronics
       - Componentes eletrônicos
       - Semicondutores
       - Placas de circuito impresso
       
    2. Mega Consumer
       - Eletrodomésticos
       - Produtos de linha branca
       - Eletrônicos de consumo
       
    3. Mega Enterprise
       - Servidores e data centers
       - Soluções de cloud computing
       - Software empresarial
       
    4. Mega Energy
       - Painéis solares
       - Baterias de alta capacidade
       - Sistemas de armazenamento de energia
    
    PRODUTOS PRINCIPAIS:
    - Smartphones Mega Line (M1, M2, M3 Pro, M3 Ultra)
    - Notebooks Mega Book (15", 17", Workstation)
    - Tablets Mega Tab (8", 10", 12.9")
    - Smart TVs Mega Vision (32" a 85")
    - Geladeiras Mega Frost
    - Ar condicionado Mega Air
    - Máquinas de lavar Mega Wash
    
    CERTIFICAÇÕES E PRÊMIOS:
    - ISO 9001:2015 (Qualidade)
    - ISO 14001:2015 (Ambiental)
    - ISO 45001:2018 (Segurança)
    - Great Place to Work 2023
    - Prêmio Sustentabilidade FIESP 2022
    - Top of Mind Tecnologia 2023
    
    RESPONSABILIDADE SOCIAL:
    - Instituto Mega de Educação (10.000 bolsas/ano)
    - Programa de reflorestamento (1 milhão de árvores plantadas)
    - Centro de reciclagem de eletrônicos
    
    CONTATOS:
    Central de Vendas: 0800 123 6789
    SAC: 0800 987 6543
    Ouvidoria: ouvidoria@megacorp.com.br
    Imprensa: press@megacorp.com.br
    Investidores: ri@megacorp.com.br
    
    REDES SOCIAIS:
    Instagram: @megacorpbr
    LinkedIn: /company/megacorp
    Twitter: @megacorp
    YouTube: MegaCorpOficial
    """
}


class LLMTestSuite:
    """Suite de testes para o sistema LLM."""
    
    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self.results = LLMSuiteResults()
    
    async def run_single_test(self, test_id: int, content: str) -> LLMTestResult:
        """Executa um único teste de análise LLM."""
        from app.services.llm import analyze_content, health_monitor
        
        result = LLMTestResult(
            test_id=test_id,
            content_size=len(content),
            success=False
        )
        
        try:
            start = time.perf_counter()
            
            profile = await asyncio.wait_for(
                analyze_content(content),
                timeout=self.timeout
            )
            
            elapsed = (time.perf_counter() - start) * 1000
            
            # Verificar se perfil tem dados
            profile_dict = profile.model_dump() if hasattr(profile, 'model_dump') else {}
            has_data = any(
                v and (isinstance(v, dict) and any(v.values()) or isinstance(v, list) and len(v) > 0)
                for v in profile_dict.values()
            )
            
            result.success = has_data
            result.response_time_ms = elapsed
            
            # Tentar identificar provider usado (via health monitor)
            all_metrics = health_monitor.get_all_metrics()
            if all_metrics:
                # Provider com mais requisições recentes
                result.provider_used = max(
                    all_metrics.keys(),
                    key=lambda p: all_metrics[p].get('requests_total', 0)
                )
            
            status = "✅" if result.success else "⚠️"
            logger.info(f"{status} Test {test_id}: {elapsed:.0f}ms, {result.content_size} chars")
            
        except asyncio.TimeoutError:
            result.error = "Timeout"
            logger.warning(f"⏰ Test {test_id}: Timeout após {self.timeout}s")
        except Exception as e:
            result.error = str(e)
            logger.error(f"❌ Test {test_id}: {type(e).__name__}: {e}")
        
        return result
    
    async def run_batch_test(
        self,
        contents: List[str],
        concurrent: int = 10
    ) -> List[LLMTestResult]:
        """Executa batch de testes com concorrência limitada."""
        semaphore = asyncio.Semaphore(concurrent)
        
        async def run_with_semaphore(test_id: int, content: str):
            async with semaphore:
                return await self.run_single_test(test_id, content)
        
        tasks = [run_with_semaphore(i, c) for i, c in enumerate(contents, 1)]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def run_full_suite(
        self,
        num_tests: int = 30,
        concurrent: int = 10
    ) -> LLMSuiteResults:
        """
        Executa a suite completa de testes.
        
        Args:
            num_tests: Número de testes a executar
            concurrent: Concorrência máxima
        
        Returns:
            LLMSuiteResults com métricas consolidadas
        """
        start_time = time.perf_counter()
        self.results = LLMSuiteResults(timestamp=datetime.now().isoformat())
        
        logger.info(f"\n🚀 Iniciando LLM Test Suite")
        logger.info(f"📋 Testes: {num_tests}, Concorrência: {concurrent}")
        
        # Gerar lista de conteúdos para teste
        contents = []
        content_types = list(SAMPLE_CONTENTS.values())
        for i in range(num_tests):
            content = content_types[i % len(content_types)]
            contents.append(content)
        
        # Executar testes
        results = await self.run_batch_test(contents, concurrent)
        
        # Processar resultados
        for r in results:
            if isinstance(r, Exception):
                self.results.results.append(LLMTestResult(
                    test_id=-1,
                    content_size=0,
                    success=False,
                    error=str(r)
                ))
            else:
                self.results.results.append(r)
        
        self.results.total_time_seconds = time.perf_counter() - start_time
        self.results.calculate_metrics()
        
        return self.results
    
    async def run_load_test(
        self,
        duration_seconds: float = 60.0,
        requests_per_second: float = 5.0
    ) -> LLMSuiteResults:
        """
        Executa teste de carga por tempo determinado.
        
        Args:
            duration_seconds: Duração do teste
            requests_per_second: Taxa de requisições por segundo
        """
        start_time = time.perf_counter()
        self.results = LLMSuiteResults(timestamp=datetime.now().isoformat())
        
        logger.info(f"\n🔥 Iniciando LLM Load Test")
        logger.info(f"📋 Duração: {duration_seconds}s, RPS: {requests_per_second}")
        
        content_types = list(SAMPLE_CONTENTS.values())
        test_id = 0
        interval = 1.0 / requests_per_second
        
        while time.perf_counter() - start_time < duration_seconds:
            test_id += 1
            content = content_types[test_id % len(content_types)]
            
            # Disparar teste sem esperar
            asyncio.create_task(self._run_and_store(test_id, content))
            
            await asyncio.sleep(interval)
        
        # Aguardar testes pendentes (timeout)
        await asyncio.sleep(min(30, self.timeout))
        
        self.results.total_time_seconds = time.perf_counter() - start_time
        self.results.calculate_metrics()
        
        return self.results
    
    async def _run_and_store(self, test_id: int, content: str):
        """Executa teste e armazena resultado."""
        result = await self.run_single_test(test_id, content)
        self.results.results.append(result)
    
    def print_report(self):
        """Imprime relatório formatado."""
        r = self.results
        
        print("\n" + "="*60)
        print("📊 RELATÓRIO DO LLM TEST SUITE")
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
        print("🔄 DISTRIBUIÇÃO POR PROVIDER:")
        for provider, count in r.providers_distribution.items():
            print(f"   - {provider}: {count} requisições")
        print()
        print(f"⚠️  ERROS ESPECÍFICOS:")
        print(f"   - Rate Limits: {r.rate_limit_count}")
        print(f"   - Timeouts: {r.timeout_count}")
        print()
        
        # Testes com falha
        failures = [res for res in r.results if not res.success]
        if failures:
            print("❌ TESTES COM FALHA (primeiros 5):")
            for f in failures[:5]:
                print(f"   - Test {f.test_id}: {f.error or 'Unknown'}")
        
        print("="*60)
    
    def save_report(self, filepath: str = "llm_test_results.json"):
        """Salva relatório em JSON."""
        data = {
            "summary": {
                "total_tests": self.results.total_tests,
                "successful": self.results.successful,
                "failed": self.results.failed,
                "success_rate": self.results.success_rate,
                "avg_response_time_ms": self.results.avg_response_time_ms,
                "total_time_seconds": self.results.total_time_seconds,
                "rate_limit_count": self.results.rate_limit_count,
                "timeout_count": self.results.timeout_count,
                "timestamp": self.results.timestamp
            },
            "providers_distribution": self.results.providers_distribution,
            "results": [asdict(r) for r in self.results.results]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Relatório salvo em {filepath}")


async def run_quick_test():
    """Executa teste rápido com poucos testes."""
    suite = LLMTestSuite(timeout=60.0)
    results = await suite.run_full_suite(num_tests=10, concurrent=3)
    suite.print_report()
    return results


async def run_full_test():
    """Executa suite completa."""
    suite = LLMTestSuite(timeout=120.0)
    results = await suite.run_full_suite(num_tests=30, concurrent=10)
    suite.print_report()
    suite.save_report()
    return results


async def run_load_test():
    """Executa teste de carga."""
    suite = LLMTestSuite(timeout=120.0)
    results = await suite.run_load_test(duration_seconds=60.0, requests_per_second=2.0)
    suite.print_report()
    suite.save_report("llm_load_test_results.json")
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick":
            asyncio.run(run_quick_test())
        elif sys.argv[1] == "--load":
            asyncio.run(run_load_test())
        else:
            asyncio.run(run_full_test())
    else:
        asyncio.run(run_full_test())

