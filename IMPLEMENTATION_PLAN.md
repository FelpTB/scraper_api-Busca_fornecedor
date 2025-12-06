# 📋 PLANO DE IMPLEMENTAÇÃO v2.0
## Sistema de Construção de Perfis de Empresas B2B

**Data:** 2025-12-05  
**Baseado no:** PRD.md v2.0  
**Estimativa Total:** 11 semanas  
**Critério Final:** Stress Test 500 empresas em paralelo, tempo médio ≤ 90s

---

## 📁 ESTRUTURA DE ARQUIVOS PROPOSTA

### Princípios de Organização
- **Máximo 500 linhas por arquivo**
- **Nomes autoexplicativos** (um não-dev entenderia)
- **Sem comentários extensos** - código deve ser autoexplicativo
- **Arquivos pequenos e focados** - uma responsabilidade por arquivo

### Nova Estrutura de Diretórios

```
app/
├── main.py                              # Entrada da API FastAPI (~100 linhas)
│
├── api/                                 # Endpoints da API
│   ├── __init__.py
│   ├── analyze_endpoint.py              # Endpoint /analyze (~150 linhas)
│   └── health_endpoint.py               # Endpoints de saúde (~50 linhas)
│
├── core/                                # Configurações centrais
│   ├── __init__.py
│   ├── config.py                        # Variáveis de ambiente (~100 linhas)
│   ├── constants.py                     # Constantes globais (~50 linhas)
│   └── exceptions.py                    # Exceções customizadas (~80 linhas)
│
├── models/                              # Modelos de dados
│   ├── __init__.py
│   ├── company_profile.py               # Modelo CompanyProfile (~200 linhas)
│   ├── scraper_models.py                # SiteProfile, ScrapingStrategy (~150 linhas)
│   ├── llm_models.py                    # LLMRequest, LLMResponse (~100 linhas)
│   └── learning_models.py               # FailureRecord, SiteKnowledge (~150 linhas)
│
├── services/                            # Serviços principais
│   │
│   ├── discovery/                       # Módulo de descoberta de sites
│   │   ├── __init__.py
│   │   ├── discovery_service.py         # Orquestrador do discovery (~200 linhas)
│   │   ├── google_search.py             # Busca no Google/Serper (~150 linhas)
│   │   └── url_validator.py             # Validação de URLs (~100 linhas)
│   │
│   ├── scraper/                         # Módulo de scraping (REFATORADO)
│   │   ├── __init__.py
│   │   ├── scraper_service.py           # Orquestrador principal (~300 linhas)
│   │   ├── site_analyzer.py             # Análise pré-scrape (~200 linhas)
│   │   ├── protection_detector.py       # Detecta Cloudflare/WAF (~150 linhas)
│   │   ├── strategy_selector.py         # Seleciona estratégia (~150 linhas)
│   │   ├── url_prober.py                # Probe paralelo de URLs (~150 linhas)
│   │   ├── http_client.py               # Cliente HTTP (curl_cffi) (~200 linhas)
│   │   ├── html_parser.py               # Parser de HTML (~200 linhas)
│   │   ├── link_extractor.py            # Extração de links (~150 linhas)
│   │   ├── subpage_scraper.py           # Scrape de subpáginas (~200 linhas)
│   │   └── circuit_breaker.py           # Circuit breaker (~100 linhas)
│   │
│   ├── llm/                             # Módulo de LLM (REFATORADO)
│   │   ├── __init__.py
│   │   ├── llm_service.py               # Orquestrador principal (~300 linhas)
│   │   ├── provider_manager.py          # Gerencia provedores (~200 linhas)
│   │   ├── queue_manager.py             # Fila de requisições (~200 linhas)
│   │   ├── rate_limiter.py              # Token bucket rate limit (~150 linhas)
│   │   ├── health_monitor.py            # Monitor de saúde (~150 linhas)
│   │   ├── content_chunker.py           # Divide conteúdo em chunks (~150 linhas)
│   │   ├── profile_merger.py            # Merge de perfis parciais (~200 linhas)
│   │   ├── response_normalizer.py       # Normaliza respostas (~150 linhas)
│   │   └── prompts.py                   # Templates de prompts (~100 linhas)
│   │
│   ├── agents/                          # Agentes especializados (NOVO)
│   │   ├── __init__.py
│   │   ├── agent_orchestrator.py        # Orquestra todos os agentes (~200 linhas)
│   │   ├── identity_agent.py            # Extrai identidade da empresa (~150 linhas)
│   │   ├── offerings_agent.py           # Extrai produtos/serviços (~150 linhas)
│   │   ├── contact_agent.py             # Extrai contatos (~150 linhas)
│   │   ├── reputation_agent.py          # Extrai certificações/parceiros (~150 linhas)
│   │   └── synthesizer_agent.py         # Consolida todos os dados (~200 linhas)
│   │
│   └── learning/                        # Learning Engine (NOVO)
│       ├── __init__.py
│       ├── failure_tracker.py           # Rastreia falhas (~200 linhas)
│       ├── pattern_analyzer.py          # Analisa padrões (~200 linhas)
│       ├── config_optimizer.py          # Sugere otimizações (~150 linhas)
│       └── site_knowledge.py            # Base de conhecimento (~150 linhas)
│
├── schemas/                             # Schemas Pydantic (NOVO)
│   ├── __init__.py
│   ├── identity_schema.py               # Schema de identidade (~80 linhas)
│   ├── classification_schema.py         # Schema de classificação (~60 linhas)
│   ├── offerings_schema.py              # Schema de produtos/serviços (~80 linhas)
│   ├── contact_schema.py                # Schema de contatos (~80 linhas)
│   └── reputation_schema.py             # Schema de reputação (~60 linhas)
│
└── utils/                               # Utilitários
    ├── __init__.py
    ├── text_cleaner.py                  # Limpeza de texto (~100 linhas)
    ├── url_utils.py                     # Funções de URL (~100 linhas)
    ├── async_helpers.py                 # Helpers para asyncio (~100 linhas)
    └── metrics_logger.py                # Log de métricas (~100 linhas)

tests/
├── __init__.py
├── conftest.py                          # Fixtures do pytest (~100 linhas)
│
├── unit/                                # Testes unitários
│   ├── test_protection_detector.py
│   ├── test_strategy_selector.py
│   ├── test_rate_limiter.py
│   ├── test_content_chunker.py
│   └── test_profile_merger.py
│
├── integration/                         # Testes de integração
│   ├── test_scraper_service.py
│   ├── test_llm_service.py
│   └── test_agent_orchestrator.py
│
├── suites/                              # Suites de teste
│   ├── scraper_test_suite.py            # 500 sites (~300 linhas)
│   ├── llm_test_suite.py                # 300 scrapes (~300 linhas)
│   └── stress_test_500.py               # STRESS TEST FINAL (~400 linhas)
│
└── data/                                # Dados de teste
    ├── empresas_500.json                # Lista de 500 empresas
    ├── sample_scrapes/                  # Scrapes de exemplo
    └── expected_profiles/               # Perfis esperados (ground truth)
```

