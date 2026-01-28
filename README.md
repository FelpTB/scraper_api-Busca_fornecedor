# Busca Fornecedor API

API para construção automática de perfis de empresas B2B brasileiras.

## Endpoints

- `POST /v2/serper` - Busca no Google
- `POST /v2/encontrar_site` - Identifica site oficial
- `POST /v2/scrape` - Extrai conteúdo do site
- `POST /v2/montagem_perfil` - Gera perfil estruturado

Todos os endpoints retornam imediatamente e processam em background.

## Variáveis de Ambiente (whitelist Railway)

As únicas variáveis de ambiente lidas pela aplicação são:

- `API_ACCESS_TOKEN` - Token de autenticação da API (opcional; default em código)
- `DATABASE_URL` - URL de conexão PostgreSQL (obrigatória)
- `LLM_URL` - URL do servidor SGLang/LLM, sem `/v1` (ex.: `http://IP:PORT`)
- `MODEL_NAME` - Nome do modelo servido pelo LLM
- `SERPER_API_KEY` - API key do Serper.dev

## Deploy

A API está configurada para deploy no Railway via Dockerfile ou Procfile.

Documentação interativa: `/docs`

## Padrões e tecnologia

- **Campos em português**: Em toda a API, perfis e banco usam `identidade`, `classificacao`, `contato`, `ofertas`, `reputacao`, `fontes` (e subcampos como `nome_empresa`, `industria`, `localizacoes`, etc.).
- **Telemetria**: Phoenix/OpenTelemetry para tracing de chamadas LLM; uso de `opentelemetry.trace.propagation.set_span_in_context` para compatibilidade com versões atuais do OTel.
