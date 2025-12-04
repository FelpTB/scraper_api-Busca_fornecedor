#!/usr/bin/env python3
"""
Teste ULTRA DETALHADO de sites problemáticos com o scraper atualizado.
Objetivo: Coletar TODAS as métricas possíveis para análise completa.
"""

import asyncio
import json
import time
import sys
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict, Counter
from urllib.parse import urlparse

# Adicionar path do projeto
sys.path.insert(0, '/Users/waltagan/busca_fornecedo_crawl')

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

# Importar configurações do scraper
from app.services.scraper import (
    _scraper_config, 
    _DEFAULT_HEADERS,
    _is_soft_404,
    _is_cloudflare_challenge,
    _parse_html,
    domain_failures
)
from app.core.proxy import proxy_manager

# Lista de domínios que falharam (extraída do analysis_scraper_result.json)
PROBLEM_DOMAINS = [
    "www.icaiu.com.br",
    "rtrrefrigeracao.com.br",
    "www.attitudeengenharia.com",
    "www.atacadodiniz.com.br",
    "www.rwcell.com.br",
    "techmag.com.br",
    "www.jmacedoeletronica.com.br",
    "atacadistadomecanico.com.br",
    "www.rwbombas.com.br",
    "www.assistenciajwl.com.br",
    "www.ideupane.com.br",
    "tngservice.com.br",
    "politecservicos.com.br",
    "www.giganteti.com.br",
    "jblservice.com.br",
    "www.pcecells.com.br",
    "astrasolar.com.br",
    "athomengenharia.com",
    "tecservice.com.br",
    "tecepi.com",
    "tornoemaquinascnc.com.br",
    "5cengenharia.com.br",
    "www.comercialsouzaatacado.com.br",
    "www.assistecltda.com.br",
    "www.bomfrio.net",
    "atakai25.com.br",
    "www.systech.com.br",
    "www.assistenciatecnicamr.com.br",
    "clickcel.com.br",
    "smart7assistenciatatuape.com.br",
    "atom.ind.br",
    "correaserviceconserto.com.br",
    "silvergasaquecedores.com.br",
    "www.asxmetalurgia.com.br",
    "astmovelaria.com.br",
    "imatecsolucoes.com.br",
    "starflash.com.br",
    "sugarbrasil.ind.br",
    "www.cnsolution.com.br",
    "www.athonenergia.com.br",
    "atlasinspecoes.com.br",
    "www.decklab.com.br",
    "phitosdobrasil.com.br",
    "playconsert.com.br",
    "t8menergiasolar.com.br",
    "manutencel.com",
    "epcellro.com.br",
    "www.brunoglad.art.br",
    "tcbalancas.com.br",
    "www.foccusassistencia.com.br",
    "tangaraquimica.com.br",
    "construforte.eng.br",
    "vistainformatica.com.br",
    "www.tecniflora.com.br",
    "castanhaoatacadista.com.br",
    "www.masterassistenciatecnica.com.br",
    "www.camilaventura.com.br",
    "antunesti.com",
    "tecnoimp.com.br",
    "tupiatacadistapneus.com.br",
    "www.tgalogistica.com.br",
    "www.wsa-automacao.com.br",
    "balancasstefanello.com.br",
    "aidflex.com.br",
    "abcsmart.com.br",
    "www.tgservices.com.br",
    "zntechsp.com.br",
    "www.destromacro.com.br",
    "atualtecbalancas.com.br",
    "stiloseventos.com.br",
    "iservice.ltda",
    "atacadez.com.br",
    "tripletbs.com.br",
    "industrialtitan.com.br",
    "surgicol.com.br",
    "www.terratronix.com.br",
    "atalaengenharia.com.br",
    "www.brtecassistencia.com.br",
    "ahelp.com.br",
    "www.tecnomont.com.br",
    "festaoatacarejo.com.br",
    "www.mitec.com.br",
    "www.maxtec.net.br",
    "www.statseletromecanica.com.br",
    "transmac.com.br",
    "www.tempos.com.br",
    "www.realfortaleza.com.br",
    "iphonebest.com.br",
    "www.globalatacadista.com.br",
    "www.asassistenciatecnica.com",
    "www.eletrogelar.com",
    "www.wjlmotores.com.br",
    "tmkmadeiras.com.br",
    "vanteccopiadoras.com.br",
    "www.isaperfumes.com.br",
    "www.grupocelinho.com.br",
    "www.starlight.srv.br",
    "www.redeconsertamais.com.br",
    "smartcomputercenter.com.br",
    "atmartinscaldeiraria.com.br",
]


