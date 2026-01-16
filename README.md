# 🔍 Busca Fornecedor

Sistema de construção automática de perfis de empresas B2B brasileiras.

## 📖 Documentação

**[Acesse a documentação completa](docs/index.html)** - Visualização interativa do fluxo do sistema, parâmetros, métricas e dashboard de monitoramento.

> Estado atual: repositório enxuto com apenas a API principal (FastAPI) e os artefatos do dashboard. Testes, scripts de diagnóstico e logs foram removidos.

## 🎯 Objetivo

Construir perfis completos de empresas em até **90 segundos** com taxa de sucesso de **~80%**.

## 📊 Métricas (Último Stress Test)

| Métrica | Valor |
|---------|-------|
| Throughput | 155 empresas/min |
| Taxa de Sucesso | 79.7% |
| Tempo Médio | 72s |
| RAM (300 paralelo) | ~3.5GB |

## 🏗️ Arquitetura

O sistema é composto por 3 etapas principais:

1. **Discovery** (~8s) - Busca do site oficial via Serper API + LLM
2. **Scrape** (~45s) - Extração de conteúdo com curl_cffi e estratégias adaptativas
3. **Profile** (~12s) - Análise LLM (Gemini/OpenAI) para extração estruturada

## 🚀 Início Rápido

### Requisitos

- Python 3.11+
- API Keys: Serper, Gemini, OpenAI (opcional), WebShare (opcional)

### Instalação

```bash
# Clone o repositório
git clone <repo-url>
cd busca_fornecedo_crawl

# Crie o ambiente virtual
python -m venv venv
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas API keys
```

### Uso

```bash
# Iniciar servidor
uvicorn app.main:app --reload

# Testar endpoint
curl -X POST http://localhost:8000/monta_perfil \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua-api-key" \
  -d '{
    "razao_social": "EMPRESA LTDA",
    "nome_fantasia": "EMPRESA",
    "cnpj": "12345678000199",
    "municipio": "São Paulo",
    "uf": "SP"
  }'
```

## ⚙️ Configuração

| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `SERPER_API_KEY` | API key do Serper.dev | ✅ |
| `GEMINI_API_KEY` | API key do Google Gemini | ✅ |
| `OPENAI_API_KEY` | API key da OpenAI | Fallback |
| `WEBSHARE_API_KEY` | API key do WebShare | Opcional |
| `API_KEY` | Chave de autenticação | ✅ |

## 📁 Estrutura

```
busca_fornecedo_crawl/
├── app/
│   ├── api/                    # Endpoints FastAPI
│   ├── core/                   # Configurações e utilitários
│   │   ├── chunking/           # Módulo de Chunking v4.0 (NOVO)
│   │   │   ├── config.py       # Configurações centralizadas
│   │   │   ├── preprocessor.py # Deduplicação de linhas
│   │   │   ├── chunker.py      # Divisão em chunks
│   │   │   └── validator.py    # Validação de chunks
│   │   └── token_utils.py      # Utilitários de tokenização
│   ├── schemas/                # Modelos Pydantic
│   └── services/
│       ├── agents/             # Agentes LLM
│       ├── concurrency_manager/# Orquestração global de recursos (v3.0)
│       │   ├── global_orchestrator.py  # Balanceamento entre módulos
│       │   ├── resource_pool.py        # Pool de recursos
│       │   └── priority_queue.py       # Fila de prioridades
│       ├── discovery/          # Busca de sites (lógica de negócio)
│       ├── discovery_manager/  # Controle de APIs externas (v3.0)
│       │   ├── serper_manager.py       # Rate limiting Serper
│       │   ├── search_cache.py         # Cache de buscas
│       │   └── google_search_manager.py # Fallback
│       ├── llm_manager/        # Gerenciamento de chamadas LLM
│       ├── profile_builder/    # Construção de perfis
│       ├── scraper/            # Extração de conteúdo (lógica de negócio)
│       └── scraper_manager/    # Controle de infraestrutura (v3.0)
│           ├── concurrency_manager.py  # Semáforos por domínio
│           ├── proxy_manager.py        # Pool de proxies
│           ├── circuit_breaker.py      # Circuit breaker centralizado
│           └── rate_limiter.py         # Rate limiting por domínio
├── docs/                       # Dashboard e documentação interativa
└── requirements.txt            # Dependências do projeto
```

## 🔧 Padrões e Tecnologias

- **Framework**: FastAPI
- **HTTP Client**: curl_cffi (sem browser headless)
- **LLM**: Google Gemini (primário), OpenAI (fallback)
- **Busca**: Serper.dev (Google Search API)
- **Proxies**: WebShare (rotating residential)
- **Validação**: Pydantic v2
- **Scraping**: Batch processing (mini-batches com delays variáveis)
- **Concorrência**: Token Bucket + Semáforos por domínio (v3.0)
- **Resiliência**: Circuit Breaker com estados CLOSED/OPEN/HALF_OPEN (v3.0)
- **Chunking**: Módulo isolado v4.0 com deduplicação e validação automática (v4.0)

## 📝 Decisões Arquiteturais

1. **Sem Browser Headless**: Por restrição de RAM do servidor (Playwright usa ~400MB/instância)
2. **Estratégias Adaptativas**: FAST → STANDARD → ROBUST → AGGRESSIVE
3. **Sistema RESCUE**: Tenta subpages quando main page tem < 500 chars
4. **Circuit Breaker**: Evita bater em domínios problemáticos (v3.0: estados CLOSED/OPEN/HALF_OPEN)
5. **Batch Scraping**: Meio termo entre sequencial e paralelo (3-5x mais rápido, simula navegação humana)
6. **Separação Negócio/Infraestrutura**: Managers centralizados para controle de recursos (v3.0)
7. **Orquestração Global**: Visão unificada de todos os recursos do sistema (v3.0)
8. **Chunking Isolado**: Módulo independente com deduplicação, chunking e validação (v4.0: reduz ~94% tokens em casos repetitivos)

