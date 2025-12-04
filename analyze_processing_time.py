#!/usr/bin/env python3
"""
Análise de tempo de processamento total de empresas.
Objetivo: Identificar empresas que demoram mais de 60 segundos para serem processadas.
"""

import json
import re
from collections import defaultdict
from datetime import datetime

def analyze_processing_time(file_path: str, threshold_seconds: float = 60.0):
    """
    Analisa tempo de processamento de cada empresa.
    
    Args:
        file_path: Caminho do arquivo de log
        threshold_seconds: Limite em segundos para considerar empresa lenta (default: 60s)
    """
    
    print("=" * 100)
    print(f"⏱️  ANÁLISE DE TEMPO DE PROCESSAMENTO (threshold: {threshold_seconds}s)")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # ========================================
    # RASTREAR TEMPOS POR EMPRESA
    # ========================================
    
    # Estrutura: url -> {start, end, total, steps: {step: duration}}
    companies = defaultdict(lambda: {
        'start_time': None,
        'end_time': None,
        'total_time': None,
        'steps': {},
        'status': 'unknown',
        'discovery': False,
    })
    
    # Estatísticas gerais
    stats = {
        'total_companies': 0,
        'completed': 0,
        'timeout': 0,
        'error': 0,
        'slow_companies': 0,  # > threshold_seconds
    }
    
    # ========================================
    # PROCESSAR LOGS
    # ========================================
    
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # === analyze_company start ===
        if '[PERF] analyze_company start' in msg:
            match = re.search(r'url=(.+)$', msg)
            if match:
                url = match.group(1).strip()
                companies[url]['start_time'] = timestamp
                stats['total_companies'] += 1
        
        # === analyze_company end ===
        if '[PERF] analyze_company end' in msg:
            match = re.search(r'url=(.+?) total=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                total = float(match.group(2))
                companies[url]['end_time'] = timestamp
                companies[url]['total_time'] = total
                companies[url]['status'] = 'completed'
                stats['completed'] += 1
                
                if total > threshold_seconds:
                    stats['slow_companies'] += 1
        
        # === analyze_company timeout ===
        if '[PERF] analyze_company timeout' in msg:
            match = re.search(r'url=(.+?) total=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                total = float(match.group(2))
                companies[url]['total_time'] = total
                companies[url]['status'] = 'timeout'
                stats['timeout'] += 1
                stats['slow_companies'] += 1
        
        # === analyze_company failed ===
        if '[PERF] analyze_company failed' in msg:
            match = re.search(r'url=(.+?) total=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                total = float(match.group(2))
                companies[url]['total_time'] = total
                companies[url]['status'] = 'error'
                stats['error'] += 1
        
        # === process_analysis steps ===
        # step=scrape_url
        if '[PERF] process_analysis step=scrape_url' in msg:
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                duration = float(match.group(2))
                companies[url]['steps']['scrape_url'] = duration
        
        # step=documents
        if '[PERF] process_analysis step=documents' in msg:
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                duration = float(match.group(2))
                companies[url]['steps']['documents'] = duration
        
        # step=llm_analysis
        if '[PERF] process_analysis step=llm_analysis' in msg:
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                duration = float(match.group(2))
                companies[url]['steps']['llm_analysis'] = duration
        
        # step=total
        if '[PERF] process_analysis step=total' in msg:
            match = re.search(r'url=(.+?) duration=(\d+\.?\d*)s', msg)
            if match:
                url = match.group(1).strip()
                duration = float(match.group(2))
                companies[url]['steps']['process_total'] = duration
        
        # === Discovery ===
        if '[DISCOVERY] Iniciando busca para:' in msg:
            # Próxima empresa terá discovery
            pass
        
        if '[DISCOVERY] Site identificado:' in msg:
            match = re.search(r'Site identificado: (.+)$', msg)
            if match:
                url = match.group(1).strip()
                companies[url]['discovery'] = True
    
    # ========================================
    # ANÁLISE
    # ========================================
    
    # Filtrar empresas com dados
    valid_companies = {url: data for url, data in companies.items() if data['total_time'] is not None}
    
    # Empresas lentas (> threshold)
    slow_companies = {url: data for url, data in valid_companies.items() 
                      if data['total_time'] > threshold_seconds}
    
    # Calcular estatísticas
    if valid_companies:
        times = [c['total_time'] for c in valid_companies.values()]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        
        # Percentis
        sorted_times = sorted(times)
        p50 = sorted_times[len(sorted_times) // 2]
        p90 = sorted_times[int(len(sorted_times) * 0.9)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 100 else max_time
    else:
        avg_time = max_time = min_time = p50 = p90 = p95 = p99 = 0
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 ESTATÍSTICAS GERAIS")
    print("=" * 100)
    print(f"  Empresas iniciadas:                   {stats['total_companies']}")
    print(f"  Completadas com sucesso:              {stats['completed']}")
    print(f"  Timeout (>300s):                      {stats['timeout']}")
    print(f"  Erro:                                 {stats['error']}")
    print(f"  Empresas lentas (>{threshold_seconds}s):            {len(slow_companies)}")
    
    print("\n" + "=" * 100)
    print("📊 TEMPO DE PROCESSAMENTO")
    print("=" * 100)
    print(f"  Mínimo:                               {min_time:.2f}s")
    print(f"  Máximo:                               {max_time:.2f}s")
    print(f"  Média:                                {avg_time:.2f}s")
    print(f"  Mediana (P50):                        {p50:.2f}s")
    print(f"  P90:                                  {p90:.2f}s")
    print(f"  P95:                                  {p95:.2f}s")
    print(f"  P99:                                  {p99:.2f}s")
    
    # Distribuição por faixa
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO POR FAIXA DE TEMPO")
    print("=" * 100)
    
    ranges = [
        (0, 10, "0-10s"),
        (10, 30, "10-30s"),
        (30, 60, "30-60s"),
        (60, 120, "60-120s"),
        (120, 180, "120-180s"),
        (180, 300, "180-300s"),
        (300, float('inf'), ">300s (timeout)")
    ]
    
    for min_r, max_r, label in ranges:
        count = sum(1 for c in valid_companies.values() 
                   if min_r <= c['total_time'] < max_r)
        pct = (count / len(valid_companies) * 100) if valid_companies else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:15} {count:>5} ({pct:5.1f}%) {bar}")
    
    # === EMPRESAS LENTAS (> threshold) ===
    print("\n" + "=" * 100)
    print(f"⚠️  EMPRESAS LENTAS (>{threshold_seconds}s)")
    print("=" * 100)
    print(f"  Total: {len(slow_companies)}")
    
    if slow_companies:
        # Ordenar por tempo
        sorted_slow = sorted(slow_companies.items(), 
                            key=lambda x: x[1]['total_time'], 
                            reverse=True)
        
        print("\n  Top 20 mais lentas:")
        print("  " + "-" * 95)
        print(f"  {'URL':<50} {'Total':>8} {'Scrape':>8} {'LLM':>8} {'Status':>10}")
        print("  " + "-" * 95)
        
        for url, data in sorted_slow[:20]:
            scrape_time = data['steps'].get('scrape_url', 0)
            llm_time = data['steps'].get('llm_analysis', 0)
            status = data['status']
            
            url_short = url[:48] + '...' if len(url) > 50 else url
            print(f"  {url_short:<50} {data['total_time']:>7.1f}s {scrape_time:>7.1f}s {llm_time:>7.1f}s {status:>10}")
        
        # Análise de onde está o gargalo
        print("\n  📍 Análise de gargalo nas empresas lentas:")
        
        scrape_heavy = sum(1 for u, d in slow_companies.items() 
                         if d['steps'].get('scrape_url', 0) > d['total_time'] * 0.5)
        llm_heavy = sum(1 for u, d in slow_companies.items() 
                       if d['steps'].get('llm_analysis', 0) > d['total_time'] * 0.5)
        
        print(f"     Gargalo em Scraping (>50% do tempo):    {scrape_heavy}")
        print(f"     Gargalo em LLM (>50% do tempo):         {llm_heavy}")
    
    # === ANÁLISE POR STEP ===
    print("\n" + "=" * 100)
    print("📊 TEMPO MÉDIO POR ETAPA")
    print("=" * 100)
    
    step_times = defaultdict(list)
    for url, data in valid_companies.items():
        for step, duration in data['steps'].items():
            step_times[step].append(duration)
    
    for step, times in sorted(step_times.items()):
        if times:
            avg = sum(times) / len(times)
            max_t = max(times)
            print(f"  {step:<25} avg: {avg:>7.2f}s  max: {max_t:>7.2f}s  ({len(times)} amostras)")
    
    # === RESUMO ===
    print("\n" + "=" * 100)
    print("💡 RESUMO E RECOMENDAÇÕES")
    print("=" * 100)
    
    print(f"""
    📌 VISÃO GERAL:
       - {len(valid_companies)} empresas processadas
       - Tempo médio: {avg_time:.1f}s
       - P95: {p95:.1f}s
       - {len(slow_companies)} empresas acima de {threshold_seconds}s ({len(slow_companies)/max(len(valid_companies),1)*100:.1f}%)
    
    📌 ANÁLISE:
    """)
    
    if avg_time > 60:
        print(f"    ⚠️  Tempo médio alto ({avg_time:.1f}s) - considerar otimizações")
    else:
        print(f"    ✅ Tempo médio OK ({avg_time:.1f}s)")
    
    if p95 > 120:
        print(f"    ⚠️  P95 alto ({p95:.1f}s) - 5% das empresas demoram mais de 2 min")
    
    if stats['timeout'] > 0:
        print(f"    🔴 {stats['timeout']} empresas deram timeout (>300s)")
    
    if slow_companies:
        # Identificar padrão
        scrape_heavy = sum(1 for u, d in slow_companies.items() 
                         if d['steps'].get('scrape_url', 0) > d['total_time'] * 0.5)
        llm_heavy = sum(1 for u, d in slow_companies.items() 
                       if d['steps'].get('llm_analysis', 0) > d['total_time'] * 0.5)
        
        if scrape_heavy > llm_heavy:
            print(f"    📍 Principal gargalo: SCRAPING ({scrape_heavy}/{len(slow_companies)} empresas lentas)")
            print("       Recomendação: Verificar sites com muitas subpáginas ou bloqueios")
        elif llm_heavy > 0:
            print(f"    📍 Principal gargalo: LLM ({llm_heavy}/{len(slow_companies)} empresas lentas)")
            print("       Recomendação: Verificar chunks muito grandes ou contenção de semáforos")
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'log_file': file_path,
        'threshold_seconds': threshold_seconds,
        'stats': {
            'total_companies': len(valid_companies),
            'slow_companies': len(slow_companies),
            'avg_time': avg_time,
            'max_time': max_time,
            'min_time': min_time,
            'p50': p50,
            'p90': p90,
            'p95': p95,
            'p99': p99,
            'completed': stats['completed'],
            'timeout': stats['timeout'],
            'error': stats['error'],
        },
        'slow_companies': [
            {
                'url': url,
                'total_time': data['total_time'],
                'scrape_time': data['steps'].get('scrape_url', 0),
                'llm_time': data['steps'].get('llm_analysis', 0),
                'status': data['status'],
            }
            for url, data in sorted(slow_companies.items(), 
                                    key=lambda x: x[1]['total_time'], 
                                    reverse=True)[:50]
        ],
        'step_averages': {
            step: sum(times) / len(times) if times else 0
            for step, times in step_times.items()
        }
    }
    
    output_file = 'analysis_processing_time.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs_app.json"
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    analyze_processing_time(file_path, threshold)