def detect_protection(html: str) -> Dict[str, bool]:
    """Detecta tipos de proteção no HTML."""
    if not html:
        return {"empty": True}
    
    html_lower = html.lower()
    
    return {
        "cloudflare": any(x in html_lower for x in [
            "cloudflare", "cf-browser-verification", "cf_chl", 
            "checking your browser", "just a moment...", "ray id:"
        ]),
        "cloudflare_challenge": _is_cloudflare_challenge(html),
        "captcha": any(x in html_lower for x in [
            "captcha", "recaptcha", "hcaptcha", "g-recaptcha",
            "challenge-form", "verificação humana"
        ]),
        "waf_block": any(x in html_lower for x in [
            "access denied", "403 forbidden", "blocked", 
            "not allowed", "security check", "firewall"
        ]),
        "bot_detection": any(x in html_lower for x in [
            "bot detected", "automated access", "suspicious activity",
            "robot", "crawler detected"
        ]),
        "rate_limit": any(x in html_lower for x in [
            "rate limit", "too many requests", "429", "slow down"
        ]),
        "maintenance": any(x in html_lower for x in [
            "maintenance", "manutenção", "em breve", "coming soon",
            "under construction"
        ]),
        "soft_404": _is_soft_404(html) if html else False,
        "empty": len(html.strip()) < 100
    }


async def test_cffi_with_proxy(url: str, proxy: str, timeout: int = 15) -> Dict:
    """Testa scrape com curl_cffi + proxy."""
    result = {
        "method": "cffi_proxy",
        "success": False,
        "status_code": None,
        "text_length": 0,
        "duration": 0,
        "error": None,
        "protection": {},
        "html_sample": ""
    }
    
    start = time.perf_counter()
    try:
        headers = _DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        async with AsyncSession(
            impersonate="chrome120",
            proxy=proxy,
            timeout=timeout,
            verify=False
        ) as session:
            resp = await session.get(url, headers=headers)
            result["status_code"] = resp.status_code
            
            if resp.status_code == 200:
                html = resp.text
                result["text_length"] = len(html)
                result["protection"] = detect_protection(html)
                result["html_sample"] = html[:500] if html else ""
                
                # Sucesso = tem conteúdo, não é challenge, não é soft 404
                if (result["text_length"] > 100 and 
                    not result["protection"].get("cloudflare_challenge") and
                    not result["protection"].get("soft_404") and
                    not result["protection"].get("empty")):
                    result["success"] = True
            else:
                result["error"] = f"HTTP_{resp.status_code}"
                
    except asyncio.TimeoutError:
        result["error"] = "TIMEOUT"
    except Exception as e:
        result["error"] = f"{type(e).__name__}"
    
    result["duration"] = round(time.perf_counter() - start, 3)
    return result


async def test_cffi_no_proxy(url: str, timeout: int = 15) -> Dict:
    """Testa scrape com curl_cffi SEM proxy."""
    result = {
        "method": "cffi_no_proxy",
        "success": False,
        "status_code": None,
        "text_length": 0,
        "duration": 0,
        "error": None,
        "protection": {},
        "html_sample": ""
    }
    
    start = time.perf_counter()
    try:
        headers = _DEFAULT_HEADERS.copy()
        headers["Referer"] = "https://www.google.com/"
        
        async with AsyncSession(
            impersonate="chrome120",
            timeout=timeout,
            verify=False
        ) as session:
            resp = await session.get(url, headers=headers)
            result["status_code"] = resp.status_code
            
            if resp.status_code == 200:
                html = resp.text
                result["text_length"] = len(html)
                result["protection"] = detect_protection(html)
                result["html_sample"] = html[:500] if html else ""
                
                if (result["text_length"] > 100 and 
                    not result["protection"].get("cloudflare_challenge") and
                    not result["protection"].get("soft_404") and
                    not result["protection"].get("empty")):
                    result["success"] = True
            else:
                result["error"] = f"HTTP_{resp.status_code}"
                
    except asyncio.TimeoutError:
        result["error"] = "TIMEOUT"
    except Exception as e:
        result["error"] = f"{type(e).__name__}"
    
    result["duration"] = round(time.perf_counter() - start, 3)
    return result


