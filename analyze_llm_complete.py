#!/usr/bin/env python3
"""
Análise completa de chamadas LLM nos logs.
Analisa tanto chamadas de Discovery quanto de Profile.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_llm_complete(file_path: str):
    """Análise completa de todas as chamadas LLM"""
    
    print("=" * 100)
    print("🔍 ANÁLISE COMPLETA DE CHAMADAS LLM")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # ========================================
    # ESTATÍSTICAS GERAIS
    # ========================================
    stats = {
        # Discovery
        'discovery_llm_start': 0,
        'discovery_llm_success': 0,
        'discovery_llm_timeout': 0,
        'discovery_llm_error': 0,
        'discovery_llm_no_result': 0,
        
        # Profile (LLM.py)
        'profile_llm_start': 0,
        'profile_llm_success': 0,
        'profile_llm_timeout': 0,
        'profile_llm_error': 0,
        'profile_llm_attempt': 0,
        'profile_llm_fallback': 0,
        
        # Por provider
        'provider_requests': Counter(),
        'provider_success': Counter(),
        'provider_errors': Counter(),
        'provider_timeouts': Counter(),
        
        # Chunks
        'chunks_processed': 0,
        'single_chunk': 0,
        'multi_chunk': 0,
    }
    
    # Listas para análise detalhada
    errors_detail = []
    timeouts_detail = []
    fallbacks_detail = []
    
    # Processar cada entrada
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        level = entry.get('level', '') if isinstance(entry, dict) else ''
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # ========================================
        # DISCOVERY LLM (discovery.py)
        # ========================================
        
        # Início da análise LLM no discovery
        if 'Resultados consolidados enviados para IA' in msg:
            stats['discovery_llm_start'] += 1
        
        # Sucesso no discovery LLM
        if 'Decisão do LLM' in msg:
            stats['discovery_llm_success'] += 1
        
        # Timeout no discovery
        if 'Timeout na análise do LLM para descoberta de site' in msg:
            stats['discovery_llm_timeout'] += 1
            timeouts_detail.append({
                'type': 'discovery',
                'message': msg,
                'timestamp': timestamp
            })
        
        # Erro no discovery LLM
        if 'Erro na análise do LLM para descoberta de site' in msg:
            stats['discovery_llm_error'] += 1
            errors_detail.append({
                'type': 'discovery',
                'message': msg,
                'timestamp': timestamp
            })
        
        # ========================================
        # PROFILE LLM (llm.py)
        # ========================================
        
        # Início de request LLM
        if '[LLM_REQUEST_START]' in msg:
            stats['profile_llm_start'] += 1
            # Extrair provider
            match = re.search(r'provider=(\w+)', msg)
            if match:
                provider = match.group(1)
                stats['provider_requests'][provider] += 1
        
        # Tentativa de LLM
        if '[LLM_ATTEMPT]' in msg:
            stats['profile_llm_attempt'] += 1
        
        # Sucesso LLM
        if '[LLM_SUCCESS]' in msg:
            stats['profile_llm_success'] += 1
            match = re.search(r'provider=(\w+)', msg)
            if match:
                provider = match.group(1)
                stats['provider_success'][provider] += 1
        
        # Erro LLM
        if '[LLM_ERROR]' in msg or '[LLM_EXCEPTION]' in msg:
            stats['profile_llm_error'] += 1
            match = re.search(r'provider=(\w+)', msg)
            if match:
                provider = match.group(1)
                stats['provider_errors'][provider] += 1
            errors_detail.append({
                'type': 'profile',
                'message': msg[:500],  # Limitar tamanho
                'timestamp': timestamp
            })
        
        # Timeout LLM
        if 'timeout' in msg.lower() and ('[LLM' in msg or 'llm' in msg.lower()):
            if 'discovery' not in msg.lower():  # Evitar duplicar discovery
                stats['profile_llm_timeout'] += 1
                match = re.search(r'provider=(\w+)', msg)
                if match:
                    provider = match.group(1)
                    stats['provider_timeouts'][provider] += 1
                timeouts_detail.append({
                    'type': 'profile',
                    'message': msg[:500],
                    'timestamp': timestamp
                })
        
        # Fallback
        if 'fallback' in msg.lower() or 'Tentando próximo provedor' in msg:
            stats['profile_llm_fallback'] += 1
            fallbacks_detail.append({
                'message': msg[:300],
                'timestamp': timestamp
            })
        
        # Chunks
        if 'step=analyze_content_single_chunk' in msg:
            stats['single_chunk'] += 1
        if 'step=analyze_content_multi_chunk' in msg or 'Processando' in msg and 'chunks' in msg:
            stats['multi_chunk'] += 1
        
        # Provider summary (métricas agregadas do performance tracker)
        if '[PROVIDER_SUMMARY]' in msg:
            # Extrair métricas do summary
            match = re.search(r'provider=(\w+).*?total=(\d+).*?success=(\d+).*?errors=(\d+)', msg)
            if match:
                provider = match.group(1)
                # Não sobrescrever, usar para validação
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 CHAMADAS LLM - DISCOVERY (find_company_website)")
    print("=" * 100)
    print(f"  Chamadas iniciadas:                   {stats['discovery_llm_start']}")
    print(f"  Chamadas bem-sucedidas:               {stats['discovery_llm_success']}")
    print(f"  Timeouts:                             {stats['discovery_llm_timeout']}")
    print(f"  Erros:                                {stats['discovery_llm_error']}")
    
    discovery_total = stats['discovery_llm_success'] + stats['discovery_llm_timeout'] + stats['discovery_llm_error']
    if stats['discovery_llm_start'] > 0:
        success_rate = (stats['discovery_llm_success'] / stats['discovery_llm_start']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 CHAMADAS LLM - PROFILE (analyze_content)")
    print("=" * 100)
    print(f"  Requests iniciados:                   {stats['profile_llm_start']}")
    print(f"  Tentativas totais (com retries):      {stats['profile_llm_attempt']}")
    print(f"  Chamadas bem-sucedidas:               {stats['profile_llm_success']}")
    print(f"  Timeouts:                             {stats['profile_llm_timeout']}")
    print(f"  Erros:                                {stats['profile_llm_error']}")
    print(f"  Fallbacks acionados:                  {stats['profile_llm_fallback']}")
    
    if stats['profile_llm_start'] > 0:
        success_rate = (stats['profile_llm_success'] / stats['profile_llm_start']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO POR PROVIDER")
    print("=" * 100)
    
    all_providers = set(stats['provider_requests'].keys()) | set(stats['provider_success'].keys())
    for provider in sorted(all_providers):
        requests = stats['provider_requests'].get(provider, 0)
        success = stats['provider_success'].get(provider, 0)
        errors = stats['provider_errors'].get(provider, 0)
        timeouts = stats['provider_timeouts'].get(provider, 0)
        rate = (success / requests * 100) if requests > 0 else 0
        
        print(f"\n  🔹 {provider.upper()}")
        print(f"     Requests:    {requests}")
        print(f"     Sucesso:     {success}")
        print(f"     Erros:       {errors}")
        print(f"     Timeouts:    {timeouts}")
        print(f"     Taxa:        {rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 CHUNKS PROCESSADOS")
    print("=" * 100)
    print(f"  Single-chunk:                         {stats['single_chunk']}")
    print(f"  Multi-chunk:                          {stats['multi_chunk']}")
    
    # ========================================
    # ANÁLISE DE FALHAS
    # ========================================
    
    print("\n" + "=" * 100)
    print("⚠️  ANÁLISE DE FALHAS")
    print("=" * 100)
    
    total_failures = (
        stats['discovery_llm_timeout'] + 
        stats['discovery_llm_error'] + 
        stats['profile_llm_timeout'] + 
        stats['profile_llm_error']
    )
    
    print(f"\n  Total de falhas identificadas:        {total_failures}")
    
    if timeouts_detail:
        print(f"\n  📍 TIMEOUTS ({len(timeouts_detail)} ocorrências):")
        # Agrupar por tipo
        discovery_timeouts = [t for t in timeouts_detail if t['type'] == 'discovery']
        profile_timeouts = [t for t in timeouts_detail if t['type'] == 'profile']
        
        if discovery_timeouts:
            print(f"     - Discovery: {len(discovery_timeouts)}")
        if profile_timeouts:
            print(f"     - Profile: {len(profile_timeouts)}")
        
        print(f"\n     Primeiros 5 timeouts:")
        for t in timeouts_detail[:5]:
            print(f"       [{t['type']}] {t['message'][:100]}...")
    
    if errors_detail:
        print(f"\n  📍 ERROS ({len(errors_detail)} ocorrências):")
        # Agrupar por tipo de erro
        error_types = Counter()
        for e in errors_detail:
            # Tentar identificar o tipo de erro
            if 'rate limit' in e['message'].lower():
                error_types['Rate Limit'] += 1
            elif 'timeout' in e['message'].lower():
                error_types['Timeout'] += 1
            elif 'connection' in e['message'].lower():
                error_types['Connection'] += 1
            elif '500' in e['message'] or '503' in e['message']:
                error_types['Server Error (5xx)'] += 1
            elif '400' in e['message'] or '401' in e['message'] or '403' in e['message']:
                error_types['Client Error (4xx)'] += 1
            else:
                error_types['Outro'] += 1
        
        print(f"     Tipos de erro:")
        for error_type, count in error_types.most_common():
            print(f"       - {error_type}: {count}")
        
        print(f"\n     Primeiros 5 erros:")
        for e in errors_detail[:5]:
            print(f"       [{e['type']}] {e['message'][:150]}...")
    
    if fallbacks_detail:
        print(f"\n  📍 FALLBACKS ({len(fallbacks_detail)} ocorrências):")
        print(f"     Primeiros 5 fallbacks:")
        for f in fallbacks_detail[:5]:
            print(f"       {f['message'][:150]}...")
    
    # ========================================
    # RESUMO FINAL
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 RESUMO FINAL")
    print("=" * 100)
    
    total_llm_calls = stats['discovery_llm_start'] + stats['profile_llm_start']
    total_success = stats['discovery_llm_success'] + stats['profile_llm_success']
    
    print(f"""
    ┌─────────────────────────────────────────────────────────────┐
    │  TOTAL DE CHAMADAS LLM                                      │
    ├─────────────────────────────────────────────────────────────┤
    │  Discovery:        {stats['discovery_llm_start']:>5} chamadas                          │
    │  Profile:          {stats['profile_llm_start']:>5} chamadas                          │
    │  ─────────────────────────────────────────────────────────  │
    │  TOTAL:            {total_llm_calls:>5} chamadas                          │
    ├─────────────────────────────────────────────────────────────┤
    │  Sucesso Total:    {total_success:>5} ({(total_success/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%)                             │
    │  Falhas Total:     {total_failures:>5} ({(total_failures/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%)                             │
    └─────────────────────────────────────────────────────────────┘
    """)
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_llm_calls': total_llm_calls,
            'discovery_calls': stats['discovery_llm_start'],
            'profile_calls': stats['profile_llm_start'],
            'total_success': total_success,
            'total_failures': total_failures,
        },
        'discovery': {
            'started': stats['discovery_llm_start'],
            'success': stats['discovery_llm_success'],
            'timeout': stats['discovery_llm_timeout'],
            'error': stats['discovery_llm_error'],
        },
        'profile': {
            'started': stats['profile_llm_start'],
            'attempts': stats['profile_llm_attempt'],
            'success': stats['profile_llm_success'],
            'timeout': stats['profile_llm_timeout'],
            'error': stats['profile_llm_error'],
            'fallbacks': stats['profile_llm_fallback'],
        },
        'providers': {
            provider: {
                'requests': stats['provider_requests'].get(provider, 0),
                'success': stats['provider_success'].get(provider, 0),
                'errors': stats['provider_errors'].get(provider, 0),
                'timeouts': stats['provider_timeouts'].get(provider, 0),
            }
            for provider in all_providers
        },
        'failures': {
            'timeouts': timeouts_detail[:20],
            'errors': errors_detail[:20],
            'fallbacks': fallbacks_detail[:20],
        }
    }
    
    output_file = 'analysis_llm_complete.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs_app_novo.json"
    analyze_llm_complete(file_path)

