# Verificação: max_tokens e Structured Output (JSON Schema)

**Objetivo:** Verificar qual `max_tokens` está em uso e se Structured Output (JSON Schema) está habilitado para extração de perfil.

---

## 1. max_tokens (tokens de saída)

### Onde é definido

- **Fluxo:** `ProviderManager.call()` → `_execute_llm_call()` usa `max_output_tokens = self._rate_limiter.get_max_output_tokens(provider)` e envia como `"max_tokens": max_output_tokens` na requisição ao LLM.
- **Fonte dos valores:** `RateLimiter` carrega a config via `get_section("llm_limits")` → arquivo **`app/configs/llm_limits.json`** (se existir); senão usa fallback hardcoded em `_get_default_config()`.

### Valores por provider (em `app/configs/llm_limits.json`)

| Provider / modelo | max_output_tokens |
|-------------------|--------------------|
| RunPod – Mistral 3 8B | **8192** |
| RunPod – **Qwen 2.5 3B** | **4096** |
| Google – Gemini 2.0 Flash | 8192 |
| OpenAI – GPT-4.1 Nano | 32768 |
| OpenRouter – Gemini 2.0 Flash Lite | 8192 |
| OpenRouter – Gemini 2.5 Flash Lite | 65536 |
| OpenRouter – GPT-4.1 Nano | 32768 |

### Fallbacks no código

- **`app/services/llm_manager/rate_limiter.py`:**  
  - `ProviderLimits.max_output_tokens` default = **16384**.  
  - `get_max_output_tokens(provider)` se o provider não estiver mapeado → **8192**.
- **`app/core/vllm_client.py`:** `chat_completion(..., max_tokens=500)` — usado apenas por outros fluxos (ex.: discovery); **não** é o fluxo de extração de perfil.

### Conclusão sobre max_tokens

- O **perfil** usa sempre o `max_tokens` do **provider** vindo do RateLimiter (logo de **`llm_limits.json`** quando existir).
- Se o provider em uso for **RunPod com Qwen 2.5 3B**, o limite de saída é **4096** tokens, o que pode ser pouco para um `CompanyProfile` grande (todas as seções + muitas categorias/produtos/serviços) e contribuir para **truncamento** e erros "Unterminated string".
- Recomendação: para extração de perfil completo, usar **pelo menos 8192** para o modelo que estiver em produção (ex.: aumentar em `llm_limits.json` para o Qwen 2.5 3B ou priorizar um provider com maior `max_output_tokens`).

---

## 2. Structured Output (JSON Schema)

### Se está em uso

**Sim.** Tanto o agente de perfil quanto o profile_builder usam **JSON Schema** do `CompanyProfile` quando o provedor suporta.

### Onde é aplicado

1. **`app/services/agents/profile_extractor_agent.py`**  
   - `_get_response_format()` retorna:
     - `type: "json_schema"`
     - `json_schema`: `CompanyProfile.model_json_schema()`
   - Esse `response_format` é passado para o LLM na chamada (via `base_agent`).

2. **`app/services/agents/base_agent.py`**  
   - `USE_STRUCTURED_OUTPUT` e `_use_structured_output` vêm de **`app/configs/profile/profile_llm.json`** → `"use_structured_output": true` (default true).  
   - Em `execute()`, chama `_call_llm(..., response_format=self._get_response_format())`.  
   - Ou seja, quando `use_structured_output` é true, o agente envia o JSON Schema.

3. **`app/services/profile_builder/provider_caller.py`**  
   - Monta `response_format` com `type: "json_schema"` e `json_schema` de `CompanyProfile.model_json_schema()` e chama `provider_manager.call(..., response_format=response_format)`.  
   - Não lê `use_structured_output`; sempre tenta `json_schema` e, em erro, usa fallback `json_object`.

4. **`app/services/llm_manager/provider_manager.py`**  
   - Se `response_format.get("type") == "json_schema"`, envia `request_params["response_format"] = response_format` para a API (ex.: SGLang/RunPod).  
   - Assim, o **Structured Output com JSON Schema está em uso** quando o provider aceita esse formato.

### Configuração em `app/configs/profile/profile_llm.json`

```json
"use_structured_output": true,
"use_structured_output_note": "WHAT: habilita json_schema via SGLang/XGrammar. WHY: garante JSON válido sem parsing adicional. HOW: true usa response_format com json_schema."
```

### Conclusão sobre Structured Output

- **Sim, estamos usando Structured Output (JSON Schema):** o schema do `CompanyProfile` (Pydantic) é convertido para JSON Schema e enviado como `response_format` nas chamadas de extração de perfil.
- Isso **não** impede que a resposta seja **truncada** se o modelo parar antes de terminar (por `max_tokens` ou limite do modelo); truncamento ainda gera JSON inválido (ex.: "Unterminated string").
- Ou seja: Structured Output garante **formato** enquanto a geração não for cortada; **aumentar `max_tokens`** continua necessário para reduzir truncamento em perfis grandes.

---

## 3. Resumo

| Item | Situação |
|------|----------|
| **max_tokens** | Definido por provider em **`app/configs/llm_limits.json`**. RunPod Qwen 2.5 3B = **4096**; RunPod Mistral = 8192; outros entre 8192 e 65536. Fallback no código: 8192 ou 16384. |
| **Structured Output (JSON Schema)** | **Em uso:** `response_format` com `type: "json_schema"` e schema de `CompanyProfile` em `profile_extractor_agent` e `provider_caller`; habilitado por `use_structured_output: true` em `profile/profile_llm.json`. |
| **Risco de truncamento** | Alto se o provider for RunPod com Qwen 2.5 3B (4096 tokens de saída). Ajustar `max_output_tokens` em `llm_limits.json` para esse modelo (ex.: 8192) ou usar provider com limite maior. |