async def test_system_curl_with_proxy(url: str, proxy: str, timeout: int = 15) -> Dict:
    """Testa scrape com system curl + proxy."""
    result = {
        "method": "curl_proxy",
        "success": False,
        "status_code": None,
        "text_length": 0,
        "duration": 0,
        "error": None,
        "curl_exit_code": None,
        "protection": {},
        "html_sample": ""
    }
    
    start = time.perf_counter()
    try:
        cmd = [
            "curl", "-L", "-k", "-s", "--compressed",
            "-w", "%{http_code}",  # Imprimir status code no final
            "--max-time", str(timeout),
            "-x", proxy,
            "-H", f"User-Agent: {_DEFAULT_HEADERS['User-Agent']}",
            "-H", "Accept: text/html,application/xhtml+xml",
            "-H", "Accept-Language: pt-BR,pt;q=0.9",
            "-H", "Referer: https://www.google.com/",
            url
        ]
        
        res = await asyncio.to_thread(
            subprocess.run, cmd, 
            capture_output=True, text=True, timeout=timeout + 5
        )
        
        result["curl_exit_code"] = res.returncode
        
        if res.returncode == 0 and res.stdout:
            # Últimos 3 chars são o status code
            output = res.stdout
            if len(output) >= 3:
                try:
                    result["status_code"] = int(output[-3:])
                    html = output[:-3]
                except:
                    html = output
                    result["status_code"] = 200  # Assumir 200 se não conseguir parsear
            else:
                html = output
                result["status_code"] = 200
            
            result["text_length"] = len(html)
            result["protection"] = detect_protection(html)
            result["html_sample"] = html[:500] if html else ""
            
            if (result["text_length"] > 100 and 
                result["status_code"] == 200 and
                not result["protection"].get("cloudflare_challenge") and
                not result["protection"].get("soft_404") and
                not result["protection"].get("empty")):
                result["success"] = True
        else:
            result["error"] = f"CURL_EXIT_{res.returncode}"
            if res.stderr:
                result["error"] += f" ({res.stderr[:100]})"
                
    except asyncio.TimeoutError:
        result["error"] = "TIMEOUT"
    except subprocess.TimeoutExpired:
        result["error"] = "SUBPROCESS_TIMEOUT"
    except Exception as e:
        result["error"] = f"{type(e).__name__}"
    
    result["duration"] = round(time.perf_counter() - start, 3)
    return result


async def test_system_curl_no_proxy(url: str, timeout: int = 15) -> Dict:
    """Testa scrape com system curl SEM proxy."""
    result = {
        "method": "curl_no_proxy",
        "success": False,
        "status_code": None,
        "text_length": 0,
        "duration": 0,
        "error": None,
        "curl_exit_code": None,
        "protection": {},
        "html_sample": ""
    }
    
    start = time.perf_counter()
    try:
        cmd = [
            "curl", "-L", "-k", "-s", "--compressed",
            "-w", "%{http_code}",
            "--max-time", str(timeout),
            "-H", f"User-Agent: {_DEFAULT_HEADERS['User-Agent']}",
            "-H", "Accept: text/html,application/xhtml+xml",
            "-H", "Accept-Language: pt-BR,pt;q=0.9",
            "-H", "Referer: https://www.google.com/",
            url
        ]
        
        res = await asyncio.to_thread(
            subprocess.run, cmd, 
            capture_output=True, text=True, timeout=timeout + 5
        )
        
        result["curl_exit_code"] = res.returncode
        
        if res.returncode == 0 and res.stdout:
            output = res.stdout
            if len(output) >= 3:
                try:
                    result["status_code"] = int(output[-3:])
                    html = output[:-3]
                except:
                    html = output
                    result["status_code"] = 200
            else:
                html = output
                result["status_code"] = 200
            
            result["text_length"] = len(html)
            result["protection"] = detect_protection(html)
            result["html_sample"] = html[:500] if html else ""
            
            if (result["text_length"] > 100 and 
                result["status_code"] == 200 and
                not result["protection"].get("cloudflare_challenge") and
                not result["protection"].get("soft_404") and
                not result["protection"].get("empty")):
                result["success"] = True
        else:
            result["error"] = f"CURL_EXIT_{res.returncode}"
                
    except asyncio.TimeoutError:
        result["error"] = "TIMEOUT"
    except subprocess.TimeoutExpired:
        result["error"] = "SUBPROCESS_TIMEOUT"
    except Exception as e:
        result["error"] = f"{type(e).__name__}"
    
    result["duration"] = round(time.perf_counter() - start, 3)
    return result


