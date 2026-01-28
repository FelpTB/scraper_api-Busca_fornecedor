# Pesquisa, melhores práticas e proposta de 3 prompts para correção

**Base:** relatório `AVALIACAO_PERFIS_LLM_100_EXECUCOES.md`  
**Problemas a corrigir:** (1) schema incompleto (identidade, classificacao, reputacao nunca retornados), (2) erros de parse por truncamento (Unterminated string), (3) itens repetidos em produtos/serviços.

---

## 1. Problemas similares em fóruns, GitHub e comunidade

### 1.1 Schema incompleto / campos ausentes

- **PARSE (arXiv):** framework de otimização de schema para extração com LLMs. O trabalho mostra que schemas desenhados para humanos frequentemente são **mal interpretados** pelos modelos: campos são omitidos ou renomeados. A solução proposta é otimizar o schema para consumo por LLM (labels mais explícitos, exemplos por campo) e validar a saída contra o schema; isso reduziu erros em até **92%** em retry e **64,7%** de melhora em precisão em extração estruturada.
- **Reintech / Crawl4AI:** recomendações explícitas: pedir no prompt **"return all fields"** e **"every section"**; incluir exemplos com a **estrutura completa** desejada; usar validação pós-extração para detectar campos faltando.
- **OpenAI / Hugging Face:** Structured Outputs (JSON Schema + gramática na geração) **garantem** que a resposta respeite o schema quando o provedor suporta (ex.: `response_format` com `json_schema`). Sem isso, o modelo tende a retornar só o que vê nos exemplos (no nosso caso, só ofertas/contato/fontes).

**Conclusão:** Nosso prompt dá exemplo só de `ofertas`. O modelo replica essa estrutura e omite identidade, classificacao e reputacao. É necessário **listar todas as seções** e dar exemplo ou esqueleto com **todas** as chaves raiz.

### 1.2 Truncamento / "Unterminated string"

