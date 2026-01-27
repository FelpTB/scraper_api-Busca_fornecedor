# Opções de Prompt Engineering para Montagem de Perfil

## Contexto e Problemas Identificados

### Problemas Atuais
1. **Loops infinitos em listas**: Modelo gera variações do mesmo produto (ex: "RCA", "Conector RCA", "RCA macho", "RCA fêmea"...)
2. **Completude inconsistente**: Alguns perfis ficam incompletos, especialmente em chunks com muitos produtos
3. **Degeneração semântica**: JSON válido mas com conteúdo repetitivo e sem valor

### Stack Atual
- ✅ SGLang com XGrammar (json_schema)
- ✅ Schema reduzido (maxItems: 60-80)
- ✅ Prompt sem schema completo
- ✅ Normalização e merge de perfis

## Pesquisa Realizada

### Frameworks Identificados
1. **Few-Shot Prompting**: Exemplos input-output ensinam o modelo o formato desejado
2. **Chain-of-Thought**: Modelo mostra raciocínio passo a passo
3. **Structured Prompt Patterns**: Templates reutilizáveis para extração
4. **Metadata-Enhanced Chunking**: Informações sobre estrutura do chunk melhoram completude

### Melhores Práticas Encontradas
- **Limites explícitos**: "Liste exatamente N itens" funciona melhor que limites implícitos
- **Stop conditions claras**: Instruções explícitas sobre quando parar
- **Few-shot examples**: 2-3 exemplos são suficientes, muitos causam overfitting
- **Chunk metadata**: Informar ao modelo sobre contexto do chunk (índice, total, tipo de conteúdo) melhora completude

---

## OPÇÃO 1: Few-Shot Prompting com Limites Explícitos

### Estratégia
Usar exemplos concretos mostrando o comportamento desejado, com limites explícitos de quantidade e condições de parada claras.

### Prompt Proposto

```python
SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido e retorne em formato JSON válido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais.
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. LIMITES DE LISTAS - CRÍTICO:
   - Máximo 60 produtos por categoria
   - Máximo 40 categorias de produtos
   - Máximo 50 serviços
   - Máximo 80 clientes
   - Máximo 50 parcerias
   - PARE quando atingir o limite ou quando não houver mais itens únicos no texto
   - Dê preferencia para itens ítens que são claramente únicos.
   - NÃO gere variações do mesmo item (ex: "RCA" e "Conector RCA" são o mesmo produto)
4. COMPLETUDE: Extraia TODOS os dados relevantes encontrados no texto, mas respeite os limites acima.

EXEMPLOS DE COMPORTAMENTO CORRETO:

<EXEMPLO_1>
INPUT: "Nossos produtos incluem: Cabo 1KV HEPR, Cabo 1KV LSZH, Cabo Flex 750V, Conector RCA, Conector XLR"

OUTPUT:
{
  "ofertas": {
    "produtos": [
      {
        "categoria": "Cabos",
        "produtos": ["Cabo 1KV HEPR", "Cabo 1KV LSZH", "Cabo Flex 750V"]
      },
      {
        "categoria": "Conectores",
        "produtos": ["Conector RCA", "Conector XLR"]
      }
    ]
  }
}
</EXEMPLO_1>

REGRAS DE PARADA:
- Se atingiu o limite máximo de itens, PARE imediatamente
- Se não há mais itens únicos no texto, PARE
- NÃO invente itens que não estão no texto

Retorne APENAS um objeto JSON válido, sem markdown ou explicações.
"""
```

### Vantagens
- ✅ Exemplos claros mostram comportamento esperado
- ✅ Limites explícitos reduzem loops
- ✅ Condições de parada bem definidas
- ✅ Demonstra deduplicação (exemplo 2)

### Desvantagens
- ⚠️ Consome mais tokens (exemplos)
- ⚠️ Pode precisar ajuste dos exemplos para diferentes tipos de conteúdo

---

## OPÇÃO 2: Chain-of-Thought com Verificação de Parada

### Estratégia
Modelo mostra raciocínio passo a passo, incluindo verificação de quando parar de extrair itens.

### Prompt Proposto

