"""
Stress Test com Dados Reais de Empresas - Fase 6

Testa o sistema com empresas brasileiras reais do arquivo data_empresas.json.

Critérios de Aprovação:
- Tempo médio: ≤ 90s por empresa (para sites encontrados)
- Taxa de sucesso: ≥ 70% (discovery + scrape + análise)
- Completude: ≥ 60% dos campos do perfil preenchidos
"""

import sys
from pathlib import Path

# Garantir que o módulo app está no path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import json
import logging
import time
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EmpresaData:
    """Dados de uma empresa do arquivo."""
    cnpj_basico: str
    nome_fantasia: str
    razao_social: str = ""
    site: str = ""  # Ignorado no modo produção
    cnae_fiscal: str = ""
    cnae_fiscal_secundaria: str = ""
    uf: str = ""
    municipio: str = ""
    correio_eletronico: str = ""
    
    @classmethod
    def from_dict(cls, data: dict, ignore_site: bool = False) -> 'EmpresaData':
        """
        Cria EmpresaData a partir de dict.
        
        Args:
            data: Dados da empresa
            ignore_site: Se True, ignora o site cadastrado (modo produção)
        """
        return cls(
            cnpj_basico=data.get('cnpj_basico', ''),
            nome_fantasia=data.get('nome_fantasia', ''),
            razao_social=data.get('razao_social', ''),
            site='' if ignore_site else data.get('site', ''),  # Ignorar se modo produção
            cnae_fiscal=data.get('cnae_fiscal', ''),
            cnae_fiscal_secundaria=data.get('cnae_fiscal_secundaria', ''),
            uf=data.get('uf', ''),
            municipio=data.get('municipio', ''),
            correio_eletronico=data.get('correio_eletronico', '')
        )
    
    @property
    def cnpj_formatado(self) -> str:
        """CNPJ formatado para display."""
        return f"{self.cnpj_basico[:2]}.{self.cnpj_basico[2:5]}.{self.cnpj_basico[5:]}/*"
    
    @property
    def cnaes_list(self) -> List[str]:
        """Lista de CNAEs (principal + secundários)."""
        cnaes = []
        if self.cnae_fiscal:
            cnaes.append(self.cnae_fiscal)
        if self.cnae_fiscal_secundaria:
            cnaes.extend(self.cnae_fiscal_secundaria.split(','))
        return cnaes


@dataclass
class TestResult:
    """Resultado de teste de uma empresa."""
    empresa: EmpresaData
    success: bool
    duration_seconds: float
    error: str = ""
    
    # Etapas
    discovery_success: bool = False
    discovery_url: str = ""
    scrape_success: bool = False
    scrape_chars: int = 0
    scrape_pages: int = 0
    llm_success: bool = False
    
    # Perfil extraído
    profile_completeness: float = 0.0
    profile_fields_filled: int = 0
    profile_fields_total: int = 0
    profile_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestMetrics:
    """Métricas consolidadas do stress test."""
    total_empresas: int = 0
    total_processadas: int = 0
    total_sucesso: int = 0
    total_falha: int = 0
    
    # Por etapa
    discovery_sucesso: int = 0
    scrape_sucesso: int = 0
    llm_sucesso: int = 0
    
    # Tempos
    tempo_total_segundos: float = 0.0
    tempo_medio_segundos: float = 0.0
    tempo_minimo_segundos: float = float('inf')
    tempo_maximo_segundos: float = 0.0
    
    # Completude
    completude_media: float = 0.0
    completude_minima: float = 100.0
    completude_maxima: float = 0.0
    
    # Erros
    erros_por_tipo: Dict[str, int] = field(default_factory=dict)
    
    @property
    def taxa_sucesso(self) -> float:
        if self.total_processadas == 0:
            return 0.0
        return (self.total_sucesso / self.total_processadas) * 100
    
    @property
    def aprovado(self) -> bool:
        """Verifica se passou nos critérios de aprovação."""
        return (
            self.tempo_medio_segundos <= 90 and
            self.taxa_sucesso >= 70 and
            self.completude_media >= 60
        )


