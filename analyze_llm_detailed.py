#!/usr/bin/env python3
"""
Análise detalhada e precisa de chamadas LLM nos logs.
Versão refinada com padrões corretos.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_llm_detailed(file_path: str):
    """Análise detalhada de todas as chamadas LLM"""
    
    print("=" * 100)
    print("🔍 ANÁLISE DETALHADA DE CHAMADAS LLM - VERSÃO REFINADA")
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
        'enviado_para_ia': 0,        # "Resultados consolidados enviados para IA"
        'decisao_llm': 0,            # "🧠 Decisão do LLM"
        'site_encontrado': 0,        # site != nao_encontrado
        'site_nao_encontrado': 0,    # site == nao_encontrado
        'timeout': 0,
        'erro': 0,
    }
    
    # Profile LLM
    profile = {
        'request_start': 0,          # [LLM_REQUEST_START]
        'attempt': 0,                # [LLM_ATTEMPT]
        'success_profile': 0,        # [LLM_SUCCESS] CompanyProfile criado
        'success_generic': 0,        # [LLM_SUCCESS] Análise bem-sucedida
        'error': 0,
        'timeout': 0,
    }
    
    # Por provider (profile)
    providers = {
        'gemini': {'requests': 0, 'success': 0, 'errors': 0},
        'openai': {'requests': 0, 'success': 0, 'errors': 0},
    }
    
    # Chunks
    chunks = {
        'single': 0,
        'multi': 0,
        'total_chunks': 0,
    }
    
    # Detalhes de falhas
    failures = {
        'timeouts': [],
        'errors': [],
    }
    
    # Empresas processadas
    companies = {
        'total_start': 0,
        'com_url': 0,
        'sem_url': 0,
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
        
        if '🧠 Decisão do LLM:' in msg:
            discovery['decisao_llm'] += 1
            if '"site": "nao_encontrado"' in msg or '"site":"nao_encontrado"' in msg:
                discovery['site_nao_encontrado'] += 1
            else:
                discovery['site_encontrado'] += 1
        
        if 'Timeout na análise do LLM para descoberta de site' in msg:
            discovery['timeout'] += 1
            failures['timeouts'].append({
                'type': 'discovery',
                'message': msg,
                'timestamp': timestamp
            })
        
        if 'Erro na análise do LLM para descoberta de site' in msg:
            discovery['erro'] += 1
            failures['errors'].append({
                'type': 'discovery',
                'message': msg,
                'timestamp': timestamp
            })
        
        # === PROFILE LLM ===
        
        # Request Start - capturar provider
        if '[LLM_REQUEST_START]' in msg:
            profile['request_start'] += 1
            if 'gemini' in msg.lower():
                providers['gemini']['requests'] += 1
            elif 'openai' in msg.lower() or 'gpt' in msg.lower():
                providers['openai']['requests'] += 1
        
        # Attempt
        if '[LLM_ATTEMPT]' in msg:
            profile['attempt'] += 1
        
        # Success - distinguir tipos
        if '[LLM_SUCCESS]' in msg:
            if 'CompanyProfile criado' in msg:
                profile['success_profile'] += 1
                # Capturar provider do sucesso
                if 'gemini' in msg.lower():
                    providers['gemini']['success'] += 1
                elif 'openai' in msg.lower() or 'gpt' in msg.lower():
                    providers['openai']['success'] += 1
            elif 'Análise bem-sucedida' in msg:
                profile['success_generic'] += 1
        
        # Errors
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
        
        # Chunks
        if 'step=analyze_content_single_chunk' in msg:
            chunks['single'] += 1
        if 'step=analyze_content_multi_chunk' in msg:
            chunks['multi'] += 1
        
        # Chunk distribution
        match = re.search(r'Chunk (\d+)/(\d+)', msg)
        if match:
            chunks['total_chunks'] = max(chunks['total_chunks'], int(match.group(2)))
    
    # Calcular empresas com URL
    companies['com_url'] = companies['total_start'] - companies['sem_url']
    
    # ========================================
    # RELATÓRIO
    # ========================================
    
    print("\n" + "=" * 100)
    print("📊 FLUXO GERAL - EMPRESAS PROCESSADAS")
    print("=" * 100)
    print(f"  Total de empresas iniciadas:          {companies['total_start']}")
    print(f"  Com URL direta (sem discovery):       {companies['com_url']}")
    print(f"  Sem URL (precisaram discovery):       {companies['sem_url']}")
    
    print("\n" + "=" * 100)
    print("📊 CHAMADAS LLM - DISCOVERY (find_company_website)")
    print("=" * 100)
    print(f"  Enviados para IA (chamadas):          {discovery['enviado_para_ia']}")
    print(f"  Decisões recebidas (respostas):       {discovery['decisao_llm']}")
    print(f"    → Sites encontrados:                {discovery['site_encontrado']}")
    print(f"    → Sites não encontrados:            {discovery['site_nao_encontrado']}")
    print(f"  Timeouts:                             {discovery['timeout']}")
    print(f"  Erros:                                {discovery['erro']}")
    
    if discovery['enviado_para_ia'] > 0:
        success_rate = (discovery['decisao_llm'] / discovery['enviado_para_ia']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 CHAMADAS LLM - PROFILE (analyze_content)")
    print("=" * 100)
    print(f"  Requests iniciados:                   {profile['request_start']}")
    print(f"  Tentativas (attempts):                {profile['attempt']}")
    print(f"  Perfis criados com sucesso:           {profile['success_profile']}")
    print(f"  Análises genéricas (sucesso):         {profile['success_generic']}")
    print(f"  Erros:                                {profile['error']}")
    
    if profile['request_start'] > 0:
        success_rate = (profile['success_profile'] / profile['request_start']) * 100
        print(f"  Taxa de sucesso (perfis):             {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO POR PROVIDER (Profile LLM)")
    print("=" * 100)
    
    for provider, stats in providers.items():
        if stats['requests'] > 0:
            rate = (stats['success'] / stats['requests']) * 100
            print(f"\n  🔹 {provider.upper()}")
            print(f"     Requests:    {stats['requests']}")
            print(f"     Sucesso:     {stats['success']}")
            print(f"     Erros:       {stats['errors']}")
            print(f"     Taxa:        {rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 CHUNKS PROCESSADOS")
    print("=" * 100)
    print(f"  Single-chunk:                         {chunks['single']}")
    print(f"  Multi-chunk:                          {chunks['multi']}")
    
    # ========================================
    # ANÁLISE DE FALHAS
    # ========================================
    
    print("\n" + "=" * 100)
    print("⚠️  ANÁLISE DE FALHAS")
    print("=" * 100)
    
    total_failures = discovery['timeout'] + discovery['erro'] + profile['error']
    
    print(f"\n  Total de falhas:                      {total_failures}")
    print(f"    → Discovery timeouts:               {discovery['timeout']}")
    print(f"    → Discovery erros:                  {discovery['erro']}")
    print(f"    → Profile erros:                    {profile['error']}")
    
    if failures['timeouts']:
        print(f"\n  📍 TIMEOUTS DETALHADOS ({len(failures['timeouts'])}):")
        for t in failures['timeouts'][:5]:
            print(f"     [{t['type']}] {t['message'][:150]}...")
    
    if failures['errors']:
        print(f"\n  📍 ERROS DETALHADOS ({len(failures['errors'])}):")
        for e in failures['errors'][:5]:
            print(f"     [{e['type']}] {e['message'][:150]}...")
    
    if total_failures == 0:
        print("\n  ✅ Nenhuma falha significativa identificada!")
    
    # ========================================
    # RESUMO FINAL
    # ========================================
    
    total_discovery_calls = discovery['enviado_para_ia']
    total_profile_calls = profile['request_start']
    total_llm_calls = total_discovery_calls + total_profile_calls
    
    total_discovery_success = discovery['decisao_llm']
    total_profile_success = profile['success_profile']
    total_success = total_discovery_success + total_profile_success
    
    print("\n" + "=" * 100)
    print("📊 RESUMO FINAL")
    print("=" * 100)
    
    print(f"""
    ┌─────────────────────────────────────────────────────────────────────┐
    │  TOTAL DE CHAMADAS LLM                                              │
    ├─────────────────────────────────────────────────────────────────────┤
    │  Discovery (find_company_website):    {total_discovery_calls:>5} chamadas                │
    │    → Sucesso:                         {total_discovery_success:>5} ({(total_discovery_success/total_discovery_calls*100) if total_discovery_calls > 0 else 0:.1f}%)                    │
    │    → Sites encontrados:               {discovery['site_encontrado']:>5}                          │
    │    → Sites não encontrados:           {discovery['site_nao_encontrado']:>5}                          │
    │    → Timeouts/Erros:                  {discovery['timeout'] + discovery['erro']:>5}                          │
    ├─────────────────────────────────────────────────────────────────────┤
    │  Profile (analyze_content):           {total_profile_calls:>5} chamadas                │
    │    → Sucesso:                         {total_profile_success:>5} ({(total_profile_success/total_profile_calls*100) if total_profile_calls > 0 else 0:.1f}%)                    │
    │    → Erros:                           {profile['error']:>5}                          │
    ├─────────────────────────────────────────────────────────────────────┤
    │  TOTAL GERAL:                         {total_llm_calls:>5} chamadas LLM            │
    │  SUCESSO GERAL:                       {total_success:>5} ({(total_success/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%)                    │
    │  FALHAS TOTAIS:                       {total_failures:>5} ({(total_failures/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%)                     │
    └─────────────────────────────────────────────────────────────────────┘
    """)
    
    # ========================================
    # CONCLUSÃO
    # ========================================
    
    print("\n" + "=" * 100)
    print("💡 CONCLUSÃO DA ANÁLISE")
    print("=" * 100)
    
    print(f"""
    📌 DISCOVERY:
       - {total_discovery_calls} chamadas LLM para descoberta de sites
       - {total_discovery_success} respostas recebidas ({(total_discovery_success/total_discovery_calls*100) if total_discovery_calls > 0 else 0:.1f}% sucesso)
       - {discovery['site_encontrado']} sites oficiais encontrados
       - {discovery['site_nao_encontrado']} sites não encontrados/inválidos
       - {discovery['timeout']} timeouts
    
    📌 PROFILE:
       - {total_profile_calls} chamadas LLM para montagem de perfil
       - {total_profile_success} perfis criados com sucesso ({(total_profile_success/total_profile_calls*100) if total_profile_calls > 0 else 0:.1f}%)
       - Provider principal: {'Gemini' if providers['gemini']['requests'] > providers['openai']['requests'] else 'OpenAI'}
       - Gemini: {providers['gemini']['requests']} requests, {providers['gemini']['success']} sucesso
       - OpenAI: {providers['openai']['requests']} requests, {providers['openai']['success']} sucesso
    
    📌 OBSERVAÇÕES:
       - {companies['com_url']} empresas vieram com URL direta (sem discovery LLM)
       - {companies['sem_url']} empresas precisaram de discovery
       - Taxa geral de sucesso: {(total_success/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%
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
        'chunks': chunks,
        'failures': {
            'total': total_failures,
            'timeouts': failures['timeouts'][:10],
            'errors': failures['errors'][:10],
        },
        'summary': {
            'total_llm_calls': total_llm_calls,
            'discovery_calls': total_discovery_calls,
            'profile_calls': total_profile_calls,
            'total_success': total_success,
            'total_failures': total_failures,
            'success_rate': f"{(total_success/total_llm_calls*100) if total_llm_calls > 0 else 0:.1f}%"
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

