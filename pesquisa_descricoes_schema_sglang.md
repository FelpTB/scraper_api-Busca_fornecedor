# Pesquisa: Descrições em JSON Schema para SGLang

## Objetivo
Verificar se é válido e benéfico adicionar descrições em cada campo do schema JSON e se o SGLang utiliza essas descrições durante a geração do perfil.

## Resultados da Pesquisa

### 1. Descrições são Lidas pelo Modelo Durante a Geração

**Fonte:** [Ultimate Guide to Supercharging LLM JSON Outputs](https://dev.to/yigit-konur/the-art-of-the-description-your-ultimate-guide-to-optimizing-llm-json-outputs-with-json-schema-jne)

**Descoberta Crítica:**
> "JSON Schema descriptions are critical for generation quality. While many developers treat the `description` field as mere documentation, **the model actually reads these descriptions during generation**."

**Como Funciona:**
- Descrições fazem parte do **"implicit prompt"** que o modelo recebe
- O modelo processa descrições como instruções diretas para cada campo
- Descrições ajudam o modelo a entender o significado semântico além do tipo de dado

### 2. OpenAI Structured Outputs e Descrições

**Fonte:** OpenAI Documentation e Community Forums

**Como Funciona:**
- Descrições são usadas principalmente para **orientação de geração**, não apenas validação
- Com `strict: true`, o modelo usa descrições para entender e gerar outputs que correspondem ao schema
- Descrições ajudam o modelo a entender a intenção e contexto de cada campo

**Impacto:**
- `gpt-4o-2024-08-06` com Structured Outputs + descrições bem escritas: **100% de confiabilidade**
- `gpt-4-0613` apenas com prompting: **menos de 40% de confiabilidade**

### 3. SGLang e XGrammar

**Fonte:** Documentação SGLang e XGrammar

**Observações:**
- SGLang usa XGrammar como backend padrão para structured outputs
- XGrammar compila JSON schemas em gramáticas context-free (CFG)
- O processo de constrained decoding funciona em nível de tokens (máscaras de logits)

**Sobre Descrições:**
- A documentação do SGLang mostra exemplos usando `Field(description=...)` no Pydantic
- XGrammar processa JSON schemas completos, incluindo campos `description`
- **Recomendação da documentação:** "It's advisable to explicitly include instructions in the prompt to guide the model to generate the desired format"

### 4. Como Descrições Ajudam na Extração

**Benefícios Identificados:**

1. **Contexto Semântico:**
   - Campo `"location"` sem descrição: modelo pode não saber o que extrair
   - Campo `"location"` com descrição: `"A cidade e estado onde o evento ocorre (ex: 'São Paulo, SP')"` → modelo entende exatamente o que buscar

2. **Resolução de Ambiguidade:**
   - `"date"` pode ser `YYYY-MM-DD` ou data em linguagem natural
   - Descrição `"Data específica no formato YYYY-MM-DD"` elimina ambiguidade

3. **Orientação para Enums:**
   - Enum `["A1", "B2", "C3"]` sem descrição: modelo não sabe o que cada valor significa
   - Descrição explicando cada enum: modelo mapeia corretamente intenções do usuário para valores

4. **Formato e Padrões:**
   - `format: "email"` ajuda, mas descrição reforça: `"Endereço de email do usuário (deve conter '@' e domínio)"`

### 5. Constrained Decoding vs Descrições

**Importante Entender:**
- **Constrained Decoding (XGrammar)**: Garante estrutura sintática (JSON válido, tipos corretos)
- **Descrições**: Guiam conteúdo semântico (o que colocar em cada campo)

**Ambos são necessários:**
- Constrained decoding garante que o JSON está correto estruturalmente
- Descrições garantem que o conteúdo dentro do JSON está correto semanticamente

### 6. Melhores Práticas para Descrições

**8 Pilares Identificados:**

1. **Eliminar Ambiguidade**: Seja explícito e específico
2. **Iluminar Intenção**: Explique o "porquê" do campo
3. **Mandatar Formatos**: Especifique formatos claramente (ex: "YYYY-MM-DD")
4. **Mostrar com Exemplos**: Inclua exemplos na descrição
5. **Decodificar Enums**: Explique o significado de cada valor enum
6. **Amplificar Restrições**: Reforce campos obrigatórios
7. **Equilibrar**: Conciso mas claro
8. **Falar a Linguagem da IA**: Escreva como instrução

**Exemplo de Boa Descrição:**
```python
Field(
    description="**Obrigatório.** Nome completo da empresa conforme registro na Receita Federal. Use o nome fantasia se disponível, caso contrário use a razão social."
)
```

**Exemplo de Descrição Ruim:**
```python
Field(description="Nome da empresa")  # Muito vago
```

## Conclusão

### ✅ SIM, é VÁLIDO e BENÉFICO adicionar descrições

**Evidências:**
1. ✅ Modelos realmente leem descrições durante a geração (não apenas validação)
2. ✅ Descrições fazem parte do "implicit prompt" que o modelo processa
3. ✅ OpenAI Structured Outputs mostra melhoria dramática com descrições bem escritas
4. ✅ SGLang/XGrammar processa JSON schemas completos, incluindo descrições
5. ✅ Documentação do SGLang mostra exemplos usando `Field(description=...)`

### ⚠️ IMPORTANTE: Como SGLang/XGrammar Usa Descrições

**Hipótese Baseada na Pesquisa:**
- **XGrammar (constrained decoding)**: Trabalha em nível sintático (tokens válidos)
- **Descrições do Schema**: Podem ser usadas de duas formas:
  1. **Se o modelo lê o schema**: Descrições ajudam semanticamente
  2. **Se apenas o constrained decoding é usado**: Descrições podem não ser lidas diretamente

**Recomendação da Documentação SGLang:**
> "For better output quality, it's advisable to explicitly include instructions in the prompt to guide the model to generate the desired format."

**Isso sugere que:**
- Descrições no schema podem ajudar, mas não substituem instruções no prompt
- Para máxima eficácia, combine:
  - Descrições no schema (para contexto semântico)
  - Instruções no prompt (para orientação explícita)

## Recomendação para Implementação

### ✅ ADICIONAR DESCRIÇÕES É RECOMENDADO

**Razões:**
1. **Compatibilidade**: Funciona com OpenAI e outros providers que leem descrições
2. **Documentação**: Melhora a documentação do código
3. **Futuro-proof**: Se SGLang/XGrammar melhorar suporte a descrições, já estará pronto
4. **Custo Zero**: Adicionar descrições não tem overhead significativo
5. **Melhoria Potencial**: Mesmo que não seja usado diretamente pelo XGrammar, pode ajudar em fallbacks ou outros providers

### Como Implementar

**Exemplo com Pydantic:**
```python
class Identidade(BaseModel):
    nome_empresa: Optional[str] = Field(
        None,
        description="Nome completo da empresa conforme registro na Receita Federal. Use nome fantasia se disponível, caso contrário use razão social."
    )
    cnpj: Optional[str] = Field(
        None,
        description="CNPJ da empresa no formato XX.XXX.XXX/XXXX-XX ou apenas números. Deve ter 14 dígitos."
    )
    descricao: Optional[str] = Field(
        None,
        description="Descrição detalhada da empresa, incluindo atividades principais, missão, histórico ou diferenciais. Extraia do texto fornecido."
    )
    ano_fundacao: Optional[str] = Field(
        None,
        description="Ano de fundação da empresa no formato YYYY (ex: '2010'). Se apenas década for mencionada, use o ano aproximado."
    )
    faixa_funcionarios: Optional[str] = Field(
        None,
        description="Faixa de número de funcionários no formato 'MIN-MAX' (ex: '10-50', '100-500') ou descrição textual se não houver números específicos."
    )
```

**Benefícios:**
- Pydantic automaticamente inclui descrições no JSON Schema gerado
- `CompanyProfile.model_json_schema()` incluirá todas as descrições
- Schema fica mais completo e informativo

## Próximos Passos

1. ✅ Adicionar descrições detalhadas em todos os campos do schema
2. ✅ Testar se há melhoria na qualidade de extração
3. ✅ Monitorar se descrições ajudam especialmente em campos ambíguos
4. ✅ Comparar resultados com e sem descrições (se possível)

## Referências

- [Ultimate Guide to Supercharging LLM JSON Outputs](https://dev.to/yigit-konur/the-art-of-the-description-your-ultimate-guide-to-optimizing-llm-json-outputs-with-json-schema-jne)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [SGLang Structured Outputs](https://docs.sglang.io/advanced_features/structured_outputs.html)
- [XGrammar Documentation](https://xgrammar.mlc.ai/docs/how_to/json_generation.html)
