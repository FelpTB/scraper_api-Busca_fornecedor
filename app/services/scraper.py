import asyncio
import subprocess
import random
import logging
from typing import List, Tuple, Set, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from app.core.proxy import proxy_manager

# Configurar logger
logger = logging.getLogger(__name__)

async def scrape_url(url: str, max_subpages: int = 100) -> Tuple[str, List[str], List[str]]:
    """
    High-performance scraper with IP Rotation and Parallelism.
    Strategy:
    1. Main Page: Playwright (JS support) with fresh proxy.
    2. Subpages: Parallel Curl Impersonation tasks (max concurrency 10) with unique IPs.
    """
    aggregated_markdown = []
    all_pdf_links = set()
    visited_urls = []

    # --- 1. SCRAPE MAIN PAGE (Playwright) ---
    print(f"[Scraper] Processing Main: {url}")
    main_proxy = await proxy_manager.get_next_proxy()
    
    md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.48, min_word_threshold=10))
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, exclude_external_images=True, markdown_generator=md_generator, page_timeout=30000)
    browser_config = BrowserConfig(browser_type="chromium", headless=True, proxy_config=main_proxy, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

    links = []
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config, magic=True)
            
            if not result.success or not result.markdown or len(result.markdown) < 200:
                raise Exception("Playwright failed or content too short")

            visited_urls.append(url)
            aggregated_markdown.append(f"--- PAGE START: {url} ---\n{result.markdown}\n--- PAGE END ---\n")
            pdfs, links = _extract_links(result.markdown, url)
            if not links: pdfs, links = _extract_links_html(result.html, url)
            all_pdf_links.update(pdfs)

    except Exception as e:
        print(f"[Main] Playwright failed: {e}. Trying System Curl Fallback.")
        text, pdfs, links = await _system_curl_scrape(url, await proxy_manager.get_next_proxy())
        if text:
            visited_urls.append(url)
            aggregated_markdown.append(f"--- PAGE START: {url} ---\n{text}\n--- PAGE END ---\n")
            all_pdf_links.update(pdfs)
        else:
            return "", [], []

    # --- 2. SCRAPE SUBPAGES (Parallel + Rotation) ---
    target_subpages = _prioritize_links(links, url)[:max_subpages]
    
    if target_subpages:
        print(f"[Scraper] Processing {len(target_subpages)} subpages with Parallel IP Rotation")
        
        # Semaphore to limit concurrency (avoid overwhelming proxy provider or local resources)
        sem = asyncio.Semaphore(10) 

        async def scrape_subpage(sub_url):
            async with sem:
                # Get fresh proxy for THIS specific request
                sub_proxy = await proxy_manager.get_next_proxy()
                
                # Try CFFI
                text, pdfs, _ = await _cffi_scrape(sub_url, sub_proxy)
                # Fallback System Curl
                if not text:
                    text, pdfs, _ = await _system_curl_scrape(sub_url, sub_proxy)
                
                if text:
                    print(f"[Sub] Success: {sub_url}")
                    return (sub_url, text, pdfs)
                else:
                    print(f"[Sub] Failed: {sub_url}")
                    return None

        # Launch parallel tasks
        tasks = [scrape_subpage(sub) for sub in target_subpages]
        results = await asyncio.gather(*tasks)

        for res in results:
            if res:
                sub_url, text, pdfs = res
                visited_urls.append(sub_url)
                aggregated_markdown.append(f"--- PAGE START: {sub_url} ---\n{text}\n--- PAGE END ---\n")
                all_pdf_links.update(pdfs)

    return "\n".join(aggregated_markdown), list(all_pdf_links), visited_urls

