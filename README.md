# Busca Fornecedor API

API para construção automática de perfis de empresas B2B brasileiras.

## Endpoints

- `POST /v2/serper` - Busca no Google
- `POST /v2/encontrar_site` - Identifica site oficial
- `POST /v2/scrape` - Extrai conteúdo do site
- `POST /v2/montagem_perfil` - Enfileira montagem de perfil (processado pelo worker)
- `POST /v2/queue_profile/enqueue` - Enfileira um CNPJ para perfil
- `POST /v2/queue_profile/enqueue_batch` - Enfileira em lote (ou elegíveis)
- `GET /v2/queue_profile/metrics` - Métricas da fila

Todos os endpoints de processamento retornam imediatamente; o trabalho pesado roda em background (worker).

## Variáveis de Ambiente (Railway)

As mesmas variáveis usadas antes; nenhuma nova obrigatória:

- `API_ACCESS_TOKEN` - Token de autenticação da API (opcional; default em código)
- `DATABASE_URL` - URL de conexão PostgreSQL (obrigatória)
- `LLM_URL` - URL do servidor SGLang/LLM, sem `/v1` (ex.: `http://IP:PORT`)
- `MODEL_NAME` - Nome do modelo servido pelo LLM
- `SERPSHOT_KEY` - API key do Serpshot (busca Google SERP; [docs](https://www.serpshot.com/docs))
- `WORKER_ID` - (opcional) Identificador do worker; se não definido, usa hostname-pid

## Deploy no Railway

1. **Serviço Web (API)**  
   - Conecte o repositório ao Railway.  
   - Use o **Dockerfile** (ou Nixpacks com Procfile).  
   - Comando padrão: `hypercorn app.main:app --bind [::]:$PORT` (já definido no Dockerfile).  
   - A tabela `queue_profile` é criada automaticamente no **startup** da API (migração idempotente).

2. **Serviço Worker (fila de perfil)**  
   - Crie um **segundo serviço** no mesmo projeto Railway, apontando para o mesmo repositório.  
   - Use a **mesma imagem** (mesmo Dockerfile) ou o mesmo build.  
   - Defina o **Start Command**: `python -m app.workers.profile_worker`.  
   - Configure as **mesmas variáveis de ambiente** do serviço web (`DATABASE_URL`, `LLM_URL`, `MODEL_NAME`, etc.).

3. **Variáveis**  
   - Defina no projeto ou em cada serviço: `DATABASE_URL`, `LLM_URL`, `MODEL_NAME`, `SERPSHOT_KEY`, e opcionalmente `API_ACCESS_TOKEN` e `WORKER_ID`.

Documentação interativa: `/docs`

## Padrões e tecnologia

- **Campos em português**: Em toda a API, perfis e banco usam `identidade`, `classificacao`, `contato`, `ofertas`, `reputacao`, `fontes` (e subcampos como `nome_empresa`, `industria`, `localizacoes`, etc.).
- **Telemetria**: Phoenix/OpenTelemetry para tracing de chamadas LLM; spans customizados criados via `trace_llm_call` sem anexar ao contexto (evita conflito com OpenAIInstrumentor). Ver `fixes/phoenix-traces-desapareceram-apos-fix-set-span-in-context.md`.
