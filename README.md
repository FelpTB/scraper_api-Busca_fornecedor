# Busca Fornecedor API

API para construção automática de perfis de empresas B2B brasileiras.

## Endpoints (4 processos + filas)

Cada processo pode ser chamado individualmente; a ordem e dependências ficam a cargo do cliente (ex.: n8n).

| Processo | Endpoint | Fila | Descrição |
|----------|----------|------|-----------|
| 1 | `POST /v2/serper` | — | Busca no Google (Serpshot) |
| 2 | `POST /v2/encontrar_site` | queue_discovery | Enfileira descoberta de site (LLM); worker processa |
| 3 | `POST /v2/scrape` | — | Extrai conteúdo do site |
| 4 | `POST /v2/montagem_perfil` | queue_profile | Enfileira montagem de perfil (LLM); worker processa |

Filas (enfileiramento em unidade; batches no n8n por repetição de chamadas):

- **Discovery:** `POST /v2/queue_discovery/enqueue`, `POST /v2/queue_discovery/enqueue_batch`, `GET /v2/queue_discovery/metrics`
- **Perfil:** `POST /v2/queue_profile/enqueue`, `POST /v2/queue_profile/enqueue_batch`, `GET /v2/queue_profile/metrics`

Processos com LLM (encontrar_site e montagem_perfil) são enfileirados e processados por workers dedicados, mantendo os workers ocupados.

## Variáveis de Ambiente (Railway)

As mesmas variáveis usadas antes; nenhuma nova obrigatória:

- `API_ACCESS_TOKEN` - Token de autenticação da API (opcional; default em código)
- `DATABASE_URL` - URL de conexão PostgreSQL (obrigatória)
- `LLM_URL` - URL do servidor SGLang/LLM, sem `/v1` (ex.: `http://IP:PORT`)
- `MODEL_NAME` - Nome do modelo servido pelo LLM
- `SERPSHOT_KEY` - API key do Serpshot (busca Google SERP; [docs](https://www.serpshot.com/docs))
- `WORKER_ID` - (opcional) Identificador do worker; se não definido, usa hostname-pid

## Deploy no Railway

**Importante:** Os logs que aparecem no console do serviço web são só da **API**. Quem processa as filas são processos **separados** (workers). Se você tiver apenas o serviço web, os jobs ficam em `queued` e nunca são processados. É obrigatório ter ao menos um serviço rodando o discovery worker e um rodando o profile worker.

1. **Serviço Web (API)**  
   - Conecte o repositório ao Railway.  
   - Use o **Dockerfile** (ou Nixpacks com Procfile).  
   - Comando padrão: `hypercorn app.main:app --bind [::]:$PORT` (já definido no Dockerfile).  
   - As tabelas `queue_profile` e `queue_discovery` são criadas automaticamente no **startup** (migração idempotente).  
   - Nos logs do web você verá "Running on http://...", "Requisição Discovery recebida", "Queue discovery: enqueued" — **nunca** "Discovery worker started".

2. **Serviço Discovery Worker (fila encontrar_site)**  
   - Crie um **novo serviço** no mesmo projeto Railway (duplicar serviço ou add service from repo), mesma imagem/build.  
   - **Start Command:** `python -m app.workers.discovery_worker`.  
   - Mesmas variáveis de ambiente do web (`DATABASE_URL`, `LLM_URL`, `MODEL_NAME`, etc.).  
   - Nos logs deste serviço deve aparecer `Discovery worker started, worker_id=...`; é este processo que consome a fila.

3. **Serviço Profile Worker (fila montagem_perfil)**  
   - Outro serviço, mesma imagem.  
   - **Start Command:** `python -m app.workers.profile_worker`.  
   - Mesmas variáveis de ambiente.  
   - Logs: `Profile worker started, worker_id=...`.

4. **Variáveis**  
   - Defina no projeto ou em cada serviço: `DATABASE_URL`, `LLM_URL`, `MODEL_NAME`, `SERPSHOT_KEY`, e opcionalmente `API_ACCESS_TOKEN` e `WORKER_ID`.

Documentação interativa: `/docs`

## Padrões e tecnologia

- **Campos em português**: Em toda a API, perfis e banco usam `identidade`, `classificacao`, `contato`, `ofertas`, `reputacao`, `fontes` (e subcampos como `nome_empresa`, `industria`, `localizacoes`, etc.).
- **Telemetria**: Phoenix/OpenTelemetry para tracing de chamadas LLM; spans customizados criados via `trace_llm_call` sem anexar ao contexto (evita conflito com OpenAIInstrumentor). Ver `fixes/phoenix-traces-desapareceram-apos-fix-set-span-in-context.md`.
