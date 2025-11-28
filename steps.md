# Roadmap de Desenvolvimento - B2B Flash Profiler

Este arquivo contém o passo-a-passo granular para construir a aplicação.
Use este arquivo como contexto para o Cursor Composer ("@steps.md implemente o passo 1").

## Fase 1: Setup e Infraestrutura
- [x] **Step 1.1:** Inicializar projeto Python, criar `venv` e estrutura de pastas (`app/core`, `app/services`, `app/schemas`).
- [x] **Step 1.2:** Criar `requirements.txt` com: `fastapi`, `uvicorn`, `crawl4ai`, `pymupdf`, `openai`, `pydantic`, `python-dotenv`.
- [x] **Step 1.3:** Instalar dependências e rodar `playwright install chromium`.
- [x] **Step 1.4:** Configurar `app/core/config.py` para ler `XAI_API_KEY` do `.env`.

## Fase 2: Modelagem de Dados
- [x] **Step 2.1:** Criar `app/schemas/profile.py`. Definir classes Pydantic aninhadas: `Identity`, `Classification`, `Offerings`, `Contact`, `TechStack`.
- [x] **Step 2.2:** Criar o modelo principal `CompanyProfile` que agrega todas as anteriores.

## Fase 3: Motor de Scraping (Crawl4AI)
- [x] **Step 3.1:** Implementar `app/services/scraper.py`. Configurar `AsyncWebCrawler`.
- [x] **Step 3.2:** **CRÍTICO:** Configurar `CrawlerRunConfig` com `exclude_external_images=True`, `css_selector=None` e `word_count_threshold=10`.
- [x] **Step 3.3:** Implementar função `scrape_url(url: str)` que retorna Markdown limpo e uma lista de URLs de PDFs encontrados (`href` terminando em .pdf).

## Fase 4: Processamento de PDF
- [x] **Step 4.1:** Implementar `app/services/pdf.py`.
- [x] **Step 4.2:** Criar função assíncrona `download_and_extract(pdf_url: str)`.
- [x] **Step 4.3:** Usar `fitz` (PyMuPDF) para abrir o stream. Extrair texto apenas das páginas: `0, 1, 2` (início) e `-2, -1` (final). Ignorar o "miolo" para economizar tempo.

## Fase 5: Integração com LLM (Grok)
- [x] **Step 5.1:** Implementar `app/services/llm.py`. Instanciar cliente `AsyncOpenAI` apontando para `base_url="https://api.x.ai/v1"`.
- [x] **Step 5.2:** Criar System Prompt otimizado: "Você é um extrator JSON. Extraia dados deste Markdown + Texto PDF. Se não encontrar, use null."
- [x] **Step 5.3:** Implementar função `analyze_content(text: str)` que chama a API e faz o parse do retorno para o modelo Pydantic `CompanyProfile`.

## Fase 6: Orquestração (FastAPI)
- [x] **Step 6.1:** Em `app/main.py`, criar endpoint `POST /analyze`.
- [x] **Step 6.2:** Implementar lógica de fluxo:
    1. Recebe URL.
    2. `await scraper.scrape_url`.
    3. Se houver PDFs, disparar `asyncio.gather` para processar até 3 PDFs em paralelo.
    4. Concatenar `Markdown Site` + `Texto PDFs`.
    5. Enviar para LLM.
    6. Retornar JSON.
- [x] **Step 6.3:** Adicionar tratamento de exceção global e timeouts.

## Fase 7: Teste
- [x] **Step 7.1:** Criar script `test_request.py` para disparar um request local e medir o tempo de execução.