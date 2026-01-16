# 🔍 Busca Fornecedor API

API para construção automática de perfis de empresas B2B brasileiras. O sistema busca, extrai e processa informações de sites corporativos para gerar perfis estruturados.

## 🎯 O que a API faz

1. **Busca no Google** - Encontra sites oficiais de empresas usando Serper API
2. **Identifica site oficial** - Usa LLM para analisar resultados e identificar o site correto
3. **Extrai conteúdo** - Faz scraping de múltiplas páginas do site
4. **Gera perfil estruturado** - Processa conteúdo com LLM para extrair informações estruturadas

## 📊 Métricas de Performance

| Métrica | Valor |
|---------|-------|
| Throughput | ~155 empresas/min |
| Taxa de Sucesso | ~80% |
| Tempo Médio Total | ~70s por empresa |
| Páginas por Site | até 100 subpáginas |

---

## 📁 Estrutura do Projeto

```
busca_fornecedo_crawl/
├── app/
│   ├── main.py                    # Entry point FastAPI
│   ├── api/v2/                    # Endpoints da API
│   │   ├── serper.py              # POST /v2/serper
│   │   ├── encontrar_site.py      # POST /v2/encontrar_site
│   │   ├── scrape.py              # POST /v2/scrape
│   │   └── montagem_perfil.py     # POST /v2/montagem_perfil
│   ├── configs/                   # Configurações JSON
│   │   ├── llm_providers.json     # Providers LLM
│   │   ├── llm_limits.json        # Limites de tokens
│   │   ├── discovery/             # Config discovery
│   │   ├── scraper/               # Config scraper
│   │   └── profile/               # Config profile
│   ├── core/                      # Módulos core
│   │   ├── config.py              # Variáveis de ambiente
│   │   ├── database.py            # Conexão PostgreSQL
│   │   ├── chunking/              # Módulo de chunking v4
│   │   ├── token_utils.py         # Contagem de tokens
│   │   └── vllm_client.py         # Cliente vLLM/RunPod
│   ├── schemas/                   # Schemas Pydantic
│   │   └── v2/                    # Schemas dos endpoints v2
│   └── services/                  # Lógica de negócio
│       ├── agents/                # Agentes LLM
│       ├── discovery/             # Serviço de discovery
│       ├── discovery_manager/     # Rate limiting Serper
│       ├── scraper/               # Scraper de sites
│       ├── scraper_manager/       # Circuit breaker, proxies
│       ├── llm_manager/           # Gerenciamento LLM
│       ├── profile_builder/       # Construção de perfis
│       └── database_service.py    # Operações de banco
├── migrations/                    # Scripts SQL
├── Dockerfile                     # Build Docker
├── Procfile                       # Config Railway
└── requirements.txt               # Dependências
```

---

## 🚀 Endpoints da API v2

A API possui 4 endpoints que devem ser chamados em sequência:

### 1️⃣ POST `/v2/serper` - Busca no Google

Busca informações da empresa no Google via Serper API.

**Request:**
```json
{
  "cnpj_basico": "12345678",
  "razao_social": "EMPRESA EXEMPLO LTDA",
  "nome_fantasia": "Empresa Exemplo",
  "municipio": "São Paulo"
}
```

**Response:**
```json
{
  "success": true,
  "serper_id": 123,
  "results_count": 10,
  "query_used": "Empresa Exemplo São Paulo site oficial"
}
```

**Dados salvos:** Tabela `serper_results`

---

### 2️⃣ POST `/v2/encontrar_site` - Identificar Site Oficial

Usa LLM para analisar os resultados do Serper e identificar o site oficial.

**Request:**
```json
{
  "cnpj_basico": "12345678"
}
```

**Response:**
```json
{
  "success": true,
  "discovery_id": 456,
  "website_url": "https://www.empresa.com.br",
  "discovery_status": "found",
  "confidence_score": 0.95
}
```

**Status possíveis:**
- `found` - Site encontrado com sucesso
- `not_found` - Site não encontrado
- `error` - Erro no processamento

**Dados salvos:** Tabela `website_discovery`

---

### 3️⃣ POST `/v2/scrape` - Extrair Conteúdo do Site

