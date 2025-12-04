"""
Scraper de alta performance com rotação de IP e paralelismo.

ESTRUTURA DO ARQUIVO:
=====================
1. CONFIGURAÇÃO E CONSTANTES
2. CIRCUIT BREAKER
3. FUNÇÕES DE SCRAPE PURO (baixar conteúdo)
4. FUNÇÕES DE PARSING (extrair dados do HTML)
5. FUNÇÕES DE SELEÇÃO DE LINKS (LLM)
6. ORQUESTRADOR PRINCIPAL (scrape_url)
"""

import asyncio
import subprocess
import random
import logging
import time
from typing import List, Tuple, Set, Optional
from urllib.parse import urljoin, urlparse, quote, unquote
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession, RequestsError
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, retry_if_exception_type, before_sleep_log, RetryError
from app.core.proxy import proxy_manager

logger = logging.getLogger(__name__)

# ============================================================================
# 1. CONFIGURAÇÃO E CONSTANTES
# ============================================================================

# Headers que imitam um navegador real para evitar bloqueios WAF
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

# Configuração otimizada (ATUALIZADA com base no relatório de falhas)
_scraper_config = {
    'site_semaphore_limit': 100,
    'circuit_breaker_threshold': 5,  # AUMENTADO: era 2, agora 5 (evita bloqueio prematuro)
    'page_timeout': 10000,
    'md_threshold': 0.6,
    'min_word_threshold': 4,
    'chunk_size': 20,
    'chunk_semaphore_limit': 100,
    'session_timeout': 15  # AUMENTADO: era 5s, agora 15s (latência de proxy)
}

# Semáforo global para limitar processamento concorrente de sites
site_semaphore = asyncio.Semaphore(_scraper_config['site_semaphore_limit'])

def configure_scraper_params(
    site_semaphore_limit: int = 100,
    circuit_breaker_threshold: int = 5,
    page_timeout: int = 10000,
    md_threshold: float = 0.6,
    min_word_threshold: int = 4,
    chunk_size: int = 20,
    chunk_semaphore_limit: int = 100,
    session_timeout: int = 15
):
    """Configura dinamicamente os parâmetros do scraper."""
    global _scraper_config, site_semaphore, CIRCUIT_BREAKER_THRESHOLD

    _scraper_config.update({
        'site_semaphore_limit': site_semaphore_limit,
        'circuit_breaker_threshold': circuit_breaker_threshold,
        'page_timeout': page_timeout,
        'md_threshold': md_threshold,
        'min_word_threshold': min_word_threshold,
        'chunk_size': chunk_size,
        'chunk_semaphore_limit': chunk_semaphore_limit,
        'session_timeout': session_timeout
    })

    site_semaphore = asyncio.Semaphore(site_semaphore_limit)
    CIRCUIT_BREAKER_THRESHOLD = circuit_breaker_threshold
    domain_failures.clear()

    logger.info(f"🔧 Scraper reconfigurado: site_sem={site_semaphore_limit}, "
                f"circuit_breaker={circuit_breaker_threshold}, session_timeout={session_timeout}s")

# ============================================================================
# 2. CIRCUIT BREAKER
# ============================================================================

domain_failures = {}
CIRCUIT_BREAKER_THRESHOLD = _scraper_config['circuit_breaker_threshold']

def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except:
        return "unknown"

def _record_failure(url: str, is_cloudflare: bool = False):
    """
    Registra falha de um domínio.
    NOTA: Falhas de Cloudflare não contam para o circuit breaker (são proteções, não erros).
    """
    if is_cloudflare:
        logger.debug(f"[CircuitBreaker] Cloudflare detectado em {url}, não contando como falha")
        return
        
    domain = _get_domain(url)
    domain_failures[domain] = domain_failures.get(domain, 0) + 1
    if domain_failures[domain] >= CIRCUIT_BREAKER_THRESHOLD:
        logger.warning(f"🔌 CIRCUIT BREAKER ABERTO para {domain} após {domain_failures[domain]} falhas consecutivas")