class StressTestEmpresas:
    """
    Stress test usando dados reais de empresas brasileiras.
    """
    
    # Total de campos relevantes para completude (estrutura aninhada)
    TOTAL_FIELDS = 15
    
    def __init__(
        self,
        data_file: str = "tests/data_empresas.json",
        max_concurrent: int = 10,
        timeout_per_empresa: float = 120.0,
        production_mode: bool = True  # Modo produção: ignora site cadastrado
    ):
        self.data_file = data_file
        self.max_concurrent = max_concurrent
        self.timeout_per_empresa = timeout_per_empresa
        self.production_mode = production_mode
        self.empresas: List[EmpresaData] = []
        self.results: List[TestResult] = []
        self.metrics = StressTestMetrics()
    
    def load_empresas(self, limit: Optional[int] = None) -> int:
        """
        Carrega empresas do arquivo JSON.
        
        Em production_mode=True, ignora o campo 'site' para forçar
        o Discovery completo (Serper + LLM).
        """
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.empresas = [
                EmpresaData.from_dict(e, ignore_site=self.production_mode) 
                for e in data
            ]
            
            if limit:
                self.empresas = self.empresas[:limit]
            
            self.metrics.total_empresas = len(self.empresas)
            
            mode = "PRODUÇÃO (Discovery completo)" if self.production_mode else "TESTE (usa site cadastrado)"
            logger.info(f"Carregadas {len(self.empresas)} empresas - Modo: {mode}")
            return len(self.empresas)
        except Exception as e:
            logger.error(f"Erro ao carregar empresas: {e}")
            return 0
    
    def _count_filled_fields(self, profile) -> int:
        """Conta campos preenchidos no perfil aninhado."""
        filled = 0
        
        # Identity
        if hasattr(profile, 'identity'):
            id_ = profile.identity
            if id_.company_name: filled += 1
            if id_.description: filled += 1
            if id_.tagline: filled += 1
        
        # Classification
        if hasattr(profile, 'classification'):
            cl = profile.classification
            if cl.industry: filled += 1
            if cl.business_model: filled += 1
            if cl.target_audience: filled += 1
        
        # Offerings
        if hasattr(profile, 'offerings'):
            of = profile.offerings
            if of.products: filled += 1
            if of.services: filled += 1
            if of.key_differentiators: filled += 1
        
        # Reputation
        if hasattr(profile, 'reputation'):
            rep = profile.reputation
            if rep.certifications: filled += 1
            if rep.client_list: filled += 1
            if rep.partnerships: filled += 1
        
        # Contact
        if hasattr(profile, 'contact'):
            ct = profile.contact
            if ct.emails: filled += 1
            if ct.phones: filled += 1
            if ct.website_url: filled += 1
        
        return filled
    
    async def process_empresa(self, empresa: EmpresaData) -> TestResult:
        """Processa uma única empresa."""
        start_time = time.perf_counter()
        result = TestResult(empresa=empresa, success=False, duration_seconds=0)
        
        try:
            # Importar aqui para evitar problemas de import circular
            from app.services.discovery import find_company_website
            from app.services.scraper import scrape_url
            from app.services.llm import analyze_content
            
            # 1. DISCOVERY - encontrar site
            # Em modo produção, SEMPRE usa discovery completo (Serper + LLM)
            if empresa.site and empresa.site.strip():
                # Site já cadastrado (modo teste)
                url = empresa.site
                if not url.startswith('http'):
                    url = f"https://{url}"
                result.discovery_success = True
                result.discovery_url = url
            else:
                # Discovery completo (modo produção)
                # Usa: razão social, nome fantasia, cidade, cnaes
                found_url = await find_company_website(
                    razao_social=empresa.razao_social,
                    nome_fantasia=empresa.nome_fantasia,
                    cnpj=empresa.cnpj_basico,
                    email=empresa.correio_eletronico,
                    municipio=empresa.municipio,
                    cnaes=empresa.cnaes_list if empresa.cnaes_list else None
                )
                
                if found_url:
                    result.discovery_success = True
                    result.discovery_url = found_url
                else:
                    result.error = "Discovery: Site não encontrado"
                    result.duration_seconds = time.perf_counter() - start_time
                    return result
            
            # 2. SCRAPE - extrair conteúdo do site
            markdown, docs, scraped_urls = await scrape_url(
                result.discovery_url, 
                max_subpages=50
            )
            
            if markdown and len(markdown) > 100:
                result.scrape_success = True
                result.scrape_chars = len(markdown)
                result.scrape_pages = len(scraped_urls)
            else:
                result.error = "Scrape: Conteúdo insuficiente"
                result.duration_seconds = time.perf_counter() - start_time
                return result
            
            # 3. LLM - analisar e extrair perfil
            combined_text = f"--- {result.discovery_url} ---\n{markdown}\n--- FIM ---"
            profile = await analyze_content(combined_text)
            
            if profile:
                result.llm_success = True
                result.profile_data = profile.model_dump() if hasattr(profile, 'model_dump') else {}
                
                # Calcular completude (estrutura aninhada)
                filled = self._count_filled_fields(profile)
                
                result.profile_fields_filled = filled
                result.profile_fields_total = self.TOTAL_FIELDS
                result.profile_completeness = (filled / self.TOTAL_FIELDS) * 100
                
                result.success = True
            else:
                result.error = "LLM: Falha na análise"
        
        except asyncio.TimeoutError:
            result.error = "Timeout: Tempo excedido"
        except Exception as e:
            result.error = f"Erro: {str(e)[:100]}"
        
        result.duration_seconds = time.perf_counter() - start_time
        return result
    
    async def run_batch(
        self, 
        empresas: List[EmpresaData],
        progress_callback: callable = None
    ) -> List[TestResult]:
        """Processa um lote de empresas com concorrência limitada."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = []
        
        async def process_with_semaphore(empresa: EmpresaData, idx: int):
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        self.process_empresa(empresa),
                        timeout=self.timeout_per_empresa
                    )
                except asyncio.TimeoutError:
                    result = TestResult(
                        empresa=empresa,
                        success=False,
                        duration_seconds=self.timeout_per_empresa,
                        error="Timeout global"
                    )
                
                if progress_callback:
                    progress_callback(idx + 1, len(empresas), result)
                
                return result
        
        tasks = [
            process_with_semaphore(empresa, idx) 
            for idx, empresa in enumerate(empresas)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Tratar exceções
        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(TestResult(
                    empresa=empresas[i],
                    success=False,
                    duration_seconds=0,
                    error=str(r)[:100]
                ))
            else:
                final_results.append(r)
        
        return final_results
    
    def calculate_metrics(self):
        """Calcula métricas consolidadas."""
        if not self.results:
            return
        
        self.metrics.total_processadas = len(self.results)
        self.metrics.total_sucesso = sum(1 for r in self.results if r.success)
        self.metrics.total_falha = self.metrics.total_processadas - self.metrics.total_sucesso
        
        # Por etapa
        self.metrics.discovery_sucesso = sum(1 for r in self.results if r.discovery_success)
        self.metrics.scrape_sucesso = sum(1 for r in self.results if r.scrape_success)
        self.metrics.llm_sucesso = sum(1 for r in self.results if r.llm_success)
        
        # Tempos (apenas para sucessos)
        success_times = [r.duration_seconds for r in self.results if r.success]
        if success_times:
            self.metrics.tempo_total_segundos = sum(r.duration_seconds for r in self.results)
            self.metrics.tempo_medio_segundos = sum(success_times) / len(success_times)
            self.metrics.tempo_minimo_segundos = min(success_times)
            self.metrics.tempo_maximo_segundos = max(success_times)
        
        # Completude
        completeness_values = [r.profile_completeness for r in self.results if r.success]
        if completeness_values:
            self.metrics.completude_media = sum(completeness_values) / len(completeness_values)
            self.metrics.completude_minima = min(completeness_values)
            self.metrics.completude_maxima = max(completeness_values)
        
        # Erros
        for r in self.results:
            if r.error:
                error_type = r.error.split(':')[0] if ':' in r.error else 'Outro'
                self.metrics.erros_por_tipo[error_type] = self.metrics.erros_por_tipo.get(error_type, 0) + 1
    
    async def run_stress_test(
        self,
        limit: Optional[int] = None,
        verbose: bool = True
    ) -> StressTestMetrics:
        """
        Executa o stress test completo.
        
        Args:
            limit: Limitar número de empresas (None = todas)
            verbose: Mostrar progresso
        
        Returns:
            Métricas consolidadas
        """
        logger.info("=" * 60)
        logger.info("STRESS TEST - Dados Reais de Empresas")
        logger.info("=" * 60)
        
        # Carregar dados
        self.load_empresas(limit)
        
        if not self.empresas:
            logger.error("Nenhuma empresa carregada!")
            return self.metrics
        
        def progress(current, total, result):
            if verbose:
                status = "✅" if result.success else "❌"
                logger.info(
                    f"[{current}/{total}] {status} {result.empresa.nome_fantasia[:30]:<30} "
                    f"| {result.duration_seconds:.1f}s | {result.profile_completeness:.0f}%"
                )
        
        logger.info(f"Processando {len(self.empresas)} empresas (concorrência: {self.max_concurrent})")
        logger.info("-" * 60)
        
        start_time = time.perf_counter()
        
        # Processar em lotes
        self.results = await self.run_batch(self.empresas, progress)
        
        total_time = time.perf_counter() - start_time
        
        # Calcular métricas
        self.calculate_metrics()
        
        # Mostrar resultados
        logger.info("=" * 60)
        logger.info("RESULTADOS")
        logger.info("=" * 60)
        logger.info(f"Tempo total: {total_time:.1f}s")
        logger.info(f"Empresas processadas: {self.metrics.total_processadas}")
        logger.info(f"Sucesso: {self.metrics.total_sucesso} ({self.metrics.taxa_sucesso:.1f}%)")
        logger.info(f"Falha: {self.metrics.total_falha}")
        logger.info("-" * 60)
        logger.info("Por etapa:")
        logger.info(f"  Discovery: {self.metrics.discovery_sucesso}")
        logger.info(f"  Scrape: {self.metrics.scrape_sucesso}")
        logger.info(f"  LLM: {self.metrics.llm_sucesso}")
        logger.info("-" * 60)
        logger.info("Tempos (sucessos):")
        logger.info(f"  Médio: {self.metrics.tempo_medio_segundos:.1f}s")
        logger.info(f"  Mínimo: {self.metrics.tempo_minimo_segundos:.1f}s")
        logger.info(f"  Máximo: {self.metrics.tempo_maximo_segundos:.1f}s")
        logger.info("-" * 60)
        logger.info("Completude:")
        logger.info(f"  Média: {self.metrics.completude_media:.1f}%")
        logger.info(f"  Mínima: {self.metrics.completude_minima:.1f}%")
        logger.info(f"  Máxima: {self.metrics.completude_maxima:.1f}%")
        
        if self.metrics.erros_por_tipo:
            logger.info("-" * 60)
            logger.info("Erros por tipo:")
            for error_type, count in sorted(self.metrics.erros_por_tipo.items(), key=lambda x: -x[1]):
                logger.info(f"  {error_type}: {count}")
        
        logger.info("=" * 60)
        if self.metrics.aprovado:
            logger.info("✅ APROVADO - Todos os critérios atendidos!")
        else:
            logger.info("❌ REPROVADO - Critérios não atendidos:")
            if self.metrics.tempo_medio_segundos > 90:
                logger.info(f"  - Tempo médio ({self.metrics.tempo_medio_segundos:.1f}s) > 90s")
            if self.metrics.taxa_sucesso < 70:
                logger.info(f"  - Taxa sucesso ({self.metrics.taxa_sucesso:.1f}%) < 70%")
            if self.metrics.completude_media < 60:
                logger.info(f"  - Completude ({self.metrics.completude_media:.1f}%) < 60%")
        logger.info("=" * 60)
        
        return self.metrics
    
    def save_report(self, output_file: str = "tests/reports/stress_test_report.json"):
        """Salva relatório detalhado em JSON."""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "config": {
                "data_file": self.data_file,
                "max_concurrent": self.max_concurrent,
                "timeout_per_empresa": self.timeout_per_empresa,
                "total_empresas": self.metrics.total_empresas
            },
            "metrics": {
                "total_empresas": self.metrics.total_empresas,
                "total_processadas": self.metrics.total_processadas,
                "total_sucesso": self.metrics.total_sucesso,
                "total_falha": self.metrics.total_falha,
                "taxa_sucesso": self.metrics.taxa_sucesso,
                "tempo_medio_segundos": self.metrics.tempo_medio_segundos,
                "tempo_minimo_segundos": self.metrics.tempo_minimo_segundos if self.metrics.tempo_minimo_segundos != float('inf') else 0,
                "tempo_maximo_segundos": self.metrics.tempo_maximo_segundos,
                "completude_media": self.metrics.completude_media,
                "discovery_sucesso": self.metrics.discovery_sucesso,
                "scrape_sucesso": self.metrics.scrape_sucesso,
                "llm_sucesso": self.metrics.llm_sucesso,
                "erros_por_tipo": self.metrics.erros_por_tipo,
                "aprovado": self.metrics.aprovado
            },
            "results": [
                {
                    "empresa": {
                        "cnpj": r.empresa.cnpj_basico,
                        "nome_fantasia": r.empresa.nome_fantasia,
                        "site_original": r.empresa.site
                    },
                    "success": r.success,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error,
                    "discovery_url": r.discovery_url,
                    "scrape_chars": r.scrape_chars,
                    "scrape_pages": r.scrape_pages,
                    "profile_completeness": r.profile_completeness,
                    "profile_fields_filled": r.profile_fields_filled
                }
                for r in self.results
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Relatório salvo em: {output_file}")
        
        # Salvar também log detalhado para análise
        try:
            from tests.suites.test_analyzer import test_analyzer
            test_id = f"stress_{len(self.empresas)}_{datetime.now().strftime('%H%M%S')}"
            test_analyzer.save_detailed_log(
                test_id=test_id,
                config=report["config"],
                metrics=report["metrics"],
                results=report["results"]
            )
        except Exception as e:
            logger.warning(f"Não foi possível salvar log detalhado: {e}")


async def run_production_test(n: int = 50, timeout: float = 120.0):
    """
    Executa teste em modo PRODUÇÃO.
    
    - Ignora site cadastrado
    - Força Discovery completo (Serper + LLM)
    - Concorrência = número de empresas
    - Timeout: 120s (Discovery=60s + Scrape+LLM=60s)
    """
    test = StressTestEmpresas(
        max_concurrent=n,  # Concorrência = empresas
        timeout_per_empresa=timeout,
        production_mode=True  # Ignora site cadastrado
    )
    await test.run_stress_test(limit=n)
    test.save_report("tests/reports/production_test_report.json")
    return test.metrics


async def run_quick_test(n: int = 5, timeout: float = 90.0):
    """Executa teste rápido em modo produção."""
    return await run_production_test(n, timeout)


async def run_full_test(timeout: float = 90.0):
    """Executa teste completo com 300 empresas (modo produção)."""
    return await run_production_test(300, timeout)


async def run_stress_500(timeout: float = 90.0):
    """Executa stress test com 500 empresas simultâneas (modo produção)."""
    # Para 500 empresas, precisaríamos de mais dados
    # Por enquanto, usa o máximo disponível (300)
    return await run_production_test(300, timeout)


if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("STRESS TEST - MODO PRODUÇÃO")
    print("="*60)
    print("• Ignora site cadastrado")
    print("• Força Discovery completo (Serper + LLM)")
    print("• Concorrência = número de empresas")
    print("• Timeout: 120s por empresa")
    print("="*60)
    
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
        timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
        asyncio.run(run_production_test(n, timeout))
    else:
        # Default: 50 empresas em modo produção
        asyncio.run(run_production_test(50, 120.0))

