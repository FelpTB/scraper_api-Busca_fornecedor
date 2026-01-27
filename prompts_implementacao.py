"""
Prompts prontos para implementação - 3 opções de engenharia de prompt
para montagem de perfil com foco em completude e prevenção de loops infinitos.
"""

# ============================================================================
# OPÇÃO 1: Few-Shot Prompting com Limites Explícitos
# ============================================================================

SYSTEM_PROMPT_OPCAO_1 = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido e retorne em formato JSON válido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais (ex: "SaaS", "Big Data", "Machine Learning").
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. LIMITES DE LISTAS - CRÍTICO (NÃO EXCEDER):
   - Máximo 60 produtos por categoria
   - Máximo 40 categorias de produtos
   - Máximo 50 serviços
   - Máximo 80 clientes na lista_clientes
   - Máximo 50 parcerias
   - Máximo 50 certificações
   - Máximo 30 estudos de caso
   - PARE quando atingir qualquer limite ou quando não houver mais itens únicos no texto
4. REGRA DE DEDUPLICAÇÃO:
   - NÃO gere variações do mesmo item (ex: "RCA" e "Conector RCA" são o mesmo produto)
   - Use o nome mais completo e específico quando houver variações
   - Se você já extraiu um item, NÃO o extraia novamente com nome diferente
5. COMPLETUDE: Extraia TODOS os dados relevantes encontrados no texto, mas respeite os limites acima.

EXEMPLOS DE COMPORTAMENTO CORRETO:

<EXEMPLO_1_PRODUTOS>
INPUT: "Nossos produtos incluem: Cabo 1KV HEPR, Cabo 1KV LSZH, Cabo Flex 750V, Conector RCA, Conector XLR, Conector P2"

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
        "produtos": ["Conector RCA", "Conector XLR", "Conector P2"]
      }
    ]
  }
}
NOTA: Cada produto mencionado uma vez, sem variações.
</EXEMPLO_1_PRODUTOS>

<EXEMPLO_2_CLIENTES>
INPUT: "Nossos clientes incluem: Petrobras, Vale, Ambev, Grupo Petrobras (RJ), Petrobras SP, Vale Mineração"

OUTPUT:
{
  "reputacao": {
    "lista_clientes": ["Petrobras", "Vale", "Ambev"]
  }
}
NOTA: "Grupo Petrobras (RJ)", "Petrobras SP" são variações de "Petrobras". "Vale Mineração" é variação de "Vale". Extrair apenas os nomes principais únicos.
</EXEMPLO_2_CLIENTES>

<EXEMPLO_3_SERVICOS>
INPUT: "Serviços oferecidos: Consultoria em automação industrial, Desenvolvimento de software customizado, Suporte técnico 24/7, Manutenção preventiva"

OUTPUT:
{
  "ofertas": {
    "servicos": [
      {
        "nome": "Consultoria em automação industrial",
        "descricao": "Consultoria especializada em automação industrial"
      },
      {
        "nome": "Desenvolvimento de software customizado",
        "descricao": "Desenvolvimento de software sob medida para necessidades específicas"
      },
      {
        "nome": "Suporte técnico 24/7",
        "descricao": "Suporte técnico disponível 24 horas por dia, 7 dias por semana"
      },
      {
        "nome": "Manutenção preventiva",
        "descricao": "Serviços de manutenção preventiva para equipamentos"
      }
    ]
  }
}
NOTA: Cada serviço mencionado uma vez, com descrição baseada no contexto.
</EXEMPLO_3_SERVICOS>

<EXEMPLO_4_PARADA>
INPUT: "Produtos: Item A, Item B, Item C" (apenas 3 itens mencionados)

OUTPUT:
{
  "ofertas": {
    "produtos": [
      {
        "categoria": "Produtos",
        "produtos": ["Item A", "Item B", "Item C"]
      }
    ]
  }
}
NOTA: Apenas 3 itens foram mencionados, então extrair apenas 3. NÃO adicionar variações ou itens não mencionados.
</EXEMPLO_4_PARADA>