# --- HELPERS ---

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
async def _cffi_scrape(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        async with AsyncSession(impersonate="chrome120", proxy=proxy, timeout=25) as s:
            resp = await s.get(url)
            if resp.status_code != 200: return "", set(), set()
            return _parse_html(resp.text, url)
    except: 
        # Re-raise so tenacity can retry, but catch finally inside retry logic if needed
        # Actually for simplicity in this scraper architecture, we might just want to return fail
        # But to use tenacity we must raise. 
        # Given the existing logic "Fallback System Curl", we should be careful.
        # Let's retry purely network errors, but if it fails 2 times, return empty to trigger fallback.
        raise Exception("Network Error") 

# Wrapper to handle the retry exception and return empty tuple on final failure
async def _cffi_scrape_safe(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        return await _cffi_scrape(url, proxy)
    except:
        return "", set(), set()

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
async def _system_curl_scrape(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        cmd = ["curl", "-L", "-k", "-s"]
        if proxy: cmd.extend(["-x", proxy])
        cmd.extend(["-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", url])
        
        res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=35)
        if res.returncode != 0 or not res.stdout: raise Exception("Curl Failed")
        return _parse_html(res.stdout, url)
    except: 
        raise Exception("Curl Error")

# Wrapper for safe execution
async def _system_curl_scrape_safe(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        return await _system_curl_scrape(url, proxy)
    except:
        return "", set(), set()

# Note: Update calls in scrape_subpage to use _safe versions if we want to suppress errors after retries
# However, the original code already has try/except blocks inside _cffi_scrape. 
# To use tenacity effectively, we need to remove the internal try/except catch-all and let tenacity catch it.
# BUT, _cffi_scrape is called by scrape_subpage which expects a return value.
# Refactoring _cffi_scrape to raise exception for tenacity, then catching it in the safe wrapper is best.
# Let's revert to the pattern: Decorator on the Logic, Safe Wrapper for the Caller.

# Redefining _cffi_scrape without the broad try/except, but with specific logic
@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def _cffi_scrape_logic(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    async with AsyncSession(impersonate="chrome120", proxy=proxy, timeout=25) as s:
        resp = await s.get(url)
        if resp.status_code != 200: raise Exception(f"Status {resp.status_code}")
        return _parse_html(resp.text, url)

async def _cffi_scrape(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        return await _cffi_scrape_logic(url, proxy)
    except Exception:
        return "", set(), set()

@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def _system_curl_scrape_logic(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    cmd = ["curl", "-L", "-k", "-s"]
    if proxy: cmd.extend(["-x", proxy])
    cmd.extend(["-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", url])
    
    res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=35)
    if res.returncode != 0 or not res.stdout: raise Exception("Curl Failed")
    return _parse_html(res.stdout, url)

async def _system_curl_scrape(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        return await _system_curl_scrape_logic(url, proxy)
    except Exception:
        return "", set(), set()


def _parse_html(html: str, url: str) -> Tuple[str, Set[str], Set[str]]:
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer", "svg"]): tag.extract()
        text = soup.get_text(separator='\n\n')
        clean = '\n'.join(l.strip() for l in text.splitlines() if l.strip())
        return clean, *_extract_links_html(str(soup), url)
    except: return "", set(), set()

def _extract_links_html(html: str, base_url: str) -> Tuple[Set[str], Set[str]]:
    pdfs, internal = set(), set()
    try:
        soup = BeautifulSoup(html, 'html.parser')
        base_domain = urlparse(base_url).netloc
        for a in soup.find_all('a', href=True):
            full = urljoin(base_url, a['href'])
            parsed = urlparse(full)
            if parsed.path.lower().endswith(".pdf"): pdfs.add(full)
            elif parsed.netloc == base_domain: internal.add(full)
    except: pass
    return pdfs, internal

def _extract_links(markdown: str, base_url: str) -> Tuple[Set[str], Set[str]]:
    return set(), set()

def _prioritize_links(links: Set[str], base_url: str) -> List[str]:
    # Expanded keyword list for richer profiles
    high = [
        # Core
        "quem-somos", "sobre", "institucional",
        # Offerings
        "portfolio", "produto", "servico", "solucoes", "atuacao", "tecnologia",
        # Trust & Proof (NEW)
        "clientes", "cases", "projetos", "obras", "certificacoes", "premios", "parceiros",
        # Team & Contact (NEW)
        "equipe", "time", "lideranca", "contato", "fale-conosco", "unidades"
    ]
    
    low = ["login", "signin", "cart", "policy", "blog", "news", "politica-privacidade", "termos"]
    
    scored = []
    for l in links:
        if l.rstrip('/') == base_url.rstrip('/'): continue
        s = 0
        lower = l.lower()
        
        if any(k in lower for k in low): s -= 100
        if any(k in lower for k in high): s += 50
        
        # Penalize deep nesting (often less relevant blog posts or detailed product specs)
        s -= len(urlparse(l).path.split('/'))
        
        scored.append((s, l))
        
    return [l for s, l in sorted(scored, key=lambda x: x[0], reverse=True) if s > -50]
