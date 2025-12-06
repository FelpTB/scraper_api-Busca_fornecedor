"""
Cliente HTTP para scraping usando curl_cffi e system curl.
Responsável por baixar o conteúdo das páginas.
"""

import asyncio
import subprocess
import logging
from typing import Tuple, Set, Optional

try:
    from curl_cffi.requests import AsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    AsyncSession = None

from .constants import DEFAULT_HEADERS, scraper_config
from .html_parser import parse_html

logger = logging.getLogger(__name__)


async def cffi_scrape(
    url: str, 
    proxy: Optional[str] = None, 
    session: Optional[AsyncSession] = None
) -> Tuple[str, Set[str], Set[str]]:
    """
    Faz scrape usando curl_cffi (imita Chrome).
    
    Args:
        url: URL para scrape
        proxy: Proxy opcional
        session: Sessão AsyncSession existente (para reutilização)
    
    Returns:
        Tuple de (texto, links_documentos, links_internos)
    """
    if not HAS_CURL_CFFI:
        raise RuntimeError("curl_cffi não está instalado")
    
    headers = DEFAULT_HEADERS.copy()
    headers["Referer"] = "https://www.google.com/"
    
    try:
        if session:
            resp = await session.get(url, headers=headers)
        else:
            async with AsyncSession(
                impersonate="chrome120", 
                proxy=proxy, 
                timeout=scraper_config.session_timeout,
                headers=headers,
                verify=False
            ) as s:
                resp = await s.get(url)
                
        if resp.status_code != 200:
            logger.warning(f"CFFI Status {resp.status_code} para {url}")
            raise Exception(f"Status {resp.status_code}")
        
        return parse_html(resp.text, url)
        
    except Exception as e:
        logger.debug(f"[CFFI] Erro em {url}: {type(e).__name__}: {str(e)}")
        raise


async def cffi_scrape_safe(
    url: str, 
    proxy: Optional[str] = None
) -> Tuple[str, Set[str], Set[str]]:
    """
    Versão safe do cffi_scrape que não propaga exceções.
    Retorna tupla vazia em caso de erro.
    """
    if not HAS_CURL_CFFI:
        return "", set(), set()
    
    try:
        headers = DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        async with AsyncSession(
            impersonate="chrome120", 
            proxy=proxy, 
            timeout=scraper_config.session_timeout,
            headers=headers,
            verify=False
        ) as s:
            resp = await s.get(url)
            if resp.status_code != 200:
                raise Exception(f"Status {resp.status_code}")
            return parse_html(resp.text, url)
    except:
        return "", set(), set()


async def system_curl_scrape(
    url: str, 
    proxy: Optional[str] = None
) -> Tuple[str, Set[str], Set[str]]:
    """
    Faz scrape usando system curl (comando do sistema).
    Fallback para quando curl_cffi falha.
    
    Args:
        url: URL para scrape
        proxy: Proxy opcional
    
    Returns:
        Tuple de (texto, links_documentos, links_internos)
    """
    headers_args = []
    for k, v in DEFAULT_HEADERS.items():
        headers_args.extend(["-H", f"{k}: {v}"])
    headers_args.extend(["-H", "Referer: https://www.google.com/"])
    
    cmd = ["curl", "-L", "-k", "-s", "--compressed", "--max-time", "15"]
    
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.extend(headers_args)
    cmd.append(url)
    
    try:
        res = await asyncio.to_thread(
            subprocess.run, cmd, 
            capture_output=True, text=True, timeout=20
        )
        
        if res.returncode != 0 or not res.stdout:
            logger.warning(f"Curl com headers falhou para {url}, tentando modo simples...")
            cmd_simple = [
                "curl", "-L", "-k", "-s", "--compressed", 
                "--max-time", "12", "-A", "Mozilla/5.0", url
            ]
            if proxy:
                cmd_simple.extend(["-x", proxy])
            res = await asyncio.to_thread(
                subprocess.run, cmd_simple, 
                capture_output=True, text=True, timeout=15
            )
            
            if res.returncode != 0 or not res.stdout:
                raise Exception("Curl Failed")
                
        return parse_html(res.stdout, url)
        
    except Exception as e:
        logger.debug(f"[SystemCurl] Erro em {url}: {type(e).__name__}: {str(e)}")
        return "", set(), set()


async def system_curl_scrape_with_exception(
    url: str, 
    proxy: Optional[str] = None
) -> Tuple[str, Set[str], Set[str]]:
    """
    Versão do system_curl_scrape que propaga exceções.
    Útil quando precisa saber se falhou para fazer retry.
    """
    headers_args = []
    for k, v in DEFAULT_HEADERS.items():
        headers_args.extend(["-H", f"{k}: {v}"])
    headers_args.extend(["-H", "Referer: https://www.google.com/"])
    
    cmd = ["curl", "-L", "-k", "-s", "--compressed", "--max-time", "15"]
    
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.extend(headers_args)
    cmd.append(url)
    
    res = await asyncio.to_thread(
        subprocess.run, cmd, 
        capture_output=True, text=True, timeout=20
    )
    
    if res.returncode != 0 or not res.stdout:
        cmd_simple = [
            "curl", "-L", "-k", "-s", "--compressed", 
            "--max-time", "12", "-A", "Mozilla/5.0", url
        ]
        if proxy:
            cmd_simple.extend(["-x", proxy])
        res = await asyncio.to_thread(
            subprocess.run, cmd_simple, 
            capture_output=True, text=True, timeout=15
        )
        
        if res.returncode != 0 or not res.stdout:
            raise Exception("Curl Failed")
            
    return parse_html(res.stdout, url)