async def test_site_detailed(domain: str, proxy: str) -> Dict[str, Any]:
    """Testa um site com TODOS os métodos e coleta métricas detalhadas."""
    url = f"https://{domain}"
    
    result = {
        "domain": domain,
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "proxy_used": proxy[:50] + "..." if proxy and len(proxy) > 50 else proxy,
        
        # Resultados por método
        "cffi_proxy": None,
        "cffi_no_proxy": None,
        "curl_proxy": None,
        "curl_no_proxy": None,
        
        # Métricas consolidadas
        "best_method": None,
        "any_success": False,
        "all_failed": True,
        "protection_detected": [],
        "status_codes": [],
        "errors": [],
        
        # Performance
        "total_duration": 0
    }
    
    start = time.perf_counter()
    
    # Executar todos os testes em paralelo
    tests = await asyncio.gather(
        test_cffi_with_proxy(url, proxy),
        test_cffi_no_proxy(url),
        test_system_curl_with_proxy(url, proxy),
        test_system_curl_no_proxy(url),
        return_exceptions=True
    )
    
    methods = ["cffi_proxy", "cffi_no_proxy", "curl_proxy", "curl_no_proxy"]
    
    for method, test_result in zip(methods, tests):
        if isinstance(test_result, Exception):
            result[method] = {"success": False, "error": str(test_result)}
        else:
            result[method] = test_result
            
            # Coletar métricas
            if test_result.get("success"):
                result["any_success"] = True
                result["all_failed"] = False
                if not result["best_method"]:
                    result["best_method"] = method
            
            if test_result.get("status_code"):
                result["status_codes"].append(test_result["status_code"])
            
            if test_result.get("error"):
                result["errors"].append(f"{method}: {test_result['error']}")
            
            # Coletar proteções detectadas
            protection = test_result.get("protection", {})
            for prot, detected in protection.items():
                if detected and prot not in result["protection_detected"]:
                    result["protection_detected"].append(prot)
    
    result["total_duration"] = round(time.perf_counter() - start, 3)
    
    return result


