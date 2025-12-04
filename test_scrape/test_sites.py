#!/usr/bin/env python3
"""
Script de teste que replica EXATAMENTE a estrutura do scraper.py
para identificar a causa raiz das falhas de conexão.

Usa:
- curl_cffi com AsyncSession (mesmo do scraper)
- ProxyManager (mesmo do scraper)
- Mesmos headers (_DEFAULT_HEADERS)
- Mesmas configurações de timeout
- Mesmo parsing HTML (_parse_html)
"""

import asyncio
import subprocess
import json
import time
import sys
import os
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any, List, Set, Tuple
from bs4 import BeautifulSoup

# Adicionar o diretório raiz ao path para importar módulos da app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curl_cffi.requests import AsyncSession
from app.core.proxy import proxy_manager

# ============================================
# COPIAR EXATAMENTE DO SCRAPER.PY
# ============================================

# Headers que imitam um navegador real (COPIADO DO SCRAPER)
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

# Configuração do scraper (ATUALIZADO - Mesmas configurações do scraper.py)
_scraper_config = {
    'site_semaphore_limit': 100,
    'circuit_breaker_threshold': 5,  # AUMENTADO: era 2, agora 5
    'page_timeout': 10000,
    'md_threshold': 0.6,
    'min_word_threshold': 4,
    'chunk_size': 20,
    'chunk_semaphore_limit': 100,
    'session_timeout': 15  # AUMENTADO: era 5s, agora 15s
}

# Sites para testar - selecionados da análise de falhas
TEST_SITES = [
    # Sites com muitos circuit breakers ativados
    "https://www.icaiu.com.br",
    "https://www.grupocelinho.com.br",
    "https://www.redesuperbom.com.br",
    "https://www.asassistenciatecnica.com",
    "https://www.globalatacadista.com.br",
    "https://abcsmart.com.br",
    
    # Sites com timeout
    "https://www.rwbombas.com.br",
    "https://weassistencia.eng.br",
    "https://clickcel.com.br",
    "https://antunesti.com",
    
    # Sites com empty content
    "https://www.assistenciatecnicamr.com.br",
    "https://dmassistenciatecnica.com.br",
    "https://www.bomfrio.net",
    "https://correaserviceconserto.com.br",
    
    # Sites com soft 404
    "http://ahelp.com.br",
    "http://tornoemaquinascnc.com.br",
]

def _is_soft_404(text: str) -> bool:
    """
    Detecta 'soft 404s' (páginas de erro que retornam status 200).
    COPIADO DO SCRAPER.
    """
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
    """
    Parse HTML e extrai texto, PDFs e links.
    COPIADO DO SCRAPER.
    """
    try:
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')
            
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "path", "defs", "symbol", "use"]): 
            tag.extract()
            
        text = soup.get_text(separator='\n\n')
        lines = [line.strip() for line in text.splitlines()]
        clean_text = '\n'.join(line for line in lines if line)
        
        # Simplificado - não precisamos dos links para o teste
        return clean_text, set(), set()
    except Exception as e:
        return "", set(), set()

# ============================================
# FUNÇÕES DE TESTE
# ============================================

