# Pesquisa: SGLang Structured Outputs - Remoção de Schema do System Prompt

## Objetivo
Remover a referência ao schema JSON do system prompt, utilizando as capacidades nativas do SGLang para forçar o formato de resposta através de `json_schema` parameter.

## Resultados da Pesquisa

### 1. SGLang Structured Outputs

**Fonte:** [SGLang Documentation - Structured Outputs](https://docs.sglang.io/advanced_features/structured_outputs.html)

#### Capacidades do SGLang:
- SGLang suporta **constrained decoding** através de três backends de gramática:
  - **XGrammar** (padrão): Melhor performance, suporta JSON schema, regex e EBNF
  - **Outlines**: Suporta JSON schema e regex
  - **Llguidance**: Suporta JSON schema, regex e EBNF

#### Como Funciona:
- O modelo é **garantido** a seguir as restrições do schema através de **constrained decoding**
- Apenas tokens válidos segundo a gramática são gerados a cada passo
- Não depende de instruções no prompt para seguir o formato

### 2. Implementação com JSON Schema

#### OpenAI Compatible API:
```python
response = client.chat.completions.create(
    model="model-name",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "schema_name",
            "schema": json_schema_dict  # JSON Schema completo
        }
    }
)
```

#### Native API (SGLang Runtime):
```python
sampling_params = {
    "temperature": 0.0,
    "json_schema": json.dumps(json_schema_dict)
}
outputs = llm.generate(prompts, sampling_params)
```

### 3. Recomendações para Modelos Pequenos

**Fonte:** Documentação oficial do SGLang

**Importante:** Embora o SGLang garanta o formato através de constrained decoding, **é recomendado manter instruções básicas no prompt** para melhor qualidade de saída, especialmente para modelos pequenos.

**Exemplo recomendado:**
```
"Por favor, gere a saída no formato JSON conforme solicitado."
```

**NÃO é necessário** incluir o schema completo no prompt quando usando `json_schema`, pois:
- O formato é garantido pelo constrained decoding
- O schema completo no prompt consome tokens desnecessariamente
- Para modelos pequenos, reduzir tokens do prompt melhora a qualidade da resposta

### 4. Melhores Práticas Identificadas

1. **Remover schema do system prompt**: O schema completo não precisa estar no prompt quando usando `json_schema`
2. **Manter instrução simples**: Manter apenas uma instrução genérica sobre formato JSON
3. **Usar Pydantic para gerar schema**: Converter modelos Pydantic para JSON Schema automaticamente
4. **XGrammar como padrão**: Usar XGrammar (padrão) para melhor performance

### 5. Compatibilidade com Modelos Pequenos

- **Issues conhecidos**: Alguns modelos pequenos podem ter problemas com structured outputs (ex: DeepSeek com MTP)
- **Solução**: XGrammar resolve a maioria dos problemas de compatibilidade
- **Performance**: Constrained decoding tem overhead mínimo, especialmente com XGrammar

## Conclusão

Para o nosso caso de uso:
1. ✅ **Remover schema completo do system prompt** - economiza tokens e melhora qualidade
2. ✅ **Usar `json_schema` via `response_format`** - garante formato sem depender do prompt
3. ✅ **Manter instrução simples** - "Gere a resposta em formato JSON válido"
4. ✅ **Converter CompanyProfile para JSON Schema** - usar `model_json_schema()` do Pydantic

## Implementação Proposta

1. Atualizar `ProfileExtractorAgent`:
   - Remover schema do `SYSTEM_PROMPT`
   - Adicionar método para gerar JSON Schema do `CompanyProfile`
   - Atualizar `_get_response_format()` para retornar `json_schema` format

2. Atualizar `provider_manager.py`:
   - Garantir que RunPod (SGLang) use `json_schema` ao invés de apenas reforço no prompt
   - Verificar se outros providers suportam `json_schema`

3. Testar com modelo pequeno (Ministral-3-8B) para validar qualidade
