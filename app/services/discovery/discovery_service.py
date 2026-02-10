"""
Serviço de Discovery v4.1 - Descoberta de sites oficiais de empresas.

Usa a API Serpshot para buscas no Google (https://www.serpshot.com/docs).

Managers de infraestrutura:
- serper_manager (Serpshot): Rate limiting, retry, connection pooling
- SearchCache: Cache de buscas recentes

A lógica de negócio permanece neste arquivo.
"""

import asyncio
import logging
import json
import time
import urllib.parse
from typing import Optional, List, Dict, Tuple

from app.core.config import settings
from app.services.agents import get_discovery_agent
from app.services.concurrency_manager.config_loader import get_section as get_config

# Importar managers de infraestrutura
from app.services.discovery_manager import (
    serper_manager,
    search_cache,
)

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DE DISCOVERY ---
_DISCOVERY_CFG = get_config("discovery/discovery", {})
DISCOVERY_TIMEOUT = _DISCOVERY_CFG.get("timeout", 60.0)
DISCOVERY_MAX_RETRIES = _DISCOVERY_CFG.get("max_retries", 3)
SERPER_NUM_RESULTS = _DISCOVERY_CFG.get("serper_num_results", 10)


# --- BLACKLIST DE DOMÍNIOS ---
BLACKLIST_DOMAINS = {
    # Sites de dados empresariais
    "econodata.com.br", "cnpj.biz", "cnpja.com", "cnpj.info", "cnpjs.rocks",
    "casadosdados.com.br", "empresascnpj.com", "consultacnpj.com",
    "informecadastral.com.br", "cadastroempresa.com.br", "transparencia.cc",
    "listamais.com.br", "solutudo.com.br", "telelistas.net", "apontador.com.br",
    "guiamais.com.br", "construtora.net.br", "b2bleads.com.br",
    "empresas.serasaexperian.com.br", "jusbrasil.com.br", "jusdados.com",
    # Redes sociais
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "twitter.com", "x.com", "tiktok.com", "pinterest.com", "threads.net",
    # Marketplaces
    "mercadolivre.com.br", "shopee.com.br", "olx.com.br", "amazon.com.br",
    "magazineluiza.com.br", "americanas.com.br",
    # Outros
    "translate.google.com", "webcache.googleusercontent.com",
}


def is_blacklisted_domain(url: str) -> bool:
    """Verifica se a URL pertence a um domínio na blacklist."""
    if not url:
        return False
    
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        
        for prefix in ('www.', 'm.', 'mobile.'):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        
        for blacklisted in BLACKLIST_DOMAINS:
            if domain == blacklisted or domain.endswith('.' + blacklisted):
                return True
        
        return False
        
    except Exception:
        return False


async def search_google_serper(query: str, num_results: int = 100, request_id: str = "") -> Tuple[List[Dict[str, str]], int]:
    """
    Realiza busca no Google usando API Serpshot.
    
    Features via serper_manager (Serpshot):
    - Cache de resultados (evita chamadas repetidas)
    - Rate limiting (controla concorrência)
    - Retry automático com backoff exponencial
    - Connection pooling HTTP/2
    
    Args:
        query: Termo de busca
        num_results: Número máximo de resultados
        request_id: ID da requisição
        
    Returns:
        Tuple de (lista de dicts com title, link, snippet, número de retries)
    """
    # 1. Verificar cache
    cached_results = await search_cache.get(query, num_results)
    if cached_results is not None:
        logger.debug(f"🔍 Serpshot (cache hit): {query[:30]}...")
        return cached_results, 0  # Cache hit = 0 retries
    
    # 2. Buscar via Serpshot API
    results, retries, _ = await serper_manager.search(query, num_results, request_id=request_id)
    
    # 3. Armazenar em cache se houve resultados
    if results:
        await search_cache.set(query, results, num_results)
    
    return results, retries


async def search_google_serper_batch(
    queries: List[str],
    num_results: int = 100,
    request_id: str = ""
) -> Tuple[List[Dict[str, str]], int]:
    """
    Realiza buscas em batch via Serpshot (até 100 queries em 1 requisição).
    Usa cache por query; apenas queries não cacheadas geram chamada à API.
    
    Returns:
        Tuple de (lista plana de resultados, total de retries)
    """
    if not queries:
        return [], 0
    
    # 1. Verificar cache para cada query
    cache_results: Dict[int, Optional[List[Dict[str, str]]]] = {}
    uncached: List[Tuple[int, str]] = []
    for i, q in enumerate(queries):
        cached = await search_cache.get(q, num_results)
        cache_results[i] = cached
        if cached is None:
            uncached.append((i, q))
    
    if not uncached:
        all_results = []
        for i in range(len(queries)):
            all_results.extend(cache_results[i] or [])
        logger.debug(f"🔍 Serpshot batch (cache hit): {len(queries)} queries")
        return all_results, 0
    
    # 2. Buscar apenas queries não cacheadas em 1 chamada batch
    uncached_queries = [q for _, q in uncached]
    batch_results, retries, _ = await serper_manager.search_batch(
        uncached_queries, num_results, country="br", language="pt-br", request_id=request_id
    )
    
    # 3. Atualizar cache e mapear resultados
    for (orig_idx, q), res_list in zip(uncached, batch_results):
        if res_list:
            await search_cache.set(q, res_list, num_results)
        cache_results[orig_idx] = res_list if res_list else []
    
    # 4. Montar lista plana na ordem original
    all_results = []
    for i in range(len(queries)):
        all_results.extend(cache_results.get(i) or [])
    
    return all_results, retries


