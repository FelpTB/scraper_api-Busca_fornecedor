Abaixo está um **resumo técnico e executivo** dos principais problemas de repetição/degeneração que vocês enfrentam, das **causas estruturais**, da **stack já existente**, das **soluções aplicadas** e das **limitações ainda presentes**, com exemplos concretos do que ocorre em produção.

---

## 1) Natureza do problema

O problema central não é “JSON inválido”.
É **degeneração semântica dentro de campos válidos**, principalmente em **listas longas**.

Características principais:

* O JSON continua válido (graças ao XGrammar).
* O modelo entra em **loop interno em arrays permitidos**.
* O output cresce sem valor semântico.
* A latência explode.
* A qualidade cai quando se aplica penalidade forte.

O problema ocorre **mesmo com constrained decoding**, porque:

* O schema controla *forma*, não controla *dinâmica de parada*.
* `uniqueItems` e `maxItems` **não são aplicados como restrições duras durante a geração** (apenas na validação).

---

## 2) Onde o problema nasce (zonas de alto risco)

Campos críticos no schema:

### 2.1 ProductCategory.items

**Principal fonte de loops**

Exemplo real típico:

```json
"items": [
  "RCA",
  "Conector RCA",
  "RCA macho",
  "RCA fêmea",
  "Conector RCA macho",
  "RCA plug",
  "RCA adaptador",
  "RCA adaptador macho",
  ...
]
```

Sintomas:

* Variações mínimas do mesmo token.
* Crescimento quase infinito até bater `max_tokens`.
* JSON válido, mas semanticamente inútil.

---

### 2.2 offerings.products

Quando o site tem catálogos genéricos ou listas técnicas:

```json
"products": [
  "P2",
  "P10",
  "XLR",
  "Cabo P2",
  "Cabo P2 estéreo",
  "Cabo P2 3.5mm",
  ...
]
```

O modelo tenta “exaurir o espaço” permitido.

---

### 2.3 reputation.client_list / partnerships

Quando há listas de logotipos ou nomes em grids:

```json
"client_list": [
  "Petrobras",
  "Petrobras RJ",
  "Petrobras SP",
  "Grupo Petrobras",
  "Petrobras Brasil",
  ...
]
```

Repetição semântica com pequenas variações.

---

## 3) Por que isso acontece (causas profundas)

### 3.1 Espaço de saída excessivo no schema

Vocês originalmente tinham:

* `products: maxItems 200`
* `ProductCategory.items: maxItems 200`
* `client_list: 200`
* `partnerships: 100`

Isso cria uma situação estruturalmente perigosa:

> O modelo **não sabe quando parar** e o schema permite continuar.

Mesmo com XGrammar:

* Ele só garante que o token emitido é válido no campo.
* Ele **não impõe parada global** baseada em significado.

---

### 3.2 Penalidades anti-loop trabalham contra extração

Quando vocês aumentaram:

* `presence_penalty`
* `frequency_penalty`

Efeitos observados:

1. O modelo evita repetir → começa a:

   * pular campos legítimos
   * colapsar para `[]`
   * empobrecer descrições

2. A qualidade geral do perfil despenca:

   * identity incompleta
   * offerings sub-preenchido
   * reputation vazia

Ou seja:

* Loop ↓
* Qualidade ↓↓↓

---

### 3.3 Prompt sobrecarregado com schema completo

Vocês colavam:

* Schema no `response_format`
* **E também no User Prompt**

Consequências:

* A atenção do modelo se dispersa.
* Menos foco no texto scraped.
* Maior chance de degeneração em listas.

---

### 3.4 max_tokens global não resolve runaway local

O runaway nasce em **1 campo específico**.
Reduzir `max_tokens` global:

* corta identity / contact / classification
* mas o loop ainda tenta nascer
* piora recall geral

---

## 4) Stack atual (nível muito alto de maturidade)

Vocês já possuem uma das stacks mais completas possíveis para esse problema:

### 4.1 Constrained decoding

* **SGLang + XGrammar**
* `response_format = json_schema`
* `strict = True`

Resultado:

* JSON sempre válido
* Estrutura garantida
* Parsing praticamente 100% confiável

---

### 4.2 Prompt engineering avançado

Elementos presentes:

* Evidência dura (anti-alucinação)
* Roteamento fechado por campo
* Regras explícitas serviço ≠ produto
* Anti-vazio em objetos
* Micro-shots direcionados
* Anti-expansão de termos genéricos

Esse nível de disciplina é **acima da média de produção**.

---

### 4.3 Proteções runtime

* Adaptive `max_tokens` por tamanho de input

