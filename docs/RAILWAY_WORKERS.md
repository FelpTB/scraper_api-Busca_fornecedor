# Workers no Railway – passo a passo

Há duas formas de rodar os workers: **um único container** (API + workers juntos) ou **vários serviços** (um container por processo).

---

## Opção A: Um único container (API + workers no mesmo deploy)

O **Dockerfile** está configurado para subir, no mesmo container:

1. **N Discovery workers** (em background)
2. **N Profile workers** (em background)
3. **API** (em foreground, expondo a porta)

**Variáveis de ambiente (opcionais):**

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `N_WORKERS` | 2 | Número de processos de cada tipo (discovery + profile). Ex.: 16 = 16 discovery + 16 profile. |
| `PORT` | 8000 | Porta da API |
| `CLAIM_BATCH_SIZE` | 10 | Quantos jobs o profile worker pega por claim (reduz round-trips ao Postgres). |
| `DATABASE_POOL_MIN_SIZE` | 5 | Conexões mínimas do pool asyncpg (por processo). |
| `DATABASE_POOL_MAX_SIZE` | 20 | Conexões máximas. Em muitos workers use 2–3 por processo para não saturar o DB. |
| `LLM_CONCURRENCY_HARD_CAP` | 32 | Teto de chamadas LLM simultâneas por provider (evita oversubscription/timeouts). |

Para usar ao máximo a placa (LLM), aumente `N_WORKERS` (ex.: 16). Em deploy com muitos workers, defina `DATABASE_POOL_MAX_SIZE=2` ou `3` para não saturar o Postgres.

Você **não precisa fazer nada no Railway**: use o deploy padrão (um serviço, um container). O comando de início do container é `/app/scripts/start_web_and_workers.sh`, que sobe os workers e depois a API.

- **Logs:** no mesmo serviço você verá linhas da API (`Running on http://...`, `Requisição Discovery recebida`) e dos workers (`[discovery_worker] Process starting`, `[profile_worker] Process starting`, `Discovery worker claimed job...`, etc.).
- **Se quiser só a API** nesse serviço (sem workers), em **Settings** do serviço defina **Start Command** (custom):  
  `hypercorn app.main:app --bind [::]:$PORT`

---

## Opção B: Vários serviços (um container para API, um para cada worker)

Se preferir separar API e workers em **serviços diferentes** (melhor para escalar e ver logs por processo):

### 1. Conferir o serviço Web

- Um serviço com nome tipo "api" ou "web".
- **Start Command:** `hypercorn app.main:app --bind [::]:$PORT` (para rodar só a API neste serviço).
- Nos logs: `Running on http://...`, `Requisição Discovery recebida`, `Queue discovery: enqueued`.

### 2. Criar o serviço Discovery Worker

1. No projeto Railway: **+ New** → **Empty Service** (ou **Add Service**).
2. **Connect** o mesmo repositório (ou use "Clone" do serviço web).
3. **Settings** do novo serviço:
   - **Build:** mesmo do web (Dockerfile ou Nixpacks).
   - **Start Command (Custom):**  
     `python -m app.workers.discovery_worker`
   - **Variables:** copiar do serviço web (ou usar variáveis do projeto):
     - `DATABASE_URL`
     - `LLM_URL`
     - `MODEL_NAME`
     - `SERPSHOT_KEY` (se precisar)
     - Outras que o app use (ex.: `API_ACCESS_TOKEN`).

4. **Deploy** e abrir **Logs** do **Discovery Worker** (não do web). Você deve ver algo como:
   - `[discovery_worker] Process starting (python -m app.workers.discovery_worker)`
   - `Discovery worker connecting to database...`
   - `Discovery worker database connected, starting claim loop`
   - `Discovery worker started, worker_id=...`
   - Se a fila estiver vazia por ~1 min: `Discovery worker alive, queue empty (queued=0, processing=0)`
   - Quando pegar job: `Discovery worker claimed job id=... cnpj=...`

Se **não aparecer nada** nos logs desse serviço: o start command está errado ou o serviço não está rodando (conferir **Settings** → Start Command e se o deploy terminou).

Se aparecer **"Process starting"** e depois **erro**: a mensagem de erro indica o problema (ex.: `DATABASE_URL` faltando, tabela não existir).

### 3. Criar o serviço Profile Worker

1. **+ New** → **Empty Service** (ou clone do discovery worker).
2. Mesmo repositório e build.
3. **Start Command:**  
   `python -m app.workers.profile_worker`
4. Mesmas **Variables** do web.
5. Nos logs deste serviço: `[profile_worker] Process starting`, `Profile worker database connected, starting claim loop`, etc.

### 4. Resumo (Opção B)

| Serviço (nome sugerido) | Start Command |
|-------------------------|----------------|
| web / api               | `hypercorn app.main:app --bind [::]:$PORT` |
| discovery_worker        | `python -m app.workers.discovery_worker` |
| profile_worker          | `python -m app.workers.profile_worker` |

Cada um é um **serviço separado** no mesmo projeto, mesmo repositório, mesma imagem, **Start Command** diferente. Variáveis de ambiente iguais nos três (ou no projeto).

### 5. Se os jobs continuarem parados

- Abra os logs do **serviço do discovery_worker** (não do web).  
- Se não houver **nenhuma** linha: o processo do worker não está subindo (serviço errado, comando errado ou deploy falhou).  
- Se houver `Discovery worker crashed: ...`: a exceção mostra a causa (banco, tabela, env, etc.).  
- Se houver `Discovery worker alive, queue empty (queued=X, processing=Y)` com `queued > 0`: o worker está rodando mas não está pegando jobs do mesmo banco (ex.: outro schema, outra `DATABASE_URL`). Confira se todos os serviços usam a mesma `DATABASE_URL`.

---

## 502 "Application failed to respond" – como diagnosticar

- **GET /healthz** – Health check mínimo (não acessa DB). Use para distinguir causa do 502:
  - Se **/healthz também retorna 502** enquanto o scrape/processamento pesado roda → processo travado (event loop bloqueado ou saturação).
  - Se **/healthz retorna 200** e só a rota de trabalho (ex.: scrape, montagem) dá 502 → provável **timeout** do gateway ou do cliente (n8n) esperando resposta além do limite.
- **POST /v2/scrape** e **POST /v2/montagem_perfil** passaram a retornar **202 Accepted** imediatamente (sem esperar o trabalho terminar). O n8n deve tratar 202 e fazer polling (ex.: GET /v2/queue_profile/metrics ou GET /jobs/:id) em vez de esperar a conclusão na mesma requisição.
- Em caso de **rate limit de logs** no Railway (ex.: "500 logs/sec reached"), reduza verbosidade (menos logs por item, usar nível `debug` para detalhes) para não perder mensagens e facilitar o diagnóstico.