---

## 🚀 FASE 1: PREPARAÇÃO E LIMPEZA (Semana 1)

### Objetivo
Preparar o ambiente, criar estrutura de arquivos e remover código legado.

---

### TAREFA 1.1: Criar Nova Estrutura de Diretórios

**Arquivo:** Estrutura de pastas

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 1.1.1 | Criar pasta `app/api/` | Mover endpoints para pasta dedicada | 30min |
| 1.1.2 | Criar pasta `app/services/discovery/` | Estrutura para discovery | 15min |
| 1.1.3 | Criar pasta `app/services/scraper/` | Estrutura para scraper | 15min |
| 1.1.4 | Criar pasta `app/services/llm/` | Estrutura para LLM | 15min |
| 1.1.5 | Criar pasta `app/services/agents/` | Estrutura para agentes | 15min |
| 1.1.6 | Criar pasta `app/services/learning/` | Estrutura para learning | 15min |
| 1.1.7 | Criar pasta `app/schemas/` | Estrutura para schemas | 15min |
| 1.1.8 | Criar pasta `tests/suites/` | Estrutura para test suites | 15min |

**Teste de Validação:**
```bash
# Verificar estrutura criada
find app -type d | sort
# Deve listar todas as pastas esperadas
```

---

### TAREFA 1.2: Remover Módulo de Documentos (PDF/DOC)

**Arquivos a modificar:** `app/services/`, `app/main.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 1.2.1 | Identificar código PDF | Localizar todas referências a PyMuPDF, fitz | 30min |
| 1.2.2 | Remover `document_processor.py` | Deletar arquivo se existir | 5min |
| 1.2.3 | Remover imports de PDF | Limpar imports em `main.py` e outros | 30min |
| 1.2.4 | Remover chamadas de PDF | Remover calls em `process_analysis()` | 30min |
| 1.2.5 | Remover dependências | Tirar PyMuPDF do `requirements.txt` | 10min |
| 1.2.6 | Atualizar testes | Remover testes relacionados a PDF | 30min |

**Teste de Validação:**
```bash
# Buscar referências a PDF (deve retornar vazio)
grep -r "PyMuPDF\|fitz\|\.pdf" app/ --include="*.py"
# Verificar imports
python -c "from app.main import app"  # Deve importar sem erro
```

---

### TAREFA 1.3: Remover Código de Browser Headless

**Arquivos a modificar:** `app/services/scraper.py`, `requirements.txt`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 1.3.1 | Identificar código Playwright | Localizar todas referências | 30min |
| 1.3.2 | Remover imports Playwright | Limpar imports | 15min |
| 1.3.3 | Remover estratégia HEADLESS | Deletar código de estratégia headless | 30min |
| 1.3.4 | Remover Crawl4AI | Limpar código de crawl4ai | 30min |
| 1.3.5 | Remover dependências | Tirar playwright, crawl4ai do requirements | 10min |
| 1.3.6 | Atualizar fallbacks | Ajustar fallbacks para não usar headless | 30min |

**Teste de Validação:**
```bash
# Buscar referências a browser headless (deve retornar vazio)
grep -r "playwright\|crawl4ai\|selenium\|puppeteer" app/ --include="*.py"
# Verificar requirements
cat requirements.txt | grep -i playwright  # Deve retornar vazio
```

---

### TAREFA 1.4: Dividir Arquivo `scraper.py` (>500 linhas)

**Arquivo original:** `app/services/scraper.py`  
**Arquivos resultantes:** 10 arquivos em `app/services/scraper/`

| # | Subtarefa | Descrição | Linhas aprox. | Estimativa |
|---|-----------|-----------|---------------|------------|
| 1.4.1 | Extrair `circuit_breaker.py` | Funções `_record_failure`, `_record_success`, `_is_circuit_open` | ~100 | 1h |
| 1.4.2 | Extrair `http_client.py` | Funções `_cffi_scrape*`, `_system_curl_scrape*` | ~200 | 1h |
| 1.4.3 | Extrair `protection_detector.py` | Função `_is_cloudflare_challenge`, detectores WAF | ~150 | 1h |
| 1.4.4 | Extrair `html_parser.py` | Funções `_parse_html`, `_is_soft_404` | ~200 | 1h |
| 1.4.5 | Extrair `link_extractor.py` | Funções `_extract_links_html`, `_filter_non_html_links` | ~150 | 1h |
| 1.4.6 | Extrair `subpage_scraper.py` | Lógica de scrape de subpáginas | ~200 | 1h |
| 1.4.7 | Criar `scraper_service.py` | Orquestrador principal `scrape_url` | ~300 | 2h |
| 1.4.8 | Atualizar imports | Corrigir todos os imports | 1h |
| 1.4.9 | Deletar `scraper.py` original | Após validar que tudo funciona | 10min |

**Teste de Validação:**
```bash
# Verificar que cada arquivo tem menos de 500 linhas
wc -l app/services/scraper/*.py
# Executar testes existentes
pytest tests/ -v
```

---

### TAREFA 1.5: Dividir Arquivo `llm.py` (>500 linhas)

**Arquivo original:** `app/services/llm.py`  
**Arquivos resultantes:** 9 arquivos em `app/services/llm/`

| # | Subtarefa | Descrição | Linhas aprox. | Estimativa |
|---|-----------|-----------|---------------|------------|
| 1.5.1 | Extrair `content_chunker.py` | Funções `chunk_content`, `_split_large_page` | ~150 | 1h |
| 1.5.2 | Extrair `profile_merger.py` | Função `merge_profiles` e helpers | ~200 | 1h |
| 1.5.3 | Extrair `response_normalizer.py` | Função `normalize_llm_response` | ~150 | 1h |
| 1.5.4 | Extrair `health_monitor.py` | Classe `LLMPerformanceTracker`, `periodic_health_monitor` | ~150 | 1h |
| 1.5.5 | Extrair `prompts.py` | Constantes SYSTEM_PROMPT, EXTRACTION_PROMPT | ~100 | 30min |
| 1.5.6 | Criar `llm_service.py` | Orquestrador principal `analyze_content` | ~300 | 2h |
| 1.5.7 | Atualizar imports | Corrigir todos os imports | 1h |
| 1.5.8 | Deletar `llm.py` original | Após validar que tudo funciona | 10min |

**Teste de Validação:**
```bash
# Verificar que cada arquivo tem menos de 500 linhas
wc -l app/services/llm/*.py
# Executar testes existentes
pytest tests/ -v
```

---

### TAREFA 1.6: Criar Arquivo de Constantes

**Arquivo:** `app/core/constants.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 1.6.1 | Extrair constantes de scraper | `_DEFAULT_HEADERS`, timeouts, etc | 30min |
| 1.6.2 | Extrair constantes de LLM | `_llm_config`, semáforos, etc | 30min |
| 1.6.3 | Centralizar User-Agents | Lista de user-agents para rotação | 15min |
| 1.6.4 | Centralizar assinaturas | CLOUDFLARE_SIGNATURES, WAF_SIGNATURES | 15min |

**Teste de Validação:**
```python
# Deve importar sem erro
from app.core.constants import DEFAULT_HEADERS, CLOUDFLARE_SIGNATURES
```

---

### 🧹 LIMPEZA FIM DA FASE 1

| # | Verificação | Comando |
|---|-------------|---------|
| 1 | Sem código PDF | `grep -r "fitz\|PyMuPDF" app/` → vazio |
| 2 | Sem código headless | `grep -r "playwright\|crawl4ai" app/` → vazio |
| 3 | Arquivos < 500 linhas | `wc -l app/**/*.py` → todos < 500 |
| 4 | Imports funcionando | `python -c "from app.main import app"` → OK |
| 5 | Testes passando | `pytest tests/ -v` → todos verdes |

---

## 🔍 FASE 2: SCRAPER ADAPTATIVO (Semanas 2-3)

### Objetivo
Implementar scraper que se adapta ao tipo de site automaticamente.

---

### TAREFA 2.1: Implementar Site Analyzer

**Arquivo:** `app/services/scraper/site_analyzer.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.1.1 | Criar classe `SiteAnalyzer` | Estrutura básica com async | 1h |
| 2.1.2 | Implementar `analyze()` | Método principal que retorna SiteProfile | 2h |
| 2.1.3 | Implementar `_check_response_time()` | Mede latência média (3 requests) | 1h |
| 2.1.4 | Implementar `_detect_site_type()` | Detecta SPA/static/hybrid | 2h |
| 2.1.5 | Implementar `_check_robots_txt()` | Verifica regras do robots.txt | 1h |
| 2.1.6 | Criar modelo `SiteProfile` | Dataclass com atributos de análise | 30min |