REGRAS DE PARADA (CRÍTICO):
1. Se você já extraiu um item, NÃO extraia variações dele
2. Se atingiu o limite máximo de itens em qualquer lista, PARE imediatamente
3. Se não há mais itens únicos no texto, PARE
4. NÃO invente itens que não estão explicitamente no texto
5. NÃO continue gerando após extrair todos os itens únicos encontrados

Se um campo não for encontrado, use null ou lista vazia.
Retorne APENAS um objeto JSON válido, sem markdown (```json), sem explicações adicionais.
"""


# ============================================================================
# OPÇÃO 2: Chain-of-Thought com Verificação de Parada
# ============================================================================

SYSTEM_PROMPT_OPCAO_2 = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido seguindo este processo estruturado:

PROCESSO DE EXTRAÇÃO (siga passo a passo internamente):

PASSO 1 - ANÁLISE INICIAL:
- Identifique o tipo de conteúdo (catálogo de produtos, página institucional, lista de serviços, página de clientes, etc.)
- Estime quantos itens únicos existem no texto para cada categoria
- Identifique seções principais (produtos, serviços, clientes, certificações, etc.)

PASSO 2 - EXTRAÇÃO COM LIMITES E VERIFICAÇÃO:
Para cada seção (produtos, serviços, clientes, etc.):
  a) Extraia itens únicos até atingir o limite:
     * Produtos: máximo 60 por categoria, máximo 40 categorias
     * Serviços: máximo 50
     * Clientes: máximo 80
     * Parcerias: máximo 50
     * Certificações: máximo 50
     * Estudos de caso: máximo 30
  
  b) ANTES de adicionar cada novo item, verifique:
     1. "Este item já foi extraído?" → Se sim, PULE
     2. "Este item é variação de um item já extraído?" → Se sim, PULE
     3. "Atingi o limite máximo para esta lista?" → Se sim, PARE esta lista
     4. "Este item está explicitamente no texto?" → Se não, PULE
  
  c) Se passou todas as verificações, adicione o item

PASSO 3 - VERIFICAÇÃO DE PARADA GLOBAL:
Antes de continuar extraindo, pergunte:
1. "Extraí todos os itens únicos do texto?" → Se sim, PARE
2. "Atingi algum limite máximo?" → Se sim, PARE
3. "Há mais itens únicos que ainda não extraí?" → Se não, PARE

PASSO 4 - CONSOLIDAÇÃO FINAL:
- Remova qualquer duplicata semântica restante
- Agrupe produtos por categoria quando aplicável
- Valide que respeitou todos os limites
- Certifique-se de que não há variações do mesmo item

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais.
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. DEDUPLICAÇÃO RIGOROSA:
   - "RCA" e "Conector RCA" = mesmo produto → extraia apenas um (use "Conector RCA")
   - "Petrobras" e "Grupo Petrobras" = mesmo cliente → extraia apenas um (use "Petrobras")
   - "Vale" e "Vale Mineração" = mesmo cliente → extraia apenas um (use "Vale")
4. NÃO invente itens que não estão no texto
5. NÃO gere variações de itens já extraídos

FORMATO DE SAÍDA:
Retorne APENAS um objeto JSON válido, sem markdown, sem explicações, sem mostrar o raciocínio.
O processo acima é para você seguir internamente, não para incluir na resposta JSON.

Se um campo não for encontrado, use null ou lista vazia.
"""


# ============================================================================
# OPÇÃO 3: Chunk-Aware Prompting com Metadados
# ============================================================================

SYSTEM_PROMPT_OPCAO_3 = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido e retorne em formato JSON válido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais.
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. LIMITES ABSOLUTOS (NÃO EXCEDER):
   - Produtos: máximo 60 por categoria, máximo 40 categorias
   - Serviços: máximo 50
   - Clientes: máximo 80
   - Parcerias: máximo 50
   - Certificações: máximo 50
   - Estudos de caso: máximo 30
4. REGRA DE PARADA CRÍTICA:
   - PARE imediatamente ao atingir qualquer limite
   - PARE se não houver mais itens únicos no texto
   - NÃO gere variações de itens já extraídos
   - NÃO invente itens que não estão explicitamente no texto
5. DEDUPLICAÇÃO:
   - "RCA" e "Conector RCA" = mesmo produto → extraia apenas um (prefira o mais específico)
   - "Petrobras" e "Grupo Petrobras" = mesmo cliente → extraia apenas um (prefira o nome principal)
   - Use o nome mais completo e específico quando houver variações
6. COMPLETUDE:
   - Extraia TODOS os dados relevantes encontrados
   - Mas respeite os limites acima
   - Priorize informações mais específicas e completas

Se um campo não for encontrado, use null ou lista vazia.
Retorne APENAS um objeto JSON válido, sem markdown ou explicações.
"""


def build_user_prompt_opcao_3(
    content: str,
    chunk_index: int = None,
    total_chunks: int = None,
    chunk_type: str = None,
    estimated_items: int = None
) -> str:
    """
    Constrói prompt do usuário com metadados do chunk para Opção 3.
    
    Args:
        content: Conteúdo do chunk
        chunk_index: Índice do chunk (1-based)
        total_chunks: Total de chunks
        chunk_type: Tipo de conteúdo detectado
        estimated_items: Estimativa de itens únicos no chunk
    
    Returns:
        Prompt formatado com metadados
    """
    metadata_parts = []
    
    # Informações sobre posição do chunk
    if chunk_index is not None and total_chunks is not None:
        metadata_parts.append(f"CONTEXTO DO CHUNK: Este é o chunk {chunk_index} de {total_chunks} chunks totais.")
        
        if chunk_index == 1:
            metadata_parts.append("PRIORIDADE: Este é o PRIMEIRO chunk - priorize informações de identidade, classificação e contato.")
        elif chunk_index == total_chunks:
            metadata_parts.append("PRIORIDADE: Este é o ÚLTIMO chunk - certifique-se de extrair todos os dados restantes que ainda não foram capturados.")
        else:
            metadata_parts.append("PRIORIDADE: Este é um chunk INTERMEDIÁRIO - foque em produtos, serviços, reputação e informações complementares.")
    
    # Tipo de conteúdo
    if chunk_type:
        metadata_parts.append(f"TIPO DE CONTEÚDO DETECTADO: {chunk_type}")
        
        if "catálogo" in chunk_type.lower() or "produtos" in chunk_type.lower():
            metadata_parts.append("ATENÇÃO ESPECIAL: Este chunk contém catálogo de produtos.")
            metadata_parts.append("INSTRUÇÕES PARA PRODUTOS:")
            metadata_parts.append("- Extraia APENAS produtos mencionados explicitamente no texto")
            metadata_parts.append("- NÃO gere variações (ex: se menciona 'RCA', não adicione 'Conector RCA', 'RCA macho', etc.)")
            metadata_parts.append("- Se um produto aparece com nomes diferentes, use o nome mais completo")
            metadata_parts.append("- PARE quando não houver mais produtos únicos ou ao atingir limite de 60 por categoria")
        
        elif "serviços" in chunk_type.lower():
            metadata_parts.append("ATENÇÃO ESPECIAL: Este chunk contém informações sobre serviços.")
            metadata_parts.append("- Extraia nome e descrição de cada serviço único")
            metadata_parts.append("- NÃO repita serviços já mencionados")
        
        elif "clientes" in chunk_type.lower() or "reputação" in chunk_type.lower():
            metadata_parts.append("ATENÇÃO ESPECIAL: Este chunk contém informações de reputação.")
            metadata_parts.append("- Extraia apenas nomes únicos de clientes/parceiros")
            metadata_parts.append("- NÃO gere variações do mesmo nome (ex: 'Petrobras' e 'Grupo Petrobras' são o mesmo)")
    
    # Estimativa de itens
    if estimated_items is not None:
        metadata_parts.append(f"ESTIMATIVA: Aproximadamente {estimated_items} itens únicos detectados neste chunk.")
        if estimated_items > 100:
            metadata_parts.append("ATENÇÃO: Este chunk tem muitos itens. Seja seletivo e extraia apenas os mais relevantes e únicos.")
    
    metadata_text = "\n".join(metadata_parts) if metadata_parts else ""
    
    return f"""{metadata_text}

Analise este conteúdo e extraia os dados em Português:

{content}

INSTRUÇÕES ESPECÍFICAS PARA ESTE CHUNK:
- Se este chunk contém lista de produtos: extraia APENAS os produtos mencionados explicitamente
- NÃO gere variações (ex: se menciona "RCA", não adicione "Conector RCA", "RCA macho", etc.)
- Se você já extraiu um item em chunks anteriores, NÃO o extraia novamente
- Respeite os limites: máximo 60 produtos/categoria, 40 categorias, 50 serviços, 80 clientes
- PARE quando não houver mais itens únicos ou quando atingir os limites
- Priorize qualidade sobre quantidade: melhor ter menos itens únicos do que muitos itens repetidos
"""


# ============================================================================
# Função auxiliar para detectar tipo de chunk
# ============================================================================

def detect_chunk_type(content: str) -> str:
    """
    Detecta o tipo de conteúdo do chunk usando heurísticas simples.
    
    Args:
        content: Conteúdo do chunk
    
    Returns:
        String descrevendo o tipo de chunk
    """
    content_lower = content.lower()
    
    # Palavras-chave para diferentes tipos
    catalog_keywords = ["catálogo", "produtos", "nossos produtos", "linha completa", 
                       "nossa linha", "catalogo", "produto", "especificações técnicas"]
    services_keywords = ["serviços", "nossos serviços", "oferecemos", "prestamos",
                        "servico", "consultoria", "desenvolvimento"]
    reputation_keywords = ["clientes", "cases", "portfólio", "parceiros", "certificações",
                          "premios", "reconhecimento", "nossos clientes"]
    institutional_keywords = ["sobre nós", "nossa empresa", "história", "missão", "visão",
                            "quem somos", "empresa"]
    
    # Contar ocorrências
    catalog_score = sum(1 for kw in catalog_keywords if kw in content_lower)
    services_score = sum(1 for kw in services_keywords if kw in content_lower)
    reputation_score = sum(1 for kw in reputation_keywords if kw in content_lower)
    institutional_score = sum(1 for kw in institutional_keywords if kw in content_lower)
    
    # Determinar tipo dominante
    scores = {
        "catálogo_produtos": catalog_score,
        "serviços": services_score,
        "reputação": reputation_score,
        "institucional": institutional_score
    }
    
    max_score = max(scores.values())
    if max_score == 0:
        return "geral"
    
    return max(scores, key=scores.get)


def estimate_unique_items(content: str) -> int:
    """
    Estima número de itens únicos no chunk (heurística simples).
    
    Args:
        content: Conteúdo do chunk
    
    Returns:
        Estimativa de itens únicos
    """
    content_lower = content.lower()
    
    # Contar listas (bullet points, números, etc.)
    import re
    bullet_points = len(re.findall(r'[•\-\*]\s+', content))
    numbered_lists = len(re.findall(r'\d+[\.\)]\s+', content))
    
    # Contar menções de produtos/serviços comuns
    product_indicators = len(re.findall(r'\b(produto|item|modelo|referência|sku|código)\b', content_lower))
    
    # Estimativa baseada em múltiplos fatores
    estimate = max(bullet_points, numbered_lists) + (product_indicators // 3)
    
    return min(estimate, 200)  # Cap em 200 para não exagerar
