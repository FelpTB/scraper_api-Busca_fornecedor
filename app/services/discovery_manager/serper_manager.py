"""
Search API Manager - Gerenciamento centralizado da API Serpshot (Google SERP).

Utiliza a API Serpshot (https://www.serpshot.com/docs) para buscas no Google.
Controla:
- Cliente HTTP com connection pooling
- Rate limiting por token bucket
- Retry logic com backoff exponencial
- Métricas de uso da API

Variável de ambiente: SERPSHOT_KEY (ex.: no Railway).
"""

import asyncio
import logging
import json
import random
import time
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Any, Tuple

import httpx

from app.core.config import settings
from app.services.concurrency_manager.config_loader import (
    get_section as get_concurrency_section,
)
from .rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


def _parse_serpshot_results(data: Any) -> List[Any]:
    """
    Extrai lista de resultados da resposta da API Serpshot (query única).
    Suporta: data como dict (uma query) ou como lista (batch, pega primeira entrada).
    Ref: https://www.serpshot.com/docs
    """
    if not isinstance(data, dict):
        return []
    inner = data.get("data")
    if inner is None:
        return []
    if isinstance(inner, list):
        if not inner:
            return []
        inner = inner[0]
    if not isinstance(inner, dict):
        return []
    raw = inner.get("results")
    if not isinstance(raw, list):
        return []
    return raw


def _parse_serpshot_results_batch(data: Any) -> List[List[Any]]:
    """
    Extrai lista de listas de resultados para resposta batch (múltiplas queries).
    Retorna uma lista por query, na mesma ordem do array queries enviado.
    Ref: https://www.serpshot.com/docs
    """
    if not isinstance(data, dict):
        return []
    inner = data.get("data")
    if not isinstance(inner, list):
        return []
    out = []
    for entry in inner:
        if not isinstance(entry, dict):
            out.append([])
            continue
        raw = entry.get("results")
        out.append(raw if isinstance(raw, list) else [])
    return out


def _log_rate_limit_headers(response: httpx.Response, context: str = "") -> None:
    """Extrai e registra cabeçalhos X-RateLimit-* para monitoramento de quotas."""
    limit = response.headers.get("X-RateLimit-Limit")
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if limit is not None or remaining is not None or reset is not None:
        parts = []
        if limit is not None:
            parts.append(f"Limit={limit}")
        if remaining is not None:
            parts.append(f"Remaining={remaining}")
        if reset is not None:
            parts.append(f"Reset={reset}")
        logger.debug(
            f"Serpshot X-RateLimit {context}: {', '.join(parts)}"
        )


def _parse_retry_after(header_value: Optional[str], max_seconds: float = 60.0) -> Optional[float]:
    """
    Parseia o header Retry-After conforme RFC 7231.
    
    Pode ser:
    - Número em segundos (ex: "120")
    - HTTP-date (ex: "Wed, 21 Oct 2015 07:28:00 GMT")
    
    Returns:
        Segundos a esperar, ou None se inválido/não presente.
        Limitado a max_seconds.
    """
    import datetime as dt_module
    if not header_value or not header_value.strip():
        return None
    val = header_value.strip()
    # Número em segundos
    try:
        seconds = float(val)
        return min(max(0, seconds), max_seconds) if seconds > 0 else None
    except ValueError:
        pass
    # HTTP-date
    try:
        retry_dt = parsedate_to_datetime(val)
        now = dt_module.datetime.now(dt_module.timezone.utc)
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=dt_module.timezone.utc)
        delta = (retry_dt - now).total_seconds()
        return min(max(0, delta), max_seconds) if delta > 0 else None
    except (ValueError, TypeError):
        return None