- **LangChain (issue #2327):** "Unterminated String JSON Error when using Structured Output" — causa raiz: resposta cortada por **limite de tokens** (max_tokens). O JSON é interrompido no meio de uma string → parse falha.
- **OpenAI Community:** "Creating a JSON response larger than max token length" e "Tips for handling finish_reason: length" — quando a resposta excede o orçamento de tokens, a API pode retornar `finish_reason: "length"`; a solução é **aumentar max_tokens**, **reduzir o tamanho do prompt** para sobrar mais tokens para a saída, ou **dividir a extração** (chunking + merge).
- **Crawl4AI:** usa chunking por `chunk_token_threshold`: divide o conteúdo, extrai por pedaço e junta os resultados, evitando uma única resposta gigante.

**Conclusão:** Os ~30% de erro de parse no nosso CSV batem com truncamento. Ações: (1) aumentar `max_tokens` da resposta; (2) no prompt, pedir **respostas concisas** (ex.: descrições curtas, listas até os limites já definidos e parar); (3) se o provedor suportar, usar **Structured Output** para reduzir tokens desperdiçados com texto livre fora do JSON.

### 1.3 Itens duplicados em listas

- **Mirascope:** guia "Removing Semantic Duplicates" — para listas extraídas por LLM, é boa prática incluir no schema **grupos de duplicatas** e pedir ao modelo que identifique itens semanticamente equivalentes e mantenha **uma única variante** (a mais completa ou comum).
- **LlamaIndex (LlamaExtract):** ao extrair entidades repetidas (ex.: linhas de tabela), o modelo tende a extrair só as primeiras dezenas. Recomendam extração **por entidade** ou em lotes menores para cobertura completa; para **deduplicação**, instruções explícitas no prompt (ex.: "cada produto deve aparecer apenas uma vez em todo o JSON") funcionam melhor do que só pós-processamento.

**Conclusão:** Reforçar no prompt: (1) **cada produto/serviço deve aparecer apenas uma vez** em todo o perfil; (2) **não repetir** o mesmo item em categorias diferentes; (3) em caso de variações (ex.: "RCA" e "Conector RCA"), manter **só uma**, a mais específica.

---

## 2. Melhores técnicas e frameworks de prompt (e alinhamento às sugestões da avaliação)

| Técnica / framework | O que faz | Como se aplica aos nossos problemas |
|---------------------|-----------|--------------------------------------|
| **Schema explícito completo** | Pedir todas as chaves/ramos do JSON no prompt, com descrição curta por seção. | Corrige schema incompleto: modelo passa a retornar identidade, classificacao, reputacao, contato, ofertas, fontes. |
| **Exemplo com estrutura cheia** | Mostrar um JSON de exemplo contendo **todas** as seções (mesmo com null/[]). | Evita que o modelo copie só um subconjunto (como hoje só ofertas/contato/fontes). |
| **Structured Output (API)** | Enviar JSON Schema (ex.: Pydantic) na chamada e usar modo que força o formato. | Garante formato válido e todas as chaves; reduz risco de truncamento “no meio” de texto livre. |
| **Instrução de deduplicação** | Regras claras: "não repita o mesmo item", "um item = uma entrada", "use o nome mais completo em caso de variação". | Reduz repetição de produtos/serviços dentro do perfil. |
| **Limites + “PARE”** | Limites máximos por lista + "PARE ao atingir o limite ou quando não houver mais itens únicos". | Controla tamanho da saída e ajuda a evitar truncamento. |
| **Resposta só JSON** | "Retorne APENAS um objeto JSON válido, sem markdown, sem explicações." | Reduz tokens gastos e risco de quebrar o parse. |
| **max_tokens e finish_reason** | Aumentar max_tokens da resposta; monitorar finish_reason == "length". | Mitiga truncamento; em caso de "length", retry ou chunking. |
| **Chunking + merge** | Dividir conteúdo em blocos, extrair por bloco, mesclar resultados. | Para páginas muito longas, evita uma única resposta gigante. |
| **DSPy / otimização de prompt** | Otimização automática de prompts com base em exemplos. | Uso opcional para refinar os prompts após validar as 3 propostas. |

Sugestões do relatório de avaliação incorporadas:

- Alinhar prompt ao schema completo (todas as seções).
- Reduzir erros de parse (max_tokens, resposta só JSON, structured output se possível).
- Reforçar regra de deduplicação (não repetir produtos/serviços).
- Manter limites de listas e regras de parada.

---

## 3. Três prompts propostos para correção

Os três prompts abaixo são **alternativas** de system prompt para o extrator de perfil. O user prompt pode permanecer: `Analise este conteúdo e extraia os dados em Português:\n\n{content}`.

Cada proposta:

- Exige **todas** as seções do schema: identidade, classificacao, ofertas, reputacao, contato, fontes.
- Reforça **deduplicação** (produtos e serviços sem repetição).
- Mantém **limites** de listas e regras de parada.
- Pede **apenas JSON**, sem markdown nem explicações (para reduzir tamanho e risco de truncamento).

---

### Prompt 1 — Schema-first (esqueleto completo)

Foco: deixar explícito que a resposta deve ter **sempre** as seis chaves raiz, com exemplo mínimo completo.

**Validação (níveis do JSON):** O prompt anterior descrevia só até nível 2; faltava o **nível 3** para `reputacao.estudos_caso` (cada item é um objeto com titulo, nome_cliente, industria, desafio, solucao, resultado). O Prompt 1 implementado inclui nível 3 para ofertas (produtos[].{categoria, produtos[]}, servicos[].{nome, descricao}) e para estudos_caso[].{titulo, nome_cliente, industria, desafio, solucao, resultado}. **Implementado em:** `profile_extractor_agent.py` e `profile_builder/constants.py`.

```
Você é um extrator de dados B2B. Extraia do texto fornecido e retorne UM ÚNICO objeto JSON válido.

OBRIGATÓRIO: O JSON deve conter SEMPRE estas 6 chaves raiz (use null ou [] quando não houver dados):
- identidade: { nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios }
- classificacao: { industria, modelo_negocio, publico_alvo, cobertura_geografica }
- ofertas: { produtos: [ { categoria, produtos: [] } ], servicos: [ { nome, descricao } ] }
- reputacao: { certificacoes: [], premios: [], parcerias: [], lista_clientes: [], estudos_caso: [ { titulo, nome_cliente, industria, desafio, solucao, resultado } ] }
- contato: { emails: [], telefones: [], url_linkedin, url_site, endereco_matriz, localizacoes: [] }
- fontes: [ URLs das páginas analisadas ]

REGRAS:
1. IDIOMA: Português (Brasil). Termos técnicos globais podem ficar em inglês.
2. Produtos vs serviços: produtos = itens físicos; serviços = atividades intangíveis.
3. DEDUPLICAÇÃO (CRÍTICO): Cada produto ou serviço deve aparecer NO MÁXIMO UMA VEZ em todo o JSON. Não repita o mesmo item em categorias diferentes. Se houver variações (ex.: "RCA" e "Conector RCA"), inclua só uma, a mais completa.
4. Limites: máx. 60 produtos por categoria, 40 categorias, 50 serviços, 80 clientes, 50 parcerias, 50 certificações, 30 estudos de caso. PARE ao atingir qualquer limite ou quando não houver mais itens únicos.
5. Não invente dados. Use null ou [] quando não encontrar.
6. Seja conciso em descrições longas para caber na resposta.

Saída: APENAS o objeto JSON, sem markdown (sem ```json), sem texto antes ou depois.
```

---

### Prompt 2 — Checklist + exemplo mínimo completo

Foco: checklist explícito de presença das seções + exemplo que inclui todas as chaves (mesmo vazias).

```
Você é um extrator de dados B2B. Extraia do texto e retorne UM objeto JSON válido.

