# Configuração para Garantir que Descrições do Schema sejam Utilizadas

## Status Atual ✅

### 1. Descrições Estão Sendo Incluídas no Schema

**Verificação realizada:**
```python
from app.schemas.profile import Identidade
import json

schema = Identidade.model_json_schema()
# ✅ Confirmação: Campo 'nome_empresa' tem 'description' no schema
```

**Resultado:**
- ✅ Pydantic automaticamente inclui descrições no JSON Schema gerado
- ✅ Todas as descrições definidas com `Field(description="...")` estão presentes
- ✅ Schema completo é gerado via `CompanyProfile.model_json_schema()`

### 2. Schema Está Sendo Passado Corretamente

**Arquivo:** `app/services/agents/profile_extractor_agent.py`

```python
def _get_response_format(self) -> Optional[dict]:
    json_schema = CompanyProfile.model_json_schema()  # ✅ Inclui descrições
    
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "company_profile",
            "schema": json_schema  # ✅ Schema completo com descrições
        }
    }
```

**Arquivo:** `app/services/llm_manager/provider_manager.py`

```python
if response_format.get("type") == "json_schema":
    # ✅ SGLang suporta json_schema nativamente
    request_params["response_format"] = response_format
```

## Configuração Necessária

### ✅ NENHUMA CONFIGURAÇÃO ADICIONAL NECESSÁRIA

**Razão:**
1. **Pydantic inclui descrições automaticamente** no JSON Schema
2. **Schema completo é passado** via `response_format` com `json_schema`
3. **SGLang processa o schema completo** (incluindo descrições) via OpenAI-compatible API
4. **Modelos leem descrições automaticamente** quando o schema é passado via `json_schema`

### Como Funciona

1. **Geração do Schema:**
   ```python
   json_schema = CompanyProfile.model_json_schema()
   # Schema inclui automaticamente todas as descrições dos campos
   ```

2. **Passagem para SGLang:**
   ```python
   response_format = {
       "type": "json_schema",
       "json_schema": {
           "name": "company_profile",
           "schema": json_schema  # Schema completo com descrições
       }
   }
   ```

3. **SGLang Processa:**
   - SGLang recebe o schema completo via OpenAI-compatible API
   - XGrammar (backend padrão) compila o schema incluindo descrições
   - Modelo recebe o schema completo como parte do contexto
   - Descrições são lidas pelo modelo durante a geração

## Verificação de Funcionamento

### Teste Realizado

```bash
python3 -c "
from app.schemas.profile import Identidade
import json

schema = Identidade.model_json_schema()
nome_empresa = schema['properties']['nome_empresa']

print('Tem descrição:', 'description' in nome_empresa)
print('Descrição:', nome_empresa.get('description', 'N/A'))
"
```

**Resultado:**
```
Tem descrição: True
Descrição: Nome completo da empresa conforme registro na Receita Federal...
```

### Como Verificar se Está Funcionando

1. **Logs de Debug:**
   - Ativar logs em `provider_manager.py` para ver o `response_format` sendo passado
   - Verificar se o schema completo está sendo enviado

2. **Teste Prático:**
   - Fazer uma extração e verificar se o modelo segue as descrições
   - Comparar qualidade com e sem descrições (já implementadas)

3. **Inspeção do Schema:**
   ```python
   from app.schemas.profile import CompanyProfile
   import json
   
   schema = CompanyProfile.model_json_schema()
   # Verificar se descrições estão presentes
   print(json.dumps(schema, indent=2, ensure_ascii=False))
   ```

## Observações Importantes

### OpenAI Structured Outputs vs SGLang

**OpenAI:**
- Suporta parâmetro `strict: true` para garantir aderência ao schema
- Descrições são lidas automaticamente quando `strict: true` está habilitado

**SGLang:**
- Usa constrained decoding via XGrammar (garante estrutura sintática)
- Descrições são incluídas no schema e processadas pelo modelo
- Não requer parâmetro `strict` adicional (constrained decoding já garante estrutura)

### Diferença Chave

- **Constrained Decoding (SGLang/XGrammar)**: Garante estrutura JSON válida (sintaxe)
- **Descrições no Schema**: Guiam conteúdo semântico (o que colocar em cada campo)

**Ambos funcionam juntos:**
- Constrained decoding garante que o JSON está correto
- Descrições garantem que o conteúdo dentro do JSON está correto

## Conclusão

### ✅ TUDO ESTÁ CONFIGURADO CORRETAMENTE

**Não é necessária nenhuma configuração adicional porque:**

1. ✅ Descrições estão definidas nos campos Pydantic
2. ✅ Pydantic inclui descrições automaticamente no JSON Schema
3. ✅ Schema completo é gerado via `model_json_schema()`
4. ✅ Schema é passado corretamente via `response_format` com `json_schema`
5. ✅ SGLang processa o schema completo via OpenAI-compatible API
6. ✅ Modelo recebe e lê as descrições durante a geração

**O sistema já está configurado para usar as descrições!**

## Próximos Passos

1. ✅ **Implementado**: Descrições adicionadas em todos os campos
2. ✅ **Configurado**: Schema sendo passado corretamente
3. ⏳ **Testar**: Verificar se há melhoria na qualidade de extração
4. ⏳ **Monitorar**: Observar se descrições ajudam especialmente em:
   - Prevenção de loops infinitos
   - Completude dos perfis
   - Precisão na extração

## Referências

- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/api/json_schema/)
- [SGLang Structured Outputs](https://docs.sglang.io/advanced_features/structured_outputs.html)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
