#!/usr/bin/env python3
"""
Análise detalhada de chamadas LLM nos logs.
Atualizado para refletir load balancing centralizado e monitoramento de semáforos.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_llm_detailed(file_path: str):
    """Análise detalhada de todas as chamadas LLM"""
    
    print("=" * 100)
    print("🔍 ANÁLISE DETALHADA DE CHAMADAS LLM (v2 - Load Balancing)")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # ========================================
    # CONTADORES
    # ========================================
    
    # Discovery
    discovery = {
        'enviado_para_ia': 0,
        'decisao_llm': 0,
        'site_encontrado': 0,
        'site_nao_encontrado': 0,
        'timeout': 0,
        'erro': 0,
        'retries': 0,
    }
    
    # Profile LLM
    profile = {
        'request_start': 0,
        'success': 0,
        'error': 0,
        'timeout': 0,
    }
    
    # Por provider
    providers = {
        'gemini': {'requests': 0, 'success': 0, 'errors': 0},
        'openai': {'requests': 0, 'success': 0, 'errors': 0},
    }
    
    # Semáforos (NOVO)
    semaphore_logs = []
    
    # Load Balancing (NOVO - Híbrido Round-Robin + Fallback)
    load_balance = {
        'decisions': 0,
        'single_chunk': 0,
        'multi_chunk': 0,
        'round_robin_normal': 0,  # Seleção via round-robin
        'round_robin_fallback': 0,  # Fallback quando semáforo locked
        'round_robin_all_locked': 0,  # Todos provedores com semáforo full
    }
    
    # Empresas
    companies = {
        'total_start': 0,
        'com_url': 0,
        'sem_url': 0,
    }
    
    # Falhas detalhadas
    failures = {
        'timeouts': [],
        'errors': [],
    }
    
    # ========================================
    # PROCESSAR LOGS
    # ========================================
    
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # === EMPRESAS ===
        if '[PERF] analyze_company start' in msg:
            companies['total_start'] += 1
        
        if '[DISCOVERY] Iniciando busca para:' in msg:
            companies['sem_url'] += 1
        
        # === DISCOVERY LLM ===
        if 'Resultados consolidados enviados para IA' in msg:
            discovery['enviado_para_ia'] += 1
        
        if 'Decisão do LLM' in msg:
            discovery['decisao_llm'] += 1
            if '"site": "nao_encontrado"' in msg or '"site":"nao_encontrado"' in msg:
                discovery['site_nao_encontrado'] += 1
            else:
                discovery['site_encontrado'] += 1
        
        if 'Timeout na análise do LLM' in msg and 'descoberta de site' in msg:
            discovery['timeout'] += 1
            failures['timeouts'].append({
                'type': 'discovery',
                'message': msg[:300],
                'timestamp': timestamp
            })
        
        if 'Erro na análise do LLM' in msg and 'descoberta de site' in msg:
            discovery['erro'] += 1
            failures['errors'].append({
                'type': 'discovery',
                'message': msg[:300],
                'timestamp': timestamp
            })
        
        if 'Discovery retry' in msg:
            discovery['retries'] += 1
        
        # === PROFILE LLM ===
        if '[LLM_REQUEST_START]' in msg:
            profile['request_start'] += 1
            if 'gemini' in msg.lower():
                providers['gemini']['requests'] += 1
            elif 'openai' in msg.lower() or 'gpt' in msg.lower():
                providers['openai']['requests'] += 1
        
        if '[LLM_SUCCESS]' in msg:
            profile['success'] += 1
            if 'gemini' in msg.lower():
                providers['gemini']['success'] += 1
            elif 'openai' in msg.lower() or 'gpt' in msg.lower():
                providers['openai']['success'] += 1
        
        if '[LLM_ERROR]' in msg or '[LLM_EXCEPTION]' in msg:
            profile['error'] += 1
            if 'gemini' in msg.lower():
                providers['gemini']['errors'] += 1
            elif 'openai' in msg.lower():
                providers['openai']['errors'] += 1
            failures['errors'].append({
                'type': 'profile',
                'message': msg[:300],
                'timestamp': timestamp
            })
        
        if '[LLM_TIMEOUT]' in msg:
            profile['timeout'] += 1
            failures['timeouts'].append({
                'type': 'profile',
                'message': msg[:300],
                'timestamp': timestamp
            })
        
        # === SEMÁFOROS (NOVO) ===
        if '[SEMAPHORE_STATUS]' in msg:
            # Parse: 🔒 [SEMAPHORE_STATUS] Google Gemini: locked=False, waiters=0, active=3
            match = re.search(r'\[SEMAPHORE_STATUS\] (.+?): locked=(\w+), waiters=(\d+)', msg)
            if match:
                semaphore_logs.append({
                    'provider': match.group(1),
                    'locked': match.group(2) == 'True',
                    'waiters': int(match.group(3)),
                    'timestamp': timestamp
                })
        
        # === LOAD BALANCING (NOVO - Híbrido Round-Robin + Fallback) ===
        if '[LOAD_BALANCE]' in msg:
            load_balance['decisions'] += 1
            if 'Single-chunk' in msg or 'single-chunk' in msg:
                load_balance['single_chunk'] += 1
        
        # Round-Robin com Fallback
        if '[ROUND_ROBIN]' in msg:
            load_balance['decisions'] += 1
            if 'Selecionado:' in msg:
                load_balance['round_robin_normal'] += 1
            elif 'Fallback:' in msg:
                load_balance['round_robin_fallback'] += 1
            elif 'Todos provedores com semáforo locked' in msg:
                load_balance['round_robin_all_locked'] += 1
        
        if 'step=analyze_content_single_chunk' in msg:
            load_balance['single_chunk'] += 1
        
        if 'step=analyze_content_multi_chunk' in msg:
            load_balance['multi_chunk'] += 1
    
    # Calcular empresas com URL
    companies['com_url'] = companies['total_start'] - companies['sem_url']
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 EMPRESAS PROCESSADAS")
    print("=" * 100)
    print(f"  Total:                                {companies['total_start']}")
    print(f"  Com URL direta:                       {companies['com_url']}")
    print(f"  Precisaram discovery:                 {companies['sem_url']}")
    
    print("\n" + "=" * 100)
    print("📊 DISCOVERY LLM")
    print("=" * 100)
    print(f"  Chamadas:                             {discovery['enviado_para_ia']}")
    print(f"  Respostas:                            {discovery['decisao_llm']}")
    print(f"    → Sites encontrados:                {discovery['site_encontrado']}")
    print(f"    → Sites não encontrados:            {discovery['site_nao_encontrado']}")
    print(f"  Timeouts:                             {discovery['timeout']}")
    print(f"  Erros:                                {discovery['erro']}")
    print(f"  Retries:                              {discovery['retries']}")
    
    if discovery['enviado_para_ia'] > 0:
        success_rate = (discovery['decisao_llm'] / discovery['enviado_para_ia']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 PROFILE LLM")
    print("=" * 100)
    print(f"  Requests:                             {profile['request_start']}")
    print(f"  Sucesso:                              {profile['success']}")
    print(f"  Erros:                                {profile['error']}")
    print(f"  Timeouts:                             {profile['timeout']}")
    
    if profile['request_start'] > 0:
        success_rate = (profile['success'] / profile['request_start']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO POR PROVIDER")
    print("=" * 100)
    
    total_requests = providers['gemini']['requests'] + providers['openai']['requests']
    
    for provider, stats in providers.items():
        if stats['requests'] > 0 or total_requests > 0:
            pct = (stats['requests'] / total_requests * 100) if total_requests > 0 else 0
            rate = (stats['success'] / stats['requests'] * 100) if stats['requests'] > 0 else 0
            print(f"\n  🔹 {provider.upper()}")
            print(f"     Requests:    {stats['requests']} ({pct:.1f}%)")
            print(f"     Sucesso:     {stats['success']}")
            print(f"     Erros:       {stats['errors']}")
            if stats['requests'] > 0:
                print(f"     Taxa:        {rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 LOAD BALANCING (Híbrido Round-Robin + Fallback)")
    print("=" * 100)
    print(f"  Decisões de balanceamento:            {load_balance['decisions']}")
    print(f"  Single-chunk (balanceado):            {load_balance['single_chunk']}")
    print(f"  Multi-chunk (round-robin):            {load_balance['multi_chunk']}")
    
    # Round-Robin stats
    print(f"\n  📊 Estatísticas do Round-Robin:")
    print(f"     Seleções normais:                  {load_balance['round_robin_normal']}")
    print(f"     Fallbacks (semáforo locked):       {load_balance['round_robin_fallback']}")
    print(f"     Todos provedores locked:           {load_balance['round_robin_all_locked']}")
    
    total_rr = load_balance['round_robin_normal'] + load_balance['round_robin_fallback'] + load_balance['round_robin_all_locked']
    if total_rr > 0:
        normal_pct = load_balance['round_robin_normal'] / total_rr * 100
        fallback_pct = load_balance['round_robin_fallback'] / total_rr * 100
        print(f"\n     Taxa de seleção normal:            {normal_pct:.1f}%")
        print(f"     Taxa de fallback:                  {fallback_pct:.1f}%")
    
    # Balanceamento efetivo
    if total_requests > 0:
        gemini_pct = providers['gemini']['requests'] / total_requests * 100
        openai_pct = providers['openai']['requests'] / total_requests * 100
        balance_score = 100 - abs(gemini_pct - openai_pct)
        print(f"\n  📈 Score de Balanceamento:            {balance_score:.1f}%")
        print(f"     (100% = distribuição 50/50, 0% = 100/0)")
    
    # === SEMÁFOROS ===
    print("\n" + "=" * 100)
    print("📊 SEMÁFOROS (Monitoramento)")
    print("=" * 100)
    print(f"  Total de logs de semáforo:            {len(semaphore_logs)}")
    
    if semaphore_logs:
        # Analisar contenção
        locked_count = sum(1 for s in semaphore_logs if s['locked'])
        waiters_total = sum(s['waiters'] for s in semaphore_logs)
        max_waiters = max(s['waiters'] for s in semaphore_logs) if semaphore_logs else 0
        
        print(f"  Logs com semáforo locked:             {locked_count}")
        print(f"  Total de waiters observados:          {waiters_total}")
        print(f"  Máximo de waiters em um momento:      {max_waiters}")
        
        # Por provider
        by_provider = defaultdict(list)
        for s in semaphore_logs:
            by_provider[s['provider']].append(s)
        
        print("\n  Por Provider:")
        for provider, logs in by_provider.items():
            locked = sum(1 for l in logs if l['locked'])
            avg_waiters = sum(l['waiters'] for l in logs) / len(logs) if logs else 0
            print(f"    {provider}: {len(logs)} logs, {locked} locked, avg waiters: {avg_waiters:.1f}")
    
    # === FALHAS ===
    total_failures = discovery['timeout'] + discovery['erro'] + profile['error'] + profile['timeout']
    
    print("\n" + "=" * 100)
    print("⚠️  ANÁLISE DE FALHAS")
    print("=" * 100)
    print(f"  Total de falhas:                      {total_failures}")
    print(f"    → Discovery timeouts:               {discovery['timeout']}")
    print(f"    → Discovery erros:                  {discovery['erro']}")
    print(f"    → Profile erros:                    {profile['error']}")
    print(f"    → Profile timeouts:                 {profile['timeout']}")
    
    if failures['timeouts']:
        print(f"\n  📍 TIMEOUTS ({len(failures['timeouts'])}):")
        for t in failures['timeouts'][:5]:
            print(f"     [{t['type']}] {t['message'][:100]}...")
    
    if failures['errors']:
        print(f"\n  📍 ERROS ({len(failures['errors'])}):")
        for e in failures['errors'][:5]:
            print(f"     [{e['type']}] {e['message'][:100]}...")
    
    # === RESUMO FINAL ===
    total_discovery_calls = discovery['enviado_para_ia']
    total_profile_calls = profile['request_start']
    total_llm_calls = total_discovery_calls + total_profile_calls
    
    total_discovery_success = discovery['decisao_llm']
    total_profile_success = profile['success']
    total_success = total_discovery_success + total_profile_success
    
    print("\n" + "=" * 100)
    print("📊 RESUMO FINAL")
    print("=" * 100)
    
    print(f"""
    ┌─────────────────────────────────────────────────────────────────────┐
    │  TIPO                         CHAMADAS    SUCESSO     FALHAS        │
    ├─────────────────────────────────────────────────────────────────────┤
    │  Discovery LLM                {total_discovery_calls:>6}      {total_discovery_success:>6}      {discovery['timeout'] + discovery['erro']:>6}        │
    │  Profile LLM                  {total_profile_calls:>6}      {total_profile_success:>6}      {profile['error'] + profile['timeout']:>6}        │
    ├─────────────────────────────────────────────────────────────────────┤
    │  TOTAL                        {total_llm_calls:>6}      {total_success:>6}      {total_failures:>6}        │
    └─────────────────────────────────────────────────────────────────────┘
    
    📌 LOAD BALANCING:
       - Gemini: {providers['gemini']['requests']} requests ({providers['gemini']['requests']/total_requests*100 if total_requests > 0 else 0:.1f}%)
       - OpenAI: {providers['openai']['requests']} requests ({providers['openai']['requests']/total_requests*100 if total_requests > 0 else 0:.1f}%)
       - Score de balanceamento: {100 - abs(providers['gemini']['requests'] - providers['openai']['requests']) / max(total_requests, 1) * 100:.1f}%
    
    📌 SEMÁFOROS:
       - {len(semaphore_logs)} logs de monitoramento
       - {sum(1 for s in semaphore_logs if s['locked'])} momentos com semáforo full
    """)
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'log_file': file_path,
        'total_log_entries': len(data),
        'companies': companies,
        'discovery': discovery,
        'profile': profile,
        'providers': providers,
        'load_balance': load_balance,
        'semaphore_summary': {
            'total_logs': len(semaphore_logs),
            'locked_count': sum(1 for s in semaphore_logs if s['locked']),
            'max_waiters': max(s['waiters'] for s in semaphore_logs) if semaphore_logs else 0,
        },
        'failures': {
            'total': total_failures,
            'timeouts': failures['timeouts'][:10],
            'errors': failures['errors'][:10],
        },
        'summary': {
            'total_llm_calls': total_llm_calls,
            'total_success': total_success,
            'total_failures': total_failures,
            'balance_score': 100 - abs(providers['gemini']['requests'] - providers['openai']['requests']) / max(total_requests, 1) * 100
        }
    }
    
    output_file = 'analysis_llm_detailed.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs_app_novo.json"
    analyze_llm_detailed(file_path)