async def test_cffi_with_proxy(url: str, proxy: Optional[str]) -> Dict[str, Any]:
    """
    Testa usando curl_cffi com proxy - EXATAMENTE como o scraper faz.
    Replica a função _cffi_scrape_logic do scraper.
    """
    start = time.time()
    result = {
        "method": "cffi_with_proxy",
        "proxy_used": proxy is not None,
        "proxy": proxy[:50] + "..." if proxy and len(proxy) > 50 else proxy,
    }
    
    try:
        headers = _DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        # EXATAMENTE como o scraper faz (session_timeout = 5)
        timeout_cfg = _scraper_config['session_timeout']
        
        async with AsyncSession(
            impersonate="chrome120", 
            proxy=proxy, 
            timeout=timeout_cfg,
            headers=headers,
            verify=False
        ) as session:
            resp = await session.get(url)
            
            result["status_code"] = resp.status_code
            result["duration"] = time.time() - start
            
            if resp.status_code != 200:
                result["status"] = "error"
                result["error"] = f"HTTP {resp.status_code}"
                return result
            
            # Parse HTML como o scraper faz
            text, _, _ = _parse_html(resp.text, url)
            
            result["raw_content_length"] = len(resp.text)
            result["parsed_text_length"] = len(text)
            result["is_soft_404"] = _is_soft_404(text)
            
            # Análise de conteúdo
            if not text or len(text) < 100:
                result["status"] = "error"
                result["error"] = "Empty/Minimal content"
                result["conclusion"] = "EMPTY_CONTENT"
            elif result["is_soft_404"]:
                result["status"] = "error"
                result["error"] = "Soft 404 detected"
                result["conclusion"] = "SOFT_404"
            else:
                result["status"] = "ok"
                result["conclusion"] = "SUCCESS"
                
            # Preview do conteúdo
            result["preview"] = text[:150].replace("\n", " ") if text else ""
            
            # Detectar proteções
            raw_lower = resp.text.lower()
            if "cloudflare" in raw_lower or "cf-browser-verification" in raw_lower:
                result["cloudflare_detected"] = True
            if "captcha" in raw_lower:
                result["captcha_detected"] = True
            if "access denied" in raw_lower or "forbidden" in raw_lower:
                result["waf_detected"] = True
                
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
        result["error_type"] = type(e).__name__
        result["duration"] = time.time() - start
        
        # Categorizar erro
        error_str = str(e).lower()
        if "timeout" in error_str or "timed out" in error_str:
            result["conclusion"] = "TIMEOUT"
        elif "connection" in error_str:
            result["conclusion"] = "CONNECTION_ERROR"
        elif "ssl" in error_str or "certificate" in error_str:
            result["conclusion"] = "SSL_ERROR"
        elif "proxy" in error_str:
            result["conclusion"] = "PROXY_ERROR"
        else:
            result["conclusion"] = "UNKNOWN_ERROR"
    
    return result

async def test_cffi_without_proxy(url: str) -> Dict[str, Any]:
    """
    Testa usando curl_cffi SEM proxy para comparação.
    """
    start = time.time()
    result = {
        "method": "cffi_without_proxy",
        "proxy_used": False,
    }
    
    try:
        headers = _DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        # Timeout maior para teste sem proxy
        async with AsyncSession(
            impersonate="chrome120", 
            proxy=None, 
            timeout=15,
            headers=headers,
            verify=False
        ) as session:
            resp = await session.get(url)
            
            result["status_code"] = resp.status_code
            result["duration"] = time.time() - start
            
            if resp.status_code != 200:
                result["status"] = "error"
                result["error"] = f"HTTP {resp.status_code}"
                return result
            
            text, _, _ = _parse_html(resp.text, url)
            
            result["raw_content_length"] = len(resp.text)
            result["parsed_text_length"] = len(text)
            result["is_soft_404"] = _is_soft_404(text)
            
            if not text or len(text) < 100:
                result["status"] = "error"
                result["conclusion"] = "EMPTY_CONTENT"
            elif result["is_soft_404"]:
                result["status"] = "error"
                result["conclusion"] = "SOFT_404"
            else:
                result["status"] = "ok"
                result["conclusion"] = "SUCCESS"
                
            result["preview"] = text[:150].replace("\n", " ") if text else ""
            
            raw_lower = resp.text.lower()
            if "cloudflare" in raw_lower:
                result["cloudflare_detected"] = True
            if "captcha" in raw_lower:
                result["captcha_detected"] = True
            if "access denied" in raw_lower or "forbidden" in raw_lower:
                result["waf_detected"] = True
                
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
        result["error_type"] = type(e).__name__
        result["duration"] = time.time() - start
        
        error_str = str(e).lower()
        if "timeout" in error_str:
            result["conclusion"] = "TIMEOUT"
        elif "connection" in error_str:
            result["conclusion"] = "CONNECTION_ERROR"
        else:
            result["conclusion"] = "UNKNOWN_ERROR"
    
    return result