def _record_success(url: str):
    domain = _get_domain(url)
    if domain in domain_failures:
        domain_failures[domain] = 0

def _is_circuit_open(url: str) -> bool:
    domain = _get_domain(url)
    return domain_failures.get(domain, 0) >= CIRCUIT_BREAKER_THRESHOLD

# ============================================================================
# 3. FUNÇÕES DE SCRAPE PURO (baixar conteúdo)
# ============================================================================

def _normalize_url(url: str) -> str:
    """
    Normaliza URL removendo caracteres problemáticos.
    CORRIGIDO: Remove vírgulas finais que causavam falhas.
    """
    try:
        # Limpar URL
        url = url.strip()
        
        # CORREÇÃO: Remover vírgulas finais (bug identificado no relatório)
        url = url.rstrip(',')
        
        # Remover aspas
        if url.startswith('"') and url.endswith('"'):
            url = url[1:-1]
        if url.startswith("'") and url.endswith("'"):
            url = url[1:-1]
        url = url.strip().rstrip(',')  # Remover vírgula novamente após strip
        
        parsed = urlparse(url)
        
        # Limpar path de fragmentos problemáticos
        path = parsed.path
        if '%20%22' in path or '%22' in path:
            for marker in ['%20%22', '%22']:
                if marker in path:
                    path = path[:path.index(marker)]
                    break
        
        # Codificar path se necessário
        if '%' not in path:
            path_parts = path.split('/')
            encoded_parts = [quote(part, safe='') if part else part for part in path_parts]
            path = '/'.join(encoded_parts)
        
        # Limpar query string
        query = parsed.query
        if query:
            if '%20%22' in query or '%22' in query:
                query = query.split('%20%22')[0].split('%22')[0]
            if query and '%' not in query:
                query_parts = query.split('&')
                encoded_query_parts = []
                for part in query_parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        encoded_query_parts.append(f"{quote(key, safe='')}={quote(value, safe='')}")
                    else:
                        encoded_query_parts.append(quote(part, safe=''))
                query = '&'.join(encoded_query_parts)
        
        # Reconstruir URL
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if query:
            normalized += f"?{query}"
        
        return normalized
    except Exception as e:
        logger.warning(f"Erro ao normalizar URL {url}: {e}")
        return url.strip().rstrip(',')

def _is_cloudflare_challenge(content: str) -> bool:
    """Detecta se o conteúdo é uma página de desafio Cloudflare."""
    if not content:
        return False
    content_lower = content.lower()
    indicators = [
        "just a moment...",
        "cf-browser-verification",
        "challenge-running",
        "cf_chl_opt",
        "checking your browser",
        "ray id:",
        "cloudflare"
    ]
    # Precisa ter cloudflare + algum indicador de challenge
    has_cloudflare = "cloudflare" in content_lower
    has_challenge = any(ind in content_lower for ind in indicators[:5])
    return has_cloudflare and has_challenge

async def _cffi_scrape_logic(url: str, session: Optional[AsyncSession] = None, proxy: Optional[str] = None) -> Tuple[str, Set[str], Set[str]]:
    """Lógica principal do scrape com curl_cffi."""
    headers = _DEFAULT_HEADERS.copy()
    headers["Referer"] = "https://www.google.com/"
    
    if session:
        resp = await session.get(url, headers=headers)
    else:
        async with AsyncSession(
            impersonate="chrome120", 
            proxy=proxy, 
            timeout=_scraper_config['session_timeout'],
            headers=headers,
            verify=False
        ) as s:
            resp = await s.get(url)
            
    if resp.status_code != 200:
        logger.warning(f"CFFI Status {resp.status_code} para {url}")
        raise Exception(f"Status {resp.status_code}")
    
    return _parse_html(resp.text, url)