async def main():
    print("=" * 100)
    print("🔬 TESTE ULTRA DETALHADO DE SITES PROBLEMÁTICOS")
    print("=" * 100)
    print(f"📅 Data: {datetime.now().isoformat()}")
    print()
    
    # Configuração
    print("⚙️ CONFIGURAÇÃO DO SCRAPER:")
    print(f"   session_timeout: {_scraper_config['session_timeout']}s")
    print(f"   circuit_breaker_threshold: {_scraper_config['circuit_breaker_threshold']}")
    print(f"   chunk_size: {_scraper_config['chunk_size']}")
    print()
    
    # Verificar proxy
    print("📡 VERIFICANDO PROXY...")
    proxy = await proxy_manager.get_next_proxy()
    if proxy:
        print(f"   ✅ Proxy disponível: {proxy[:50]}...")
    else:
        print("   ⚠️ Nenhum proxy disponível!")
        proxy = None
    print()
    
    # Limpar circuit breaker
    domain_failures.clear()
    
    # Sites a testar
    sites = PROBLEM_DOMAINS[:100]
    print(f"📊 Sites a testar: {len(sites)}")
    print()
    
    # Contadores globais
    stats = {
        "total": len(sites),
        "any_success": 0,
        "all_failed": 0,
        
        # Por método
        "cffi_proxy_success": 0,
        "cffi_proxy_fail": 0,
        "cffi_no_proxy_success": 0,
        "cffi_no_proxy_fail": 0,
        "curl_proxy_success": 0,
        "curl_proxy_fail": 0,
        "curl_no_proxy_success": 0,
        "curl_no_proxy_fail": 0,
        
        # Proteções
        "cloudflare_detected": 0,
        "cloudflare_challenge": 0,
        "captcha_detected": 0,
        "waf_block": 0,
        "soft_404": 0,
        "empty_content": 0,
        "rate_limit": 0,
        
        # Erros
        "timeout_errors": 0,
        "connection_errors": 0,
        "http_errors": Counter(),
        "curl_exit_codes": Counter(),
        
        # Best method distribution
        "best_method_dist": Counter()
    }
    
    results = []
    
    # Processar em batches
    batch_size = 5  # Menor para não sobrecarregar
    
    for i in range(0, len(sites), batch_size):
        batch = sites[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(sites) + batch_size - 1) // batch_size
        
        print(f"\n{'='*100}")
        print(f"📦 BATCH {batch_num}/{total_batches} ({len(batch)} sites)")
        print("=" * 100)
        
        # Processar batch
        for domain in batch:
            # Obter novo proxy para cada site
            current_proxy = await proxy_manager.get_next_proxy() if proxy else None
            
            print(f"\n🔍 Testando: {domain}")
            result = await test_site_detailed(domain, current_proxy)
            results.append(result)
            
            # Atualizar estatísticas
            if result["any_success"]:
                stats["any_success"] += 1
            else:
                stats["all_failed"] += 1
            
            # Por método
            for method in ["cffi_proxy", "cffi_no_proxy", "curl_proxy", "curl_no_proxy"]:
                method_result = result.get(method, {})
                if method_result.get("success"):
                    stats[f"{method}_success"] += 1
                else:
                    stats[f"{method}_fail"] += 1
                
                # Contar erros
                if method_result.get("error"):
                    if "TIMEOUT" in str(method_result.get("error", "")):
                        stats["timeout_errors"] += 1
                    if "Connection" in str(method_result.get("error", "")):
                        stats["connection_errors"] += 1
                
                # HTTP status codes
                if method_result.get("status_code") and method_result["status_code"] != 200:
                    stats["http_errors"][method_result["status_code"]] += 1
                
                # Curl exit codes
                if method_result.get("curl_exit_code") and method_result["curl_exit_code"] != 0:
                    stats["curl_exit_codes"][method_result["curl_exit_code"]] += 1
            
            # Proteções
            for prot in result.get("protection_detected", []):
                if prot == "cloudflare":
                    stats["cloudflare_detected"] += 1
                elif prot == "cloudflare_challenge":
                    stats["cloudflare_challenge"] += 1
                elif prot == "captcha":
                    stats["captcha_detected"] += 1
                elif prot == "waf_block":
                    stats["waf_block"] += 1
                elif prot == "soft_404":
                    stats["soft_404"] += 1
                elif prot == "empty":
                    stats["empty_content"] += 1
                elif prot == "rate_limit":
                    stats["rate_limit"] += 1
            
            # Best method
            if result.get("best_method"):
                stats["best_method_dist"][result["best_method"]] += 1
            
            # Imprimir resultado resumido
            status = "✅" if result["any_success"] else "❌"
            best = result.get("best_method", "NENHUM")
            prots = ", ".join(result.get("protection_detected", [])) or "Nenhuma"
            
            print(f"   {status} Sucesso: {result['any_success']}")
            print(f"      Melhor método: {best}")
            print(f"      Proteções: {prots}")
            
            # Detalhes por método
            for method in ["cffi_proxy", "cffi_no_proxy", "curl_proxy", "curl_no_proxy"]:
                m = result.get(method, {})
                s = "✅" if m.get("success") else "❌"
                dur = m.get("duration", 0) or 0
                txt = m.get("text_length", 0) or 0
                err = m.get("error", "") or ""
                sc = str(m.get("status_code", "-") or "-")
                
                print(f"      {method:20} | {s} | {sc:>3} | {txt:>6} chars | {dur:.2f}s | {err}")
    
    # ========================================================================
    # RELATÓRIO FINAL ULTRA DETALHADO
    # ========================================================================
    
    print("\n")
    print("=" * 100)
    print("📊 RELATÓRIO FINAL ULTRA DETALHADO")
    print("=" * 100)
    
    # 1. RESUMO GERAL
    print("\n" + "─" * 100)
    print("📈 1. RESUMO GERAL")
    print("─" * 100)
    success_rate = (stats["any_success"] / stats["total"]) * 100
    print(f"""
    Total de sites testados:     {stats['total']}
    ✅ Pelo menos 1 método OK:   {stats['any_success']} ({success_rate:.1f}%)
    ❌ Todos métodos falharam:   {stats['all_failed']} ({100-success_rate:.1f}%)
    """)
    
    # 2. SUCESSO POR MÉTODO
    print("\n" + "─" * 100)
    print("🔧 2. SUCESSO POR MÉTODO DE SCRAPE")
    print("─" * 100)
    print("""
    ┌─────────────────────────┬──────────┬──────────┬──────────────┐
    │ Método                  │ Sucesso  │ Falha    │ Taxa Sucesso │
    ├─────────────────────────┼──────────┼──────────┼──────────────┤""")
    
    methods_data = [
        ("curl_cffi + Proxy", stats["cffi_proxy_success"], stats["cffi_proxy_fail"]),
        ("curl_cffi sem Proxy", stats["cffi_no_proxy_success"], stats["cffi_no_proxy_fail"]),
        ("System Curl + Proxy", stats["curl_proxy_success"], stats["curl_proxy_fail"]),
        ("System Curl sem Proxy", stats["curl_no_proxy_success"], stats["curl_no_proxy_fail"]),
    ]
    
    for name, success, fail in methods_data:
        total = success + fail
        rate = (success / total * 100) if total > 0 else 0
        print(f"    │ {name:<23} │ {success:>8} │ {fail:>8} │ {rate:>10.1f}% │")
    
    print("    └─────────────────────────┴──────────┴──────────┴──────────────┘")
    
    # 3. MELHOR MÉTODO POR SITE
    print("\n" + "─" * 100)
    print("🏆 3. DISTRIBUIÇÃO DE MELHOR MÉTODO (quando sucesso)")
    print("─" * 100)
    if stats["best_method_dist"]:
        for method, count in stats["best_method_dist"].most_common():
            pct = (count / stats["any_success"] * 100) if stats["any_success"] > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"    {method:<20} │ {count:>4} ({pct:>5.1f}%) │ {bar}")
    else:
        print("    Nenhum método teve sucesso")
    
    # 4. PROTEÇÕES DETECTADAS
    print("\n" + "─" * 100)
    print("🛡️ 4. PROTEÇÕES ANTI-BOT DETECTADAS")
    print("─" * 100)
    print(f"""
    ┌────────────────────────────┬──────────┬─────────────┐
    │ Tipo de Proteção           │ Sites    │ % do Total  │
    ├────────────────────────────┼──────────┼─────────────┤
    │ 🔒 Cloudflare (qualquer)   │ {stats['cloudflare_detected']:>8} │ {stats['cloudflare_detected']/stats['total']*100:>9.1f}%  │
    │ 🔐 Cloudflare Challenge    │ {stats['cloudflare_challenge']:>8} │ {stats['cloudflare_challenge']/stats['total']*100:>9.1f}%  │
    │ 🤖 CAPTCHA                 │ {stats['captcha_detected']:>8} │ {stats['captcha_detected']/stats['total']*100:>9.1f}%  │
    │ 🚫 WAF/Access Denied       │ {stats['waf_block']:>8} │ {stats['waf_block']/stats['total']*100:>9.1f}%  │
    │ 📭 Conteúdo Vazio          │ {stats['empty_content']:>8} │ {stats['empty_content']/stats['total']*100:>9.1f}%  │
    │ 🔍 Soft 404                │ {stats['soft_404']:>8} │ {stats['soft_404']/stats['total']*100:>9.1f}%  │
    │ ⏱️ Rate Limit              │ {stats['rate_limit']:>8} │ {stats['rate_limit']/stats['total']*100:>9.1f}%  │
    └────────────────────────────┴──────────┴─────────────┘
    """)
    
    # 5. ERROS HTTP
    print("\n" + "─" * 100)
    print("🌐 5. ERROS HTTP POR STATUS CODE")
    print("─" * 100)
    if stats["http_errors"]:
        print("    ┌─────────────┬──────────┐")
        print("    │ Status Code │ Contagem │")
        print("    ├─────────────┼──────────┤")
        for code, count in stats["http_errors"].most_common(10):
            print(f"    │ HTTP {code:<6} │ {count:>8} │")
        print("    └─────────────┴──────────┘")
    else:
        print("    Nenhum erro HTTP diferente de 200")
    
    # 6. ERROS CURL (exit codes)
    print("\n" + "─" * 100)
    print("💻 6. ERROS DO SYSTEM CURL (EXIT CODES)")
    print("─" * 100)
    curl_errors_desc = {
        6: "Could not resolve host",
        7: "Failed to connect",
        28: "Operation timeout",
        35: "SSL connect error",
        52: "Empty reply from server",
        56: "Recv failure (HTTP/2 error)",
        60: "SSL certificate problem"
    }
    if stats["curl_exit_codes"]:
        print("    ┌─────────────┬──────────┬─────────────────────────────┐")
        print("    │ Exit Code   │ Contagem │ Descrição                   │")
        print("    ├─────────────┼──────────┼─────────────────────────────┤")
        for code, count in stats["curl_exit_codes"].most_common():
            desc = curl_errors_desc.get(code, "Unknown error")
            print(f"    │ {code:>11} │ {count:>8} │ {desc:<27} │")
        print("    └─────────────┴──────────┴─────────────────────────────┘")
    else:
        print("    Nenhum erro de curl reportado")
    
    # 7. TIMEOUTS E CONEXÃO
    print("\n" + "─" * 100)
    print("⏱️ 7. PROBLEMAS DE CONECTIVIDADE")
    print("─" * 100)
    print(f"""
    Timeouts:              {stats['timeout_errors']}
    Erros de conexão:      {stats['connection_errors']}
    """)
    
    # 8. COMPARAÇÃO curl_cffi vs System Curl
    print("\n" + "─" * 100)
    print("⚔️ 8. COMPARAÇÃO: curl_cffi vs System Curl")
    print("─" * 100)
    
    cffi_total = stats["cffi_proxy_success"] + stats["cffi_no_proxy_success"]
    curl_total = stats["curl_proxy_success"] + stats["curl_no_proxy_success"]
    
    cffi_rate = cffi_total / (stats["total"] * 2) * 100  # *2 porque são 2 testes
    curl_rate = curl_total / (stats["total"] * 2) * 100
    
    print(f"""
    ┌────────────────────┬──────────────┬──────────────┐
    │ Biblioteca         │ Sucessos     │ Taxa         │
    ├────────────────────┼──────────────┼──────────────┤
    │ curl_cffi          │ {cffi_total:>12} │ {cffi_rate:>10.1f}% │
    │ System Curl        │ {curl_total:>12} │ {curl_rate:>10.1f}% │
    └────────────────────┴──────────────┴──────────────┘
    
    {"🏆 curl_cffi é SUPERIOR!" if cffi_total > curl_total else "🏆 System Curl é SUPERIOR!" if curl_total > cffi_total else "⚖️ Empate!"}
    Diferença: {abs(cffi_total - curl_total)} sites
    """)
    
    # 9. IMPACTO DO PROXY
    print("\n" + "─" * 100)
    print("🔄 9. IMPACTO DO PROXY NOS RESULTADOS")
    print("─" * 100)
    
    with_proxy = stats["cffi_proxy_success"] + stats["curl_proxy_success"]
    without_proxy = stats["cffi_no_proxy_success"] + stats["curl_no_proxy_success"]
    
    print(f"""
    ┌────────────────────┬──────────────┬──────────────┐
    │ Modo               │ Sucessos     │ Taxa         │
    ├────────────────────┼──────────────┼──────────────┤
    │ COM Proxy          │ {with_proxy:>12} │ {with_proxy/(stats['total']*2)*100:>10.1f}% │
    │ SEM Proxy          │ {without_proxy:>12} │ {without_proxy/(stats['total']*2)*100:>10.1f}% │
    └────────────────────┴──────────────┴──────────────┘
    
    {"🔄 Proxy AJUDA!" if with_proxy > without_proxy else "⚡ Sem Proxy é MELHOR!" if without_proxy > with_proxy else "⚖️ Sem diferença!"}
    """)
    
    # 10. SITES QUE FALHARAM COMPLETAMENTE
    print("\n" + "─" * 100)
    print("❌ 10. SITES QUE FALHARAM EM TODOS OS MÉTODOS")
    print("─" * 100)
    
    failed_sites = [r for r in results if not r.get("any_success")]
    if failed_sites:
        print(f"    Total: {len(failed_sites)} sites\n")
        for r in failed_sites[:20]:
            prots = ", ".join(r.get("protection_detected", [])) or "N/A"
            errors = "; ".join(r.get("errors", [])[:2]) or "N/A"
            print(f"    • {r['domain']}")
            print(f"      Proteções: {prots}")
            print(f"      Erros: {errors[:80]}...")
            print()
    else:
        print("    🎉 Nenhum site falhou completamente!")
    
    # 11. CONCLUSÕES
    print("\n" + "─" * 100)
    print("💡 11. CONCLUSÕES E RECOMENDAÇÕES")
    print("─" * 100)
    print(f"""
    DESCOBERTAS PRINCIPAIS:
    ─────────────────────────
    
    1. TAXA DE SUCESSO GERAL: {success_rate:.1f}%
       {"✅ EXCELENTE!" if success_rate >= 90 else "⚠️ PRECISA MELHORAR" if success_rate >= 70 else "❌ CRÍTICO!"}
    
    2. CLOUDFLARE:
       - {stats['cloudflare_detected']} sites têm Cloudflare ({stats['cloudflare_detected']/stats['total']*100:.1f}%)
       - {stats['cloudflare_challenge']} requerem challenge ({stats['cloudflare_challenge']/stats['total']*100:.1f}%)
       {"⚠️ Cloudflare é um problema significativo!" if stats['cloudflare_detected'] > stats['total'] * 0.2 else "✅ Cloudflare não é grande problema"}
    
    3. MELHOR ABORDAGEM:
       - curl_cffi: {cffi_rate:.1f}% sucesso
       - System Curl: {curl_rate:.1f}% sucesso
       {"→ Recomendação: Priorizar curl_cffi" if cffi_rate > curl_rate else "→ Recomendação: Priorizar System Curl"}
    
    4. PROXY:
       - Com proxy: {with_proxy/(stats['total']*2)*100:.1f}% sucesso
       - Sem proxy: {without_proxy/(stats['total']*2)*100:.1f}% sucesso
       {"→ Proxy está ajudando" if with_proxy > without_proxy else "→ Proxy não está fazendo diferença ou atrapalhando"}
    
    5. PROBLEMAS CRÍTICOS:
       - Timeouts: {stats['timeout_errors']}
       - HTTP/2 errors (curl 56): {stats['curl_exit_codes'].get(56, 0)}
       - Sites completamente inacessíveis: {len(failed_sites)}
    """)
    
    # Salvar resultados
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": dict(_scraper_config),
        "stats": {
            **stats,
            "http_errors": dict(stats["http_errors"]),
            "curl_exit_codes": dict(stats["curl_exit_codes"]),
            "best_method_dist": dict(stats["best_method_dist"])
        },
        "results": results
    }
    
    output_file = "test_scrape/test_100_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n💾 Resultados detalhados salvos em: {output_file}")
    print("=" * 100)

if __name__ == "__main__":
    asyncio.run(main())
