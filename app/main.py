import asyncio
import os
import logging
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from app.schemas.profile import CompanyProfile
from app.services.scraper import scrape_url
from app.services.pdf import download_and_extract
from app.services.llm import analyze_content
from app.core.security import get_api_key

# Configurar Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="B2B Flash Profiler")

class AnalyzeRequest(BaseModel):
    url: HttpUrl

# --- Global Exception Handlers ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.post("/analyze", response_model=CompanyProfile, dependencies=[Depends(get_api_key)])
async def analyze_company(request: AnalyzeRequest):
    """
    Analyzes a company website and linked PDFs to generate a structured profile.
    Enforces a 300-second hard timeout to allow for slow, stealthy scraping.
    """
    try:
        # Wrap the orchestration in a task to enforce timeout
        logger.info(f"Starting analysis for: {request.url}")
        return await asyncio.wait_for(process_analysis(str(request.url)), timeout=300.0)
    except asyncio.TimeoutError:
        logger.error(f"Timeout analyzing {request.url}")
        raise HTTPException(status_code=504, detail="Analysis timed out (exceeded 300s)")
    except Exception as e:
        # Errors raised inside process_analysis (like LLM failure after retries) will be caught here
        logger.error(f"Analysis failed for {request.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_analysis(url: str) -> CompanyProfile:
    # 1. Scrape the main website AND subpages (Increased to 100 for max coverage)
    markdown, pdf_links, scraped_urls = await scrape_url(url, max_subpages=100)
    
    if not markdown:
        raise Exception("Failed to scrape content from the URL")

    # 2. Process PDFs (Max 3 in parallel)
    pdf_texts = []
    target_pdfs = []
    if pdf_links:
        # Limit to top 3 unique PDFs
        target_pdfs = pdf_links[:3]
        results = await asyncio.gather(*[download_and_extract(pdf) for pdf in target_pdfs])
        pdf_texts = [res for res in results if res]

    # 3. Combine content
    combined_text = f"--- WEB CRAWL START ({url}) ---\n{markdown}\n--- WEB CRAWL END ---\n\n"
    if pdf_texts:
        combined_text += "\n".join(pdf_texts)

    # 4. LLM Analysis
    # Note: Exceptions from analyze_content (after retries exhausted) will propagate up
    profile = await analyze_content(combined_text)
    
    # 5. Add Sources (Scraped URLs + PDFs)
    all_sources = scraped_urls + target_pdfs
    profile.sources = list(set(all_sources)) # Remove duplicates if any
    
    # 6. Return Result (No longer saving to file)
    return profile

@app.get("/")
async def root():
    return {"status": "ok", "service": "B2B Flash Profiler"}
