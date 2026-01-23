# Implementação v8.0 - Solução Definitiva Anti-Loop

## 📋 Resumo das Mudanças

Implementação completa baseada na análise de `repetition-issues-4.jsonl` e documentação do XGrammar/SGLang.

### Problema Identificado

1. **`uniqueItems` e `maxItems` podem ser ignorados pelo XGrammar** ([GitHub Issue #160](https://github.com/mlc-ai/xgrammar/issues/160))
2. **Loops de repetição não eram causados por tamanho do input**, mas por **estrutura do conteúdo** (catálogos, listas combinatórias)
3. **`temperature=0.0` aumenta risco de loops** em "modo lista" (relatos da comunidade)
4. **Geração degenerada (runaway)** até bater `max_tokens` (4096), resultando em JSON truncado

---

## ✅ Solução Implementada (4 Camadas)

### 1. **PROMPT v8.0** - Hard Caps Numéricos + Anti-Template

**Arquivo:** `app/services/agents/profile_extractor_agent.py`

**Mudanças principais:**
- ✅ **Hard cap numérico**: máximo **40 itens por categoria** (não depende de schema)
- ✅ **Anti-template**: se 5 itens seguidos compartilham mesmo molde, encerrar
- ✅ **Regras binárias** para roteamento (ISO 9001→reputation, NR-10→team)
- ✅ **Instruções operacionais curtas** (sem markdown pesado)

```python
SYSTEM_PROMPT = """
...
5) Anti-loop forte para listas longas (regra numérica + anti-template)
- Para offerings.product_categories[].items:
  a) HARD CAP: no máximo 40 itens por categoria.
  b) ANTI-TEMPLATE: se 5 itens seguidos compartilharem o mesmo "molde" textual
     (ex.: começam com "2 RCA + 2 RCA"), mantenha somente os primeiros 5 únicos 
     e encerre a categoria.
...
"""
```

---

### 2. **Loop Detector** - Detecta Runaway Generation em Tempo Real

**Arquivo:** `app/services/llm_manager/provider_manager.py`

**Função:** `_detect_repetition_loop(content, ctx_label)`

**Heurísticas implementadas:**

| Heurística | Detecção | Ação |
|------------|----------|------|
| **N-grams repetidos** | Mesmo 4-gram > 8 vezes | ✅ Lança `ProviderDegenerationError` |
| **Trechos repetidos** | Mesmo trecho (30 chars) > 5 vezes | ✅ Lança `ProviderDegenerationError` |
| **JSON não fechado** | > 3000 chars sem `}` no final | ✅ Lança `ProviderDegenerationError` |

**Exemplo de detecção:**
```python
# Detecta padrões como "2 RCA + 2 RCA" repetidos muitas vezes
if max_ngram_count > 8:
    logger.warning(f"LoopDetector: n-gram repetido detectado ('{most_repeated}' x{max_ngram_count})")
    return True
```

---

### 3. **Retry Seletivo** - Parâmetros Ajustados para Degeneração

**Arquivo:** `app/services/llm_manager/manager.py`

**Estratégia:**
- **Primeira tentativa:** `temperature=0.1`, `presence_penalty=0.3`, `frequency_penalty=0.4`
- **Se loop detectado (retry):**
  - ✅ `temperature` → **0.2** (destrava loops)
  - ✅ `presence_penalty` → **0.6** (penaliza mais)
  - ✅ `frequency_penalty` → **0.8** (penaliza mais)
  - ✅ **Retry imediato** (sem backoff delay)

```python
# v8.0: Parâmetros adaptativos para retry seletivo
if attempt > 0 and isinstance(last_error, ProviderDegenerationError):
    adjusted_temperature = 0.2
    adjusted_presence = 0.6
    adjusted_frequency = 0.8
    logger.info(f"Retry anti-loop: temp=0.2, presence=0.6, frequency=0.8")
```

**Nova exceção:**
```python
class ProviderDegenerationError(ProviderError):
    """Erro de geração degenerada (loop/repetição detectada)."""
    pass
```

---

### 4. **max_tokens Adaptativo** - Baseado no Tamanho do Input

**Arquivo:** `app/services/llm_manager/provider_manager.py`

**Estratégia:**

| Input Tokens | max_tokens | Justificativa |
|--------------|------------|---------------|
| < 3000 | **1200** | Input pequeno → evita runaway |
| 3000-8000 | **2000** | Input médio → balanceado |
| > 8000 | **4096** (limite) | Input grande → permite resposta completa |

```python
# v8.0: max_tokens ADAPTATIVO
if estimated_tokens < 3000:
    max_output_tokens = min(1200, max_output_tokens_limit)
elif estimated_tokens < 8000:
    max_output_tokens = min(2000, max_output_tokens_limit)
else:
    max_output_tokens = max_output_tokens_limit
```

**Benefício:** Reduz drasticamente picos de latência por runaway (loop até 4096 tokens).

---

### 5. **Pós-Processamento Robusto** - Deduplicação Determinística

**Arquivo:** `app/services/agents/profile_extractor_agent.py`

**Função:** `_deduplicate_and_filter_lists(data)`

**Não depende de `uniqueItems` do XGrammar** (pode ser ignorado)

**Recursos implementados:**

1. **Deduplicação case-insensitive** (todas as listas)
2. **Filtro anti-template** para `product_categories[].items`:
   - Hard cap: **máximo 40 itens**
   - Se 5 itens consecutivos compartilham mesmo prefixo/padrão → parar

```python
def filter_template_items(items: list, max_items: int = 40) -> list:
    """
    Hard cap: máximo 40 itens
    Anti-template: se 5 itens seguidos compartilham mesmo prefixo,
    manter apenas os primeiros 5 únicos.
    """
    filtered = []
    pattern_counts = {}
    
    for item in items:
        if len(filtered) >= max_items:
            break
        
        # Extrair "molde" (primeiras 2-3 palavras)
        pattern = ' '.join(item.split()[:3])
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        # Se padrão aparece > 5 vezes, parar
        if pattern_counts[pattern] <= 5:
            filtered.append(item)
    
    return filtered
```

**Listas processadas:**
- ✅ `offerings.products`
- ✅ `offerings.services`
- ✅ **`offerings.product_categories[].items`** (crítico)
- ✅ `offerings.engagement_models`
- ✅ `offerings.key_differentiators`
- ✅ `reputation.client_list`
- ✅ `reputation.certifications`
- ✅ `reputation.awards`
- ✅ `reputation.partnerships`
- ✅ `team.key_roles`
- ✅ `team.team_certifications`
- ✅ `contact.emails`
- ✅ `contact.phones`
- ✅ `contact.locations`

---

### 6. **Documentação Atualizada** - uniqueItems como Hint

**Arquivo:** `app/schemas/profile.py`

```python
"""
v8.0: Deduplicação robusta via pós-processamento
      - uniqueItems/maxItems/minLength são HINTS para o modelo (podem ser ignorados por XGrammar)
      - Validadores Pydantic garantem deduplicação básica
      - Pós-processamento no agente garante deduplicação robusta + anti-template
      - Hard caps numéricos no PROMPT v8.0 (40 itens por categoria)
"""
```

**Comentários atualizados:**
```python
json_schema_extra={"uniqueItems": True}  # Hint para o modelo (não garantido por XGrammar)
```

---

## 📊 Comparação: v7.0 vs v8.0

| Aspecto | v7.0 | v8.0 |
|---------|------|------|
| **Prompt** | Regras soft, sem caps numéricos | **Hard cap: 40 itens + anti-template** |
| **Temperature** | 0.0 (aumenta risco) | **0.1 baseline, 0.2 no retry** |
| **Loop detector** | ❌ Não implementado | ✅ **3 heurísticas em tempo real** |
| **Retry seletivo** | Backoff genérico | ✅ **Parâmetros ajustados + sem delay** |
| **max_tokens** | Fixo (4096) | ✅ **Adaptativo (1200/2000/4096)** |
| **Deduplicação** | Dependia de uniqueItems (ignorado) | ✅ **Pós-processamento robusto** |
| **Anti-template** | ❌ Apenas no prompt | ✅ **Filtro determinístico** |

---

## 🎯 Resultado Esperado

### Antes (v7.0):
```json
"items": [
  "2 RCA + 2 RCA",
  "2 RCA + 2 RCA coaxial",
  "2 RCA + 2 RCA balanceado",
  "2 RCA + 2 RCA com terra",
  ... (dezenas de repetições até 4096 tokens)
]
```
**Latência:** 35-120s (runaway)
**JSON:** Truncado/inválido

### Depois (v8.0):
```json
"items": [
  "RCA",
  "P2",
  "P10",
  "XLR"
]
```
**Latência:** Estável ~5-15s (sem runaway)
**JSON:** Válido e completo

---

## 🔧 Configurações Finais

### Parâmetros de Geração (ProfileExtractorAgent)

```python
DEFAULT_TEMPERATURE = 0.1           # 0.1 reduz loops (0.0 aumenta risco)
DEFAULT_PRESENCE_PENALTY = 0.3      # Baseline anti-loop
DEFAULT_FREQUENCY_PENALTY = 0.4     # Baseline anti-repetição
DEFAULT_SEED = 42                   # Reprodutibilidade
DEFAULT_TIMEOUT = 120.0             # 2 minutos
DEFAULT_MAX_RETRIES = 3             # Com retry seletivo
```

### max_tokens por Input

```python
Input < 3k tokens  → max_tokens = 1200
Input 3k-8k tokens → max_tokens = 2000
Input > 8k tokens  → max_tokens = 4096
```

---

## 📈 Métricas de Sucesso

### Objetivos:
1. ✅ **Eliminar runaway loops** (JSON truncado/inválido)
2. ✅ **Latência média estável** (~10-20s, semelhante ao prompt3/prompt5)
3. ✅ **Redução de outliers** (picos de 120s → < 30s)
4. ✅ **Deduplicação garantida** (não depende de XGrammar)
5. ✅ **Roteamento correto** (sem confusão team/reputation)

### Monitoramento:
- LoopDetector logs: `"LoopDetector: n-gram repetido detectado"`
- Retry seletivo: `"Retry anti-loop (attempt=X): temp=0.2"`
- max_tokens adaptativo: `"Input pequeno, limitando max_tokens a 1200"`

---

## 🚀 Próximos Passos

1. **Testar em produção** com empresas do `repetition-issues-4.jsonl`
2. **Monitorar taxa de degeneração** (quantos retries anti-loop ocorrem)
3. **Ajustar thresholds** se necessário:
   - Loop detector: n-gram > 8 (pode ajustar para 6-10)
   - Anti-template: 5 itens consecutivos (pode ajustar para 3-7)
   - max_tokens: 1200/2000/4096 (pode ajustar baseado em P95)

---

## 📚 Referências

1. [XGrammar Issue #160](https://github.com/mlc-ai/xgrammar/issues/160) - uniqueItems não suportado
2. [SGLang OpenAI API](https://www.aidoczh.com/sglang/backend/openai_api_completions.html) - presence/frequency_penalty
3. [Qwen Loop Reports](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct-GPTQ-Int8/discussions/1) - temperature=0 aumenta loops
4. Community consensus: `temperature=0.1-0.2` + penalties efetivo para anti-loop

---

**Versão:** v8.0
**Data:** 2026-01-23
**Status:** ✅ Implementado e pronto para teste