**Código de Referência:**
```python
# app/services/scraper/site_analyzer.py
from dataclasses import dataclass
from enum import Enum

class SiteType(Enum):
    STATIC = "static"
    SPA = "spa"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

@dataclass
class SiteProfile:
    url: str
    response_time_ms: float
    site_type: SiteType
    protection_type: str  # "none", "cloudflare", "waf", "captcha"
    requires_javascript: bool
    best_strategy: str
    valid_url_variations: list[str]

class SiteAnalyzer:
    async def analyze(self, url: str, timeout: float = 5.0) -> SiteProfile:
        """Analisa site e retorna perfil com recomendações."""
        pass
```

**Testes:**
```python
# tests/unit/test_site_analyzer.py
async def test_analyze_static_site():
    analyzer = SiteAnalyzer()
    profile = await analyzer.analyze("https://example.com")
    assert profile.site_type == SiteType.STATIC
    assert profile.protection_type == "none"

async def test_analyze_cloudflare_site():
    # Mock de resposta Cloudflare
    pass
```

---

### TAREFA 2.2: Implementar Protection Detector

**Arquivo:** `app/services/scraper/protection_detector.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.2.1 | Criar classe `ProtectionDetector` | Estrutura com assinaturas | 1h |
| 2.2.2 | Implementar `detect()` | Retorna tipo de proteção | 2h |
| 2.2.3 | Implementar `_check_cloudflare()` | Detecta Cloudflare por headers/body | 1h |
| 2.2.4 | Implementar `_check_waf()` | Detecta WAF genérico | 1h |
| 2.2.5 | Implementar `_check_captcha()` | Detecta reCAPTCHA, hCaptcha | 1h |
| 2.2.6 | Implementar `_check_rate_limit()` | Detecta rate limiting | 30min |

**Código de Referência:**
```python
# app/services/scraper/protection_detector.py
from enum import Enum

class ProtectionType(Enum):
    NONE = "none"
    CLOUDFLARE = "cloudflare"
    WAF = "waf"
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"

class ProtectionDetector:
    CLOUDFLARE_SIGNATURES = [
        "cf-browser-verification",
        "cf_chl_opt",
        "just a moment",
        "ray id:",
    ]
    
    async def detect(self, response_headers: dict, response_body: str) -> ProtectionType:
        """Detecta tipo de proteção baseado em resposta."""
        pass
```

**Testes:**
```python
# tests/unit/test_protection_detector.py
def test_detect_cloudflare():
    detector = ProtectionDetector()
    body = "Please wait while we verify your browser... Ray ID: abc123"
    result = detector.detect({}, body)
    assert result == ProtectionType.CLOUDFLARE
```

---

### TAREFA 2.3: Implementar Strategy Selector

**Arquivo:** `app/services/scraper/strategy_selector.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.3.1 | Criar enum `ScrapingStrategy` | FAST, STANDARD, ROBUST, AGGRESSIVE | 30min |
| 2.3.2 | Criar classe `StrategySelector` | Estrutura básica | 30min |
| 2.3.3 | Implementar `select()` | Retorna lista ordenada de estratégias | 2h |
| 2.3.4 | Implementar regras por proteção | Lógica para cada tipo de proteção | 2h |
| 2.3.5 | Implementar regras por site_type | Lógica para SPA vs static | 1h |

