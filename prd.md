# Product Requirements Document (PRD)
**Nome do Produto:** B2B Flash Profiler (Beta)
**Versão:** 1.0
**Status:** Em Desenvolvimento
**Responsável:** Engineering Team

## 1. Visão Geral e Problema
A análise de perfis B2B é tradicionalmente lenta, dependendo de processos manuais ou scrapers sequenciais que levam minutos. O objetivo deste projeto é quebrar essa barreira de latência, entregando um perfil estruturado e rico de qualquer empresa em **menos de 20 segundos**, viabilizando automações em tempo real.

## 2. Objetivos Principais
1.  **Velocidade Extrema:** Processamento completo (Request -> JSON) em < 20s.
2.  **Riqueza de Dados:** Combinar dados da Home Page e PDFs (apresentações/cases) encontrados.
3.  **Confiabilidade Estrutural:** Saída garantida em JSON validado (Schema Pydantic), sem alucinações de formato.

## 3. Escopo do Produto (MVP Beta)
### ✅ Incluído (In-Scope)
- **Interface:** API REST local (FastAPI).
- **Entrada:** URL do site da empresa (ex: `site.com`).
- **Scraping:** Navegação headless otimizada (Crawl4AI) com bloqueio de mídia.
- **Documentos:** Detecção e extração de texto de PDFs linkados na home (PyMuPDF).
- **Inteligência:** Integração com Grok Beta (via xAI API) para síntese.
- **Saída:** JSON contendo Identidade, Classificação, Ofertas, Contatos e Stack Tecnológico.

### ❌ Não Incluído (Out-of-Scope)
- Persistência em Banco de Dados (Supabase/Postgres) nesta fase.
- Interface Gráfica (Frontend).
- Autenticação de Usuário.
- Filas de processamento externas (Redis/RabbitMQ).

## 4. Requisitos Funcionais
| ID | Funcionalidade | Descrição |
| :--- | :--- | :--- |
| **FR-01** | **Ingestão de URL** | O sistema deve aceitar URLs HTTP/HTTPS e normalizá-las. |
| **FR-02** | **Scraping Otimizado** | O crawler deve ignorar imagens, fontes e CSS para maximizar velocidade. |
| **FR-03** | **PDF Discovery** | Identificar links `.pdf` na página inicial. Limite: processar no máx. 3 PDFs simultâneos. |
| **FR-04** | **PDF Extraction** | Extrair texto cru dos PDFs. Truncar para ler apenas as primeiras 3 e últimas 2 páginas. |
| **FR-05** | **LLM Synthesis** | Enviar texto consolidado (Web + PDF) para o Grok com prompt de "JSON Mode". |
| **FR-06** | **Schema Validation** | O retorno deve ser validado estritamente contra um modelo Pydantic antes de responder. |

## 5. Requisitos Não-Funcionais (SLA & Performance)
- **Latência Total:** Média de 15s, Máximo de 20s (P95).
- **Timeout:** Hard timeout de 25s para abortar a operação.
- **Concorrência:** O sistema deve usar `asyncio` para realizar scraping e download de PDFs em paralelo.
- **Custo de Tokens:** O texto deve ser limpo (Markdown) para evitar desperdício de tokens no LLM.

## 6. Stack Tecnológico
- **Core:** Python 3.11+
- **API:** FastAPI + Uvicorn
- **Scraping:** Crawl4AI (Playwright Wrapper)
- **PDF:** PyMuPDF (fitz)
- **AI:** xAI API (Grok Beta)

## 7. Critérios de Aceite
- [ ] CURL para `POST /analyze` retorna JSON válido em 18 segundos.
- [ ] O JSON contém campos preenchidos corretamente (ex: "target_audience" não está vazio).
- [ ] O sistema não quebra se o site alvo estiver offline (retorna erro tratado).