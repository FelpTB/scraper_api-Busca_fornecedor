# 📡 Guia de Execução da API - B2B Flash Profiler

Este guia contém instruções completas para usar todos os endpoints da API, incluindo os novos endpoints modulares v2 e o endpoint original.

---

## 📋 Índice

1. [Configuração Inicial](#configuração-inicial)
2. [Iniciando a Aplicação](#iniciando-a-aplicação)
3. [Autenticação](#autenticação)
4. [Endpoints v2 (Modulares)](#endpoints-v2-modulares)
   - [4.1 Serper - Busca Google](#41-serper---busca-google)
   - [4.2 Encontrar Site - Descoberta](#42-encontrar-site---descoberta)
   - [4.3 Scrape - Extração de Conteúdo](#43-scrape---extração-de-conteúdo)
   - [4.4 Montagem Perfil - Análise LLM](#44-montagem-perfil---análise-llm)
5. [Endpoint Original](#endpoint-original)
6. [Fluxo Completo N8N](#fluxo-completo-n8n)
7. [Exemplos em Python](#exemplos-em-python)
8. [Tratamento de Erros](#tratamento-de-erros)

---

## 🔧 Configuração Inicial

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```bash
# Autenticação
API_ACCESS_TOKEN=seu-token-secreto-aqui

# Banco de Dados (PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/database

# Serper API (Google Search)
SERPER_API_KEY=sua-chave-serper

# vLLM RunPod (LLM Self-hosted)
VLLM_BASE_URL=https://seu-runpod.proxy.runpod.net/v1
VLLM_API_KEY=buscafornecedor
VLLM_MODEL=mistralai/Ministral-3-3B-Instruct-2512

# Phoenix Tracing (Opcional - Observabilidade)
PHOENIX_COLLECTOR_URL=https://seu-phoenix.up.railway.app

# LLM Providers (Opcional - Fallback)
GOOGLE_API_KEY=sua-chave-google
XAI_API_KEY=sua-chave-xai
OPENAI_API_KEY=sua-chave-openai
```

### Instalação de Dependências

```bash
# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Executar migrations do banco de dados
python migrations/run_migrations.py
```

---

## 🚀 Iniciando a Aplicação

### Desenvolvimento Local

```bash
# Ativar ambiente virtual
source venv/bin/activate

# Iniciar servidor FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em: `http://localhost:8000`

### Documentação Interativa

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Health Check

```bash
curl http://localhost:8000/
```

Resposta esperada:
```json
{
  "status": "ok",
  "service": "B2B Flash Profiler"
}
```

---

## 🔐 Autenticação

Todos os endpoints (exceto `/` e `/docs`) requerem autenticação via header `x-api-key`.

### Header Obrigatório

```
x-api-key: seu-token-secreto-aqui
```

### Exemplo com curl

```bash
curl -X GET "http://localhost:8000/api/v2/serper" \
  -H "x-api-key: seu-token-secreto-aqui"
```

### Exemplo com Python

```python
import requests

headers = {
    "x-api-key": "seu-token-secreto-aqui",
    "Content-Type": "application/json"
}

response = requests.post(
    "http://localhost:8000/api/v2/serper",
    headers=headers,
    json={...}
)
```

---

## 📡 Endpoints v2 (Modulares)

Os endpoints v2 são modulares e podem ser usados de forma independente ou em sequência para construir um fluxo completo.

---

### 4.1 Serper - Busca Google

**Endpoint:** `POST /api/v2/serper`

**Descrição:** Busca resultados no Google usando Serper API e salva no banco de dados.

#### Request Body

```json
{
  "cnpj_basico": "12345678",
  "razao_social": "Empresa Exemplo LTDA",
  "nome_fantasia": "Exemplo",
  "municipio": "São Paulo"
}
```

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `cnpj_basico` | string (8 dígitos) | ✅ Sim | CNPJ básico (8 primeiros dígitos) |
| `razao_social` | string | ⚠️ Condicional* | Razão social da empresa |
| `nome_fantasia` | string | ⚠️ Condicional* | Nome fantasia da empresa |
| `municipio` | string | ❌ Opcional | Município da empresa |

> ⚠️ **Condicional**: Forneça pelo menos `razao_social` ou `nome_fantasia`.

#### Exemplo com curl

```bash
curl -X POST "http://localhost:8000/api/v2/serper" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678",
    "razao_social": "Empresa Exemplo LTDA",
    "nome_fantasia": "Exemplo",
    "municipio": "São Paulo"
  }'
```

#### Response

```json
{
  "success": true,
  "serper_id": 123,
  "results_count": 10,
  "query_used": "Empresa Exemplo LTDA site oficial São Paulo"
}
```

#### Campos da Response

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `success` | boolean | Indica se a operação foi bem-sucedida |
| `serper_id` | integer | ID do registro salvo no banco de dados |
| `results_count` | integer | Número de resultados encontrados |
| `query_used` | string | Query de busca utilizada |

---

### 4.2 Encontrar Site - Descoberta

**Endpoint:** `POST /api/v2/encontrar_site`

**Descrição:** Identifica o site oficial da empresa usando LLM para analisar resultados Serper salvos.

#### Request Body

```json
{
  "cnpj_basico": "12345678"
}
```

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `cnpj_basico` | string (8 dígitos) | ✅ Sim | CNPJ básico (8 primeiros dígitos) |

> ⚠️ **Pré-requisito**: Execute `/api/v2/serper` primeiro para este endpoint funcionar.

#### Exemplo com curl

```bash
curl -X POST "http://localhost:8000/api/v2/encontrar_site" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678"
  }'
```

#### Response

```json
{
  "success": true,
  "discovery_id": 456,
  "website_url": "https://www.exemplo.com.br",
  "discovery_status": "found",
  "confidence_score": 0.95
}
```

#### Campos da Response

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `success` | boolean | Indica se a operação foi bem-sucedida |
| `discovery_id` | integer | ID do registro salvo no banco de dados |
| `website_url` | string \| null | URL do site oficial encontrado |
| `discovery_status` | string | Status: `"found"` ou `"not_found"` |
| `confidence_score` | float \| null | Score de confiança (0.0 a 1.0) |

---

### 4.3 Scrape - Extração de Conteúdo

**Endpoint:** `POST /api/v2/scrape`

**Descrição:** Faz scraping do site oficial e salva chunks no banco de dados.

#### Request Body

```json
{
  "cnpj_basico": "12345678",
  "website_url": "https://www.exemplo.com.br"
}
```

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `cnpj_basico` | string (8 dígitos) | ✅ Sim | CNPJ básico (8 primeiros dígitos) |
| `website_url` | string (URL) | ✅ Sim | URL do site oficial para scraping |

> ⚠️ **Pré-requisito**: Execute `/api/v2/encontrar_site` primeiro (ou forneça a URL manualmente).

#### Exemplo com curl

```bash
curl -X POST "http://localhost:8000/api/v2/scrape" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678",
    "website_url": "https://www.exemplo.com.br"
  }'
```

#### Response

```json
{
  "success": true,
  "chunks_saved": 15,
  "total_tokens": 125000,
  "pages_scraped": 8,
  "processing_time_ms": 3450.5
}
```

#### Campos da Response

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `success` | boolean | Indica se a operação foi bem-sucedida |
| `chunks_saved` | integer | Número de chunks salvos no banco |
| `total_tokens` | integer | Total de tokens processados |
| `pages_scraped` | integer | Número de páginas scraped com sucesso |
| `processing_time_ms` | float | Tempo de processamento em milissegundos |

---

### 4.4 Montagem Perfil - Análise LLM

**Endpoint:** `POST /api/v2/montagem_perfil`

**Descrição:** Monta o perfil completo da empresa a partir de chunks scraped usando LLM em paralelo.

#### Request Body

```json
{
  "cnpj_basico": "12345678"
}
```

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `cnpj_basico` | string (8 dígitos) | ✅ Sim | CNPJ básico (8 primeiros dígitos) |

> ⚠️ **Pré-requisito**: Execute `/api/v2/scrape` primeiro para ter chunks disponíveis.

#### Exemplo com curl

```bash
curl -X POST "http://localhost:8000/api/v2/montagem_perfil" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678"
  }'
```

#### Response

```json
{
  "success": true,
  "company_id": 789,
  "profile_status": "success",
  "chunks_processed": 15,
  "processing_time_ms": 5432.1
}
```

#### Campos da Response

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `success` | boolean | Indica se a operação foi bem-sucedida |
| `company_id` | integer \| null | ID do registro salvo no banco (tabela `company_profile`) |
| `profile_status` | string | Status: `"success"`, `"partial"` ou `"error"` |
| `chunks_processed` | integer | Número de chunks processados pelo LLM |
| `processing_time_ms` | float | Tempo de processamento em milissegundos |

---

## 🔄 Endpoint Original

**Endpoint:** `POST /monta_perfil`

**Descrição:** Endpoint original que executa todo o fluxo em uma única chamada (retrocompatibilidade).

#### Request Body

```json
{
  "url": "https://www.exemplo.com.br",
  "razao_social": "Empresa Exemplo LTDA",
  "nome_fantasia": "Exemplo",
  "cnpj": "12.345.678/0001-90",
  "email": "contato@exemplo.com.br",
  "municipio": "São Paulo",
  "cnaes": ["4751201", "4752100"]
}
```

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `url` | string (URL) | ⚠️ Condicional* | URL direta do site |
| `razao_social` | string | ⚠️ Condicional* | Razão social |
| `nome_fantasia` | string | ⚠️ Condicional* | Nome fantasia |
| `cnpj` | string | ❌ Opcional | CNPJ formatado ou não |
| `email` | string | ❌ Opcional | Email de contato |
| `municipio` | string | ❌ Opcional | Município |
| `cnaes` | array[string] | ❌ Opcional | Lista de CNAEs |

> ⚠️ **Condicional**: Forneça **OU** `url` diretamente **OU** ao menos um dos campos (`razao_social`, `nome_fantasia`, `cnpj`) para discovery automático.

#### Exemplo com curl

```bash
curl -X POST "http://localhost:8000/monta_perfil" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.exemplo.com.br"
  }'
```

#### Response

Retorna um objeto `CompanyProfile` completo com todos os dados estruturados da empresa.

**Timeout:** 300 segundos (5 minutos)

---

## 🔗 Fluxo Completo N8N

Para usar os endpoints v2 em sequência (simulando o fluxo N8N):

### Passo 1: Buscar no Google (Serper)

```bash
curl -X POST "http://localhost:8000/api/v2/serper" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678",
    "razao_social": "Empresa Exemplo LTDA",
    "nome_fantasia": "Exemplo",
    "municipio": "São Paulo"
  }'
```

**Resposta:** `serper_id` (salvar para referência)

### Passo 2: Encontrar Site Oficial

```bash
curl -X POST "http://localhost:8000/api/v2/encontrar_site" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678"
  }'
```

**Resposta:** `website_url` e `discovery_id` (salvar para referência)

### Passo 3: Fazer Scraping

```bash
curl -X POST "http://localhost:8000/api/v2/scrape" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678",
    "website_url": "https://www.exemplo.com.br"
  }'
```

**Resposta:** `chunks_saved` (número de chunks salvos)

### Passo 4: Montar Perfil

```bash
curl -X POST "http://localhost:8000/api/v2/montagem_perfil" \
  -H "x-api-key: seu-token-secreto-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "cnpj_basico": "12345678"
  }'
```

**Resposta:** `company_id` e `profile_status`

---

## 🐍 Exemplos em Python

### Exemplo 1: Fluxo Completo v2

```python
import requests
import time

BASE_URL = "http://localhost:8000"
API_KEY = "seu-token-secreto-aqui"
CNPJ_BASICO = "12345678"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# 1. Serper
print("🔍 Buscando no Google...")
serper_response = requests.post(
    f"{BASE_URL}/api/v2/serper",
    headers=headers,
    json={
        "cnpj_basico": CNPJ_BASICO,
        "razao_social": "Empresa Exemplo LTDA",
        "nome_fantasia": "Exemplo",
        "municipio": "São Paulo"
    }
)
serper_data = serper_response.json()
print(f"✅ Serper: {serper_data['results_count']} resultados encontrados")
serper_id = serper_data["serper_id"]

# 2. Discovery
print("🌐 Encontrando site oficial...")
discovery_response = requests.post(
    f"{BASE_URL}/api/v2/encontrar_site",
    headers=headers,
    json={"cnpj_basico": CNPJ_BASICO}
)
discovery_data = discovery_response.json()
if discovery_data["discovery_status"] == "found":
    website_url = discovery_data["website_url"]
    print(f"✅ Site encontrado: {website_url}")
else:
    print("❌ Site não encontrado")
    exit(1)

# 3. Scrape
print("📄 Fazendo scraping...")
scrape_response = requests.post(
    f"{BASE_URL}/api/v2/scrape",
    headers=headers,
    json={
        "cnpj_basico": CNPJ_BASICO,
        "website_url": website_url
    }
)
scrape_data = scrape_response.json()
print(f"✅ Scrape: {scrape_data['chunks_saved']} chunks salvos")

# 4. Profile
print("🤖 Montando perfil...")
profile_response = requests.post(
    f"{BASE_URL}/api/v2/montagem_perfil",
    headers=headers,
    json={"cnpj_basico": CNPJ_BASICO}
)
profile_data = profile_response.json()
print(f"✅ Perfil: {profile_data['profile_status']} (ID: {profile_data['company_id']})")
```

### Exemplo 2: Endpoint Original (Tudo em Uma Chamada)

```python
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "seu-token-secreto-aqui"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

response = requests.post(
    f"{BASE_URL}/monta_perfil",
    headers=headers,
    json={
        "url": "https://www.exemplo.com.br"
    },
    timeout=300  # 5 minutos
)

profile = response.json()
print(f"✅ Perfil criado: {profile['identity']['company_name']}")
```

### Exemplo 3: Usando httpx (Assíncrono)

```python
import httpx
import asyncio

BASE_URL = "http://localhost:8000"
API_KEY = "seu-token-secreto-aqui"

async def fluxo_completo():
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Serper
        serper_resp = await client.post(
            f"{BASE_URL}/api/v2/serper",
            headers=headers,
            json={
                "cnpj_basico": "12345678",
                "razao_social": "Empresa Exemplo LTDA",
                "nome_fantasia": "Exemplo"
            }
        )
        serper_data = serper_resp.json()
        
        # 2. Discovery
        discovery_resp = await client.post(
            f"{BASE_URL}/api/v2/encontrar_site",
            headers=headers,
            json={"cnpj_basico": "12345678"}
        )
        discovery_data = discovery_resp.json()
        
        # 3. Scrape
        scrape_resp = await client.post(
            f"{BASE_URL}/api/v2/scrape",
            headers=headers,
            json={
                "cnpj_basico": "12345678",
                "website_url": discovery_data["website_url"]
            }
        )
        scrape_data = scrape_resp.json()
        
        # 4. Profile
        profile_resp = await client.post(
            f"{BASE_URL}/api/v2/montagem_perfil",
            headers=headers,
            json={"cnpj_basico": "12345678"}
        )
        profile_data = profile_resp.json()
        
        return profile_data

# Executar
result = asyncio.run(fluxo_completo())
print(result)
```

---

## ⚠️ Tratamento de Erros

### Códigos de Status HTTP

| Código | Significado | Ação |
|--------|-------------|------|
| `200` | Sucesso | Operação concluída com sucesso |
| `400` | Bad Request | Dados inválidos no request body |
| `403` | Forbidden | API key inválida ou ausente |
| `404` | Not Found | Recurso não encontrado (ex: site não encontrado) |
| `500` | Internal Server Error | Erro interno do servidor |
| `504` | Gateway Timeout | Timeout na operação |

### Exemplo de Tratamento de Erros

```python
import requests

def fazer_requisicao(endpoint, data):
    try:
        response = requests.post(
            f"http://localhost:8000{endpoint}",
            headers={
                "x-api-key": "seu-token-secreto-aqui",
                "Content-Type": "application/json"
            },
            json=data,
            timeout=60
        )
        response.raise_for_status()  # Levanta exceção para códigos 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("❌ Erro: API key inválida")
        elif e.response.status_code == 404:
            print("❌ Erro: Recurso não encontrado")
        elif e.response.status_code == 504:
            print("❌ Erro: Timeout na operação")
        else:
            print(f"❌ Erro HTTP {e.response.status_code}: {e.response.text}")
        raise
    except requests.exceptions.Timeout:
        print("❌ Erro: Timeout na requisição")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro na requisição: {e}")
        raise

# Uso
try:
    resultado = fazer_requisicao("/api/v2/serper", {
        "cnpj_basico": "12345678",
        "razao_social": "Empresa Exemplo LTDA"
    })
    print("✅ Sucesso:", resultado)
except Exception as e:
    print("❌ Falha:", e)
```

---

## 📊 Tempos Estimados

| Endpoint | Tempo Médio | Observação |
|----------|-------------|------------|
| `/api/v2/serper` | 2-5s | Depende da Serper API |
| `/api/v2/encontrar_site` | 5-15s | Usa LLM para análise |
| `/api/v2/scrape` | 20-60s | Depende do tamanho do site |
| `/api/v2/montagem_perfil` | 10-30s | Processa chunks em paralelo |
| `/monta_perfil` (original) | 60-120s | Executa todo o fluxo |

---

## 🔍 Consultando Dados Salvos

### Via Banco de Dados

Os dados são salvos automaticamente nas seguintes tabelas:

- `serper_results` - Resultados da busca Google
- `website_discovery` - Descoberta de site oficial
- `scraped_chunks` - Chunks de conteúdo scraped
- `company_profile` - Perfil completo da empresa

### Exemplo de Query SQL

```sql
-- Buscar perfil completo de uma empresa
SELECT 
    cp.cnpj_basico,
    cp.company_name,
    cp.profile_json
FROM company_profile cp
WHERE cp.cnpj_basico = '12345678';

-- Buscar chunks scraped
SELECT 
    chunk_content,
    tokens,
    created_at
FROM scraped_chunks
WHERE cnpj_basico = '12345678'
ORDER BY created_at DESC;
```

---

## 📝 Notas Importantes

1. **Ordem dos Endpoints v2**: Os endpoints v2 devem ser executados em sequência:
   - `serper` → `encontrar_site` → `scrape` → `montagem_perfil`

2. **CNPJ Básico**: Sempre use o CNPJ básico (8 primeiros dígitos) em todos os endpoints v2.

3. **Timeout**: O endpoint `/monta_perfil` tem timeout de 300 segundos. Os endpoints v2 têm timeouts individuais menores.

4. **Retry**: Em caso de falha, você pode reexecutar qualquer endpoint v2. Os dados são salvos incrementalmente.

5. **Paralelismo**: O endpoint `/api/v2/montagem_perfil` processa chunks em paralelo para melhor performance.

---

## 🆘 Suporte

Para mais informações, consulte:
- **Documentação Swagger**: `http://localhost:8000/docs`
- **Documentação ReDoc**: `http://localhost:8000/redoc`
- **Logs**: Verifique os logs em `logs/server_YYYYMMDD.log`

---

*Última atualização: Janeiro 2026*

