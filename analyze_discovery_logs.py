#!/usr/bin/env python3
"""
Análise de logs para identificar discrepância entre empresas processadas
e chamadas de LLM no discovery.

Objetivo: Encontrar por que 250 empresas resultaram em apenas 201 chamadas LLM
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

def analyze_discovery_logs(file_path: str):
    """Analisa logs focando no fluxo de discovery de sites"""
    
    print("=" * 80)
    print("ANÁLISE DE LOGS - DISCOVERY DE SITES")
    print("=" * 80)
    
    # Carregar logs
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📊 Total de entradas de log: {len(data):,}")
    
    # Contadores
    stats = {
        # Fluxo principal
        'analyze_company_start': 0,
        'analyze_company_com_url': 0,  # Requisições que JÁ vieram com URL
        'analyze_company_sem_url': 0,  # Requisições que precisaram discovery
        
        # Serper
        'serper_buscas': 0,
        'serper_resultados_ok': 0,
        'serper_sem_resultados': 0,
        'serper_erros': 0,
        
        # Discovery
        'discovery_iniciado': 0,  # [DISCOVERY] Iniciando busca
        'discovery_site_identificado': 0,  # [DISCOVERY] Site identificado
        'discovery_sem_queries': 0,
        'discovery_sem_resultados_google': 0,
        'discovery_llm_chamadas': 0,
        'discovery_llm_success': 0,
        'discovery_llm_timeouts': 0,
        'discovery_llm_erros': 0,
        'discovery_site_encontrado': 0,
        'discovery_site_nao_encontrado': 0,
        
        # Profile LLM
        'llm_profile_chamadas': 0,
    }
    
    # PRIMEIRA PASSAGEM: Contar todos os padrões de mensagens
    all_messages = []
    for entry in data:
        msg = entry.get('message', '') if isinstance(entry, dict) else str(entry)
        all_messages.append(msg)
    
    # URLs processadas diretamente (sem discovery)
    urls_diretas = []
    urls_descobertas = []
    
    for msg in all_messages:
        # ========================================
        # FLUXO PRINCIPAL (main.py)
        # ========================================
        
        # Início do processamento
        if '[PERF] analyze_company start url=' in msg:
            stats['analyze_company_start'] += 1
        
        # Discovery iniciado (significa que NÃO tinha URL)
        if '[DISCOVERY] Iniciando busca para:' in msg:
            stats['discovery_iniciado'] += 1
            stats['analyze_company_sem_url'] += 1
        
        # Site identificado pelo discovery
        if '[DISCOVERY] Site identificado:' in msg:
            stats['discovery_site_identificado'] += 1
            match = re.search(r'\[DISCOVERY\] Site identificado: (.+)$', msg)
            if match:
                urls_descobertas.append(match.group(1))
        
        # ========================================
        # SERPER (discovery.py)
        # ========================================
        
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
        
        # ========================================
        # DISCOVERY LLM (discovery.py)
        # ========================================
        
        if 'Sem Nome Fantasia ou Razão Social para busca' in msg:
            stats['discovery_sem_queries'] += 1
        
        if 'Nenhum resultado encontrado no Google após múltiplas buscas' in msg:
            stats['discovery_sem_resultados_google'] += 1
        
        if 'Resultados consolidados enviados para IA' in msg:
            stats['discovery_llm_chamadas'] += 1
        
        if 'Decisão do LLM' in msg:
            stats['discovery_llm_success'] += 1
            if '"site_oficial": "sim"' in msg or '"site_oficial":"sim"' in msg:
                stats['discovery_site_encontrado'] += 1
            elif '"site_oficial": "nao"' in msg or '"site_oficial":"nao"' in msg or 'nao_encontrado' in msg:
                stats['discovery_site_nao_encontrado'] += 1
        
        if 'Timeout na análise do LLM para descoberta de site' in msg:
            stats['discovery_llm_timeouts'] += 1
        
        if 'Erro na análise do LLM para descoberta de site' in msg:
            stats['discovery_llm_erros'] += 1
        
        if 'Site não encontrado ou não oficial' in msg:
            stats['discovery_site_nao_encontrado'] += 1
        
        # ========================================
        # LLM PROFILE (llm.py)
        # ========================================
        
        if '[LLM_REQUEST_START]' in msg:
            stats['llm_profile_chamadas'] += 1
    
    # Calcular requisições com URL direta
    stats['analyze_company_com_url'] = stats['analyze_company_start'] - stats['analyze_company_sem_url']
    
    # Relatório
    print("\n" + "=" * 80)
    print("📊 FLUXO PRINCIPAL (main.py - analyze_company)")
    print("=" * 80)
    print(f"  Total requisições processadas:        {stats['analyze_company_start']}")
    print(f"  Requisições COM URL (sem discovery):  {stats['analyze_company_com_url']}")
    print(f"  Requisições SEM URL (com discovery):  {stats['analyze_company_sem_url']}")
    
    print("\n" + "=" * 80)
    print("📊 DISCOVERY (find_company_website)")
    print("=" * 80)
    print(f"  [DISCOVERY] Iniciando busca:          {stats['discovery_iniciado']}")
    print(f"  [DISCOVERY] Site identificado:        {stats['discovery_site_identificado']}")
    
    print("\n" + "=" * 80)
    print("📊 SERPER (BUSCA GOOGLE)")
    print("=" * 80)
    print(f"  Total de buscas Serper:               {stats['serper_buscas']}")
    print(f"  Buscas com resultados > 0:            {stats['serper_resultados_ok']}")
    print(f"  Buscas com 0 resultados:              {stats['serper_sem_resultados']}")
    print(f"  Erros na API Serper:                  {stats['serper_erros']}")
    
    print("\n" + "=" * 80)
    print("📊 DISCOVERY LLM (análise de resultados)")
    print("=" * 80)
    print(f"  Saída: Sem queries válidas:           {stats['discovery_sem_queries']}")
    print(f"  Saída: Sem resultados Google:         {stats['discovery_sem_resultados_google']}")
    print(f"  Chamadas LLM para discovery:          {stats['discovery_llm_chamadas']}")
    print(f"  LLM respostas bem-sucedidas:          {stats['discovery_llm_success']}")
    print(f"  LLM Timeouts:                         {stats['discovery_llm_timeouts']}")
    print(f"  LLM Erros:                            {stats['discovery_llm_erros']}")
    print(f"  Sites oficiais encontrados:           {stats['discovery_site_encontrado']}")
    print(f"  Sites não oficiais/inválidos:         {stats['discovery_site_nao_encontrado']}")
    
    print("\n" + "=" * 80)
    print("📊 LLM PROFILE (analyze_content)")
    print("=" * 80)
    print(f"  Chamadas LLM para perfil:             {stats['llm_profile_chamadas']}")
    
    # Análise da discrepância
    print("\n" + "=" * 80)
    print("🔍 ANÁLISE DA DISCREPÂNCIA")
    print("=" * 80)
    
    esperado = 250
    total_processado = stats['analyze_company_start']
    discovery_iniciado = stats['discovery_iniciado']
    discovery_llm = stats['discovery_llm_chamadas']
    
    print(f"\n  🎯 CENÁRIO ESPERADO:")
    print(f"     Empresas esperadas:                {esperado}")
    
    print(f"\n  📊 REALIDADE DOS LOGS:")
    print(f"     Total requisições processadas:     {total_processado}")
    print(f"     Requisições COM URL (diretas):     {stats['analyze_company_com_url']}")
    print(f"     Requisições SEM URL (discovery):   {stats['analyze_company_sem_url']}")
    
    print(f"\n  📋 FLUXO DO DISCOVERY:")
    print(f"     Discovery iniciado:                {discovery_iniciado}")
    print(f"     -> Sem queries (exit):             {stats['discovery_sem_queries']}")
    print(f"     -> Sem resultados Google (exit):   {stats['discovery_sem_resultados_google']}")
    print(f"     -> Chamadas LLM discovery:         {discovery_llm}")
    print(f"        -> Sucesso:                     {stats['discovery_llm_success']}")
    print(f"        -> Timeout:                     {stats['discovery_llm_timeouts']}")
    print(f"        -> Erro:                        {stats['discovery_llm_erros']}")
    
    # Verificar consistência
    print(f"\n  ⚠️  VERIFICAÇÃO DE CONSISTÊNCIA:")
    
    discovery_exits = (
        stats['discovery_sem_queries'] + 
        stats['discovery_sem_resultados_google'] + 
        stats['discovery_llm_success'] +
        stats['discovery_llm_timeouts'] +
        stats['discovery_llm_erros']
    )
    print(f"     Discovery saídas totais:           {discovery_exits}")
    print(f"     Discovery iniciado:                {discovery_iniciado}")
    if discovery_exits != discovery_iniciado:
        print(f"     ⚠️  DIFERENÇA: {discovery_iniciado - discovery_exits} (possível saída não mapeada)")
    
    # Conclusão
    print("\n" + "=" * 80)
    print("💡 CONCLUSÃO")
    print("=" * 80)
    
    if stats['analyze_company_com_url'] > 0:
        print(f"\n  ✅ CAUSA IDENTIFICADA:")
        print(f"     {stats['analyze_company_com_url']} requisições JÁ VIERAM COM URL.")
        print(f"     Para essas requisições, find_company_website() NÃO É CHAMADA.")
        print(f"     Portanto, NÃO há chamada LLM de discovery para elas.")
    
    print(f"\n  📊 RESUMO FINAL:")
    print(f"     - {stats['analyze_company_com_url']} empresas com URL direta (sem discovery LLM)")
    print(f"     - {stats['analyze_company_sem_url']} empresas precisaram discovery")
    print(f"       -> {stats['discovery_llm_chamadas']} chamadas LLM discovery")
    print(f"       -> {stats['discovery_site_identificado']} sites identificados com sucesso")
    
    # URLs descobertas
    if urls_descobertas:
        print(f"\n  🔗 Primeiras 5 URLs descobertas pelo discovery:")
        for url in urls_descobertas[:5]:
            print(f"     - {url}")
    
    # Salvar resultado
    result = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'conclusion': {
            'total_requisicoes': total_processado,
            'requisicoes_com_url': stats['analyze_company_com_url'],
            'requisicoes_sem_url': stats['analyze_company_sem_url'],
            'discovery_llm_calls': discovery_llm,
            'explicacao': f"{stats['analyze_company_com_url']} requisições já vieram com URL, "
                         f"portanto find_company_website() não foi chamada para elas."
        },
        'urls_descobertas': urls_descobertas[:20]
    }
    
    output_file = 'analysis_discovery_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultado salvo em: {output_file}")
    
    return result

if __name__ == "__main__":
    analyze_discovery_logs("logs_app.json")
