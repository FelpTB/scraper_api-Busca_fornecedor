# Avaliação de performance – execuções LLM da API

**Arquivo analisado:** `teste_100_results-1355.csv`  
**Schema de referência:** `app/schemas/profile.py` (CompanyProfile)  
**Data da análise:** Janeiro 2025

---

## 1. Resumo executivo

- **Total de linhas de dados no CSV:** 101  
- **Perfis com JSON válido:** 71 (70,3%)  
- **Erros de parse:** 30 (29,7%) – principalmente *Unterminated string* (resposta truncada ou JSON mal formado)

**Conclusão principal:** As respostas da API **não retornam** as seções `identidade`, `classificacao` e `reputacao` do schema. Apenas `ofertas`, `contato` e `fontes` aparecem. Isso indica que o prompt ou o fluxo da API está pedindo/aceitando apenas um subconjunto do perfil completo.

---

## 2. Estatísticas das execuções

### 2.1 Completude (baseado em `app/schemas/profile.py`)

| Seção        | Execuções que preencheram ao menos 1 campo | %   |
|-------------|--------------------------------------------|-----|
| identidade  | 0 / 101                                    | 0%  |
| classificacao | 0 / 101                                  | 0%  |
| ofertas    | 66 / 101                                   | 65,3% |
| reputacao  | 0 / 101                                    | 0%  |
| contato    | 48 / 101                                   | 47,5% |
| fontes     | 71 / 101                                   | 70,3% |

- **Campos preenchidos por execução:** mínimo 1, máximo 43, média **13,5**.  
- **Seções distintas preenchidas por execução (máx. 6):** média **1,9**.

### 2.2 Conformidade com o schema (chaves raiz retornadas)

O LLM retorna **somente** estas chaves raiz:

| Chave     | Ocorrências (em 71 perfis válidos) |
|----------|-------------------------------------|
| ofertas  | 71/71 (100%)                        |
| fontes   | 71/71 (100%)                        |
| contato  | 53/71 (74,6%)                       |

As chaves **identidade**, **classificacao** e **reputacao** **nunca** aparecem no CSV.

### 2.3 Volume extraído (perfis válidos)

- **Total de categorias de produtos:** 275  
- **Total de itens de produtos:** 942  
- **Total de serviços:** 231  

---

## 3. Comportamentos repetitivos

- **Perfis com apenas ofertas/contato/fontes** (sem identidade, classificação, reputação): **71/101** – compatível com o fato de só essas seções serem retornadas.  
- **Perfis vazios ou mínimos (≤2 campos):** 4/101.  
- **Estruturas de chaves mais comuns:**
  - `('contato', 'fontes', 'ofertas')`: **53 vezes**
  - `('fontes', 'ofertas')`: **18 vezes**

Ou seja, o formato da resposta é muito estável: sempre um subconjunto de ofertas + contato + fontes.

### 3.1 Repetição de itens dentro do perfil (produtos e serviços duplicados)

Foi analisada a ocorrência de **itens repetidos** dentro de um mesmo perfil: mesmo produto ou mesmo serviço (nome) aparecendo mais de uma vez, considerando normalização (minúsculas, espaços).

**Produtos:**

| Métrica | Valor |
|--------|--------|
| Perfis com produtos | 49 / 71 válidos |
| Perfis com ao menos 1 produto repetido | 12 / 49 |
| Taxa média de repetição (produtos) | 2,9% |
| Taxa máxima de repetição (produtos) | 20,8% |
| Total de itens repetidos (soma em todos os perfis) | 48 |

**Serviços:**

| Métrica | Valor |
|--------|--------|
| Perfis com serviços | 50 / 71 válidos |
| Perfis com ao menos 1 serviço repetido | 0 / 50 |
| Taxa média/máxima de repetição (serviços) | 0% |

**Exemplos de perfis com maior taxa de repetição em produtos:**

1. **20,8%** (48 itens, 38 únicos) — ex.: "escritórios" (3x), "cabo 1kv hepr" (2x), "cabo 1kv lszh" (2x)  
2. **17,6%** (17 itens, 14 únicos) — ex.: "expo west 2018" (2x), "expo west 2019" (2x)  
3. **15,7%** (89 itens, 75 únicos) — ex.: "hp" (7x), "lenovo" (3x), "dell" (3x)  
4. **14,3%** — ex.: "pintura epóxi" (2x); outro perfil: "cabos" (3x), "demais produtos" (3x), "inversores" (2x)

Conclusão: é **comum** o LLM devolver o mesmo produto em mais de uma categoria ou várias vezes na mesma lista (ex.: "HP", "Cabos", "Cabo 1KV HEPR"). Reforçar a **regra de deduplicação** no prompt e, se possível, deduplicar em pós-processamento antes de persistir o perfil.

---

## 4. Qualidade geral dos perfis

### 4.1 Erros de parse (30 execuções)

Todos os erros amostrados são **Unterminated string** no JSON (strings não fechadas). Isso sugere:

- Resposta do modelo **truncada** (limite de tokens ou corte no pipeline), ou  
- **Problemas de escape** em strings (aspas/quebras de linha dentro do conteúdo).

Recomendação: revisar limite de tokens da resposta e tratamento de caracteres especiais no conteúdo extraído.

### 4.2 Completude em relação ao schema

- **Identidade** (nome_empresa, CNPJ, descrição, ano_fundacao, faixa_funcionarios): **0%** – nunca preenchida.  
- **Classificação** (indústria, modelo_negócio, público_alvo, cobertura_geografica): **0%** – nunca preenchida.  
- **Reputação** (certificações, prêmios, parcerias, lista_clientes, estudos_caso): **0%** – nunca preenchida.

Ou seja, os perfis estão **incompletos** em relação ao `CompanyProfile` definido em `app/schemas/profile.py`.

### 4.3 Descrições repetidas

Como nenhuma execução retornou `identidade.descricao`, não há como avaliar repetição de textos de descrição neste conjunto.

---

## 5. Recomendações

1. **Alinhar prompt/API ao schema completo**  
   Garantir que o prompt (e o contrato da API) exijam e aceitem **todas** as seções do `CompanyProfile`: identidade, classificacao, ofertas, reputacao, contato, fontes.

2. **Reduzir erros de parse**  
   - Aumentar ou revisar o limite de tokens da resposta do LLM.  
   - Validar/escapar strings antes de montar o JSON (ou usar structured output se o provedor suportar).

3. **Monitorar completude em produção**  
   Usar métricas por seção (ex.: % de respostas com identidade/classificacao preenchidas) para detectar regressões.

4. **Reavaliar após mudanças**  
   Rodar novamente o script `avaliacao_perfis_llm.py` (ou equivalente) em novos exports da API e comparar com este relatório.

5. **Reduzir repetição de itens (produtos/serviços)**  
   - Reforçar no prompt a regra de **não repetir** o mesmo item (ex.: "NÃO inclua o mesmo produto em mais de uma categoria" e "use o nome mais completo e evite variações do mesmo item").  
   - Opcional: deduplicar em pós-processamento (normalizar nome e remover duplicatas) antes de salvar o perfil.

---

## 6. Como reproduzir a análise

```bash
python avaliacao_perfis_llm.py
```

O script lê `teste_100_results-1355.csv`, extrai o JSON de cada `output_messages`, avalia completude por seção do schema, detecta **repetição de itens** (produtos e serviços duplicados dentro do mesmo perfil), conta estruturas repetidas e imprime estatísticas + amostra de erros no terminal.