async def test_system_curl(url: str, proxy: Optional[str]) -> Dict[str, Any]:
    """
    Testa usando system curl como fallback - EXATAMENTE como o scraper faz.
    Replica a função _system_curl_scrape_logic do scraper.
    """
    start = time.time()
    result = {
        "method": "system_curl",
        "proxy_used": proxy is not None,
    }
    
    try:
        # Construir headers como o scraper faz
        headers_args = []
        for k, v in _DEFAULT_HEADERS.items():
            headers_args.extend(["-H", f"{k}: {v}"])
        headers_args.extend(["-H", "Referer: https://www.google.com/"])
        
        # Timeout de 10s como no scraper
        # IMPORTANTE: --compressed para descompactar gzip/br automaticamente
        cmd = ["curl", "-L", "-k", "-s", "--compressed", "--max-time", "10"]
        
        if proxy:
            cmd.extend(["-x", proxy])
        cmd.extend(headers_args)
        cmd.append(url)
        
        res = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=15
        )
        
        result["duration"] = time.time() - start
        result["return_code"] = res.returncode
        
        if res.returncode != 0 or not res.stdout:
            result["status"] = "error"
            result["error"] = f"Curl return code {res.returncode}"
            result["stderr"] = res.stderr[:200] if res.stderr else ""
            result["conclusion"] = "CURL_FAILED"
            return result
        
        text, _, _ = _parse_html(res.stdout, url)
        
        result["raw_content_length"] = len(res.stdout)
        result["parsed_text_length"] = len(text)
        result["is_soft_404"] = _is_soft_404(text)
        
        if not text or len(text) < 100:
            result["status"] = "error"
            result["conclusion"] = "EMPTY_CONTENT"
        elif result["is_soft_404"]:
            result["status"] = "error"
            result["conclusion"] = "SOFT_404"
        else:
            result["status"] = "ok"
            result["conclusion"] = "SUCCESS"
            
        result["preview"] = text[:150].replace("\n", " ") if text else ""
        
        raw_lower = res.stdout.lower()
        if "cloudflare" in raw_lower:
            result["cloudflare_detected"] = True
        if "captcha" in raw_lower:
            result["captcha_detected"] = True
        if "access denied" in raw_lower or "forbidden" in raw_lower:
            result["waf_detected"] = True
            
    except subprocess.TimeoutExpired:
        result["status"] = "error"
        result["error"] = "Subprocess timeout"
        result["conclusion"] = "TIMEOUT"
        result["duration"] = time.time() - start
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
        result["conclusion"] = "UNKNOWN_ERROR"
        result["duration"] = time.time() - start
    
    return result