Faz scraping do site e salva conteúdo em chunks.

**Request:**
```json
{
  "cnpj_basico": "12345678",
  "website_url": "https://www.empresa.com.br"
}
```

**Response:**
```json
{
  "success": true,
  "chunks_saved": 15,
  "total_tokens": 125000,
  "pages_scraped": 8,
  "processing_time_ms": 3450.5
}
```

**Dados salvos:** Tabela `scraped_chunks`

---

### 4️⃣ POST `/v2/montagem_perfil` - Gerar Perfil Estruturado

Processa chunks com LLM para extrair perfil estruturado da empresa.

**Request:**
```json
{
  "cnpj_basico": "12345678"
}
```

**Response:**
```json
{
  "success": true,
  "company_id": 789,
  "profile_status": "success",
  "chunks_processed": 15,
  "processing_time_ms": 5432.1
}
```

**Status possíveis:**
- `success` - Todos os chunks processados
- `partial` - Alguns chunks processados
- `error` - Nenhum chunk processado

**Dados salvos:** Tabela `company_profile`

---

## 🔗 Integração com n8n

### Configuração do HTTP Request Node

Para cada endpoint, configure um nó **HTTP Request** no n8n:

#### Configurações Comuns

| Campo | Valor |
|-------|-------|
| Method | POST |
| URL | `https://sua-api.railway.app/v2/{endpoint}` |
| Authentication | Header Auth |
| Header Name | `X-API-Key` |
| Header Value | `sua-api-key` |
| Body Content Type | JSON |

### Fluxo Completo no n8n

```
[Trigger] → [1. Serper] → [2. Encontrar Site] → [3. Scrape] → [4. Montagem Perfil] → [Resultado]
```

### Exemplo: Nó 1 - Serper

**HTTP Request Node:**
```
URL: https://sua-api.railway.app/v2/serper
Method: POST
Headers:
  - X-API-Key: sua-api-key
  - Content-Type: application/json
Body:
{
  "cnpj_basico": "{{ $json.cnpj_basico }}",
  "razao_social": "{{ $json.razao_social }}",
  "nome_fantasia": "{{ $json.nome_fantasia }}",
  "municipio": "{{ $json.municipio }}"
}
```

### Exemplo: Nó 2 - Encontrar Site

**HTTP Request Node:**
```
URL: https://sua-api.railway.app/v2/encontrar_site
Method: POST
Headers:
  - X-API-Key: sua-api-key
  - Content-Type: application/json
Body:
{
  "cnpj_basico": "{{ $json.cnpj_basico }}"
}
```

### Exemplo: Nó 3 - Scrape

**HTTP Request Node:**
```
URL: https://sua-api.railway.app/v2/scrape
Method: POST
Headers:
  - X-API-Key: sua-api-key
  - Content-Type: application/json
Body:
{
  "cnpj_basico": "{{ $json.cnpj_basico }}",
  "website_url": "{{ $node['Encontrar Site'].json.website_url }}"
}
```

**⚠️ Importante:** Só chame o scrape se `discovery_status === "found"`

### Exemplo: Nó 4 - Montagem Perfil

**HTTP Request Node:**
```
URL: https://sua-api.railway.app/v2/montagem_perfil
Method: POST
Headers:
  - X-API-Key: sua-api-key
  - Content-Type: application/json
Body:
{
  "cnpj_basico": "{{ $json.cnpj_basico }}"
}
```

### Fluxo com Condicionais

```
[Serper] 
    ↓
[Encontrar Site] 
    ↓
[IF: discovery_status == "found"]
    ├── true → [Scrape] → [Montagem Perfil] → [Sucesso]
    └── false → [Log: Site não encontrado]
```

---

## 🗄️ Banco de Dados

### Tabelas

| Tabela | Descrição | Chave |
|--------|-----------|-------|
| `serper_results` | Resultados da busca Google | `cnpj_basico` |
| `website_discovery` | Site oficial descoberto | `cnpj_basico` |
| `scraped_chunks` | Chunks de conteúdo extraído | `cnpj_basico` |
| `company_profile` | Perfil estruturado final | `cnpj` |