* Loop detector heurístico:

  * n-gram repetido
  * chunk repetido
  * runaway sem fechar JSON

* Retry seletivo com parâmetros ajustados

* Pós-process determinístico:

  * deduplicação
  * filtro anti-template
  * hard caps finais

Essa arquitetura já é **industrial-grade**.

---

## 5) Limitação fundamental que permaneceu

Mesmo com tudo isso, restou um ponto estrutural:

> **O modelo ainda decide sozinho quando parar listas.**

Nem:

* XGrammar
* uniqueItems
* maxItems
* penalidades

garantem parada **semântica correta**.

O sistema só impede:

* JSON inválido
* quebra estrutural

Ele **não impede degeneração interna válida**.

---

## 6) Soluções aplicadas na v9.1 (e por que funcionam)

### 6.1 Redução agressiva de espaço de degeneração (schema-level)

Mudança crítica:

* `products`: 200 → **60**
* `product_categories`: 80 → **40**
* `ProductCategory.items`: 200 → **80**
* `client_list`: 200 → **80**
* `partnerships`: 100 → **50**

Efeito direto:

* Menos espaço para runaway
* Menos tokens gerados
* Menos latência
* Loop muito mais raro

Essa é a **mudança de maior impacto real**.

---

### 6.2 Remoção do schema do User Prompt

Antes:

* schema no prompt
* schema no response_format

Agora:

* schema **somente** no XGrammar

Efeitos:

* menos ruído cognitivo
* melhor foco no conteúdo scraped
* melhor qualidade sem aumentar custo

---

### 6.3 Troca de penalidades por controle estrutural

Mudança:

* `presence_penalty`: 0
* `frequency_penalty`: 0
* (opcional) `repetition_penalty`: leve (≈1.08)

Efeito:

* recupera fidelidade textual
* evita sub-preenchimento
* deixa o controle de loop **para o schema + caps**, não para criatividade

---

### 6.4 Retry baseado em tamanho, não em criatividade

Antes:

* retry subia penalidades → matava qualidade

Agora:

* retry reduz `max_tokens`
* sobe levemente `repetition_penalty`
* mantém criatividade controlada

Resultado:

* recuperação sem colapsar perfil

---

## 7) Exemplos típicos de falhas observadas

### Caso A — Degeneração em ProductCategory.items

Input:

> “Conectores disponíveis: RCA, P2, P10, XLR”

Output ruim (antes v9.1):

```json
"items": [
  "RCA",
  "Conector RCA",
  "RCA macho",
  "RCA fêmea",
  "RCA plug",
  "RCA adaptador",
  "RCA adaptador macho",
  "RCA adaptador fêmea",
  ...
]
```

Efeito:

* 200+ itens
* latência alta
* pós-process corta brutalmente
* semântica pobre

---

### Caso B — Sub-preenchimento após penalidades

Após subir `frequency_penalty`:

```json
"services": [],
"products": [],
"product_categories": [],
"client_list": []
```

Mesmo quando havia evidência clara.

Efeito:

* loop ↓
* qualidade ↓↓↓
* recall quase zero em campos críticos

---

### Caso C — Variação mínima em clientes

Input:

> “Clientes: Petrobras, Vale, Ambev”

Output ruim:

```json
"client_list": [
  "Petrobras",
  "Petrobras RJ",
  "Grupo Petrobras",
  "Petrobras Brasil",
  "Vale",
  "Vale S.A.",
  "Vale Mineração",
  ...
]
```

Mesmo nome expandido artificialmente.

---

## 8) Conclusão técnica

O problema **não era**:

* JSON inválido
* parsing
* prompt fraco
* ausência de constrained decoding

O problema era:

### 🔴 Um desequilíbrio estrutural entre:

* espaço de saída enorme
* listas abertas
* ausência de parada semântica nativa nos LLMs

e

* necessidade de extração precisa
* latência previsível
* zero alucinação

---

## 9) Estado atual (v9.1)

Com as mudanças:

* Loop rate ↓ drasticamente
* Latência p95/p99 ↓
* Qualidade recuperada
* Menos retries
* JSON sempre válido
* Perfil mais estável e consistente

O sistema agora está:

* **constrained por design** (schema + caps)
* **guiado por política** (prompt)
* **protegido por runtime** (detector + retry + pós-process)

Esse é exatamente o padrão usado em pipelines industriais de:

* company profiling
* KYC
* enrichment B2B
* data extraction regulada

---

Se você quiser, no próximo passo eu posso:

* transformar isso em um **documento técnico oficial** (post-mortem / design doc)
* ou um **“problem statement + solution architecture”** para apresentar a outro engenheiro, time ou stakeholder.