## 📊 Monitoramento

- Logs estruturados com timestamps
- Métricas de performance por etapa
- Tracking de falhas por domínio
- Relatórios JSON detalhados
- Status em tempo real dos managers (v3.0)
- Dashboard em tempo real: http://localhost:8000/monitor

## 🧪 Testes de Performance

O projeto inclui testes focados para cada etapa do pipeline:

### Teste de Discovery

Avalia e otimiza a performance da etapa de discovery (busca de sites oficiais).

```bash
# Teste rápido (10 empresas)
python tests/discovery/test_discovery_performance.py --empresas 10

# Teste médio (50 empresas)
python tests/discovery/test_discovery_performance.py --empresas 50

# Teste completo (100 empresas)
python tests/discovery/test_discovery_performance.py --empresas 100

# Ou use o script interativo
./tests/discovery/exemplo_uso.sh
```

**Métricas coletadas:**
- Taxa de sucesso
- Tempo médio, mediano, min/max
- Percentis (P50, P75, P90, P95, P99)
- Throughput (empresas/segundo)
- Tipos de falha categorizados

**Resultados salvos em:** `tests/discovery/results/`
- `test_results_[timestamp].json` - Resultados detalhados
- `test_statistics_[timestamp].json` - Estatísticas agregadas
- `test_log_[timestamp].txt` - Logs completos

**Documentação completa:** [tests/discovery/README.md](tests/discovery/README.md)

### Módulo de Chunking v4.0

O módulo de chunking é responsável por dividir conteúdo grande em chunks menores respeitando limites de tokens para processamento LLM.

```bash
# Testar chunking completo
python tests/test_chunking_module.py
```

**Funcionalidades:**
- **Pré-processamento**: Deduplicação de linhas repetidas (economiza até 94% de tokens)
- **Chunking**: Divisão inteligente por páginas, parágrafos e linhas
- **Validação**: Garantia de que chunks estão dentro dos limites
- **Preservação**: 100% do conteúdo único preservado

**Uso:**
```python
from app.core.chunking import process_content, get_chunking_config

# Pipeline completo: preprocess → chunk → validate
chunks = process_content(raw_content)

# Acessar conteúdo de cada chunk
for chunk in chunks:
    print(f"Chunk {chunk.index}/{chunk.total_chunks}: {chunk.tokens} tokens")
    content = chunk.content
```

**Configuração:**
- Arquivo: `app/configs/chunking/chunking.json`
- Limite padrão: 20,000 tokens por chunk
- Effective max: 14,705 tokens (considerando overhead)
- Deduplicação: Ativada por padrão

**Resultados:**
- Economia média: ~94% de tokens em arquivos repetitivos
- Performance: <20ms por arquivo
- Validação: 100% dos chunks dentro dos limites

## 🐛 Erros Comuns

| Erro | Causa | Mitigação |
|------|-------|-----------|
| Conteúdo Insuficiente | Site SPA ou main page vazia | Sistema RESCUE |
| Site Não Encontrado | Empresa sem presença online | Múltiplas queries |
| Timeout | Site lento ou proteção | Estratégias adaptativas |

## 📜 Changelog

### v4.0 (Atual)
- ✅ Módulo de Chunking isolado e reestruturado
- ✅ Deduplicação de linhas repetidas (economia de ~94% tokens)
- ✅ Validação automática de chunks
- ✅ Configurações centralizadas em JSON
- ✅ Pipeline completo: preprocess → chunk → validate
- ✅ Testes end-to-end com arquivos reais
- ✅ Performance: <20ms por arquivo

### v3.0
- ✅ Separação de controle de concorrência em módulos dedicados
- ✅ `scraper_manager/`: Concorrência, proxies, circuit breaker, rate limiting
- ✅ `discovery_manager/`: Serper API, cache, Google fallback
- ✅ `concurrency_manager/`: Orquestração global, resource pool, priority queue
- ✅ Circuit Breaker com estados (CLOSED/OPEN/HALF_OPEN) e recovery automático
- ✅ Proxy Pool com quarentena e teste de latência
- ✅ Cache de buscas com TTL e LRU eviction
- ✅ Preparado para +500 chamadas consecutivas sem gargalos
- ✅ Simplificação: removidos endpoints/artefatos de teste e logs de diagnóstico

### v2.2
- ✅ Batch Scraping: 3-5x mais rápido que sequencial (delays variáveis 3-7s)
- ✅ Simula navegação humana para evitar detecção de bot
- ✅ Configurável por ambiente (batch_size, delays)

### v2.1
- ✅ Sistema RESCUE para main pages com < 500 chars
- ✅ Documentação interativa completa
- ✅ Teste de stress com 300 empresas

### v2.0
- ✅ Scraper adaptativo com múltiplas estratégias
- ✅ LLM Provider Manager com fallback
- ✅ Circuit Breaker por domínio
- ✅ Learning Engine

### v1.0
- ✅ Scraper básico com curl_cffi
- ✅ Discovery via Serper
- ✅ Análise LLM simples

## 📄 Licença

Proprietário - Uso interno apenas.

---

*Documentação gerada em Dezembro 2025*