class SerperManager:
    """
    Gerenciador centralizado da API Serpshot (Google SERP).
    
    Features:
    - Connection pooling com HTTP/2
    - Rate limiting por Token Bucket
    - Alta concorrência
    - Retry automático com backoff exponencial
    - Tratamento de rate limiting (429)
    - Métricas de uso
    """
    
    def __init__(
        self,
        rate_per_second: float = None,  # Valores default vêm da config central
        max_burst: int = None,
        max_concurrent: int = None,  # Alta concorrência para conexões HTTP
        request_timeout: float = None,
        connect_timeout: float = None,
        max_retries: int = None,
        retry_base_delay: float = None,
        retry_max_delay: float = None
    ):
        """
        Args:
            rate_per_second: Taxa máxima de requisições por segundo
            max_burst: Máximo de requisições em burst
            max_concurrent: Limite de conexões HTTP simultâneas (não é rate limit!)
            request_timeout: Timeout de leitura em segundos
            connect_timeout: Timeout de conexão em segundos
            max_retries: Máximo de tentativas
            retry_base_delay: Delay base para retry (segundos)
            retry_max_delay: Delay máximo para retry (segundos)
        """
        serper_cfg = get_concurrency_section("discovery/serper", {})
        # Variável de ambiente SERPSHOT_RATE_PER_SECOND (Railway) sobrescreve o JSON se > 0
        env_rate = settings.SERPSHOT_RATE_PER_SECOND
        self._rate_per_second = (
            rate_per_second if rate_per_second is not None
            else (env_rate if env_rate > 0 else serper_cfg.get("rate_per_second", 190.0))
        )
        default_burst = serper_cfg.get("max_burst", 200)
        self._max_burst = (
            max_burst if max_burst is not None
            else (max(default_burst, self._rate_per_second + 50) if env_rate > 0 else default_burst)
        )
        self._max_concurrent = max_concurrent if max_concurrent is not None else serper_cfg.get("max_concurrent", 1000)
        self._request_timeout = request_timeout if request_timeout is not None else serper_cfg.get("request_timeout", 15.0)
        self._connect_timeout = connect_timeout if connect_timeout is not None else serper_cfg.get("connect_timeout", 5.0)
        self._max_retries = max_retries if max_retries is not None else serper_cfg.get("max_retries", 3)
        self._retry_base_delay = retry_base_delay if retry_base_delay is not None else serper_cfg.get("retry_base_delay", 1.0)
        self._retry_max_delay = retry_max_delay if retry_max_delay is not None else serper_cfg.get("retry_max_delay", 10.0)
        self._rate_limiter_timeout = serper_cfg.get("rate_limiter_timeout", 10.0)
        self._rate_limiter_retry_timeout = serper_cfg.get("rate_limiter_retry_timeout", 5.0)
        self._connection_semaphore_timeout = serper_cfg.get("connection_semaphore_timeout", 10.0)
        self._retry_after_max = serper_cfg.get("retry_after_max", 60.0)
        self._retry_jitter = serper_cfg.get("retry_jitter", 2.0)  # segundos de jitter max
        
        # Rate limiter (controla taxa, NÃO concorrência)
        self._rate_limiter = TokenBucketRateLimiter(
            rate_per_second=self._rate_per_second,
            max_burst=self._max_burst,
            name="serpshot"
        )
        
        # Semáforo para limitar conexões HTTP (recurso, não taxa)
        # Este é um limite de RECURSOS (conexões), não de TAXA
        self._connection_semaphore: Optional[asyncio.Semaphore] = None
        self._semaphore_lock = asyncio.Lock()
        
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        
        # Métricas
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rate_limited_requests = 0
        self._total_latency_ms = 0
        
        logger.info(
            f"SerpshotManager: rate={self._rate_per_second}/s, burst={self._max_burst}, "
            f"max_concurrent={self._max_concurrent}, timeout={self._request_timeout}s"
        )
    
    async def _get_connection_semaphore(self) -> asyncio.Semaphore:
        """Retorna semáforo de conexões (lazy initialization)."""
        async with self._semaphore_lock:
            if self._connection_semaphore is None:
                self._connection_semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._connection_semaphore
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP global com connection pooling."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=self._connect_timeout,
                        read=self._request_timeout,
                        write=self._request_timeout,
                        pool=self._request_timeout
                    ),
                    limits=httpx.Limits(
                        max_keepalive_connections=100,
                        max_connections=self._max_concurrent,
                        keepalive_expiry=30.0
                    ),
                    http2=True
                )
                logger.info(
                    f"🌐 Serpshot: Cliente HTTP criado "
                    f"(pool={self._max_concurrent}, http2=True)"
                )
        return self._client
    
    async def close(self):
        """Fecha o cliente HTTP global."""
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None
                logger.info("🌐 Serpshot: Cliente HTTP fechado")
    
    async def search(
        self,
        query: str,
        num_results: int = 100,
        country: str = "br",
        language: str = "pt-br",
        request_id: str = ""
    ) -> Tuple[List[Dict[str, str]], int, bool]:
        """
        Realiza busca no Google usando API Serpshot.
        
        O fluxo agora é:
        1. Adquirir token do rate limiter (controla taxa de envio)
        2. Adquirir slot de conexão (controla recursos HTTP)
        3. Executar requisição
        
        Isso permite que muitas requisições esperem apenas pelo rate limit,
        não por requisições anteriores terminarem.
        
        Args:
            query: Termo de busca
            num_results: Número máximo de resultados
            country: Código do país (gl)
            language: Código do idioma (hl)
            request_id: ID da requisição
            
        Returns:
            Tuple de (lista de resultados, número de retries, total_failure)
            total_failure=True quando retries esgotados e nenhum resultado (inserir vazio no DB).
        """
        if not settings.SERPSHOT_KEY:
            logger.warning("⚠️ SERPSHOT_KEY não configurada")
            return [], 0, False
        
        import time as time_module
        
        # 1. Aguardar rate limit (controla TAXA de envio)
        # Medir tempo real de espera para detectar fila
        rate_start = time_module.perf_counter()
        
        # Timeout configurável para fail-fast: se não conseguir token rapidamente,
        # melhor falhar rápido do que esperar muito e travar a empresa
        rate_limit_acquired = await self._rate_limiter.acquire(timeout=self._rate_limiter_timeout)
        
        rate_wait_ms = (time_module.perf_counter() - rate_start) * 1000
        
        # Se esperou mais que 10ms, considerar como fila
        
        if not rate_limit_acquired:
            logger.error(f"❌ Serpshot: Rate limit timeout para query: {query[:50]}...")
            return [], 0, False
        
        # 2. Adquirir slot de conexão HTTP (controla RECURSOS)
        connection_semaphore = await self._get_connection_semaphore()
        
        conn_start = time_module.perf_counter()
        
        # Adquirir semáforo com timeout para evitar espera indefinida
        try:
            await asyncio.wait_for(
                connection_semaphore.acquire(),
                timeout=self._connection_semaphore_timeout
            )
        except asyncio.TimeoutError:
            conn_wait_ms = (time_module.perf_counter() - conn_start) * 1000
            # Calcular vagas quando timeout ocorre (todas ocupadas provavelmente)
            available = connection_semaphore._value
            used = self._max_concurrent - available
            logger.error(
                f"❌ Serpshot: Timeout aguardando slot de conexão após {conn_wait_ms:.0f}ms "
                f"(timeout={self._connection_semaphore_timeout}s) | "
                f"Vagas: {used}/{self._max_concurrent} usadas, {available} disponíveis"
            )
            return [], 0, False
        
        conn_wait_ms = (time_module.perf_counter() - conn_start) * 1000
        
        
        try:
            # 3. Executar requisição
            req_start = time_module.perf_counter()
            result = await self._search_with_retry(
                query, num_results, country, language, request_id
            )
            req_duration = (time_module.perf_counter() - req_start) * 1000
            
            # Log se requisição demorou muito (possível travamento)
            if req_duration > self._request_timeout * 1000 * 1.5:  # 50% acima do timeout
                available = connection_semaphore._value
                used = self._max_concurrent - available
                logger.warning(
                    f"⚠️ Serpshot: Requisição demorou {req_duration:.0f}ms "
                    f"(timeout configurado: {self._request_timeout * 1000:.0f}ms) | "
                    f"Vagas: {used}/{self._max_concurrent} usadas"
                )
            
            return result
        finally:
            # Sempre liberar semáforo, mesmo em caso de erro
            connection_semaphore.release()
            available_after = connection_semaphore._value
            used_after = self._max_concurrent - available_after
    
    async def _search_with_retry(
        self,
        query: str,
        num_results: int,
        country: str,
        language: str,
        request_id: str = ""
    ) -> Tuple[List[Dict[str, str]], int, bool]:
        """Executa busca com retry logic via API Serpshot (POST /api/search/google)."""
        url = "https://api.serpshot.com/api/search/google"
        # Serpshot: queries é array (até 100); location US, IN, JP, BR, GB, DE, CA, FR, ID, MX, SG
        country_code = (country or "br").lower()
        location = country_code.upper() if len(country_code) == 2 else "BR"
        if location == "BR":
            lr = "pt-BR"
            hl = "pt-BR"
            gl = "br"
        else:
            lr = (language or "en").replace("_", "-") if language else "en"
            hl = lr
            gl = country_code
        num = 30
        payload = json.dumps({
            "queries": [query],
            "type": "search",
            "num": num,
            "page": 1,
            "location": location,
            "lr": lr,
            "gl": gl,
            "hl": hl
        })
        headers = {
            "X-API-Key": settings.SERPSHOT_KEY,
            "Content-Type": "application/json"
        }
        
        client = await self._get_client()
        last_error = None
        last_error_type = None
        last_retry_after: Optional[float] = None
        retries_count = 0
        
        for attempt in range(self._max_retries):
            try:
                if attempt > 0:
                    retries_count += 1
                    # Usar Retry-After da API se disponível (429), senão backoff exponencial
                    if last_retry_after is not None:
                        base_delay = last_retry_after
                        delay_src = "Retry-After"
                    else:
                        base_delay = min(
                            self._retry_base_delay * (2 ** (attempt - 1)),
                            self._retry_max_delay
                        )
                        delay_src = "backoff"
                    # Jitter para evitar thundering herd: cada worker espera um pouco diferente
                    jitter = random.uniform(0, min(self._retry_jitter, base_delay * 0.5))
                    delay = base_delay + jitter
                    logger.warning(
                        f"🔄 Serpshot retry {attempt + 1}/{self._max_retries} "
                        f"após {delay:.1f}s (reason={last_error_type}, src={delay_src})"
                    )
                    
                    await asyncio.sleep(delay)
                    last_retry_after = None  # Usado apenas uma vez
                    
                    # Re-adquirir rate limit para retry (timeout configurável)
                    if not await self._rate_limiter.acquire(timeout=self._rate_limiter_retry_timeout):
                        logger.warning("⚠️ Serpshot: Rate limit timeout no retry")
                        continue
                
                start_time = time.perf_counter()
                response = await client.post(url, headers=headers, content=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                self._total_requests += 1
                self._total_latency_ms += latency_ms
                
                _log_rate_limit_headers(response, f"status={response.status_code}")
                
                if response.status_code == 429:
                    self._rate_limited_requests += 1
                    retry_after_val = response.headers.get("Retry-After")
                    parsed = _parse_retry_after(retry_after_val, self._retry_after_max)
                    if parsed is not None:
                        last_retry_after = parsed
                    ra_str = f"Retry-After={retry_after_val!r} (usado={parsed:.1f}s)" if parsed is not None else f"Retry-After={retry_after_val!r}"
                    logger.warning(
                        f"⚠️ Serpshot rate limit (429), "
                        f"tentativa {attempt + 1}/{self._max_retries} ({ra_str})"
                    )
                    last_error = "Rate limit (429)"
                    last_error_type = "rate_limit"
                    continue
                
                if response.status_code >= 500:
                    logger.warning(
                        f"⚠️ Serpshot server error ({response.status_code}), "
                        f"tentativa {attempt + 1}/{self._max_retries}"
                    )
                    last_error = f"Server error ({response.status_code})"
                    last_error_type = "error"
                    continue
                
                if response.status_code >= 400:
                    self._failed_requests += 1
                    logger.error(f"❌ Serpshot client error: {response.status_code}")
                    return [], retries_count, True
                
                data = response.json()
                # Serpshot: { "code": 200, "data": { "results": [...] } } ou data como lista (batch)
                raw_results = _parse_serpshot_results(data)
                results = []
                for item in raw_results:
                    if not isinstance(item, dict):
                        continue
                    results.append({
                        "title": (item.get("title") or "").strip(),
                        "link": (item.get("link") or "").strip(),
                        "snippet": (item.get("snippet") or "").strip(),
                    })
                
                self._successful_requests += 1
                logger.info(f"✅ Serpshot: {len(results)} resultados retornados de {num} solicitados ({latency_ms:.0f}ms)")
                return results, retries_count, False
                
            except httpx.TimeoutException:
                last_error_type = "timeout"
                last_error = f"timeout após {self._request_timeout}s"
                logger.warning(
                    f"⚠️ Serpshot {last_error_type}: {last_error}, "
                    f"tentativa {attempt + 1}/{self._max_retries}"
                )
                
            except httpx.ConnectError as e:
                last_error_type = "error"
                last_error = str(e) if str(e) else "falha ao conectar"
                logger.warning(
                    f"⚠️ Serpshot ConnectError: {last_error}, "
                    f"tentativa {attempt + 1}/{self._max_retries}"
                )
                
            except httpx.PoolTimeout:
                last_error_type = "timeout"
                last_error = "pool de conexões esgotado"
                logger.warning(
                    f"⚠️ Serpshot PoolTimeout: {last_error}, "
                    f"tentativa {attempt + 1}/{self._max_retries}"
                )
                
            except Exception as e:
                last_error_type = "error"
                last_error = str(e) if str(e) else "erro desconhecido"
                logger.warning(
                    f"⚠️ Serpshot {type(e).__name__}: {last_error}, "
                    f"tentativa {attempt + 1}/{self._max_retries}"
                )
        
        self._failed_requests += 1
        logger.error(
            f"❌ Serpshot falhou após {self._max_retries} tentativas: "
            f"[{last_error_type}] {last_error}"
        )
        return [], retries_count, True
    
    async def search_batch(
        self,
        queries: List[str],
        num_results: int = 30,
        country: str = "br",
        language: str = "pt-br",
        request_id: str = ""
    ) -> Tuple[List[List[Dict[str, str]]], int, bool]:
        """
        Realiza buscas em batch (até 100 queries por requisição).
        Uma única chamada de API para múltiplas queries; otimiza throughput para Big Data.
        
        Args:
            queries: Lista de termos de busca (máx 100)
            num_results: Resultados por query
            country: Código do país
            language: Código do idioma
            request_id: ID da requisição
            
        Returns:
            Tuple de (lista de listas de resultados, retries_count, total_failure)
        """
        if not queries:
            return [], 0, False
        if not settings.SERPSHOT_KEY:
            logger.warning("⚠️ SERPSHOT_KEY não configurada")
            return [[] for _ in queries], 0, False
        
        batch_size = min(100, len(queries))
        qs = queries[:batch_size]
        
        import time as time_module
        rate_limit_acquired = await self._rate_limiter.acquire(timeout=self._rate_limiter_timeout)
        if not rate_limit_acquired:
            logger.error("❌ Serpshot: Rate limit timeout para batch")
            return [[] for _ in qs], 0, False
        
        connection_semaphore = await self._get_connection_semaphore()
        try:
            await asyncio.wait_for(
                connection_semaphore.acquire(),
                timeout=self._connection_semaphore_timeout
            )
        except asyncio.TimeoutError:
            logger.error("❌ Serpshot: Timeout aguardando slot de conexão (batch)")
            return [[] for _ in qs], 0, False
        
        try:
            return await self._search_batch_with_retry(
                qs, num_results, country, language, request_id
            )
        finally:
            connection_semaphore.release()
    
    async def _search_batch_with_retry(
        self,
        queries: List[str],
        num_results: int,
        country: str,
        language: str,
        request_id: str = ""
    ) -> Tuple[List[List[Dict[str, str]]], int, bool]:
        """Executa batch com retry logic. Até 100 queries por requisição."""
        url = "https://api.serpshot.com/api/search/google"
        country_code = (country or "br").lower()
        location = country_code.upper() if len(country_code) == 2 else "BR"
        if location == "BR":
            lr, hl, gl = "pt-BR", "pt-BR", "br"
        else:
            lr = hl = (language or "en").replace("_", "-") if language else "en"
            gl = country_code
        
        payload = json.dumps({
            "queries": queries,
            "type": "search",
            "num": min(30, num_results),
            "page": 1,
            "location": location,
            "lr": lr,
            "gl": gl,
            "hl": hl
        })
        headers = {
            "X-API-Key": settings.SERPSHOT_KEY,
            "Content-Type": "application/json"
        }
        
        client = await self._get_client()
        last_error = None
        last_error_type = None
        last_retry_after: Optional[float] = None
        retries_count = 0
        
        for attempt in range(self._max_retries):
            try:
                if attempt > 0:
                    retries_count += 1
                    base_delay = (
                        last_retry_after
                        if last_retry_after is not None
                        else min(
                            self._retry_base_delay * (2 ** (attempt - 1)),
                            self._retry_max_delay
                        )
                    )
                    jitter = random.uniform(0, min(self._retry_jitter, base_delay * 0.5))
                    delay = base_delay + jitter
                    logger.warning(
                        f"🔄 Serpshot batch retry {attempt + 1}/{self._max_retries} "
                        f"após {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    last_retry_after = None
                    if not await self._rate_limiter.acquire(timeout=self._rate_limiter_retry_timeout):
                        continue
                
                response = await client.post(url, headers=headers, content=payload)
                _log_rate_limit_headers(response, f"status={response.status_code}")
                
                if response.status_code == 429:
                    self._rate_limited_requests += 1
                    retry_after_val = response.headers.get("Retry-After")
                    parsed = _parse_retry_after(retry_after_val, self._retry_after_max)
                    if parsed is not None:
                        last_retry_after = parsed
                    ra_str = f"Retry-After={retry_after_val!r}" + (f" (usado={parsed:.1f}s)" if parsed else "")
                    logger.warning(
                        f"⚠️ Serpshot batch rate limit (429), "
                        f"tentativa {attempt + 1}/{self._max_retries} ({ra_str})"
                    )
                    last_error = "Rate limit (429)"
                    last_error_type = "rate_limit"
                    continue
                
                if response.status_code >= 500:
                    last_error = f"Server error ({response.status_code})"
                    last_error_type = "error"
                    continue
                
                if response.status_code >= 400:
                    self._failed_requests += 1
                    logger.error(f"❌ Serpshot batch client error: {response.status_code}")
                    return [[] for _ in queries], retries_count, True
                
                data = response.json()
                raw_batch = _parse_serpshot_results_batch(data)
                results_batch = []
                for raw in raw_batch:
                    items = []
                    for item in (raw or []):
                        if isinstance(item, dict):
                            items.append({
                                "title": (item.get("title") or "").strip(),
                                "link": (item.get("link") or "").strip(),
                                "snippet": (item.get("snippet") or "").strip(),
                            })
                    results_batch.append(items)
                
                self._successful_requests += 1
                total_results = sum(len(r) for r in results_batch)
                logger.info(
                    f"✅ Serpshot batch: {len(queries)} queries, "
                    f"{total_results} resultados totais"
                )
                return results_batch, retries_count, False
                
            except httpx.TimeoutException:
                last_error_type = "timeout"
                last_error = f"timeout após {self._request_timeout}s"
            except Exception as e:
                last_error_type = "error"
                last_error = str(e) or "erro desconhecido"
        
        self._failed_requests += 1
        logger.error(f"❌ Serpshot batch falhou após {self._max_retries} tentativas: [{last_error_type}] {last_error}")
        return [[] for _ in queries], retries_count, True
    
    def update_config(
        self,
        rate_per_second: Optional[float] = None,
        max_burst: Optional[int] = None,
        max_concurrent: Optional[int] = None,
        request_timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        """Atualiza configurações do manager."""
        if rate_per_second is not None:
            self._rate_per_second = rate_per_second
            self._rate_limiter.update_config(rate_per_second=rate_per_second)
        
        if max_burst is not None:
            self._max_burst = max_burst
            self._rate_limiter.update_config(max_burst=max_burst)
        
        if max_concurrent is not None:
            self._max_concurrent = max_concurrent
            self._connection_semaphore = asyncio.Semaphore(max_concurrent)
            
        if request_timeout is not None:
            self._request_timeout = request_timeout
            
        if max_retries is not None:
            self._max_retries = max_retries
        
        logger.info(
            f"SerpshotManager: Configuração atualizada - "
            f"rate={self._rate_per_second}/s, concurrent={self._max_concurrent}, "
            f"timeout={self._request_timeout}s"
        )
    
    def get_status(self) -> dict:
        """Retorna status e métricas."""
        avg_latency = 0
        if self._successful_requests > 0:
            avg_latency = self._total_latency_ms / self._successful_requests
        
        success_rate = 0
        if self._total_requests > 0:
            success_rate = self._successful_requests / self._total_requests
        
        # Calcular vagas do semáforo
        semaphore_info = {
            "max": self._max_concurrent,
            "available": 0,
            "used": 0,
            "utilization": 0.0
        }
        
        if self._connection_semaphore is not None:
            try:
                available = self._connection_semaphore._value
                used = max(0, self._max_concurrent - available)
                utilization = (used / self._max_concurrent * 100) if self._max_concurrent > 0 else 0.0
                semaphore_info = {
                    "max": self._max_concurrent,
                    "available": available,
                    "used": used,
                    "utilization": round(utilization, 1)
                }
            except Exception:
                pass  # Semáforo pode não estar inicializado ainda
        
        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "rate_limited_requests": self._rate_limited_requests,
            "success_rate": f"{success_rate:.1%}",
            "avg_latency_ms": round(avg_latency, 2),
            "rate_limiter": self._rate_limiter.get_status(),
            "semaphore": semaphore_info,
            "config": {
                "rate_per_second": self._rate_per_second,
                "max_burst": self._max_burst,
                "max_concurrent": self._max_concurrent,
                "request_timeout": self._request_timeout,
                "max_retries": self._max_retries
            }
        }
    
    def reset_metrics(self):
        """Reseta métricas."""
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rate_limited_requests = 0
        self._total_latency_ms = 0
        self._rate_limiter.reset_metrics()
        logger.info("SerpshotManager: Métricas resetadas")


# Instância singleton
serper_manager = SerperManager()


# Funções de conveniência
async def search_serper(
    query: str,
    num_results: int = 100
) -> List[Dict[str, str]]:
    """Busca usando Serpshot API (função de conveniência)."""
    results, _, _ = await serper_manager.search(query, num_results)
    return results


async def search_serper_batch(
    queries: List[str],
    num_results: int = 30,
    country: str = "br",
    language: str = "pt-br"
) -> Tuple[List[List[Dict[str, str]]], int, bool]:
    """Busca em batch (até 100 queries por requisição)."""
    return await serper_manager.search_batch(queries, num_results, country, language)