```python
SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido seguindo este processo:

PROCESSO DE EXTRAÇÃO (siga passo a passo):

PASSO 1 - ANÁLISE INICIAL:
- Identifique o tipo de conteúdo (catálogo, página institucional, lista de serviços, etc.)
- Estime quantos itens únicos existem no texto
- Identifique seções principais (produtos, serviços, clientes, etc.)

PASSO 2 - EXTRAÇÃO COM LIMITES:
- Para cada seção, extraia itens únicos até atingir o limite:
  * Produtos: máximo 60 por categoria, máximo 40 categorias
  * Serviços: máximo 50
  * Clientes: máximo 80
  * Parcerias: máximo 50
- Para cada item extraído, verifique: "Este item já foi extraído ou é variação de um item existente?"
- Se SIM: pule o item
- Se NÃO: adicione à lista

PASSO 3 - VERIFICAÇÃO DE PARADA:
Antes de adicionar cada novo item, pergunte:
1. "Este item já está na lista?" → Se sim, PARE de adicionar variações
2. "Atingi o limite máximo?" → Se sim, PARE imediatamente
3. "Há mais itens únicos no texto?" → Se não, PARE

PASSO 4 - CONSOLIDAÇÃO:
- Remova duplicatas semânticas
- Agrupe produtos por categoria
- Valide que todos os campos obrigatórios foram preenchidos

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL)
2. NÃO gere variações: "RCA" e "Conector RCA" são o mesmo produto
3. NÃO invente itens que não estão no texto
4. PARE quando não houver mais itens únicos ou quando atingir limites

FORMATO DE SAÍDA:
Retorne APENAS um objeto JSON válido, sem markdown, sem explicações, sem raciocínio visível na saída final.
O raciocínio acima é para você seguir internamente, não para incluir na resposta.
"""
```

### Vantagens
- ✅ Processo estruturado reduz loops
- ✅ Verificação explícita de parada
- ✅ Melhor para modelos que se beneficiam de raciocínio passo a passo
- ✅ Foco em deduplicação

### Desvantagens
- ⚠️ Pode gerar mais tokens se modelo não seguir instrução de não mostrar raciocínio
- ⚠️ Requer modelo com boa capacidade de seguir instruções complexas

---

## OPÇÃO 3: Chunk-Aware Prompting com Metadados

### Estratégia
Incluir informações sobre o chunk (índice, total, tipo de conteúdo) para guiar o modelo sobre contexto e quando parar.

### Prompt Proposto

```python
def _build_user_prompt(self, content: str = "", chunk_index: int = None, total_chunks: int = None, chunk_type: str = None, **kwargs) -> str:
    """
    Constrói prompt com metadados do chunk.
    """
    metadata = []
    if chunk_index is not None and total_chunks is not None:
        metadata.append(f"CONTEXTO DO CHUNK: Este é o chunk {chunk_index} de {total_chunks} chunks totais.")
        if chunk_index == 1:
            metadata.append("Este é o PRIMEIRO chunk - priorize informações de identidade e classificação.")
        elif chunk_index == total_chunks:
            metadata.append("Este é o ÚLTIMO chunk - certifique-se de extrair todos os dados restantes.")
        else:
            metadata.append("Este é um chunk INTERMEDIÁRIO - foque em produtos, serviços e reputação.")
    
    if chunk_type:
        metadata.append(f"TIPO DE CONTEÚDO: {chunk_type}")
        if "catálogo" in chunk_type.lower() or "produtos" in chunk_type.lower():
            metadata.append("ATENÇÃO: Este chunk contém muitos produtos. Extraia APENAS itens únicos mencionados explicitamente. NÃO gere variações.")
    
    metadata_text = "\n".join(metadata) if metadata else ""
    
    return f"""{metadata_text}

Analise este conteúdo e extraia os dados em Português:

{content}

INSTRUÇÕES ESPECÍFICAS PARA ESTE CHUNK:
- Se este chunk contém lista de produtos: extraia APENAS os produtos mencionados explicitamente
- NÃO gere variações (ex: se menciona "RCA", não adicione "Conector RCA", "RCA macho", etc.)
- Se você já extraiu um item em chunks anteriores, NÃO o extraia novamente
- Respeite os limites: máximo 60 produtos/categoria, 40 categorias, 50 serviços, 80 clientes
- PARE quando não houver mais itens únicos ou quando atingir os limites
"""

SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido e retorne em formato JSON válido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais.
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. LIMITES ABSOLUTOS (NÃO EXCEDER):
   - Produtos: máximo 60 por categoria, máximo 40 categorias
   - Serviços: máximo 50
   - Clientes: máximo 80
   - Parcerias: máximo 50
4. REGRA DE PARADA CRÍTICA:
   - PARE imediatamente ao atingir qualquer limite
   - PARE se não houver mais itens únicos no texto
   - NÃO gere variações de itens já extraídos
   - NÃO invente itens que não estão explicitamente no texto
5. DEDUPLICAÇÃO:
   - "RCA" e "Conector RCA" = mesmo produto → extraia apenas um
   - "Petrobras" e "Grupo Petrobras" = mesmo cliente → extraia apenas um
   - Use o nome mais completo e específico quando houver variações
6. COMPLETUDE:
   - Extraia TODOS os dados relevantes encontrados
   - Mas respeite os limites acima
   - Priorize informações mais específicas e completas

Se um campo não for encontrado, use null ou lista vazia.
Retorne APENAS um objeto JSON válido, sem markdown ou explicações.
"""
```