### Campos da Tabela `company_profile`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | BIGSERIAL | ID único |
| `cnpj` | TEXT | CNPJ completo |
| `company_name` | TEXT | Nome da empresa |
| `industry` | TEXT | Setor de atuação |
| `business_model` | TEXT | Modelo de negócio |
| `target_audience` | TEXT | Público-alvo |
| `geographic_coverage` | TEXT | Cobertura geográfica |
| `website_url` | TEXT | URL do site |
| `profile_json` | JSONB | Perfil completo em JSON |
| `created_at` | TIMESTAMPTZ | Data de criação |

### Consultar Perfil Final

```sql
SELECT 
  company_name,
  industry,
  business_model,
  target_audience,
  website_url,
  profile_json
FROM company_profile
WHERE cnpj LIKE '12345678%';
```

---

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `API_KEY` | Chave de autenticação da API | ✅ |
| `SERPER_API_KEY` | API key do Serper.dev | ✅ |
| `GEMINI_API_KEY` | API key do Google Gemini | ✅ |
| `OPENAI_API_KEY` | API key da OpenAI | Fallback |
| `DATABASE_URL` | URL de conexão PostgreSQL | ✅ |
| `RUNPOD_API_KEY` | API key do RunPod (vLLM) | Opcional |
| `WEBSHARE_API_KEY` | API key do WebShare (proxies) | Opcional |

### Deploy no Railway

1. Conecte o repositório ao Railway
2. Configure as variáveis de ambiente
3. O Procfile já está configurado:
   ```
   web: hypercorn app.main:app --bind 0.0.0.0:$PORT
   ```

---

## 🔧 Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Framework | FastAPI |
| HTTP Client | curl_cffi (sem browser) |
| LLM Primário | Google Gemini |
| LLM Fallback | OpenAI GPT-4 |
| LLM Self-hosted | vLLM via RunPod |
| Busca | Serper.dev (Google) |
| Banco de Dados | PostgreSQL (Supabase) |
| Proxies | WebShare (rotating) |
| Deploy | Railway |

---

## 📋 Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLUXO COMPLETO                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Input: CNPJ + Dados]                                         │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐    Salva em                                   │
│  │ 1. Serper   │ ──────────────► serper_results                │
│  └─────────────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────┐    Salva em                              │
│  │ 2. Encontrar Site│ ──────────────► website_discovery        │
│  └──────────────────┘                                          │
│         │                                                       │
│         ▼ (se found)                                           │
│  ┌─────────────┐    Salva em                                   │
│  │ 3. Scrape   │ ──────────────► scraped_chunks                │
│  └─────────────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────┐    Salva em                              │
│  │ 4. Montagem Perfil│ ──────────────► company_profile         │
│  └──────────────────┘                                          │
│         │                                                       │
│         ▼                                                       │
│  [Output: Perfil Estruturado]                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🐛 Tratamento de Erros

| Código | Descrição | Ação Recomendada |
|--------|-----------|------------------|
| 200 | Sucesso | Continuar fluxo |
| 400 | Request inválido | Verificar campos obrigatórios |
| 401 | Não autorizado | Verificar API Key |
| 500 | Erro interno | Verificar logs, retry após 30s |

### Retry no n8n

Configure o nó HTTP Request com:
- **Continue On Fail**: true
- **Retry On Fail**: true
- **Max Tries**: 3
- **Wait Between Tries**: 30000 (30s)

---

## 📜 Changelog

### v5.0 (Atual)
- ✅ Endpoints v2 separados (serper, encontrar_site, scrape, montagem_perfil)
- ✅ Persistência em PostgreSQL (Supabase)
- ✅ Chunking v4 com deduplicação (~94% economia de tokens)
- ✅ Suporte a vLLM via RunPod
- ✅ Phoenix Tracing para observabilidade LLM
- ✅ Estrutura de projeto limpa e otimizada

### v4.0
- ✅ Módulo de Chunking isolado
- ✅ Deduplicação de linhas repetidas

### v3.0
- ✅ Separação de managers (scraper, discovery, llm)
- ✅ Circuit Breaker com estados
- ✅ Cache de buscas

---

## 📄 Licença

Proprietário - Uso interno apenas.

---

*Documentação atualizada em Janeiro 2026*