async def _cffi_scrape(url: str, proxy: Optional[str], session: Optional[AsyncSession] = None) -> Tuple[str, Set[str], Set[str]]:
    """Wrapper do scrape CFFI com tratamento de erros."""
    try:
        return await _cffi_scrape_logic(url, session=session, proxy=proxy)
    except Exception as e:
        logger.debug(f"[CFFI] Erro em {url}: {type(e).__name__}: {str(e)}")
        raise e

async def _cffi_scrape_safe(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    """Versão safe que não propaga exceções."""
    try:
        headers = _DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        async with AsyncSession(
            impersonate="chrome120", 
            proxy=proxy, 
            timeout=_scraper_config['session_timeout'],
            headers=headers,
            verify=False
        ) as s:
            resp = await s.get(url)
            if resp.status_code != 200:
                raise Exception(f"Status {resp.status_code}")
            return _parse_html(resp.text, url)
    except:
        return "", set(), set()

async def _system_curl_scrape_logic(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    """Lógica principal do scrape com system curl."""
    headers_args = []
    for k, v in _DEFAULT_HEADERS.items():
        headers_args.extend(["-H", f"{k}: {v}"])
    headers_args.extend(["-H", "Referer: https://www.google.com/"])
    
    # Timeout aumentado para 15s (era 10s)
    cmd = ["curl", "-L", "-k", "-s", "--compressed", "--max-time", "15"]
    
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.extend(headers_args)
    cmd.append(url)
    
    res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=20)
    
    if res.returncode != 0 or not res.stdout:
        # Fallback: modo simples
        logger.warning(f"Curl com headers falhou para {url}, tentando modo simples...")
        cmd_simple = ["curl", "-L", "-k", "-s", "--compressed", "--max-time", "12", "-A", "Mozilla/5.0", url]
        if proxy:
            cmd_simple.extend(["-x", proxy])
        res = await asyncio.to_thread(subprocess.run, cmd_simple, capture_output=True, text=True, timeout=15)
        
        if res.returncode != 0 or not res.stdout:
            raise Exception("Curl Failed")
            
    return _parse_html(res.stdout, url)

async def _system_curl_scrape(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    """Wrapper do system curl com tratamento de erros."""
    try:
        return await _system_curl_scrape_logic(url, proxy)
    except Exception as e:
        logger.debug(f"[SystemCurl] Erro em {url}: {type(e).__name__}: {str(e)}")
        return "", set(), set()

async def _system_curl_scrape_safe(url: str, proxy: Optional[str]) -> Tuple[str, Set[str], Set[str]]:
    """Versão safe que não propaga exceções."""
    try:
        return await _system_curl_scrape_logic(url, proxy)
    except:
        return "", set(), set()

# ============================================================================
# 4. FUNÇÕES DE PARSING (extrair dados do HTML)
# ============================================================================

def _is_soft_404(text: str) -> bool:
    """Detecta 'soft 404s' (páginas de erro com status 200)."""
    if len(text) > 1000:
        return False
        
    lower_text = text.lower()
    error_keywords = [
        "404 not found", "page not found", "página não encontrada", 
        "erro 404", "não encontramos a página", "página inexistente",
        "ops! página não encontrada", "error 404", "file not found"
    ]
    
    if len(text) < 200 and ("found" in lower_text or "erro" in lower_text or "página" in lower_text):
        if any(k in lower_text for k in error_keywords) or "not found" in lower_text:
            return True
            
    return any(k in lower_text for k in error_keywords)

def _parse_html(html: str, url: str) -> Tuple[str, Set[str], Set[str]]:
    """Extrai texto limpo e links do HTML."""
    try:
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')
            
        # Remover elementos não textuais
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "path", "defs", "symbol", "use"]): 
            tag.extract()
            
        text = soup.get_text(separator='\n\n')
        lines = [line.strip() for line in text.splitlines()]
        clean_text = '\n'.join(line for line in lines if line)
        
        return clean_text, *_extract_links_html(str(soup), url)
    except Exception as e:
        logger.error(f"Erro no parsing HTML de {url}: {e}")
        return "", set(), set()

