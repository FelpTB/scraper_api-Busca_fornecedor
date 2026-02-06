# Serpshot – Rate limit e “Rate limit timeout”

## Erro que aparecia nos logs

As mensagens **não são HTTP 429 do Serpshot**. São do **nosso** rate limiter (Token Bucket):

- `⏰ TokenBucket[serpshot]: Timeout após 30.0s (tokens=0.08)`
- `❌ Serpshot: Rate limit timeout para query: ...`

Ou seja: a requisição ficou **mais de 30 segundos** esperando **permissão** (um token) para ser enviada. Como não conseguiu token a tempo, desistimos e retornamos 0 resultados. O Serpshot em si pode nem ter sido chamado nesses casos.

## Causa

1. **Pico de requisições**  
   Dezenas ou centenas de buscas (CNPJs) chegam quase ao mesmo tempo (ex.: batch do n8n).

2. **Token Bucket muito restritivo**  
   Com `rate_per_second: 2` e `max_burst: 5`:
   - Só 5 requisições saem imediatamente.
   - Depois, entram no máximo 2 por segundo.
   - Em 30 s: 5 + 2×30 = **65** requisições recebem token; o restante continua na fila.

3. **Timeout de 30 s**  
   Quem ainda está na fila após 30 s atinge `rate_limiter_timeout` e recebe “Rate limit timeout” (0 resultados). Isso é **timeout do nosso limiter**, não 429 do Serpshot.

## Limites do Serpshot (documentação)

- **Concorrência por plano** (requisições simultâneas): Basic 50, Standard 100, Premium 150, Ultimate 200.  
  Ref: [Serpshot](https://www.serpshot.com/) / documentação.
- **Batch**: uma única chamada pode enviar **até 100 queries** (`queries`: array de strings).  
  Ref: [Serpshot Docs](https://www.serpshot.com/docs) – POST `/api/search/google`.
- Não há um limite explícito “X requisições por segundo” na documentação; o que aparece é o limite de **requisições simultâneas** por plano.

## Solução aplicada

Em `app/configs/discovery/serper.json`:

- **rate_per_second**: `2` → `8`  
  Fila de ~100 requisições recebe tokens em ~10–12 s (25 de burst + 8/s).
- **max_burst**: `5` → `25`  
  Mais requisições saem logo no pico.
- **rate_limiter_timeout**: `30` → `90`  
  Em picos grandes, quem está na fila pode esperar até 90 s por um token antes de desistir.
- **rate_limiter_retry_timeout** e **connection_semaphore_timeout**  
  Aumentados de forma coerente (ex.: 30 s) para não cortar retentativas ou conexões antes da hora.
- **max_concurrent**: `10` → `20`  
  Mais requisições em voo ao mesmo tempo, ainda abaixo do limite de concorrência do Serpshot (50+).

Com isso, o “Rate limit timeout” causado pelo **nosso** Token Bucket deve deixar de ocorrer nos picos atuais, sem depender de 429 do Serpshot.

## Se aparecer 429 do Serpshot

Se nos logs aparecer **429** vindo da API (ex.: em `serper_manager` quando `response.status_code == 429`):

1. Reduza **rate_per_second** e **max_burst** em `serper.json` para não enviar picos tão altos.
2. Confirme no painel Serpshot o limite de **requisições simultâneas** do seu plano e deixe **max_concurrent** abaixo desse valor.
3. O código já faz retry com backoff para 429 em `app/services/discovery_manager/serper_manager.py`.

## Otimização futura: batch

A API Serpshot aceita **até 100 queries em uma requisição**. Hoje enviamos **1 query por requisição**. Agrupar várias buscas em uma única chamada (batch) reduziria número de requisições e a pressão no Token Bucket e no Serpshot. Isso exigiria mudança no fluxo (montar lotes de CNPJs, uma chamada por lote, mapear resultados de volta por CNPJ).