**Código de Referência:**
```python
# app/services/scraper/strategy_selector.py
from enum import Enum

class ScrapingStrategy(Enum):
    FAST = "fast"           # curl_cffi sem proxy, timeout 10s
    STANDARD = "standard"   # curl_cffi com proxy, timeout 15s
    ROBUST = "robust"       # System curl com retry, timeout 20s
    AGGRESSIVE = "aggressive"  # curl_cffi + UA rotation + proxy rotation

class StrategySelector:
    def select(self, site_profile: SiteProfile) -> list[ScrapingStrategy]:
        """
        Retorna estratégias ordenadas por prioridade.
        Para Cloudflare: [AGGRESSIVE, ROBUST, STANDARD]
        Para sites normais: [FAST, STANDARD, ROBUST]
        """
        pass
```

**Testes:**
```python
# tests/unit/test_strategy_selector.py
def test_select_for_cloudflare():
    selector = StrategySelector()
    profile = SiteProfile(protection_type="cloudflare", ...)
    strategies = selector.select(profile)
    assert strategies[0] == ScrapingStrategy.AGGRESSIVE
```

---

### TAREFA 2.4: Implementar URL Prober

**Arquivo:** `app/services/scraper/url_prober.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.4.1 | Criar classe `URLProber` | Estrutura com semáforo | 30min |
| 2.4.2 | Implementar `_generate_variations()` | Gera https/http, www/non-www | 1h |
| 2.4.3 | Implementar `probe()` | Testa variações em paralelo | 2h |
| 2.4.4 | Implementar `_test_url()` | Testa uma URL específica | 1h |
| 2.4.5 | Retornar melhor URL | Primeira que responde com sucesso | 30min |

**Código de Referência:**
```python
# app/services/scraper/url_prober.py
import asyncio

class URLProber:
    def __init__(self, timeout: float = 3.0, max_concurrent: int = 4):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def probe(self, base_url: str) -> tuple[str, float]:
        """
        Testa variações de URL em paralelo.
        Retorna (melhor_url, tempo_resposta) ou raise URLNotReachable.
        """
        variations = self._generate_variations(base_url)
        # Executar em paralelo...
```

**Testes:**
```python
# tests/unit/test_url_prober.py
async def test_probe_selects_fastest():
    prober = URLProber()
    best_url, response_time = await prober.probe("example.com")
    assert best_url.startswith("http")
    assert response_time > 0
```

---

### TAREFA 2.5: Refatorar Scraper Service

**Arquivo:** `app/services/scraper/scraper_service.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.5.1 | Criar classe `ScraperService` | Injeta dependências | 1h |
| 2.5.2 | Implementar `scrape()` | Método principal orquestrador | 3h |
| 2.5.3 | Integrar SiteAnalyzer | Chamar analyze antes de scrape | 1h |
| 2.5.4 | Integrar StrategySelector | Selecionar estratégia baseado em profile | 1h |
| 2.5.5 | Implementar fallback em cascata | Tentar próxima estratégia se falhar | 2h |
| 2.5.6 | Implementar retry com backoff | Exponential backoff entre retries | 1h |
| 2.5.7 | Integrar circuit breaker | Usar circuit breaker por domínio | 1h |

**Código de Referência:**
```python
# app/services/scraper/scraper_service.py
class ScraperService:
    def __init__(
        self,
        site_analyzer: SiteAnalyzer,
        protection_detector: ProtectionDetector,
        strategy_selector: StrategySelector,
        url_prober: URLProber,
    ):
        self.site_analyzer = site_analyzer
        self.protection_detector = protection_detector
        self.strategy_selector = strategy_selector
        self.url_prober = url_prober
    
    async def scrape(self, url: str, max_subpages: int = 30) -> ScrapedContent:
        """
        Fluxo:
        1. Probe URL (encontrar melhor variação)
        2. Analisar site (detectar proteção)
        3. Selecionar estratégia
        4. Scrape main page
        5. Extrair links
        6. Scrape subpages em paralelo
        7. Consolidar conteúdo
        """
        pass
```

**Testes:**
```python
# tests/integration/test_scraper_service.py
async def test_scrape_static_site():
    service = ScraperService(...)
    result = await service.scrape("https://example.com")
    assert result.main_page_content
    assert len(result.subpages) >= 0
```

---

### TAREFA 2.6: Criar Scraper Test Suite

**Arquivo:** `tests/suites/scraper_test_suite.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 2.6.1 | Coletar 500 URLs de teste | Dividir por categoria | 4h |
| 2.6.2 | Criar estrutura do teste | Classe ScraperTestSuite | 1h |
| 2.6.3 | Implementar `run_full_suite()` | Executa todos os testes | 2h |
| 2.6.4 | Implementar métricas | Coletar tempo, sucesso, estratégia | 2h |
| 2.6.5 | Implementar relatório | Gerar relatório JSON/HTML | 2h |

**Teste de Validação da Fase:**
```bash
# Executar suite de scraper
python -m tests.suites.scraper_test_suite
# Meta: Taxa de sucesso > 85%
```

---

### 🧹 LIMPEZA FIM DA FASE 2

| # | Verificação | Ação |
|---|-------------|------|
| 1 | Arquivo `scraper.py` original | DELETAR se ainda existir |
| 2 | Funções não utilizadas | Buscar com `grep` e remover |
| 3 | Imports não utilizados | Usar `autoflake` ou manual |
| 4 | Variáveis globais órfãs | Mover para constants.py ou remover |
| 5 | Comentários TODO antigos | Remover ou resolver |

```bash
# Encontrar código morto
vulture app/services/scraper/

