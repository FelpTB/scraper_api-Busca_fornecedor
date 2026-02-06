# Serpshot 429 – Rate limit e como resolver

## O que é o 429

O **HTTP 429 (Too Many Requests)** é retornado pela API do Serpshot quando o número de requisições por segundo (ou por minuto) ultrapassa o limite do plano. Ou seja: estamos enviando requisições mais rápido do que o Serpshot permite.

## Por que estava falhando

A configuração em `app/configs/discovery/serper.json` estava com valores muito altos para uso real da API Serpshot:

- **rate_per_second: 190** – permitia até 190 requisições por segundo
- **max_burst: 170** – burst de até 170 requisições

Com vários workers ou muitas buscas em paralelo, o volume de chamadas ao Serpshot passava do limite do provedor e o 429 aparecia.

## Solução aplicada

No mesmo arquivo `app/configs/discovery/serper.json` foram reduzidos:

- **rate_per_second** → `2` (até 2 req/s em média)
- **max_burst** → `5` (burst menor)
- **max_concurrent** → `10` (menos requisições simultâneas)
- **max_retries** → `3` (mais tentativas em caso de 429)
- **retry_base_delay** e **retry_max_delay** aumentados para dar tempo ao rate limit do Serpshot (1s a 8s)

Assim, as chamadas ao Serpshot ficam dentro do limite e, em caso de 429, o cliente faz retry com backoff.

## Ajuste fino

Se ainda aparecer 429 com frequência:

1. Reduza mais **rate_per_second** (ex.: 1) e **max_burst** (ex.: 3).
2. Confirme no painel do Serpshot qual é o limite do seu plano (req/s ou req/min).
3. Aumente **retry_base_delay** / **retry_max_delay** se o Serpshot exigir janelas maiores entre retentativas.

O tratamento de 429 com retry e backoff está em `app/services/discovery_manager/serper_manager.py`.