CHECKLIST – Sua resposta DEVE conter exatamente estas chaves no primeiro nível:
[ ] identidade
[ ] classificacao
[ ] ofertas
[ ] reputacao
[ ] contato
[ ] fontes

Exemplo de estrutura (preencha com os dados do texto; use null ou [] quando não houver):

{
  "identidade": { "nome_empresa": null, "cnpj": null, "descricao": null, "ano_fundacao": null, "faixa_funcionarios": null },
  "classificacao": { "industria": null, "modelo_negocio": null, "publico_alvo": null, "cobertura_geografica": null },
  "ofertas": { "produtos": [], "servicos": [] },
  "reputacao": { "certificacoes": [], "premios": [], "parcerias": [], "lista_clientes": [], "estudos_caso": [] },
  "contato": { "emails": [], "telefones": [], "url_linkedin": null, "url_site": null, "endereco_matriz": null, "localizacoes": [] },
  "fontes": []
}

REGRAS:
- Português (Brasil). Produtos = físicos; serviços = intangíveis.
- DEDUPLICAÇÃO: Nenhum produto ou serviço repetido. Cada item aparece UMA vez só. Variações (ex.: "Cabo 1KV" e "cabo 1kv") = mesmo item; use um nome só.
- Limites: 60 produtos/categoria, 40 categorias, 50 serviços, 80 clientes, 50 parcerias, 50 certificações, 30 estudos de caso. PARE ao atingir limite ou fim dos itens únicos.
- Não invente. Seja conciso para evitar corte da resposta.

Retorne APENAS o JSON, sem markdown e sem explicações.
```

---

### Prompt 3 — Concisão + prioridade (anti-truncamento)

Foco: reduzir chance de truncamento pedindo prioridade de preenchimento e descrições curtas, mantendo schema completo e deduplicação.

```
Você é um extrator de dados B2B. Retorne UM objeto JSON válido com TODAS as 6 seções abaixo. Use null ou [] quando não houver dado.

