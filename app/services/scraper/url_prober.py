"""
Prober de URLs para encontrar a melhor variação acessível.
Testa http/https, www/non-www em paralelo.
"""

import asyncio
import time
import logging
import subprocess
from typing import List, Tuple, Optional
from urllib.parse import urlparse

try:
    from curl_cffi.requests import AsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    AsyncSession = None

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .constants import DEFAULT_HEADERS

logger = logging.getLogger(__name__)


class URLProber:
    """
    Testa variações de URL em paralelo para encontrar a melhor.
    Retorna a primeira URL que responde com sucesso.
    
    Otimizado para alta concorrência (500 empresas simultâneas).
    """
    
    def __init__(self, timeout: float = 10.0, max_concurrent: int = 500):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._cache: dict = {}  # Cache de URLs já validadas
    
    async def probe(self, base_url: str) -> Tuple[str, float]:
        """
        Testa variações de URL em paralelo.
        Otimizado: testa URL original primeiro, só testa variações se falhar.
        
        Args:
            base_url: URL base para gerar variações
        
        Returns:
            Tuple de (melhor_url, tempo_resposta_ms)
        
        Raises:
            URLNotReachable: Se nenhuma variação responder
        """
        # Verificar cache
        if base_url in self._cache:
            cached = self._cache[base_url]
            return cached['url'], cached['time']
        
        # Normalizar URL
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
        
        # OTIMIZAÇÃO: Tentar URL original primeiro (mais rápido)
        result = await self._test_url(base_url)
        if result and result[1] < 400:
            self._cache[base_url] = {'url': base_url, 'time': result[0]}
            return base_url, result[0]
        
        # Se falhou, tentar variações
        variations = self._generate_variations(base_url)
        # Remover a URL original já testada
        variations = [v for v in variations if v != base_url]
        
        if not variations:
            raise URLNotReachable(f"URL {base_url} não respondeu")
        
        # Criar tasks para variações restantes
        tasks = [self._test_url(url) for url in variations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtrar resultados bem-sucedidos
        successful = []
        for url, result in zip(variations, results):
            if isinstance(result, Exception):
                continue
            if result is not None:
                response_time, status = result
                if status < 400:
                    successful.append((url, response_time, status))
        
        if not successful:
            raise URLNotReachable(f"Nenhuma variação de {base_url} respondeu")
        
        # Ordenar por status (2xx primeiro) e depois por tempo
        successful.sort(key=lambda x: (x[2] >= 300, x[1]))
        
        best_url, best_time, best_status = successful[0]
        
        # Cachear resultado
        self._cache[base_url] = {'url': best_url, 'time': best_time}
        
        logger.info(f"🎯 Melhor URL: {best_url} ({best_time:.0f}ms, status {best_status})")
        
        return best_url, best_time
    
    def _generate_variations(self, base_url: str) -> List[str]:
        """
        Gera variações de uma URL (http/https, www/non-www).
        
        Args:
            base_url: URL base
        
        Returns:
            Lista de variações únicas
        """
        # Normalizar URL
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
        
        parsed = urlparse(base_url)
        domain = parsed.netloc
        path = parsed.path or '/'
        
        # Remover www. se existir para ter a versão base
        base_domain = domain.replace('www.', '')
        
        variations = set()
        
        # Gerar todas as combinações
        for scheme in ['https', 'http']:
            for prefix in ['', 'www.']:
                full_domain = prefix + base_domain
                # Evitar www.www.
                if not full_domain.startswith('www.www.'):
                    url = f"{scheme}://{full_domain}{path}"
                    variations.add(url.rstrip('/'))
        
        # Adicionar URL original se não estiver
        original = f"{parsed.scheme}://{domain}{path}".rstrip('/')
        variations.add(original)
        
        # Ordenar: https primeiro, www primeiro
        sorted_vars = sorted(variations, key=lambda x: (
            not x.startswith('https'),
            'www.' not in x
        ))
        
        return sorted_vars
    
    async def _test_url(self, url: str) -> Optional[Tuple[float, int]]:
        """
        Testa uma URL específica.
        Usa curl_cffi se disponível, senão httpx, senão system curl.
        
        Args:
            url: URL para testar
        
        Returns:
            Tuple de (tempo_ms, status_code) ou None se falhar
        """
        async with self.semaphore:
            # Tentar curl_cffi primeiro (mais robusto)
            if HAS_CURL_CFFI:
                result = await self._test_with_curl_cffi(url)
                if result:
                    return result
            
            # Fallback para httpx
            if HAS_HTTPX:
                result = await self._test_with_httpx(url)
                if result:
                    return result
            
            # Fallback para system curl
            result = await self._test_with_system_curl(url)
            return result
    
    async def _test_with_curl_cffi(self, url: str) -> Optional[Tuple[float, int]]:
        """Testa URL com curl_cffi."""
        try:
            headers = DEFAULT_HEADERS.copy()
            
            async with AsyncSession(
                impersonate="chrome120",
                timeout=self.timeout,
                verify=False
            ) as session:
                start = time.perf_counter()
                resp = await session.head(url, headers=headers, allow_redirects=True)
                elapsed = (time.perf_counter() - start) * 1000
                return elapsed, resp.status_code
        except Exception as e:
            logger.debug(f"curl_cffi falhou para {url}: {e}")
            return None
    
    async def _test_with_httpx(self, url: str) -> Optional[Tuple[float, int]]:
        """Testa URL com httpx."""
        try:
            headers = {k: v for k, v in DEFAULT_HEADERS.items()}
            
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=False,
                follow_redirects=True
            ) as client:
                start = time.perf_counter()
                resp = await client.head(url, headers=headers)
                elapsed = (time.perf_counter() - start) * 1000
                return elapsed, resp.status_code
        except Exception as e:
            logger.debug(f"httpx falhou para {url}: {e}")
            return None
    
    async def _test_with_system_curl(self, url: str) -> Optional[Tuple[float, int]]:
        """Testa URL com system curl (último recurso)."""
        try:
            cmd = [
                "curl", "-I", "-L", "-k", "-s", 
                "--max-time", str(int(self.timeout)),
                "-o", "/dev/null", "-w", "%{http_code}",
                "-A", "Mozilla/5.0",
                url
            ]
            
            start = time.perf_counter()
            res = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=self.timeout + 2
            )
            elapsed = (time.perf_counter() - start) * 1000
            
            if res.returncode == 0 and res.stdout.strip():
                status_code = int(res.stdout.strip())
                return elapsed, status_code
            return None
        except Exception as e:
            logger.debug(f"system curl falhou para {url}: {e}")
            return None
    
    async def find_best_variation(
        self, 
        urls: List[str]
    ) -> Tuple[str, float]:
        """
        Encontra a melhor URL de uma lista.
        
        Args:
            urls: Lista de URLs para testar
        
        Returns:
            Tuple de (melhor_url, tempo_ms)
        """
        tasks = [self._test_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception) or result is None:
                continue
            response_time, status = result
            if status < 400:
                successful.append((url, response_time, status))
        
        if not successful:
            raise URLNotReachable("Nenhuma URL da lista respondeu")
        
        successful.sort(key=lambda x: (x[2] >= 300, x[1]))
        return successful[0][0], successful[0][1]


class URLNotReachable(Exception):
    """Exceção quando nenhuma variação de URL responde."""
    pass


# Instância singleton
url_prober = URLProber()