### Modificações Necessárias no Código

```python
# Em profile_extractor_agent.py
async def extract_profile(
    self,
    content: str,
    chunk_index: int = None,
    total_chunks: int = None,
    chunk_type: str = None,
    ctx_label: str = "",
    request_id: str = ""
) -> CompanyProfile:
    # ... código existente ...
    return await self.execute(
        priority=LLMPriority.NORMAL,
        timeout=self.DEFAULT_TIMEOUT,
        ctx_label=ctx_label,
        request_id=request_id,
        content=content,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        chunk_type=chunk_type
    )
```

### Vantagens
- ✅ Contexto do chunk ajuda modelo a entender quando parar
- ✅ Permite estratégias diferentes por tipo de chunk
- ✅ Reduz loops em chunks de catálogo
- ✅ Melhora completude ao informar posição do chunk

### Desvantagens
- ⚠️ Requer modificação no código para passar metadados
- ⚠️ Precisa detectar tipo de chunk (pode ser heurístico)

---

## Comparação das Opções

| Critério | Opção 1: Few-Shot | Opção 2: Chain-of-Thought | Opção 3: Chunk-Aware |
|----------|-------------------|---------------------------|----------------------|
| **Prevenção de Loops** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Completude** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Simplicidade** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Tokens Consumidos** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Facilidade Implementação** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Eficácia em Chunks Longos** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## Recomendação

### Implementação Gradual Sugerida:

**FASE 1 (Imediato)**: Implementar **Opção 1 (Few-Shot)**
- Mais fácil de implementar
- Melhora imediata na prevenção de loops
- Pode ser testada rapidamente

**FASE 2 (Curto Prazo)**: Adicionar **Opção 3 (Chunk-Aware)**
- Melhora significativa em completude
- Especialmente útil para chunks de catálogo
- Requer modificação no código mas traz grande valor

**FASE 3 (Opcional)**: Combinar com **Opção 2 (Chain-of-Thought)**
- Se ainda houver problemas de loops
- Útil para casos muito complexos

## Considerações sobre Estrutura do Chunk

### ✅ RECOMENDADO: Passar Metadados do Chunk

**Benefícios identificados na pesquisa:**
1. **Completude**: Modelo entende contexto e prioriza melhor
2. **Parada**: Sabe quando está no último chunk e deve extrair tudo
3. **Foco**: Pode focar em diferentes seções por chunk
4. **Prevenção de Loops**: Sabe que é chunk de catálogo e deve ser mais conservador

**Metadados Úteis:**
- `chunk_index` / `total_chunks`: Posição do chunk
- `chunk_type`: Tipo de conteúdo (catálogo, institucional, serviços, etc.)
- `estimated_items`: Estimativa de quantos itens únicos existem
- `previous_items`: Lista de itens já extraídos (para deduplicação)

**Implementação Sugerida:**
```python
# Detectar tipo de chunk (heurístico simples)
def detect_chunk_type(content: str) -> str:
    content_lower = content.lower()
    if any(word in content_lower for word in ["catálogo", "produtos", "nossos produtos", "linha completa"]):
        return "catálogo_produtos"
    elif any(word in content_lower for word in ["serviços", "nossos serviços", "oferecemos"]):
        return "serviços"
    elif any(word in content_lower for word in ["clientes", "cases", "portfólio"]):
        return "reputação"
    else:
        return "institucional"
```

## Próximos Passos

1. ✅ Implementar Opção 1 (Few-Shot) como baseline
2. ✅ Testar com chunks problemáticos conhecidos
3. ✅ Medir: taxa de loops, completude, latência
4. ✅ Iterar baseado em resultados
5. ✅ Adicionar Opção 3 se necessário

## Referências

- Brex Prompt Engineering Guide: https://github.com/brexhq/prompt-engineering
- Few-Shot Learning for Information Extraction: https://arxiv.org/abs/2209.09450
- Chain-of-Thought Prompting: https://arxiv.org/pdf/2201.11903.pdf
- Structured Output Best Practices: OpenAI Documentation
- Chunking and Metadata in RAG: LangChain Documentation
