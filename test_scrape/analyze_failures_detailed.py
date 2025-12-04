#!/usr/bin/env python3
"""
Análise DETALHADA de falhas do scraper.
Objetivo: Identificar os MOTIVOS ESPECÍFICOS das falhas de conexão.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse

def extract_error_details(msg: str) -> dict:
    """Extrai detalhes do erro da mensagem"""
    details = {
        'type': 'unknown',
        'status_code': None,
        'error_msg': None,
        'url': None
    }
    
    # Extrair URL
    url_patterns = [
        r'url=(\S+)',
        r'em (\S+)',
        r'(?:https?://\S+)',
    ]
    for pattern in url_patterns:
        match = re.search(pattern, msg)
        if match:
            details['url'] = match.group(1) if '(' not in pattern else match.group(0)
            break
    
    # Extrair Status Code
    status_match = re.search(r'Status (\d{3})', msg)
    if status_match:
        details['status_code'] = int(status_match.group(1))
        details['type'] = 'http_error'
    
    # Identificar tipo de erro
    error_patterns = {
        'timeout': ['timeout', 'timed out', 'TimeoutError'],
        'connection_refused': ['connection refused', 'ConnectionRefusedError'],
        'connection_reset': ['connection reset', 'ConnectionResetError'],
        'dns_error': ['name resolution', 'getaddrinfo', 'DNS', 'Temporary failure'],
        'ssl_error': ['SSL', 'certificate', 'CERTIFICATE_VERIFY'],
        'proxy_error': ['proxy', 'ProxyError'],
        'soft_404': ['Soft 404', 'soft 404'],
        'empty_content': ['Conteúdo insuficiente', 'empty content', 'Empty'],
        'curl_failed': ['Curl Failed', 'curl failed'],
        'http_403': ['403', 'Forbidden'],
        'http_404': ['404', 'Not Found'],
        'http_500': ['500', 'Internal Server Error'],
        'http_502': ['502', 'Bad Gateway'],
        'http_503': ['503', 'Service Unavailable'],
    }
    
    msg_lower = msg.lower()
    for error_type, patterns in error_patterns.items():
        if any(p.lower() in msg_lower for p in patterns):
            details['type'] = error_type
            break
    
    # Extrair mensagem de erro completa
    error_match = re.search(r'error[=:]?\s*(\S+)', msg, re.IGNORECASE)
    if error_match:
        details['error_msg'] = error_match.group(1)
    
    return details

def analyze_failures_detailed(file_path: str, output_dir: str = 'test_scrape'):
    """Análise detalhada das falhas do scraper"""
    
    print("=" * 100)
    print("🔍 ANÁLISE DETALHADA DE FALHAS - SCRAPER")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # Estruturas para análise
    errors_by_type = defaultdict(list)
    errors_by_domain = defaultdict(list)
    errors_by_step = defaultdict(list)
    status_codes = Counter()
    cffi_errors = []
    curl_errors = []
    circuit_breaker_triggers = []
    failed_domains_detail = defaultdict(lambda: {
        'cffi_failures': 0,
        'curl_failures': 0,
        'status_codes': [],
        'error_types': [],
        'sample_urls': []
    })
    
    # Processar logs
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # ===== IDENTIFICAR FALHAS CFFI =====
        if 'CFFI' in msg and ('Erro' in msg or 'falhou' in msg or '❌' in msg):
            details = extract_error_details(msg)
            cffi_errors.append({
                'message': msg[:200],
                'timestamp': timestamp,
                **details
            })
            
            if details['url']:
                try:
                    domain = urlparse(details['url']).netloc
                    failed_domains_detail[domain]['cffi_failures'] += 1
                    if details['status_code']:
                        failed_domains_detail[domain]['status_codes'].append(details['status_code'])
                    failed_domains_detail[domain]['error_types'].append(details['type'])
                    if len(failed_domains_detail[domain]['sample_urls']) < 5:
                        failed_domains_detail[domain]['sample_urls'].append(details['url'])
                except:
                    pass
            
            if details['status_code']:
                status_codes[details['status_code']] += 1
            errors_by_type[details['type']].append(msg[:200])
        
        # ===== IDENTIFICAR FALHAS CURL =====
        if 'Curl' in msg and ('Erro' in msg or 'falhou' in msg or '❌' in msg or 'Failed' in msg):
            details = extract_error_details(msg)
            curl_errors.append({
                'message': msg[:200],
                'timestamp': timestamp,
                **details
            })
            
            if details['url']:
                try:
                    domain = urlparse(details['url']).netloc
                    failed_domains_detail[domain]['curl_failures'] += 1
                    if details['status_code']:
                        failed_domains_detail[domain]['status_codes'].append(details['status_code'])
                    failed_domains_detail[domain]['error_types'].append(details['type'])
                    if len(failed_domains_detail[domain]['sample_urls']) < 5:
                        failed_domains_detail[domain]['sample_urls'].append(details['url'])
                except:
                    pass
            
            if details['status_code']:
                status_codes[details['status_code']] += 1
            errors_by_type[details['type']].append(msg[:200])
        
        # ===== CIRCUIT BREAKER =====
        if 'CIRCUIT BREAKER ABERTO' in msg:
            match = re.search(r'ABERTO para (\S+) após (\d+) falhas', msg)
            if match:
                circuit_breaker_triggers.append({
                    'domain': match.group(1),
                    'failures': int(match.group(2)),
                    'timestamp': timestamp
                })
        
        # ===== ERROS POR STEP =====
        if '[Main]' in msg and ('Falha' in msg or 'falhou' in msg or '❌' in msg):
            errors_by_step['main_page'].append(msg[:200])
        
        if '[Sub]' in msg and ('Falha' in msg or '❌' in msg):
            errors_by_step['subpage'].append(msg[:200])
        
        if '[Chunk]' in msg and 'Erro' in msg:
            errors_by_step['chunk'].append(msg[:200])
        
        # ===== STATUS CODES ESPECÍFICOS =====
        status_match = re.search(r'Status (\d{3})', msg)
        if status_match:
            status_codes[int(status_match.group(1))] += 1
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO DE ERROS POR TIPO")
    print("=" * 100)
    
    error_type_counts = {k: len(v) for k, v in errors_by_type.items()}
    for error_type, count in sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {error_type:30s} {count:5d}")
        # Mostrar exemplo
        if errors_by_type[error_type]:
            print(f"      Exemplo: {errors_by_type[error_type][0][:100]}...")
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO DE STATUS CODES HTTP")
    print("=" * 100)
    
    for status, count in status_codes.most_common(20):
        status_desc = {
            200: "OK",
            301: "Moved Permanently",
            302: "Found (Redirect)",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            408: "Request Timeout",
            429: "Too Many Requests",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout",
            520: "CloudFlare Error",
            521: "CloudFlare Origin Down",
            522: "CloudFlare Connection Timeout",
            523: "CloudFlare Unreachable",
            524: "CloudFlare A Timeout",
            525: "CloudFlare SSL Handshake Failed",
            526: "CloudFlare Invalid SSL",
        }.get(status, "Unknown")
        print(f"  HTTP {status} ({status_desc:30s}): {count:5d}")
    
    print("\n" + "=" * 100)
    print("📊 ERROS POR ETAPA DO SCRAPER")
    print("=" * 100)
    
    for step, errors in errors_by_step.items():
        print(f"  {step:20s}: {len(errors):5d} erros")
    
    print("\n" + "=" * 100)
    print("📊 TOP 30 DOMÍNIOS COM MAIS FALHAS")
    print("=" * 100)
    
    # Ordenar por total de falhas
    domains_sorted = sorted(
        failed_domains_detail.items(),
        key=lambda x: x[1]['cffi_failures'] + x[1]['curl_failures'],
        reverse=True
    )[:30]
    
    for domain, info in domains_sorted:
        total = info['cffi_failures'] + info['curl_failures']
        print(f"\n  🌐 {domain}")
        print(f"      Total falhas: {total} (CFFI: {info['cffi_failures']}, Curl: {info['curl_failures']})")
        if info['status_codes']:
            unique_codes = list(set(info['status_codes']))
            print(f"      Status codes: {unique_codes}")
        if info['error_types']:
            unique_types = list(set(info['error_types']))[:5]
            print(f"      Tipos de erro: {unique_types}")
    
    print("\n" + "=" * 100)
    print("📊 CIRCUIT BREAKERS ATIVADOS")
    print("=" * 100)
    print(f"  Total: {len(circuit_breaker_triggers)}")
    
    # Agrupar por domínio
    cb_by_domain = defaultdict(int)
    for trigger in circuit_breaker_triggers:
        cb_by_domain[trigger['domain']] += 1
    
    print("\n  Domínios bloqueados (top 20):")
    for domain, count in sorted(cb_by_domain.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"    - {domain}: {count}x")
    
    print("\n" + "=" * 100)
    print("📊 RESUMO DE CFFI vs CURL")
    print("=" * 100)
    print(f"  Erros CFFI: {len(cffi_errors)}")
    print(f"  Erros Curl: {len(curl_errors)}")
    
    # ========================================
    # ANÁLISE DE CAUSAS RAIZ
    # ========================================
    
    print("\n" + "=" * 100)
    print("🔍 ANÁLISE DE CAUSAS RAIZ")
    print("=" * 100)
    
    causes = {
        'timeout': 0,
        'connection_refused': 0,
        'dns_error': 0,
        'ssl_error': 0,
        'http_403_waf': 0,
        'http_404': 0,
        'http_5xx': 0,
        'empty_content': 0,
        'cloudflare': 0,
        'proxy_error': 0,
        'other': 0
    }
    
    for error_type, count in error_type_counts.items():
        if 'timeout' in error_type:
            causes['timeout'] += count
        elif 'connection_refused' in error_type or 'connection_reset' in error_type:
            causes['connection_refused'] += count
        elif 'dns' in error_type:
            causes['dns_error'] += count
        elif 'ssl' in error_type:
            causes['ssl_error'] += count
        elif '403' in error_type:
            causes['http_403_waf'] += count
        elif '404' in error_type or 'soft_404' in error_type:
            causes['http_404'] += count
        elif '5' in error_type and 'http' in error_type:
            causes['http_5xx'] += count
        elif 'empty' in error_type:
            causes['empty_content'] += count
        elif 'proxy' in error_type:
            causes['proxy_error'] += count
        else:
            causes['other'] += count
    
    # Ajustar para CloudFlare (status codes 520-526)
    for status in [520, 521, 522, 523, 524, 525, 526]:
        if status in status_codes:
            causes['cloudflare'] += status_codes[status]
    
    print("\n  📌 CAUSAS IDENTIFICADAS:")
    for cause, count in sorted(causes.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            icon = {
                'timeout': '⏱️',
                'connection_refused': '🚫',
                'dns_error': '🌐',
                'ssl_error': '🔒',
                'http_403_waf': '🛡️',
                'http_404': '❓',
                'http_5xx': '💥',
                'empty_content': '📭',
                'cloudflare': '☁️',
                'proxy_error': '🔄',
                'other': '❔'
            }.get(cause, '•')
            print(f"    {icon} {cause:25s}: {count:5d}")
    
    # ========================================
    # SALVAR RESULTADOS
    # ========================================
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'log_file': file_path,
        'summary': {
            'total_cffi_errors': len(cffi_errors),
            'total_curl_errors': len(curl_errors),
            'total_circuit_breakers': len(circuit_breaker_triggers),
            'unique_failed_domains': len(failed_domains_detail),
        },
        'errors_by_type': error_type_counts,
        'status_codes': dict(status_codes),
        'errors_by_step': {k: len(v) for k, v in errors_by_step.items()},
        'causes_analysis': causes,
        'top_failed_domains': [
            {
                'domain': domain,
                'total_failures': info['cffi_failures'] + info['curl_failures'],
                'cffi_failures': info['cffi_failures'],
                'curl_failures': info['curl_failures'],
                'status_codes': list(set(info['status_codes'])),
                'error_types': list(set(info['error_types']))[:5],
                'sample_urls': info['sample_urls']
            }
            for domain, info in domains_sorted
        ],
        'circuit_breaker_domains': list(cb_by_domain.keys()),
        'sample_cffi_errors': cffi_errors[:50],
        'sample_curl_errors': curl_errors[:50],
    }
    
    output_file = f'{output_dir}/analysis_failures_detailed.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    # ========================================
    # GERAR LISTA DE SITES PARA TESTE
    # ========================================
    
    # Sites para testar manualmente
    test_sites = []
    for domain, info in domains_sorted[:20]:
        if info['sample_urls']:
            test_sites.append({
                'domain': domain,
                'url': info['sample_urls'][0],
                'error_types': list(set(info['error_types']))[:3],
                'status_codes': list(set(info['status_codes']))[:3]
            })
    
    test_file = f'{output_dir}/sites_to_test.json'
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_sites, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Lista de sites para teste salva em: {test_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "log_api_v2.json"
    analyze_failures_detailed(file_path)

