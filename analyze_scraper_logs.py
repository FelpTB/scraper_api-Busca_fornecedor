#!/usr/bin/env python3
"""
Análise de logs do processo de scraping.
Objetivo: Identificar por que alguns sites não estão sendo scrapados corretamente.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_scraper_logs(file_path: str):
    """Analisa logs do scraper para identificar falhas"""
    
    print("=" * 100)
    print("🕷️  ANÁLISE DE LOGS - SCRAPER")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # ========================================
    # CONTADORES
    # ========================================
    
    stats = {
        # Main Page
        'main_processing': 0,
        'main_success': 0,
        'main_fail_cffi': 0,
        'main_fail_curl': 0,
        'main_soft_404': 0,
        'main_variation_tried': 0,
        'main_fatal': 0,
        
        # Subpages
        'subpages_requested': 0,
        'subpages_success': 0,
        'subpages_fail_cffi': 0,
        'subpages_fail_curl': 0,
        'subpages_soft_404': 0,
        
        # LLM Link Selection
        'llm_link_selection': 0,
        'links_found': 0,
        'links_filtered': 0,
        'links_selected': 0,
        
        # Circuit Breaker
        'circuit_breaker_opened': 0,
        'circuit_breaker_skipped': 0,
        
        # Semaphore
        'site_semaphore_waiting': 0,
        
        # Performance
        'total_scrapes': 0,
    }
    
    # URLs com problemas
    failed_urls = []
    soft_404_urls = []
    circuit_breaker_domains = []
    
    # Performance por URL
    performance_data = []
    
    # ========================================
    # PROCESSAR LOGS
    # ========================================
    
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # === MAIN PAGE ===
        if '[Scraper] Processing Main:' in msg:
            stats['main_processing'] += 1
            # Extrair URL
            match = re.search(r'Processing Main: (.+)$', msg)
            if match:
                url = match.group(1)
        
        if '[Main] Curl Impersonation falhou' in msg:
            stats['main_fail_cffi'] += 1
            if 'Soft 404' in msg:
                stats['main_soft_404'] += 1
                match = re.search(r'em (.+?)\. Tentando', msg)
                if match:
                    soft_404_urls.append(match.group(1))
        
        if '[Main] Soft 404 detectado em' in msg:
            stats['main_soft_404'] += 1
            match = re.search(r'detectado em (.+?)\.', msg)
            if match:
                soft_404_urls.append(match.group(1))
        
        if '[Main] Falha em' in msg and 'Tentando variação' in msg:
            stats['main_variation_tried'] += 1
        
        if '[Main] Falha fatal' in msg:
            stats['main_fatal'] += 1
            match = re.search(r'home (.+?): (.+)$', msg)
            if match:
                failed_urls.append({
                    'url': match.group(1),
                    'error': match.group(2)[:100],
                    'type': 'main_fatal'
                })
        
        # === SUBPAGES ===
        if '[Scraper] Processing' in msg and 'subpages' in msg:
            match = re.search(r'Processing (\d+) subpages', msg)
            if match:
                stats['subpages_requested'] += int(match.group(1))
        
        if '[Sub] ✅ Success' in msg:
            stats['subpages_success'] += 1
        
        if '[Sub] ⚠️ Falha' in msg or '[Sub] ❌' in msg:
            if 'CFFI' in msg:
                stats['subpages_fail_cffi'] += 1
            if 'Curl' in msg:
                stats['subpages_fail_curl'] += 1
            if 'Soft 404' in msg or '404' in msg:
                stats['subpages_soft_404'] += 1
        
        # === LLM LINK SELECTION ===
        if 'Encontrados' in msg and 'links' in msg and 'LLM' in msg:
            stats['llm_link_selection'] += 1
            match = re.search(r'Encontrados (\d+) links', msg)
            if match:
                stats['links_found'] += int(match.group(1))
        
        if 'Filtrados' in msg and 'links não-HTML' in msg:
            match = re.search(r'Filtrados (\d+) links', msg)
            if match:
                stats['links_filtered'] += int(match.group(1))
        
        if 'LLM selecionou' in msg:
            match = re.search(r'selecionou (\d+) de (\d+)', msg)
            if match:
                stats['links_selected'] += int(match.group(1))
        
        # === CIRCUIT BREAKER ===
        if 'CIRCUIT BREAKER ABERTO' in msg:
            stats['circuit_breaker_opened'] += 1
            match = re.search(r'ABERTO para (.+?) após', msg)
            if match:
                circuit_breaker_domains.append(match.group(1))
        
        if 'CircuitBreaker' in msg and 'Pulou' in msg:
            match = re.search(r'Pulou (\d+) URLs', msg)
            if match:
                stats['circuit_breaker_skipped'] += int(match.group(1))
        
        # === SEMAPHORE ===
        if '[Scraper] Site semaphore full' in msg:
            stats['site_semaphore_waiting'] += 1
        
        # === PERFORMANCE ===
        if '[PERF] scraper step=total' in msg:
            stats['total_scrapes'] += 1
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s pages=(\d+)', msg)
            if match:
                performance_data.append({
                    'url': match.group(1),
                    'duration': float(match.group(2)),
                    'pages': int(match.group(3))
                })
        
        if '[PERF] scraper step=main_page' in msg:
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s pages=(\d+) pdfs=(\d+) links=(\d+)', msg)
            if match:
                pass  # Já capturado no total
        
        if '[PERF] scraper step=subpages' in msg:
            match = re.search(r'subpages_requested=(\d+) subpages_ok=(\d+)', msg)
            if match:
                requested = int(match.group(1))
                ok = int(match.group(2))
                if requested > 0:
                    stats['subpages_requested'] = max(stats['subpages_requested'], requested)
                    stats['subpages_success'] = max(stats['subpages_success'], ok)
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 MAIN PAGE")
    print("=" * 100)
    print(f"  Páginas processadas:                  {stats['main_processing']}")
    print(f"  Falhas CFFI:                          {stats['main_fail_cffi']}")
    print(f"  Soft 404 detectados:                  {stats['main_soft_404']}")
    print(f"  Variações tentadas (www):             {stats['main_variation_tried']}")
    print(f"  Falhas fatais:                        {stats['main_fatal']}")
    
    if stats['main_processing'] > 0:
        success_rate = ((stats['main_processing'] - stats['main_fatal']) / stats['main_processing']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 SUBPAGES")
    print("=" * 100)
    print(f"  Subpáginas solicitadas:               {stats['subpages_requested']}")
    print(f"  Subpáginas OK:                        {stats['subpages_success']}")
    print(f"  Falhas CFFI:                          {stats['subpages_fail_cffi']}")
    print(f"  Falhas Curl:                          {stats['subpages_fail_curl']}")
    print(f"  Soft 404:                             {stats['subpages_soft_404']}")
    
    if stats['subpages_requested'] > 0:
        success_rate = (stats['subpages_success'] / stats['subpages_requested']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 SELEÇÃO DE LINKS (LLM)")
    print("=" * 100)
    print(f"  Seleções LLM:                         {stats['llm_link_selection']}")
    print(f"  Links encontrados (total):            {stats['links_found']}")
    print(f"  Links filtrados (não-HTML):           {stats['links_filtered']}")
    print(f"  Links selecionados pelo LLM:          {stats['links_selected']}")
    
    print("\n" + "=" * 100)
    print("📊 CIRCUIT BREAKER")
    print("=" * 100)
    print(f"  Circuit breakers abertos:             {stats['circuit_breaker_opened']}")
    print(f"  URLs puladas por circuit breaker:     {stats['circuit_breaker_skipped']}")
    
    if circuit_breaker_domains:
        print(f"\n  Domínios bloqueados:")
        for domain in list(set(circuit_breaker_domains))[:10]:
            print(f"    - {domain}")
    
    print("\n" + "=" * 100)
    print("📊 CONCORRÊNCIA")
    print("=" * 100)
    print(f"  Esperas por semáforo cheio:           {stats['site_semaphore_waiting']}")
    
    # === PERFORMANCE ===
    print("\n" + "=" * 100)
    print("📊 PERFORMANCE")
    print("=" * 100)
    print(f"  Total de scrapes completos:           {stats['total_scrapes']}")
    
    if performance_data:
        durations = [p['duration'] for p in performance_data]
        pages = [p['pages'] for p in performance_data]
        
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        avg_pages = sum(pages) / len(pages)
        
        print(f"  Duração média:                        {avg_duration:.2f}s")
        print(f"  Duração máxima:                       {max_duration:.2f}s")
        print(f"  Duração mínima:                       {min_duration:.2f}s")
        print(f"  Média de páginas por site:            {avg_pages:.1f}")
        
        # Sites lentos (> 30s)
        slow_sites = [p for p in performance_data if p['duration'] > 30]
        if slow_sites:
            print(f"\n  ⚠️  Sites lentos (> 30s): {len(slow_sites)}")
            for site in sorted(slow_sites, key=lambda x: x['duration'], reverse=True)[:5]:
                print(f"     - {site['url'][:60]}... ({site['duration']:.1f}s, {site['pages']} páginas)")
    
    # === FALHAS ===
    print("\n" + "=" * 100)
    print("⚠️  ANÁLISE DE FALHAS")
    print("=" * 100)
    
    total_failures = stats['main_fatal'] + stats['subpages_fail_cffi'] + stats['subpages_fail_curl']
    print(f"  Total de falhas:                      {total_failures}")
    
    if failed_urls:
        print(f"\n  📍 URLs com falha fatal ({len(failed_urls)}):")
        for f in failed_urls[:10]:
            print(f"     - {f['url'][:60]}...")
            print(f"       Erro: {f['error']}")
    
    if soft_404_urls:
        unique_soft_404 = list(set(soft_404_urls))
        print(f"\n  📍 Soft 404 detectados ({len(unique_soft_404)}):")
        for url in unique_soft_404[:10]:
            print(f"     - {url[:80]}...")
    
    # === RESUMO ===
    print("\n" + "=" * 100)
    print("💡 RESUMO E RECOMENDAÇÕES")
    print("=" * 100)
    
    print(f"""
    📌 MAIN PAGE:
       - {stats['main_processing']} sites processados
       - {stats['main_fatal']} falhas fatais ({stats['main_fatal']/max(stats['main_processing'],1)*100:.1f}%)
       - {stats['main_soft_404']} soft 404 detectados
    
    📌 SUBPAGES:
       - {stats['subpages_requested']} subpáginas solicitadas
       - {stats['subpages_success']} OK ({stats['subpages_success']/max(stats['subpages_requested'],1)*100:.1f}%)
       - {stats['subpages_fail_cffi'] + stats['subpages_fail_curl']} falhas
    
    📌 CIRCUIT BREAKER:
       - {stats['circuit_breaker_opened']} domínios bloqueados
       - {stats['circuit_breaker_skipped']} URLs puladas
    
    ⚠️  PROBLEMAS IDENTIFICADOS:
    """)
    
    if stats['main_fatal'] > 0:
        print(f"    - {stats['main_fatal']} sites não puderam ser scrapados (falha fatal)")
    
    if stats['main_soft_404'] > 0:
        print(f"    - {stats['main_soft_404']} sites retornaram soft 404 (página de erro)")
    
    if stats['circuit_breaker_opened'] > 0:
        print(f"    - {stats['circuit_breaker_opened']} domínios foram bloqueados por muitas falhas")
    
    if stats['site_semaphore_waiting'] > 0:
        print(f"    - {stats['site_semaphore_waiting']} vezes o sistema esperou por limite de concorrência")
    
    if not any([stats['main_fatal'], stats['main_soft_404'], stats['circuit_breaker_opened']]):
        print("    ✅ Nenhum problema crítico identificado")
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'log_file': file_path,
        'stats': stats,
        'failed_urls': failed_urls[:50],
        'soft_404_urls': list(set(soft_404_urls))[:50],
        'circuit_breaker_domains': list(set(circuit_breaker_domains)),
        'performance': {
            'total_scrapes': stats['total_scrapes'],
            'avg_duration': sum(p['duration'] for p in performance_data) / len(performance_data) if performance_data else 0,
            'slow_sites': [p for p in performance_data if p['duration'] > 30][:20]
        }
    }
    
    output_file = 'analysis_scraper_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs_app.json"
    analyze_scraper_logs(file_path)