def _extract_links_html(html: str, base_url: str) -> Tuple[Set[str], Set[str]]:
    """Extrai links HTML e documentos."""
    documents, internal = set(), set()
    try:
        soup = BeautifulSoup(html, 'html.parser')
        base_domain = urlparse(base_url).netloc
        
        DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx'}
        EXCLUDED_EXTENSIONS = {
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
            '.zip', '.rar', '.tar', '.gz', '.xls', '.xlsx', '.csv', '.txt', '.xml', '.json', '.js', '.css',
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.woff', '.woff2', '.ttf', '.eot', '.otf'
        }
        
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            
            # CORREÇÃO: Remover vírgulas finais
            href = href.rstrip(',')
            
            if href.startswith('#') or href.lower().startswith('javascript:'):
                continue
                
            full = urljoin(base_url, href)
            
            # Remover vírgula final do URL completo também
            full = full.rstrip(',')
            
            if '#' in full:
                full_no_frag = full.split('#')[0]
                base_no_frag = base_url.split('#')[0]
                if full_no_frag == base_no_frag:
                    continue

            parsed = urlparse(full)
            path_lower = parsed.path.lower()
            
            if any(path_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
                documents.add(full)
            elif any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                continue
            elif parsed.netloc == base_domain:
                if not any(ext in parsed.query.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg']):
                    internal.add(full)
    except:
        pass
    return documents, internal

def _filter_non_html_links(links: Set[str]) -> Set[str]:
    """Filtra links que são arquivos não-HTML."""
    DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx'}
    EXCLUDED_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
        '.zip', '.rar', '.tar', '.gz', '.xls', '.xlsx', '.csv', '.txt', '.xml', '.json', '.js', '.css',
        '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
        '.woff', '.woff2', '.ttf', '.eot', '.otf'
    }
    
    filtered = set()
    for link in links:
        # CORREÇÃO: Limpar vírgulas
        link = link.strip().rstrip(',')
        if not link:
            continue
            
        parsed = urlparse(link)
        path_lower = parsed.path.lower()
        
        if any(path_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
            continue
        if any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue
        if any(ext in parsed.query.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
            continue
        if any(dir_name in path_lower for dir_name in ['/wp-content/uploads/', '/assets/', '/images/', '/img/', '/static/', '/media/']):
            if any(path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']):
                continue
        
        filtered.add(link)
    
    return filtered

def _prioritize_links(links: Set[str], base_url: str) -> List[str]:
    """Prioriza links por relevância."""
    high = [
        "quem-somos", "sobre", "institucional",
        "portfolio", "produto", "servico", "solucoes", "atuacao", "tecnologia",
        "catalogo", "catalogo-digital", "catalogo-online", "produtos", "servicos",
        "clientes", "cases", "projetos", "obras", "certificacoes", "premios", "parceiros",
        "equipe", "time", "lideranca", "contato", "fale-conosco", "unidades"
    ]
    low = ["login", "signin", "cart", "policy", "blog", "news", "politica-privacidade", "termos"]
    
    scored = []
    for l in links:
        # CORREÇÃO: Limpar vírgulas
        l = l.strip().rstrip(',')
        if not l or l.rstrip('/') == base_url.rstrip('/'):
            continue
            
        s = 0
        lower = l.lower()
        
        if any(k in lower for k in low):
            s -= 100
        if any(k in lower for k in high):
            s += 50
        s -= len(urlparse(l).path.split('/'))
        
        if any(x in lower for x in ["page", "p=", "pagina", "nav"]):
            if not any(k in lower for k in low):
                s += 30

        scored.append((s, l))
        
    return [l for s, l in sorted(scored, key=lambda x: x[0], reverse=True) if s > -80]

# ============================================================================
# 5. FUNÇÕES DE SELEÇÃO DE LINKS (LLM)
# ============================================================================

async def _select_links_with_llm(links: Set[str], base_url: str, max_links: int = 30) -> List[str]:
    """Usa LLM para selecionar links mais relevantes."""
    start_ts = time.perf_counter()
    
    if not links:
        return []
    
    # Filtrar links não-HTML
    filtered_links = _filter_non_html_links(links)
    logger.info(f"Filtrados {len(links) - len(filtered_links)} links não-HTML. Restam {len(filtered_links)} links válidos.")
    
    if not filtered_links:
        return []
    
    if len(filtered_links) <= max_links:
        duration = time.perf_counter() - start_ts
        logger.info(f"[PERF] select_links_llm duration={duration:.3f}s strategy=short_circuit")
        return list(filtered_links)
    
    from openai import AsyncOpenAI
    from app.core.config import settings
    import json
    
    client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    links_list = "\n".join([f"{i+1}. {url}" for i, url in enumerate(sorted(filtered_links))])
    
    prompt = f"""Você é um especialista em análise de websites B2B.

CONTEXTO: Estamos coletando dados para criar um perfil completo de empresa com os seguintes campos:

**IDENTITY**: Nome da empresa, CNPJ, tagline, descrição, ano de fundação, número de funcionários
**CLASSIFICATION**: Indústria, modelo de negócio (B2B/B2C), público-alvo, cobertura geográfica
**TEAM**: Tamanho da equipe, cargos-chave, certificações do time
**OFFERINGS**: Produtos, categorias de produtos, serviços, detalhes de serviços, modelos de engajamento, diferenciais
**REPUTATION**: Certificações, prêmios, parcerias, lista de clientes, cases de sucesso
**CONTACT**: E-mails, telefones, LinkedIn, endereço, localizações

TAREFA: Selecione os {max_links} links MAIS RELEVANTES da lista abaixo. Priorize:
1. Páginas "Sobre", "Quem Somos", "Institucional"
2. Páginas de Produtos/Serviços/Soluções/Catálogos
3. Páginas de Cases, Clientes, Projetos
4. Páginas de Contato, Equipe, Localizações
5. Páginas de Certificações, Prêmios, Parcerias

EVITE: Blogs, notícias, políticas de privacidade, login, carrinho, termos de uso

LISTA DE LINKS DO SITE {base_url}:
{links_list}

Responda APENAS com um JSON array contendo os números dos links selecionados (ex: [1, 3, 5, 7, ...]):
"""

    try:
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em análise de websites B2B. Responda sempre em JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        
        try:
            result = json.loads(content)
            if isinstance(result, list):
                selected_indices = result
            elif "links" in result:
                selected_indices = result["links"]
            elif "selected" in result:
                selected_indices = result["selected"]
            elif "indices" in result:
                selected_indices = result["indices"]
            else:
                for value in result.values():
                    if isinstance(value, list):
                        selected_indices = value
                        break
                else:
                    selected_indices = []
        except:
            logger.warning("LLM não retornou JSON válido, usando fallback")
            return _prioritize_links(filtered_links, base_url)[:max_links]
        
        sorted_links = sorted(filtered_links)
        selected_urls = []
        for idx in selected_indices:
            try:
                idx_int = int(idx)  # Converter para int (LLM pode retornar strings)
                if 1 <= idx_int <= len(sorted_links):
                    selected_urls.append(sorted_links[idx_int - 1])
            except (ValueError, TypeError):
                continue  # Ignorar índices inválidos
        
        duration = time.perf_counter() - start_ts
        logger.info(f"[PERF] select_links_llm duration={duration:.3f}s selected={len(selected_urls)} strategy=llm")
        return selected_urls[:max_links]
        
    except Exception as e:
        logger.error(f"Erro ao usar LLM para selecionar links: {e}")
        return _prioritize_links(filtered_links, base_url)[:max_links]

# ============================================================================
# 6. ORQUESTRADOR PRINCIPAL
# ============================================================================

async def scrape_url(url: str, max_subpages: int = 100) -> Tuple[str, List[str], List[str]]:
    """
    Scraper de alta performance com rotação de IP e paralelismo.
    
    Estratégia:
    1. Main Page: curl_cffi (imita Chrome) com proxy rotativo
    2. Fallback: System curl se curl_cffi falhar
    3. Subpages: Processamento paralelo com sessões reutilizadas
    
    Retorna: (texto_agregado, lista_pdfs, urls_visitadas)
    """
    overall_start = time.perf_counter()
    aggregated_markdown = []
    all_pdf_links = set()
    visited_urls = []

    # --- ETAPA 1: SCRAPE DA PÁGINA PRINCIPAL ---
    main_start = time.perf_counter()
    
    if site_semaphore.locked():
        logger.warning(f"[Scraper] Site semaphore full, waiting... url={url}")
    
    async with site_semaphore:
        logger.info(f"[Scraper] Processing Main: {url}")
        main_proxy = await proxy_manager.get_next_proxy()
        
        try:
            text, pdfs, links = await _cffi_scrape_safe(url, main_proxy)
            
            # Verificar se é Cloudflare challenge
            is_cloudflare = _is_cloudflare_challenge(text)
            
            if not text or len(text) < 100 or _is_soft_404(text):
                reason = "Soft 404" if text and _is_soft_404(text) else "Conteúdo insuficiente"
                if is_cloudflare:
                    reason = "Cloudflare challenge"
                logger.warning(f"[Main] CFFI falhou ({reason}) em {url}. Tentando System Curl.")
                text, pdfs, links = await _system_curl_scrape_safe(url, await proxy_manager.get_next_proxy())

            if text and not _is_soft_404(text):
                visited_urls.append(url)
                aggregated_markdown.append(f"--- PAGE START: {url} ---\n{text}\n--- PAGE END ---\n")
                all_pdf_links.update(pdfs)
            else:
                # Tentar variação www <-> non-www
                parsed = urlparse(url)
                domain = parsed.netloc
                new_url = None
                
                if domain.startswith("www."):
                    new_url = f"{parsed.scheme}://{domain[4:]}"
                else:
                    new_url = f"{parsed.scheme}://www.{domain}"
                
                if new_url and new_url != url:
                    logger.warning(f"[Main] Tentando variação: {new_url}")
                    try:
                        text, pdfs, links = await _system_curl_scrape_logic(new_url, await proxy_manager.get_next_proxy())
                        if text:
                            visited_urls.append(new_url)
                            aggregated_markdown.append(f"--- PAGE START: {new_url} ---\n{text}\n--- PAGE END ---\n")
                            all_pdf_links.update(pdfs)
                            url = new_url
                    except:
                        pass
                
                if not text:
                    return "", [], []

        except Exception as e:
            logger.error(f"[Main] Falha fatal em {url}: {e}")
            return "", [], []

    main_duration = time.perf_counter() - main_start
    logger.info(f"[PERF] main_page url={url} duration={main_duration:.3f}s links={len(links)}")

    # --- ETAPA 2: SCRAPE DAS SUBPÁGINAS ---
    logger.info(f"[Scraper] Encontrados {len(links)} links. Selecionando com LLM...")
    target_subpages = await _select_links_with_llm(links, url, max_links=max_subpages)
    
    if target_subpages:
        subpages_start = time.perf_counter()
        logger.info(f"[Scraper] Processing {len(target_subpages)} subpages")
        
        chunk_size = _scraper_config['chunk_size']
        url_chunks = [target_subpages[i:i + chunk_size] for i in range(0, len(target_subpages), chunk_size)]
        
        async def scrape_chunk(urls_chunk):
            chunk_results = []
            chunk_proxy = await proxy_manager.get_next_proxy()
            
            try:
                async with AsyncSession(
                    impersonate="chrome120",
                    proxy=chunk_proxy,
                    timeout=_scraper_config['session_timeout'],
                    verify=False
                ) as session:
                    
                    skipped_count = 0
                    
                    for sub_url in urls_chunk:
                        if _is_circuit_open(sub_url):
                            skipped_count += 1
                            chunk_results.append(None)
                            continue

                        normalized_url = _normalize_url(sub_url)
                        
                        try:
                            text, pdfs, _ = await _cffi_scrape(normalized_url, proxy=None, session=session)
                            
                            # Verificar Cloudflare
                            is_cf = _is_cloudflare_challenge(text) if text else False
                            
                            if not text or len(text) < 100 or _is_soft_404(text):
                                _record_failure(normalized_url, is_cloudflare=is_cf)
                                raise Exception("Empty or soft 404")
                            
                            logger.info(f"[Sub] ✅ Success: {normalized_url} ({len(text)} chars)")
                            _record_success(normalized_url)
                            chunk_results.append((normalized_url, text, pdfs))
                            continue
                            
                        except Exception as e:
                            if "Empty" not in str(e) and "soft" not in str(e).lower():
                                _record_failure(normalized_url)
                        
                        # Fallback: System Curl
                        try:
                            fallback_proxy = await proxy_manager.get_next_proxy()
                            text, pdfs, _ = await _system_curl_scrape(normalized_url, fallback_proxy)
                            
                            if text and len(text) >= 100 and not _is_soft_404(text):
                                logger.info(f"[Sub] ✅ Success (Curl): {normalized_url}")
                                _record_success(normalized_url)
                                chunk_results.append((normalized_url, text, pdfs))
                            else:
                                logger.warning(f"[Sub] ❌ Falha total: {normalized_url}")
                                _record_failure(normalized_url)
                                chunk_results.append(None)
                        except Exception as e:
                            logger.error(f"[Sub] ❌ Erro Curl: {normalized_url}: {e}")
                            _record_failure(normalized_url)
                            chunk_results.append(None)
                    
                    if skipped_count > 0:
                        logger.warning(f"🔌 [CircuitBreaker] Pulou {skipped_count} URLs neste chunk")
                            
            except Exception as e_session:
                logger.error(f"[Chunk] ❌ Erro na sessão (Proxy: {chunk_proxy}): {e_session}")
                for _ in range(len(urls_chunk) - len(chunk_results)):
                    chunk_results.append(None)
                    
            return chunk_results

        # Processar chunks em paralelo
        chunk_sem = asyncio.Semaphore(_scraper_config['chunk_semaphore_limit'])
        
        async def scrape_chunk_wrapper(chunk):
            async with chunk_sem:
                return await scrape_chunk(chunk)

        tasks = [scrape_chunk_wrapper(chunk) for chunk in url_chunks]
        results_of_chunks = await asyncio.gather(*tasks)
        
        # Consolidar resultados
        results = []
        for chunk_res in results_of_chunks:
            results.extend(chunk_res)

        success_subpages = 0
        for res in results:
            if res:
                sub_url, text, pdfs = res
                visited_urls.append(sub_url)
                aggregated_markdown.append(f"--- PAGE START: {sub_url} ---\n{text}\n--- PAGE END ---\n")
                all_pdf_links.update(pdfs)
                success_subpages += 1

        subpages_duration = time.perf_counter() - subpages_start
        logger.info(f"[PERF] subpages duration={subpages_duration:.3f}s requested={len(target_subpages)} ok={success_subpages}")

    total_duration = time.perf_counter() - overall_start
    logger.info(f"[PERF] total url={url} duration={total_duration:.3f}s pages={len(visited_urls)} pdfs={len(all_pdf_links)}")
    
    return "\n".join(aggregated_markdown), list(all_pdf_links), visited_urls