# Remover imports não usados
autoflake --remove-all-unused-imports --in-place app/services/scraper/*.py
```

---

## 🤖 FASE 3: LLM MANAGER v2.0 (Semanas 4-5)

### Objetivo
Implementar gerenciamento inteligente de LLM com múltiplos provedores.

---

### TAREFA 3.1: Implementar Rate Limiter (Token Bucket)

**Arquivo:** `app/services/llm/rate_limiter.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.1.1 | Criar classe `TokenBucket` | Implementa algoritmo token bucket | 2h |
| 3.1.2 | Implementar `acquire()` | Aguarda tokens disponíveis | 1h |
| 3.1.3 | Implementar `_refill()` | Reabastece tokens por tempo | 1h |
| 3.1.4 | Implementar `get_wait_time()` | Retorna tempo de espera estimado | 30min |
| 3.1.5 | Criar `RateLimiter` por provider | Gerencia múltiplos buckets | 1h |

**Código de Referência:**
```python
# app/services/llm/rate_limiter.py
import asyncio
import time

class TokenBucket:
    def __init__(self, tokens_per_minute: int, tokens_per_second: int = None):
        self.tpm = tokens_per_minute
        self.tps = tokens_per_second or (tokens_per_minute // 60)
        self.tokens = self.tpm
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """Aguarda até ter tokens disponíveis ou timeout."""
        pass
    
    def _refill(self):
        """Reabastece tokens baseado no tempo passado."""
        pass
```

**Testes:**
```python
# tests/unit/test_rate_limiter.py
async def test_token_bucket_acquire():
    bucket = TokenBucket(tokens_per_minute=60)
    assert await bucket.acquire(1)  # Deve passar imediatamente
    
async def test_token_bucket_wait():
    bucket = TokenBucket(tokens_per_minute=1)
    await bucket.acquire(1)  # Primeiro passa
    # Segundo deve aguardar
```

---

### TAREFA 3.2: Implementar Health Monitor

**Arquivo:** `app/services/llm/health_monitor.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.2.1 | Criar classe `HealthMonitor` | Estrutura com métricas por provider | 1h |
| 3.2.2 | Implementar `record_success()` | Registra sucesso | 30min |
| 3.2.3 | Implementar `record_failure()` | Registra falha com tipo | 30min |
| 3.2.4 | Implementar `calculate_health_score()` | Calcula score 0-100 | 2h |
| 3.2.5 | Implementar `get_healthy_providers()` | Retorna providers ordenados | 1h |
| 3.2.6 | Implementar `is_provider_healthy()` | Verifica se score > threshold | 30min |

**Código de Referência:**
```python
# app/services/llm/health_monitor.py
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class ProviderMetrics:
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    rate_limits_hit: int = 0
    timeouts: int = 0
    avg_latency_ms: float = 0
    health_score: int = 100

class HealthMonitor:
    def __init__(self, unhealthy_threshold: int = 20):
        self.metrics: dict[str, ProviderMetrics] = defaultdict(ProviderMetrics)
        self.unhealthy_threshold = unhealthy_threshold
    
    def calculate_health_score(self, provider: str) -> int:
        """
        Score = (success_rate * 0.4) + (latency_score * 0.3) + 
                (rate_limit_score * 0.2) + (recency_score * 0.1)
        """
        pass
```

**Testes:**
```python
# tests/unit/test_health_monitor.py
def test_health_score_decreases_on_failures():
    monitor = HealthMonitor()
    monitor.record_success("openai", latency_ms=100)
    score_before = monitor.calculate_health_score("openai")
    
    monitor.record_failure("openai", error_type="timeout")
    score_after = monitor.calculate_health_score("openai")
    
    assert score_after < score_before
```

---

### TAREFA 3.3: Implementar Queue Manager

**Arquivo:** `app/services/llm/queue_manager.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.3.1 | Criar classe `QueueManager` | Gerencia filas por provider | 1h |
| 3.3.2 | Implementar `enqueue()` | Adiciona request à fila | 1h |
| 3.3.3 | Implementar `get_best_provider()` | Seleciona provider ideal | 2h |
| 3.3.4 | Integrar rate_limiter | Verificar tokens antes de enviar | 1h |
| 3.3.5 | Integrar health_monitor | Considerar saúde na seleção | 1h |

**Código de Referência:**
```python
# app/services/llm/queue_manager.py
class QueueManager:
    def __init__(
        self,
        rate_limiter: RateLimiter,
        health_monitor: HealthMonitor,
        providers: list[str],
    ):
        self.rate_limiter = rate_limiter
        self.health_monitor = health_monitor
        self.providers = providers
    
    async def get_best_provider(self, estimated_tokens: int) -> str:
        """
        Seleciona provider baseado em:
        1. Saúde (health_score > threshold)
        2. Disponibilidade (tokens no bucket)
        3. Prioridade configurada
        """
        pass
```

---

### TAREFA 3.4: Implementar Provider Manager

**Arquivo:** `app/services/llm/provider_manager.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.4.1 | Criar classe `ProviderManager` | Gerencia conexões com providers | 1h |
| 3.4.2 | Implementar config do Google | API key, model, base_url | 30min |
| 3.4.3 | Implementar config do OpenAI | API key, model, base_url | 30min |
| 3.4.4 | Implementar config do OpenRouter | API key, model, headers especiais | 1h |
| 3.4.5 | Implementar `call()` | Faz chamada ao provider | 2h |
| 3.4.6 | Implementar retry por provider | Retry com backoff | 1h |

**Código de Referência:**
```python
# app/services/llm/provider_manager.py
from dataclasses import dataclass

@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str
    max_concurrent: int
    priority: int

class ProviderManager:
    def __init__(self, configs: list[ProviderConfig]):
        self.configs = {c.name: c for c in configs}
        self.clients = {}  # Lazy init
    
    async def call(
        self, 
        provider: str, 
        messages: list[dict], 
        timeout: float = 60.0
    ) -> dict:
        """Faz chamada ao provider e retorna resposta."""
        pass
```

---

### TAREFA 3.5: Refatorar LLM Service

**Arquivo:** `app/services/llm/llm_service.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.5.1 | Criar classe `LLMService` | Injeta dependências | 1h |
| 3.5.2 | Implementar `analyze()` | Método principal | 3h |
| 3.5.3 | Integrar content_chunker | Dividir conteúdo se necessário | 1h |
| 3.5.4 | Integrar queue_manager | Selecionar provider | 1h |
| 3.5.5 | Integrar health_monitor | Registrar métricas | 1h |
| 3.5.6 | Implementar fallback entre providers | Tentar outro se falhar | 2h |
| 3.5.7 | Integrar profile_merger | Merge se múltiplos chunks | 1h |

**Código de Referência:**
```python
# app/services/llm/llm_service.py
class LLMService:
    def __init__(
        self,
        provider_manager: ProviderManager,
        queue_manager: QueueManager,
        health_monitor: HealthMonitor,
        content_chunker: ContentChunker,
        profile_merger: ProfileMerger,
    ):
        # Injeção de dependências
        pass
    
    async def analyze(self, content: str, company_info: dict) -> CompanyProfile:
        """
        Fluxo:
        1. Estimar tokens
        2. Dividir em chunks se necessário
        3. Para cada chunk:
           a. Selecionar provider (via queue_manager)
           b. Fazer chamada (via provider_manager)
           c. Registrar métricas (via health_monitor)
           d. Retry/fallback se falhar
        4. Merge chunks se necessário
        5. Validar e retornar CompanyProfile
        """
        pass
```

---

### TAREFA 3.6: Criar LLM Test Suite

**Arquivo:** `tests/suites/llm_test_suite.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 3.6.1 | Coletar 300 scrapes de exemplo | Dividir por tamanho | 4h |
| 3.6.2 | Criar estrutura do teste | Classe LLMTestSuite | 1h |
| 3.6.3 | Implementar `run_full_suite()` | Executa todos os testes | 2h |
| 3.6.4 | Implementar `test_concurrent_load()` | Testa carga simultânea | 2h |
| 3.6.5 | Implementar métricas de qualidade | Comparar com ground truth | 3h |

**Teste de Validação da Fase:**
```bash
# Executar suite de LLM
python -m tests.suites.llm_test_suite
# Meta: Taxa de sucesso > 90%, Rate limits < 5%
```

---

### 🧹 LIMPEZA FIM DA FASE 3

| # | Verificação | Ação |
|---|-------------|------|
| 1 | Arquivo `llm.py` original | DELETAR se ainda existir |
| 2 | Arquivo `llm_balancer.py` | DELETAR - funcionalidade incorporada |
| 3 | Semáforos globais antigos | REMOVER - usar rate_limiter |
| 4 | Funções `_call_llm` antigas | REMOVER - usar provider_manager |
| 5 | Imports httpx diretos | CENTRALIZAR em provider_manager |

```bash
# Verificar arquivos antigos
ls -la app/services/llm*.py  # Deve ter apenas pasta llm/

# Verificar imports não usados
autoflake --check app/services/llm/*.py
```

---

## 🤖 FASE 4: SISTEMA DE AGENTES (Semana 6)

### Objetivo
Implementar arquitetura multi-agente para extração especializada.

---

### TAREFA 4.1: Implementar Agent Orchestrator

**Arquivo:** `app/services/agents/agent_orchestrator.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.1.1 | Criar classe `AgentOrchestrator` | Coordena todos os agentes | 1h |
| 4.1.2 | Implementar `run_pipeline()` | Executa agentes em sequência | 2h |
| 4.1.3 | Implementar contexto compartilhado | Passa dados entre agentes | 1h |
| 4.1.4 | Implementar handling de erros | Continuar mesmo se agente falhar | 1h |

**Código de Referência:**
```python
# app/services/agents/agent_orchestrator.py
class AgentOrchestrator:
    def __init__(
        self,
        identity_agent: IdentityAgent,
        offerings_agent: OfferingsAgent,
        contact_agent: ContactAgent,
        reputation_agent: ReputationAgent,
        synthesizer_agent: SynthesizerAgent,
    ):
        self.agents = [
            ("identity", identity_agent),
            ("offerings", offerings_agent),
            ("contact", contact_agent),
            ("reputation", reputation_agent),
        ]
        self.synthesizer = synthesizer_agent
    
    async def run_pipeline(
        self, 
        content: str, 
        company_info: dict
    ) -> CompanyProfile:
        """
        Executa agentes em sequência:
        1. Identity → context + identity
        2. Offerings → context + offerings
        3. Contact → context + contact
        4. Reputation → context + reputation
        5. Synthesizer → CompanyProfile final
        """
        context = {"content": content, "company_info": company_info}
        
        for name, agent in self.agents:
            try:
                result = await agent.extract(context)
                context[name] = result
            except Exception as e:
                context[name] = None
                # Log error but continue
        
        return await self.synthesizer.synthesize(context)
```

---

### TAREFA 4.2: Implementar Identity Agent

**Arquivo:** `app/services/agents/identity_agent.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.2.1 | Criar classe `IdentityAgent` | Estrutura básica | 30min |
| 4.2.2 | Criar prompt especializado | Focado em identidade | 1h |
| 4.2.3 | Implementar `extract()` | Extrai company_name, description, industry | 2h |
| 4.2.4 | Criar IdentitySchema | Validação Pydantic | 30min |

**Código de Referência:**
```python
# app/services/agents/identity_agent.py
from app.schemas.identity_schema import IdentitySchema

class IdentityAgent:
    PROMPT = """
    Extraia APENAS informações de IDENTIDADE da empresa:
    - company_name: Nome oficial da empresa
    - description: Descrição do que a empresa faz (2-3 frases)
    - industry: Setor/indústria principal
    - business_model: B2B, B2C, B2B2C, etc
    
    Conteúdo do site:
    {content}
    """
    
    async def extract(self, context: dict) -> IdentitySchema:
        """Extrai e valida identidade."""
        pass
```

---

### TAREFA 4.3: Implementar Offerings Agent

**Arquivo:** `app/services/agents/offerings_agent.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.3.1 | Criar classe `OfferingsAgent` | Estrutura básica | 30min |
| 4.3.2 | Criar prompt especializado | Focado em produtos/serviços | 1h |
| 4.3.3 | Implementar `extract()` | Extrai products, services, features | 2h |
| 4.3.4 | Criar OfferingsSchema | Validação Pydantic | 30min |

---

### TAREFA 4.4: Implementar Contact Agent

**Arquivo:** `app/services/agents/contact_agent.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.4.1 | Criar classe `ContactAgent` | Estrutura básica | 30min |
| 4.4.2 | Criar prompt especializado | Focado em contatos | 1h |
| 4.4.3 | Implementar `extract()` | Extrai emails, phones, addresses | 2h |
| 4.4.4 | Criar ContactSchema | Validação Pydantic | 30min |

---

### TAREFA 4.5: Implementar Reputation Agent

**Arquivo:** `app/services/agents/reputation_agent.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.5.1 | Criar classe `ReputationAgent` | Estrutura básica | 30min |
| 4.5.2 | Criar prompt especializado | Focado em reputação | 1h |
| 4.5.3 | Implementar `extract()` | Extrai certifications, partnerships, clients | 2h |
| 4.5.4 | Criar ReputationSchema | Validação Pydantic | 30min |

---

### TAREFA 4.6: Implementar Synthesizer Agent

**Arquivo:** `app/services/agents/synthesizer_agent.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 4.6.1 | Criar classe `SynthesizerAgent` | Estrutura básica | 30min |
| 4.6.2 | Implementar `synthesize()` | Consolida dados de todos os agentes | 2h |
| 4.6.3 | Implementar resolução de conflitos | Quando dados divergem | 1h |
| 4.6.4 | Implementar preenchimento de gaps | Inferir dados faltantes | 1h |
| 4.6.5 | Validar CompanyProfile final | Garantir schema válido | 1h |

**Código de Referência:**
```python
# app/services/agents/synthesizer_agent.py
class SynthesizerAgent:
    async def synthesize(self, context: dict) -> CompanyProfile:
        """
        Consolida dados de todos os agentes:
        1. Combina identity + offerings + contact + reputation
        2. Resolve conflitos (priorizar dados mais completos)
        3. Preenche gaps (inferir se possível)
        4. Valida e retorna CompanyProfile
        """
        pass
```

---

### 🧹 LIMPEZA FIM DA FASE 4

| # | Verificação | Ação |
|---|-------------|------|
| 1 | Funções `analyze_content` antigas | INTEGRAR ou REMOVER |
| 2 | Prompts duplicados | CENTRALIZAR em cada agente |
| 3 | Schemas duplicados | CONSOLIDAR em pasta schemas/ |

---

## 📚 FASE 5: LEARNING ENGINE (Semanas 7-8)

### Objetivo
Implementar sistema de aprendizado com falhas.

---

### TAREFA 5.1: Implementar Failure Tracker

**Arquivo:** `app/services/learning/failure_tracker.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 5.1.1 | Criar classe `FailureTracker` | Estrutura com storage | 1h |
| 5.1.2 | Criar modelo `FailureRecord` | Dataclass com campos | 30min |
| 5.1.3 | Implementar `record()` | Salva falha | 1h |
| 5.1.4 | Implementar `get_by_domain()` | Busca por domínio | 1h |
| 5.1.5 | Implementar `get_patterns()` | Agrupa por tipo | 2h |
| 5.1.6 | Implementar storage JSON | Persistência simples | 1h |

**Código de Referência:**
```python
# app/services/learning/failure_tracker.py
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class FailureRecord:
    timestamp: datetime
    module: str  # "scraper", "llm", "discovery"
    error_type: str
    url: str
    domain: str
    context: dict
    strategy_used: str
    retry_count: int

class FailureTracker:
    def __init__(self, storage_path: str = "data/failures.json"):
        self.storage_path = storage_path
        self.records: list[FailureRecord] = []
        self._load()
    
    def record(self, failure: FailureRecord):
        """Salva nova falha."""
        self.records.append(failure)
        self._save()
```

---

### TAREFA 5.2: Implementar Pattern Analyzer

**Arquivo:** `app/services/learning/pattern_analyzer.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 5.2.1 | Criar classe `PatternAnalyzer` | Analisa padrões de falha | 1h |
| 5.2.2 | Implementar `analyze_scraper_failures()` | Agrupa falhas de scraper | 2h |
| 5.2.3 | Implementar `analyze_llm_failures()` | Agrupa falhas de LLM | 2h |
| 5.2.4 | Implementar `get_recommendations()` | Gera recomendações | 2h |

---

### TAREFA 5.3: Implementar Config Optimizer

**Arquivo:** `app/services/learning/config_optimizer.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 5.3.1 | Criar classe `ConfigOptimizer` | Sugere otimizações | 1h |
| 5.3.2 | Implementar `suggest_scraper_config()` | Otimizações de scraper | 2h |
| 5.3.3 | Implementar `suggest_llm_config()` | Otimizações de LLM | 2h |
| 5.3.4 | Implementar `apply_suggestions()` | Aplica automaticamente | 1h |

---

### TAREFA 5.4: Implementar Site Knowledge Base

**Arquivo:** `app/services/learning/site_knowledge.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 5.4.1 | Criar classe `SiteKnowledgeBase` | Base de conhecimento | 1h |
| 5.4.2 | Criar modelo `SiteKnowledge` | Perfil de site | 30min |
| 5.4.3 | Implementar `add_profile()` | Salva perfil | 1h |
| 5.4.4 | Implementar `get_profile()` | Busca perfil | 30min |
| 5.4.5 | Implementar `get_best_strategy()` | Retorna melhor estratégia | 1h |

**Código de Referência:**
```python
# app/services/learning/site_knowledge.py
@dataclass
class SiteKnowledge:
    domain: str
    protection_type: str
    best_strategy: str
    avg_response_time: float
    success_rate: float
    last_success: datetime
    special_config: dict = None

class SiteKnowledgeBase:
    def __init__(self, storage_path: str = "data/site_knowledge.json"):
        self.storage_path = storage_path
        self.profiles: dict[str, SiteKnowledge] = {}
        self._load()
    
    def get_best_strategy(self, domain: str) -> str:
        """Retorna melhor estratégia ou 'standard' se desconhecido."""
        profile = self.profiles.get(domain)
        return profile.best_strategy if profile else "standard"
```

---

### 🧹 LIMPEZA FIM DA FASE 5

| # | Verificação | Ação |
|---|-------------|------|
| 1 | Logs de falha antigos | MIGRAR para FailureTracker |
| 2 | Configurações hardcoded | MOVER para ConfigOptimizer |
| 3 | Arquivos JSON de teste | ORGANIZAR em data/ |

---

## 🧪 FASE 6: TESTES E VALIDAÇÃO (Semanas 9-10)

### Objetivo
Criar suites de teste completas e validar sistema.

---

### TAREFA 6.1: Preparar Dados de Teste

**Arquivos:** `tests/data/`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 6.1.1 | Coletar 500 empresas brasileiras | CNPJs válidos, sites verificados | 8h |
| 6.1.2 | Criar ground truth | Perfis esperados para 100 empresas | 8h |
| 6.1.3 | Coletar 300 scrapes de exemplo | Conteúdo pré-scraped | 4h |
| 6.1.4 | Organizar por categoria | Dividir por tipo de site | 2h |

---

### TAREFA 6.2: Implementar Scraper Test Suite Final

**Arquivo:** `tests/suites/scraper_test_suite.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 6.2.1 | Refinar categorias de sites | 8 categorias diferentes | 2h |
| 6.2.2 | Implementar baseline comparison | Comparar com versão anterior | 2h |
| 6.2.3 | Implementar relatório detalhado | JSON + HTML | 2h |
| 6.2.4 | Executar suite completa | 500 sites | 4h |
| 6.2.5 | Analisar resultados | Identificar gaps | 2h |

---

### TAREFA 6.3: Implementar LLM Test Suite Final

**Arquivo:** `tests/suites/llm_test_suite.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 6.3.1 | Implementar teste de qualidade | Score de extração | 3h |
| 6.3.2 | Implementar teste de carga | N requisições simultâneas | 2h |
| 6.3.3 | Implementar teste por provider | Isolar cada provider | 2h |
| 6.3.4 | Executar suite completa | 300 scrapes | 4h |
| 6.3.5 | Analisar resultados | Identificar gaps | 2h |

---

### TAREFA 6.4: Implementar Stress Test 500

**Arquivo:** `tests/suites/stress_test_500.py`

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 6.4.1 | Criar estrutura do teste | Classe StressTest500 | 2h |
| 6.4.2 | Implementar `run_stress_test()` | Execução paralela | 4h |
| 6.4.3 | Implementar `calculate_metrics()` | Métricas de sucesso | 2h |
| 6.4.4 | Implementar `calculate_completeness()` | Completude do perfil | 2h |
| 6.4.5 | Implementar `validate_approval()` | Verifica critérios | 1h |
| 6.4.6 | Implementar relatório final | Aprovado/Reprovado | 2h |

---

### TAREFA 6.5: Corrigir Issues Encontrados

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 6.5.1 | Analisar falhas do scraper | Identificar padrões | 4h |
| 6.5.2 | Corrigir issues de scraper | Implementar fixes | 8h |
| 6.5.3 | Analisar falhas do LLM | Identificar padrões | 4h |
| 6.5.4 | Corrigir issues de LLM | Implementar fixes | 8h |
| 6.5.5 | Re-executar testes | Validar correções | 4h |

---

### 🧹 LIMPEZA FIM DA FASE 6

| # | Verificação | Ação |
|---|-------------|------|
| 1 | Testes antigos | REMOVER se redundantes |
| 2 | Mocks não utilizados | REMOVER |
| 3 | Dados de teste temporários | ORGANIZAR ou REMOVER |

---

## ✅ FASE 7: APROVAÇÃO FINAL (Semana 11)

### Objetivo
Executar stress test final e preparar deploy.

---

### TAREFA 7.1: Executar Stress Test Final

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 7.1.1 | Preparar ambiente | Limpar caches, reiniciar serviços | 1h |
| 7.1.2 | Executar stress test | 500 empresas em paralelo | 4h |
| 7.1.3 | Monitorar métricas | CPU, memória, rate limits | durante |
| 7.1.4 | Coletar resultados | Salvar relatório completo | 1h |

---

### TAREFA 7.2: Validar Critérios de Aprovação

| Critério | Meta | Como Verificar |
|----------|------|----------------|
| Tempo médio | ≤ 90s | `metrics.tempo_medio` |
| Taxa de sucesso | ≥ 90% | `metrics.taxa_sucesso` |
| Completude | ≥ 85% | `metrics.completude_media` |
| Crashes | = 0 | Logs de erro |
| Memory leaks | = 0 | Monitoramento de memória |

---

### TAREFA 7.3: Documentar Mudanças

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 7.3.1 | Atualizar README.md | Novas instruções | 2h |
| 7.3.2 | Documentar API | Endpoints e parâmetros | 2h |
| 7.3.3 | Documentar configurações | Variáveis de ambiente | 1h |
| 7.3.4 | Criar CHANGELOG.md | Todas as mudanças da v2.0 | 1h |

---

### TAREFA 7.4: Preparar Deploy

| # | Subtarefa | Descrição | Estimativa |
|---|-----------|-----------|------------|
| 7.4.1 | Atualizar requirements.txt | Versões finais | 30min |
| 7.4.2 | Verificar variáveis de ambiente | Documentar todas | 30min |
| 7.4.3 | Criar script de migração | Se necessário | 2h |
| 7.4.4 | Preparar rollback | Plano de contingência | 1h |

---

### 🧹 LIMPEZA FINAL

| # | Verificação | Comando |
|---|-------------|---------|
| 1 | Sem arquivos TODO | `grep -r "TODO" app/` |
| 2 | Sem prints de debug | `grep -r "print(" app/` |
| 3 | Todos os arquivos < 500 linhas | `wc -l app/**/*.py` |
| 4 | Imports organizados | `isort --check app/` |
| 5 | Código formatado | `black --check app/` |
| 6 | Sem erros de lint | `flake8 app/` |
| 7 | Testes passando | `pytest tests/ -v` |

---

## 📊 RESUMO DO PLANO

| Fase | Semanas | Tarefas | Objetivo Principal |
|------|---------|---------|-------------------|
| 1 | 1 | 6 | Limpeza e estruturação |
| 2 | 2-3 | 6 | Scraper adaptativo |
| 3 | 4-5 | 6 | LLM Manager v2.0 |
| 4 | 6 | 6 | Sistema de agentes |
| 5 | 7-8 | 4 | Learning engine |
| 6 | 9-10 | 5 | Testes e validação |
| 7 | 11 | 4 | Aprovação final |

**Total:** 37 tarefas principais, ~250 subtarefas

---

## 🎯 CHECKLIST DE CONCLUSÃO

- [ ] Todos os arquivos < 500 linhas
- [ ] Nomes de funções autoexplicativos
- [ ] Código sem comentários extensos
- [ ] Módulo PDF removido
- [ ] Módulo headless browser removido
- [ ] Scraper test suite passando (>85%)
- [ ] LLM test suite passando (>90%)
- [ ] **STRESS TEST 500 APROVADO**
- [ ] Documentação atualizada
- [ ] Código limpo (sem TODOs, prints, código morto)

---

*Documento gerado em 2025-12-05. Baseado no PRD.md v2.0*

