#!/usr/bin/env python3
"""
Análise de logs para o fluxo de discovery de sites.
Atualizado para refletir as modificações de load balancing e retry.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_discovery_logs(file_path: str):
    """Analisa logs focando no fluxo de discovery de sites"""
    
    print("=" * 100)
    print("🔍 ANÁLISE DE LOGS - DISCOVERY DE SITES (v2 - Load Balancing)")
    print("=" * 100)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # Contadores
    stats = {
        # Fluxo principal
        'analyze_company_start': 0,
        'analyze_company_com_url': 0,
        'analyze_company_sem_url': 0,
        
        # Serper
        'serper_buscas': 0,
        'serper_resultados_ok': 0,
        'serper_sem_resultados': 0,
        'serper_erros': 0,
        
        # Discovery
        'discovery_iniciado': 0,
        'discovery_site_identificado': 0,
        'discovery_sem_queries': 0,
        'discovery_sem_resultados_google': 0,
        'discovery_llm_chamadas': 0,
        'discovery_llm_success': 0,
        'discovery_llm_timeouts': 0,
        'discovery_llm_erros': 0,
        'discovery_site_encontrado': 0,
        'discovery_site_nao_encontrado': 0,
        
        # Load Balancing (NOVO)
        'load_balance_decisions': 0,
        'provider_gemini': 0,
        'provider_openai': 0,
        
        # Retry (NOVO)
        'discovery_retries': 0,
        
        # Profile LLM
        'llm_profile_chamadas': 0,
    }
    
    # URLs descobertas
    urls_descobertas = []
    
    # Detalhes de falhas
    falhas_discovery = []
    
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        timestamp = entry.get('timestamp', '') if isinstance(entry, dict) else ''
        
        # === FLUXO PRINCIPAL ===
        if '[PERF] analyze_company start' in msg:
            stats['analyze_company_start'] += 1
        
        if '[DISCOVERY] Iniciando busca para:' in msg:
            stats['discovery_iniciado'] += 1
            stats['analyze_company_sem_url'] += 1
        
        if '[DISCOVERY] Site identificado:' in msg:
            stats['discovery_site_identificado'] += 1
            match = re.search(r'\[DISCOVERY\] Site identificado: (.+)$', msg)
            if match:
                urls_descobertas.append(match.group(1))
        
        # === SERPER ===
        if 'Buscando no Google via Serper' in msg:
            stats['serper_buscas'] += 1
        
        match = re.search(r'Serper retornou (\d+) resultados', msg)
        if match:
            num = int(match.group(1))
            if num > 0:
                stats['serper_resultados_ok'] += 1
            else:
                stats['serper_sem_resultados'] += 1
        
        if 'Erro na Serper API' in msg or 'Erro na execução da busca Serper' in msg:
            stats['serper_erros'] += 1
        
        # === DISCOVERY LLM ===
        if 'Sem Nome Fantasia ou Razão Social para busca' in msg:
            stats['discovery_sem_queries'] += 1
        
        if 'Nenhum resultado encontrado no Google após múltiplas buscas' in msg:
            stats['discovery_sem_resultados_google'] += 1
        
        if 'Resultados consolidados enviados para IA' in msg:
            stats['discovery_llm_chamadas'] += 1
        
        # Decisão do LLM (com provider no log agora)
        if 'Decisão do LLM' in msg:
            stats['discovery_llm_success'] += 1
            if '"site": "nao_encontrado"' in msg or '"site":"nao_encontrado"' in msg:
                stats['discovery_site_nao_encontrado'] += 1
            elif '"site_oficial": "sim"' in msg or '"site_oficial":"sim"' in msg:
                stats['discovery_site_encontrado'] += 1
        
        # Timeout (novo formato com 35s)
        if 'Timeout na análise do LLM' in msg and 'descoberta de site' in msg:
            stats['discovery_llm_timeouts'] += 1
            falhas_discovery.append({
                'type': 'timeout',
                'message': msg[:200],
                'timestamp': timestamp
            })
        
        # Erro (novo formato)
        if 'Erro na análise do LLM' in msg and 'descoberta de site' in msg:
            stats['discovery_llm_erros'] += 1
            falhas_discovery.append({
                'type': 'error',
                'message': msg[:200],
                'timestamp': timestamp
            })
        
        # === LOAD BALANCING (NOVO) ===
        if '[LOAD_BALANCE]' in msg:
            stats['load_balance_decisions'] += 1
        
        # === RETRY (NOVO) ===
        if 'Discovery retry' in msg:
            stats['discovery_retries'] += 1
        
        # === PROVIDER TRACKING ===
        # Nas chamadas de discovery, verificar qual provider foi usado
        if 'Decisão do LLM' in msg:
            if 'Google Gemini' in msg or 'gemini' in msg.lower():
                stats['provider_gemini'] += 1
            elif 'OpenAI' in msg or 'gpt' in msg.lower():
                stats['provider_openai'] += 1
        
        # === PROFILE LLM ===
        if '[LLM_REQUEST_START]' in msg:
            stats['llm_profile_chamadas'] += 1
    
    # Calcular requisições com URL direta
    stats['analyze_company_com_url'] = stats['analyze_company_start'] - stats['analyze_company_sem_url']
    
    # === RELATÓRIO ===
    print("\n" + "=" * 100)
    print("📊 FLUXO PRINCIPAL")
    print("=" * 100)
    print(f"  Total requisições:                    {stats['analyze_company_start']}")
    print(f"  COM URL (sem discovery):              {stats['analyze_company_com_url']}")
    print(f"  SEM URL (com discovery):              {stats['analyze_company_sem_url']}")
    
    print("\n" + "=" * 100)
    print("📊 DISCOVERY")
    print("=" * 100)
    print(f"  Iniciado:                             {stats['discovery_iniciado']}")
    print(f"  Sites identificados:                  {stats['discovery_site_identificado']}")
    
    print("\n" + "=" * 100)
    print("📊 SERPER (BUSCA GOOGLE)")
    print("=" * 100)
    print(f"  Total de buscas:                      {stats['serper_buscas']}")
    print(f"  Com resultados:                       {stats['serper_resultados_ok']}")
    print(f"  Sem resultados:                       {stats['serper_sem_resultados']}")
    print(f"  Erros:                                {stats['serper_erros']}")
    
    print("\n" + "=" * 100)
    print("📊 DISCOVERY LLM (com Load Balancing)")
    print("=" * 100)
    print(f"  Chamadas LLM:                         {stats['discovery_llm_chamadas']}")
    print(f"  Respostas OK:                         {stats['discovery_llm_success']}")
    print(f"  Sites encontrados:                    {stats['discovery_site_encontrado']}")
    print(f"  Sites não encontrados:                {stats['discovery_site_nao_encontrado']}")
    print(f"  Timeouts (35s):                       {stats['discovery_llm_timeouts']}")
    print(f"  Erros:                                {stats['discovery_llm_erros']}")
    print(f"  Retries:                              {stats['discovery_retries']}")
    
    if stats['discovery_llm_chamadas'] > 0:
        success_rate = (stats['discovery_llm_success'] / stats['discovery_llm_chamadas']) * 100
        print(f"  Taxa de sucesso:                      {success_rate:.1f}%")
    
    print("\n" + "=" * 100)
    print("📊 DISTRIBUIÇÃO POR PROVIDER (Discovery)")
    print("=" * 100)
    total_provider = stats['provider_gemini'] + stats['provider_openai']
    if total_provider > 0:
        print(f"  Google Gemini:                        {stats['provider_gemini']} ({stats['provider_gemini']/total_provider*100:.1f}%)")
        print(f"  OpenAI:                               {stats['provider_openai']} ({stats['provider_openai']/total_provider*100:.1f}%)")
    else:
        print("  ⚠️  Nenhum provider identificado nos logs")
    
    print(f"\n  Load Balance Decisions:               {stats['load_balance_decisions']}")
    
    # === FALHAS ===
    if falhas_discovery:
        print("\n" + "=" * 100)
        print("⚠️  FALHAS NO DISCOVERY")
        print("=" * 100)
        print(f"  Total: {len(falhas_discovery)}")
        for f in falhas_discovery[:5]:
            print(f"    [{f['type']}] {f['message'][:100]}...")
    
    # === RESUMO ===
    print("\n" + "=" * 100)
    print("💡 RESUMO")
    print("=" * 100)
    
    total_falhas = stats['discovery_llm_timeouts'] + stats['discovery_llm_erros']
    
    print(f"""
    📌 EMPRESAS:
       - {stats['analyze_company_start']} empresas processadas
       - {stats['analyze_company_com_url']} com URL direta
       - {stats['analyze_company_sem_url']} precisaram discovery
    
    📌 DISCOVERY LLM:
       - {stats['discovery_llm_chamadas']} chamadas
       - {stats['discovery_llm_success']} respostas ({(stats['discovery_llm_success']/stats['discovery_llm_chamadas']*100) if stats['discovery_llm_chamadas'] > 0 else 0:.1f}%)
       - {total_falhas} falhas (timeout/erro)
       - {stats['discovery_retries']} retries executados
    
    📌 LOAD BALANCING:
       - Gemini: {stats['provider_gemini']} chamadas
       - OpenAI: {stats['provider_openai']} chamadas
       - {stats['load_balance_decisions']} decisões de balanceamento
    """)
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'log_file': file_path,
        'stats': stats,
        'falhas': falhas_discovery[:20],
        'urls_descobertas': urls_descobertas[:20]
    }
    
    output_file = 'analysis_discovery_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs_app.json"
    analyze_discovery_logs(file_path)