async def close_serper_client():
    """Fecha o cliente HTTP global (chamar no shutdown da aplicação)."""
    await serper_manager.close()
    logger.info("🌐 Discovery: Cliente HTTP fechado")


def _build_search_queries(
    razao_social: str,
    nome_fantasia: str,
    municipio: str
) -> List[str]:
    """
    Constrói queries de busca otimizadas.
    
    Queries (máximo 2):
    - Q1: Nome Fantasia + cidade (se existir)
    - Q2: Razão Social + cidade (se existir)
    """
    queries = []
    
    nf = nome_fantasia.strip() if nome_fantasia else ""
    rs = razao_social.strip() if razao_social else ""
    city = municipio.strip() if municipio else ""
    
    # Q1: Nome Fantasia + Municipio
    if nf:
        q1 = f'{nf} {city} site oficial'.strip()
        queries.append(q1)
    
    # Q2: Razão Social + Municipio (apenas se diferente)
    clean_rs = ""
    if rs:
        clean_rs = rs.replace(" LTDA", "").replace(" S.A.", "").replace(" EIRELI", "")
        clean_rs = clean_rs.replace(" ME", "").replace(" EPP", "").replace(" S/A", "").strip()
    
    if clean_rs:
        q2 = f'{clean_rs} {city} site oficial'.strip()
        if not nf or clean_rs.upper() != nf.upper():
            queries.append(q2)
    
    return queries


def _filter_search_results(
    results: List[Dict[str, str]],
    ctx_label: str = ""
) -> List[Dict[str, str]]:
    """Filtra resultados de busca removendo domínios da blacklist."""
    filtered = []
    blacklisted_count = 0
    seen_links = set()
    
    for r in results:
        link = r.get('link', '')
        
        # Deduplicar
        if link in seen_links:
            continue
        seen_links.add(link)
        
        # Verificar blacklist
        if is_blacklisted_domain(link):
            blacklisted_count += 1
            continue
        
        filtered.append(r)
    
    if blacklisted_count > 0:
        logger.debug(f"{ctx_label}🚫 {blacklisted_count} resultados filtrados (blacklist)")
    
    return filtered


async def find_company_website(
    razao_social: str,
    nome_fantasia: str,
    cnpj: str,
    email: Optional[str] = None,
    municipio: Optional[str] = None,
    cnaes: Optional[List[str]] = None,
    ctx_label: str = "",
    request_id: str = ""
) -> Optional[str]:
    """
    Orquestra a descoberta do site oficial da empresa.

    Fluxo:
    1. Construir queries de busca
    2. Executar buscas em paralelo (via Serper API)
    3. Filtrar resultados (blacklist)
    4. Usar DiscoveryAgent para análise

    Args:
        razao_social: Razão social da empresa
        nome_fantasia: Nome fantasia
        cnpj: CNPJ da empresa
        email: Email (opcional, usado para validação cruzada)
        municipio: Cidade
        cnaes: Lista de CNAEs
        ctx_label: Label para logging

    Returns:
        URL do site oficial ou None
    """
    # 1. CONSTRUIR QUERIES
    queries = _build_search_queries(razao_social, nome_fantasia, municipio or "")

    if not queries:
        logger.warning(f"{ctx_label}⚠️ Sem Nome Fantasia ou Razão Social para busca.")
        return None

    # 2. EXECUTAR BUSCAS VIA SEARCH_BATCH (1 requisição para múltiplas queries)
    serper_start = time.time()
    all_results, total_retries = await search_google_serper_batch(
        queries, num_results=SERPER_NUM_RESULTS, request_id=request_id
    )
    serper_duration = (time.time() - serper_start) * 1000
    
    # 3. FILTRAR RESULTADOS
    filtered_results = _filter_search_results(all_results, ctx_label)

    if not filtered_results:
        logger.warning(f"{ctx_label}⚠️ Nenhum resultado encontrado após filtros.")
        return None

    # 4. USAR DISCOVERY AGENT PARA ANÁLISE
    discovery_agent = get_discovery_agent()
    agent_start = time.time()

    try:
        site = await discovery_agent.find_website(
            nome_fantasia=nome_fantasia,
            razao_social=razao_social,
            cnpj=cnpj,
            email=email,
            municipio=municipio,
            cnaes=cnaes,
            search_results=filtered_results,
            ctx_label=ctx_label,
            request_id=request_id
        )

        agent_duration = (time.time() - agent_start) * 1000

        if not site:
            logger.warning(f"{ctx_label}Site não encontrado pelo agente")

        return site

    except Exception as e:
        agent_duration = (time.time() - agent_start) * 1000
        logger.error(f"{ctx_label}❌ Erro no DiscoveryAgent: {e}")
        return None


def get_discovery_status() -> dict:
    """Retorna status dos componentes de discovery."""
    return {
        "serper": serper_manager.get_status(),
        "cache": search_cache.get_status(),
    }