SEÇÕES OBRIGATÓRIAS (não omita nenhuma):
1. identidade: nome_empresa, cnpj, descricao (curta), ano_fundacao, faixa_funcionarios
2. classificacao: industria, modelo_negocio, publico_alvo, cobertura_geografica
3. ofertas: produtos [ { categoria, produtos: [] } ], servicos [ { nome, descricao } ]
4. reputacao: certificacoes, premios, parcerias, lista_clientes, estudos_caso
5. contato: emails, telefones, url_linkedin, url_site, endereco_matriz, localizacoes
6. fontes: lista de URLs

PRIORIDADE (para caber na resposta): preencha primeiro identidade, classificacao, contato e fontes; depois ofertas e reputacao. Em descrições longas, use no máximo 1–2 frases.

DEDUPLICAÇÃO (CRÍTICO): Cada produto e cada serviço deve aparecer UMA ÚNICA VEZ em todo o JSON. Não coloque o mesmo produto em duas categorias. "RCA" e "Conector RCA" = um item; inclua só "Conector RCA".

Limites: 60 produtos/categoria, 40 categorias, 50 serviços, 80 clientes, 50 parcerias, 50 certificações, 30 estudos de caso. PARE ao atingir ou quando não houver mais itens únicos. Não invente dados.

Idioma: Português (Brasil).

Retorne somente o objeto JSON, sem markdown e sem texto adicional.
```

---

## 4. Resumo e próximos passos

| Problema | Prompt 1 | Prompt 2 | Prompt 3 |
|----------|----------|----------|----------|
| Schema incompleto | Esqueleto das 6 chaves | Checklist + exemplo com 6 chaves | Lista explícita das 6 seções |
| Truncamento | Concisão + “caber na resposta” | Concisão | Prioridade de preenchimento + descrições curtas |
| Itens repetidos | Regra “no máximo uma vez” + variação única | “Nenhum produto/serviço repetido” + exemplo | “Uma única vez” + exemplo RCA |

Recomendações de implementação:

1. **Testar os 3 prompts** no mesmo conjunto de páginas (ex.: novo export ou subconjunto do CSV atual), medindo: (a) presença das 6 seções, (b) taxa de parse válido, (c) repetição de itens (com `avaliacao_perfis_llm.py`).
2. **Aumentar max_tokens** da chamada ao LLM e, se disponível, usar **Structured Output** (JSON Schema) para garantir formato e reduzir truncamento.
3. **Manter deduplicação em pós-processamento** como segurança (normalizar nome e remover duplicatas em produtos/serviços) mesmo após melhorar o prompt.
4. **Monitorar** finish_reason e tamanho da resposta para detectar truncamento em produção.

---

## 5. Referências

- **LangChain #2327:** [Unterminated String JSON Error when using Structured Output](https://github.com/langchain-ai/langchainjs/issues/2327) — truncamento por max_tokens.
- **OpenAI:** [Structured model outputs](https://platform.openai.com/docs/guides/structured-outputs), [Tips for finish_reason: length](https://community.openai.com/t/tips-for-handling-finish_reason-length-with-json/806445).
- **PARSE (arXiv):** [PARSE: LLM Driven Schema Optimization for Reliable Entity Extraction](https://arxiv.org/html/2510.08623v1) — otimização de schema para LLM.
- **Reintech:** [How to Structure Prompts for Consistent JSON Output from LLMs](https://reintech.io/blog/structure-prompts-consistent-json-output-llms) — "return all fields", exemplos completos.
- **Crawl4AI:** [Extracting JSON (LLM)](https://docs.crawl4ai.com/extraction/llm-strategies) — chunking e schema validation.
- **Mirascope:** [Removing Semantic Duplicates](https://mirascope.com/docs/mirascope/guides/more-advanced/removing-semantic-duplicates) — deduplicação em listas extraídas.
- **LlamaIndex:** [Extract Repeating Entities](https://developers.llamaindex.ai/python/cloud/llamaextract/examples/extract_repeating_entities/) — extração por entidade.
- **DSPy:** [Prompt Engineering with DSPy](https://www.ibm.com/think/tutorials/prompt-engineering-with-dspy) — otimização automática de prompts.