async def test_site_comprehensive(url: str) -> Dict[str, Any]:
    """
    Executa bateria completa de testes para um site.
    """
    print(f"\n{'='*70}")
    print(f"🔍 Testando: {url}")
    print(f"{'='*70}")
    
    result = {
        "url": url,
        "domain": urlparse(url).netloc,
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # 1. Obter proxy do ProxyManager (como o scraper faz)
    print("  📡 Obtendo proxy do ProxyManager...", end=" ")
    proxy = await proxy_manager.get_next_proxy()
    if proxy:
        print(f"✅ Proxy obtido")
        result["proxy_available"] = True
    else:
        print("⚠️ Nenhum proxy disponível")
        result["proxy_available"] = False
    
    # 2. Teste CFFI COM Proxy (como o scraper faz)
    print(f"  🌐 [1/4] CFFI + Proxy (timeout={_scraper_config['session_timeout']}s)...", end=" ")
    cffi_proxy = await test_cffi_with_proxy(url, proxy)
    result["tests"]["cffi_with_proxy"] = cffi_proxy
    _print_test_result(cffi_proxy)
    
    # 3. Teste CFFI SEM Proxy (para comparação)
    print(f"  🌐 [2/4] CFFI sem Proxy (timeout=15s)...", end=" ")
    cffi_no_proxy = await test_cffi_without_proxy(url)
    result["tests"]["cffi_without_proxy"] = cffi_no_proxy
    _print_test_result(cffi_no_proxy)
    
    # 4. Teste System Curl COM Proxy
    print(f"  🖥️ [3/4] System Curl + Proxy...", end=" ")
    curl_proxy = await test_system_curl(url, proxy)
    result["tests"]["curl_with_proxy"] = curl_proxy
    _print_test_result(curl_proxy)
    
    # 5. Teste System Curl SEM Proxy
    print(f"  🖥️ [4/4] System Curl sem Proxy...", end=" ")
    curl_no_proxy = await test_system_curl(url, None)
    result["tests"]["curl_without_proxy"] = curl_no_proxy
    _print_test_result(curl_no_proxy)
    
    # Diagnóstico
    result["diagnosis"] = _diagnose_results(result["tests"])
    print(f"\n  💡 Diagnóstico: {result['diagnosis']['summary']}")
    
    return result

def _print_test_result(test: Dict[str, Any]):
    """Imprime resultado de um teste de forma concisa."""
    status = test.get("status", "?")
    conclusion = test.get("conclusion", "?")
    duration = test.get("duration", 0)
    
    if status == "ok":
        content_len = test.get("parsed_text_length", 0)
        print(f"✅ OK ({content_len} chars, {duration:.2f}s)")
        if test.get("cloudflare_detected"):
            print(f"       ⚠️ Cloudflare presente no HTML")
        if test.get("captcha_detected"):
            print(f"       ⚠️ Captcha presente no HTML")
    else:
        error = test.get("error", conclusion)[:50]
        print(f"❌ {conclusion} - {error} ({duration:.2f}s)")

def _diagnose_results(tests: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Analisa os resultados dos 4 testes e identifica a causa raiz.
    """
    diagnosis = {
        "tests_passed": 0,
        "tests_failed": 0,
        "issues": [],
        "summary": ""
    }
    
    cffi_proxy = tests.get("cffi_with_proxy", {})
    cffi_no_proxy = tests.get("cffi_without_proxy", {})
    curl_proxy = tests.get("curl_with_proxy", {})
    curl_no_proxy = tests.get("curl_without_proxy", {})
    
    # Contar sucessos/falhas
    for test in [cffi_proxy, cffi_no_proxy, curl_proxy, curl_no_proxy]:
        if test.get("status") == "ok":
            diagnosis["tests_passed"] += 1
        else:
            diagnosis["tests_failed"] += 1
    
    # Analisar padrões
    cffi_proxy_ok = cffi_proxy.get("status") == "ok"
    cffi_no_proxy_ok = cffi_no_proxy.get("status") == "ok"
    curl_proxy_ok = curl_proxy.get("status") == "ok"
    curl_no_proxy_ok = curl_no_proxy.get("status") == "ok"
    
    # CASO 1: Todos OK
    if diagnosis["tests_passed"] == 4:
        diagnosis["summary"] = "✅ SITE FUNCIONANDO - Todos os métodos OK"
        diagnosis["root_cause"] = "NONE"
        return diagnosis
    
    # CASO 2: Todos falharam
    if diagnosis["tests_failed"] == 4:
        # Verificar tipo de erro mais comum
        errors = [
            cffi_proxy.get("conclusion"),
            cffi_no_proxy.get("conclusion"),
            curl_proxy.get("conclusion"),
            curl_no_proxy.get("conclusion")
        ]
        
        if all("TIMEOUT" in str(e) for e in errors if e):
            diagnosis["summary"] = "⏱️ SITE COM TIMEOUT - Servidor muito lento ou bloqueando"
            diagnosis["root_cause"] = "SERVER_TIMEOUT"
        elif any("EMPTY" in str(e) for e in errors if e):
            diagnosis["summary"] = "📭 CONTEÚDO VAZIO - Site pode ser SPA/JS ou bloqueando"
            diagnosis["root_cause"] = "EMPTY_CONTENT_ALL"
        else:
            diagnosis["summary"] = "❌ SITE INACESSÍVEL - Todos os métodos falharam"
            diagnosis["root_cause"] = "SITE_UNREACHABLE"
        return diagnosis
    
    # CASO 3: Proxy funciona, sem proxy não
    if (cffi_proxy_ok or curl_proxy_ok) and not (cffi_no_proxy_ok or curl_no_proxy_ok):
        diagnosis["summary"] = "🔄 SITE BLOQUEIA IP DIRETO - Funciona apenas com proxy"
        diagnosis["root_cause"] = "IP_BLOCKED"
        diagnosis["issues"].append("Site bloqueia conexões diretas")
        return diagnosis
    
    # CASO 4: Sem proxy funciona, com proxy não
    if (cffi_no_proxy_ok or curl_no_proxy_ok) and not (cffi_proxy_ok or curl_proxy_ok):
        diagnosis["summary"] = "🚫 PROBLEMA NO PROXY - Funciona apenas sem proxy"
        diagnosis["root_cause"] = "PROXY_ISSUE"
        diagnosis["issues"].append("Proxy pode estar lento, bloqueado ou com problema")
        return diagnosis
    
    # CASO 5: CFFI funciona, Curl não (ou vice-versa)
    if (cffi_proxy_ok or cffi_no_proxy_ok) and not (curl_proxy_ok or curl_no_proxy_ok):
        diagnosis["summary"] = "⚙️ CURL FALHANDO - curl_cffi funciona mas system curl não"
        diagnosis["root_cause"] = "CURL_SPECIFIC"
        return diagnosis
    
    if (curl_proxy_ok or curl_no_proxy_ok) and not (cffi_proxy_ok or cffi_no_proxy_ok):
        diagnosis["summary"] = "⚙️ CFFI FALHANDO - System curl funciona mas curl_cffi não"
        diagnosis["root_cause"] = "CFFI_SPECIFIC"
        return diagnosis
    
    # CASO 6: Timeout no proxy (principal problema identificado nos logs)
    if "TIMEOUT" in str(cffi_proxy.get("conclusion")) and cffi_no_proxy_ok:
        diagnosis["summary"] = "⏱️ PROXY TIMEOUT - O timeout de 5s é muito curto para o proxy"
        diagnosis["root_cause"] = "PROXY_TIMEOUT_CONFIG"
        diagnosis["issues"].append(f"Timeout configurado: {_scraper_config['session_timeout']}s")
        return diagnosis
    
    # CASO 7: Misto
    diagnosis["summary"] = f"🔀 RESULTADO MISTO - {diagnosis['tests_passed']}/4 OK"
    diagnosis["root_cause"] = "MIXED"
    
    # Adicionar detalhes específicos
    if cffi_proxy.get("cloudflare_detected") or cffi_no_proxy.get("cloudflare_detected"):
        diagnosis["issues"].append("Cloudflare detectado")
    if cffi_proxy.get("captcha_detected") or cffi_no_proxy.get("captcha_detected"):
        diagnosis["issues"].append("Captcha detectado")
    if cffi_proxy.get("waf_detected") or cffi_no_proxy.get("waf_detected"):
        diagnosis["issues"].append("WAF/Access Denied detectado")
    
    return diagnosis

async def main():
    """Executa testes em todos os sites."""
    print("="*70)
    print("🔬 TESTE DE DIAGNÓSTICO - REPLICA EXATA DO SCRAPER")
    print("="*70)
    print(f"📅 Data: {datetime.now().isoformat()}")
    print(f"📋 Sites a testar: {len(TEST_SITES)}")
    print(f"\n⚙️ Configurações do Scraper:")
    print(f"   - session_timeout: {_scraper_config['session_timeout']}s")
    print(f"   - circuit_breaker_threshold: {_scraper_config['circuit_breaker_threshold']}")
    print(f"   - chunk_size: {_scraper_config['chunk_size']}")
    
    # Verificar proxy
    print(f"\n📡 Verificando ProxyManager...")
    proxy = await proxy_manager.get_next_proxy()
    if proxy:
        print(f"   ✅ Proxy disponível: {proxy[:30]}...")
        print(f"   Total de proxies carregados: {len(proxy_manager.proxies)}")
    else:
        print("   ⚠️ ATENÇÃO: Nenhum proxy disponível!")
        print("   Os testes serão executados mas podem não refletir o comportamento real do scraper.")
    
    results = []
    conclusions = {
        "cffi_with_proxy": {},
        "cffi_without_proxy": {},
        "curl_with_proxy": {},
        "curl_without_proxy": {},
    }
    root_causes = {}
    
    for url in TEST_SITES:
        result = await test_site_comprehensive(url)
        results.append(result)
        
        # Contabilizar conclusões por método
        for method, test in result.get("tests", {}).items():
            conclusion = test.get("conclusion", "UNKNOWN")
            if conclusion not in conclusions[method]:
                conclusions[method][conclusion] = 0
            conclusions[method][conclusion] += 1
        
        # Contabilizar causas raiz
        root_cause = result.get("diagnosis", {}).get("root_cause", "UNKNOWN")
        root_causes[root_cause] = root_causes.get(root_cause, 0) + 1
    
    # Resumo
    print("\n" + "="*70)
    print("📊 RESUMO DOS TESTES")
    print("="*70)
    
    print("\n📌 RESULTADOS POR MÉTODO:")
    for method, concs in conclusions.items():
        print(f"\n  {method}:")
        for conc, count in sorted(concs.items(), key=lambda x: x[1], reverse=True):
            icon = "✅" if conc == "SUCCESS" else "❌"
            print(f"    {icon} {conc}: {count}")
    
    print("\n📌 DIAGNÓSTICOS (CAUSAS RAIZ):")
    for cause, count in sorted(root_causes.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cause}: {count}")
    
    # Análise comparativa
    print("\n" + "="*70)
    print("🔍 ANÁLISE COMPARATIVA")
    print("="*70)
    
    cffi_proxy_success = conclusions["cffi_with_proxy"].get("SUCCESS", 0)
    cffi_no_proxy_success = conclusions["cffi_without_proxy"].get("SUCCESS", 0)
    curl_proxy_success = conclusions["curl_with_proxy"].get("SUCCESS", 0)
    curl_no_proxy_success = conclusions["curl_without_proxy"].get("SUCCESS", 0)
    
    total = len(TEST_SITES)
    print(f"""
  Método                    | Sucesso | Taxa
  --------------------------|---------|--------
  CFFI + Proxy              | {cffi_proxy_success:>5}   | {cffi_proxy_success/total*100:.1f}%
  CFFI sem Proxy            | {cffi_no_proxy_success:>5}   | {cffi_no_proxy_success/total*100:.1f}%
  System Curl + Proxy       | {curl_proxy_success:>5}   | {curl_proxy_success/total*100:.1f}%
  System Curl sem Proxy     | {curl_no_proxy_success:>5}   | {curl_no_proxy_success/total*100:.1f}%
""")
    
    # Diagnóstico final
    print("="*70)
    print("💡 CONCLUSÃO PRINCIPAL")
    print("="*70)
    
    if cffi_no_proxy_success > cffi_proxy_success:
        diff = cffi_no_proxy_success - cffi_proxy_success
        print(f"""
  🚫 PROXY É O PROBLEMA!
  
  O método CFFI sem proxy teve {diff} sucessos A MAIS que com proxy.
  
  Possíveis causas:
  1. Timeout de {_scraper_config['session_timeout']}s é muito curto para o proxy
  2. Proxy está sendo bloqueado pelos sites
  3. Proxy está com alta latência
  
  RECOMENDAÇÃO: Aumentar session_timeout para 15-25s
""")
    elif cffi_proxy_success > cffi_no_proxy_success:
        print(f"""
  ✅ PROXY AJUDANDO!
  
  O método CFFI com proxy funciona melhor que sem proxy.
  Sites podem estar bloqueando seu IP direto.
""")
    elif cffi_proxy_success == 0 and cffi_no_proxy_success == 0:
        print(f"""
  ❌ NENHUM SUCESSO COM CFFI!
  
  Isso indica problema mais grave:
  1. Sites com proteção anti-bot (Cloudflare, WAF)
  2. Sites que requerem JavaScript para renderização
  3. Headers sendo detectados como bot
""")
    else:
        print(f"""
  🔀 RESULTADO MISTO
  
  Taxa de sucesso similar com e sem proxy.
  Verifique os diagnósticos individuais para cada site.
""")
    
    # Salvar resultados
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": _scraper_config,
        "proxy_available": proxy is not None,
        "proxy_count": len(proxy_manager.proxies),
        "total_sites": len(TEST_SITES),
        "conclusions_by_method": conclusions,
        "root_causes": root_causes,
        "comparative": {
            "cffi_with_proxy_success": cffi_proxy_success,
            "cffi_without_proxy_success": cffi_no_proxy_success,
            "curl_with_proxy_success": curl_proxy_success,
            "curl_without_proxy_success": curl_no_proxy_success,
        },
        "results": results
    }
    
    with open("test_scrape/test_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultados salvos em: test_scrape/test_results.json")
    
    return output

if __name__ == "__main__":
    asyncio.run(main())
