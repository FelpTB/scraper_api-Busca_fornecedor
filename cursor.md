# Project: B2B High-Performance Profiler (Beta)

## Objective
Build a local FastAPI application that accepts a company URL, scrapes the website (and linked PDFs), and uses the Grok Beta LLM to generate a comprehensive structured JSON profile. The hard requirement is execution time < 20 seconds.

## Architecture & File Structure
Please scaffold the following structure and implement the code:

/app
  ├── main.py            # FastAPI entrypoint with /analyze endpoint
  ├── core/
  │   └── config.py      # Env vars (XAI_API_KEY)
  ├── schemas/
  │   └── profile.py     # Pydantic models for the B2B Profile
  └── services/
      ├── scraper.py     # Crawl4AI logic (Image blocking enabled)
      ├── pdf.py         # PyMuPDF extraction logic
      └── llm.py         # Grok API interaction (System Prompt: JSON only)
.env                     # Example env file
requirements.txt         # Dependencies

## Implementation Details

### 1. Data Models (schemas/profile.py)
Create a Pydantic model `CompanyProfile` containing:
- identity: (company_name, tagline, description, founding_year)
- classification: (industry, business_model [B2B/B2C], target_audience)
- offerings: (products, services, key_differentiators)
- contact: (emails, phones, linkedin_url, address)
- stack: (inferred_tech_stack list)

### 2. Scraper Service (services/scraper.py)
- Use `AsyncWebCrawler` from `crawl4ai`.
- CRITICAL: Configure `CrawlerRunConfig` with `exclude_external_images=True` and `markdown_generator=PruningContentFilter`.
- Function `get_site_content(url)` should return clean Markdown.

### 3. PDF Service (services/pdf.py)
- Function `extract_pdf_text(url)` that downloads a PDF stream.
- Use `fitz` (PyMuPDF) to extract text.
- Optimization: Only extract text from the first 3 pages and the last 2 pages to save time/tokens.

### 4. LLM Service (services/llm.py)
- Initialize `AsyncOpenAI` client with `base_url="https://api.x.ai/v1"`.
- Function `generate_profile(text_content)` that sends the accumulated text to Grok.
- System Prompt: "You are a B2B data extractor. Output strictly valid JSON matching this schema..."

### 5. API Endpoint (main.py)
- POST `/analyze`:
  - Input: `{ "url": "https://example.com" }`
  - Logic: Run scraping. If the scraper finds PDF links in the DOM, run PDF extraction in parallel (asyncio.gather).
  - Combine text -> Send to LLM -> Return JSON.
  - Implement a global timeout safeguard.

## Action
Generate the full project code now based on the rules in .cursorrules.