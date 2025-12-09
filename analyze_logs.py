#!/usr/bin/env python3
"""
Analisador de Logs da API B2B Flash Profiler
Gera estatísticas detalhadas de execução
NOTA: Lida com logs truncados pelo Railway rate limit
"""

import json
import re
from datetime import datetime
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple
import statistics

def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse timestamp do log"""
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str.split(',')[0], "%Y-%m-%d %H:%M:%S")
    except:
        try:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00').split('.')[0])
        except:
            return None

def get_message_and_attrs(log_entry: dict) -> Tuple[str, str, str, str]:
    """Extrai message, level, timestamp e module do log entry"""
    if 'attributes' in log_entry:
        attrs = log_entry.get('attributes', {})
        message = log_entry.get('message', '')
        level = attrs.get('level', 'info').upper()
        timestamp = attrs.get('timestamp', '')
        module = attrs.get('module', '')
        return message, level, timestamp, module
    
    return (
        log_entry.get('message', ''),
        log_entry.get('level', 'INFO').upper(),
        log_entry.get('timestamp', ''),
        log_entry.get('module', '')
    )

def extract_cnpj(message: str) -> str:
    """Extrai CNPJ da mensagem"""
    match = re.search(r'\[CNPJ:\s*(\d+)', message)
    if match:
        return match.group(1)
    return ""

def analyze_logs(log_file: str):
    """Analisa arquivo de logs e gera estatísticas"""
    
    print(f"📂 Carregando logs de: {log_file}")
    
    with open(log_file, 'r') as f:
        logs = json.load(f)
    
    total_logs = len(logs)
    print(f"📊 Total de linhas de log: {total_logs}")
    
    # Estruturas de rastreamento por empresa
    company_events = defaultdict(lambda: {
        'discovery_start': False,
        'site_found': False,
        'scrape_start': False,
        'scrape_ok': False,
        'llm_start': False,
        'llm_ok': False,
        'merge_ok': False,
        'errors': [],
        'llm_providers': [],
        'chunks': 0,
        'start_time': None,
        'end_time': None
    })
    
    # Contadores globais
    llm_provider_calls = Counter()
    llm_provider_success = Counter()
    llm_provider_failures = Counter()
    
    error_types = Counter()
    serper_error_count = 0
    scrape_error_count = 0
    llm_error_count = 0
    
    total_chunks_processed = 0
    retries = 0
    rate_limits = 0
    
    # Timestamps
    first_ts = None
    last_ts = None
    
    # Detectar logs truncados
    truncated_logs = 0
    
    for log in logs:
        message, level, ts_str, module = get_message_and_attrs(log)
        ts = parse_timestamp(ts_str)
        
        # Ignorar logs de sistema
        if any(x in message for x in ["Starting Container", "Running on http", "HealthMonitor"]):
            continue
        
        # Verificar truncamento (Railway rate limit)
        if "Railway rate limit" in message:
            truncated_logs += 1
            continue
        
        if ts:
            if not first_ts:
                first_ts = ts
            last_ts = ts
        
        cnpj = extract_cnpj(message)
        
        if cnpj:
            ce = company_events[cnpj]
            if ts:
                if not ce['start_time']:
                    ce['start_time'] = ts
                ce['end_time'] = ts
        
        # === DISCOVERY ===
        if "[DISCOVERY]" in message:
            if "Iniciando busca" in message and cnpj:
                company_events[cnpj]['discovery_start'] = True
            elif "Site encontrado" in message or "encontrado:" in message:
                if cnpj:
                    company_events[cnpj]['site_found'] = True
        
        # === SERPER ERRORS ===
        if "Serper erro" in message or "serper" in message.lower() and level == "ERROR":
            serper_error_count += 1
            error_types["serper_error"] += 1
            if cnpj:
                company_events[cnpj]['errors'].append("serper_error")
        
        # === SCRAPE ===
        if "SCRAPE" in message or module == "scraper_service" or "scrape" in message.lower():
            if "Iniciando" in message and cnpj:
                company_events[cnpj]['scrape_start'] = True
            elif "concluído" in message.lower() or "URLs scraped" in message:
                if cnpj:
                    company_events[cnpj]['scrape_ok'] = True
            
            if level == "ERROR" or "falhou" in message.lower() or "Failed" in message:
                scrape_error_count += 1
                error_type = "scrape_generic"
                
                if "DNS" in message:
                    error_type = "dns_error"
                elif "SSL" in message:
                    error_type = "ssl_error"
                elif "403" in message:
                    error_type = "forbidden_403"
                elif "404" in message:
                    error_type = "not_found_404"
                elif "500" in message or "502" in message or "503" in message:
                    error_type = "server_error_5xx"
                elif "timeout" in message.lower():
                    error_type = "timeout"
                elif "cloudflare" in message.lower():
                    error_type = "cloudflare"
                elif "javascript" in message.lower():
                    error_type = "javascript_required"
                
                error_types[error_type] += 1
                if cnpj:
                    company_events[cnpj]['errors'].append(error_type)
        
        # === LLM ===
        if "LLM" in message or module in ["llm_service", "provider_manager"]:
            # Provider calls
            for provider in ["OpenRouter3", "OpenRouter2", "OpenRouter", "Google Gemini", "OpenAI"]:
                if provider in message:
                    if "OK com" in message or "Sucesso com" in message:
                        llm_provider_calls[provider] += 1
                        llm_provider_success[provider] += 1
                        if cnpj:
                            company_events[cnpj]['llm_providers'].append(provider)
                            company_events[cnpj]['llm_ok'] = True
                    elif level == "ERROR" or "falhou" in message.lower():
                        llm_provider_calls[provider] += 1
                        llm_provider_failures[provider] += 1
            
            if level == "ERROR" or "falhou" in message.lower():
                llm_error_count += 1
                if "rate" in message.lower() or "429" in message:
                    error_types["llm_rate_limit"] += 1
                    rate_limits += 1
                elif "timeout" in message.lower():
                    error_types["llm_timeout"] += 1
                else:
                    error_types["llm_generic"] += 1
                    
                if cnpj:
                    company_events[cnpj]['errors'].append("llm_error")
            
            if "retry" in message.lower() or "Retrying" in message:
                retries += 1
        
        # === CHUNKS ===
        if "Chunk" in message and "OK" in message:
            total_chunks_processed += 1
            match = re.search(r'Chunk \d+/(\d+)', message)
            if match and cnpj:
                chunks = int(match.group(1))
                if chunks > company_events[cnpj]['chunks']:
                    company_events[cnpj]['chunks'] = chunks
        
        # === MERGE (SUCESSO FINAL) ===
        if "Merge concluído" in message:
            if cnpj:
                company_events[cnpj]['merge_ok'] = True
            elif not cnpj:
                # Mensagem sem CNPJ - contar mesmo assim
                pass
    
    # === CALCULAR ESTATÍSTICAS ===
    total_companies = len(company_events)
    
    # Contar por estado
    discovery_started = sum(1 for c in company_events.values() if c['discovery_start'])
    sites_found = sum(1 for c in company_events.values() if c['site_found'])
    scrape_started = sum(1 for c in company_events.values() if c['scrape_start'])
    scrape_success = sum(1 for c in company_events.values() if c['scrape_ok'])
    llm_success = sum(1 for c in company_events.values() if c['llm_ok'])
    merge_success = sum(1 for c in company_events.values() if c['merge_ok'])
    
    # Inferir sucesso: se teve LLM OK, provavelmente sucesso
    inferred_success = sum(1 for c in company_events.values() if c['llm_ok'] and not c['errors'])
    
    # Tempos de processamento
    processing_times = []
    for cnpj, ce in company_events.items():
        if ce['start_time'] and ce['end_time']:
            delta = (ce['end_time'] - ce['start_time']).total_seconds()
            if delta > 0:
                processing_times.append(delta)
    
    # === GERAR RELATÓRIO ===
    print("\n" + "="*80)
    print("📊 RELATÓRIO DE ANÁLISE DE LOGS - API B2B FLASH PROFILER")
    print("="*80)
    
    if truncated_logs > 0:
        print(f"\n⚠️  AVISO: {truncated_logs} logs truncados pelo Railway rate limit (500 logs/sec)")
        print("   Algumas estatísticas podem estar incompletas.")
    
    # Período
    if first_ts and last_ts:
        duration = (last_ts - first_ts).total_seconds()
        print(f"\n⏱️  PERÍODO DE PROCESSAMENTO:")
        print(f"   Início: {first_ts}")
        print(f"   Fim:    {last_ts}")
        print(f"   Duração: {duration:.1f}s ({duration/60:.1f} min)")
        if inferred_success > 0 and duration > 0:
            print(f"   Throughput: {inferred_success / (duration/60):.1f} empresas/min")
    
    # Resumo
    print(f"\n📈 RESUMO GERAL:")
    print(f"   Empresas identificadas: {total_companies}")
    print(f"   Discovery iniciado: {discovery_started}")
    print(f"   Sites encontrados: {sites_found} ({sites_found/max(total_companies,1)*100:.1f}%)")
    print(f"   Scrape iniciado: {scrape_started}")
    print(f"   Scrape sucesso: {scrape_success}")
    print(f"   LLM processado: {llm_success}")
    print(f"   Merge concluído: {merge_success}")
    print(f"   ")
    print(f"   ✅ Sucesso inferido: {inferred_success} ({inferred_success/max(total_companies,1)*100:.1f}%)")
    print(f"   ❌ Falhas inferidas: {total_companies - inferred_success} ({(total_companies - inferred_success)/max(total_companies,1)*100:.1f}%)")
    
    # Erros
    print(f"\n❌ ERROS POR TIPO ({sum(error_types.values())} total):")
    for error, count in error_types.most_common(15):
        print(f"   {error:25s}: {count:4d}")
    
    # Resumo de erros por categoria
    print(f"\n📊 ERROS POR CATEGORIA:")
    print(f"   🔍 Serper/Discovery: {serper_error_count}")
    print(f"   🕷️  Scrape: {scrape_error_count}")
    print(f"   🤖 LLM: {llm_error_count}")
    
    # LLM Distribution
    print(f"\n📊 DISTRIBUIÇÃO DE CHAMADAS LLM:")
    total_llm = sum(llm_provider_calls.values())
    if total_llm > 0:
        print(f"   {'Provider':15s} | {'Calls':>6s} | {'%':>6s} | {'✅ OK':>6s} | {'❌ Fail':>6s} | {'Taxa':>6s}")
        print(f"   {'-'*15}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")
        for provider in ["OpenRouter", "OpenRouter2", "OpenRouter3", "Google Gemini", "OpenAI"]:
            calls = llm_provider_calls.get(provider, 0)
            success = llm_provider_success.get(provider, 0)
            failures = llm_provider_failures.get(provider, 0)
            pct = calls / total_llm * 100 if total_llm > 0 else 0
            rate = success / calls * 100 if calls > 0 else 0
            print(f"   {provider:15s} | {calls:6d} | {pct:5.1f}% | {success:6d} | {failures:6d} | {rate:5.1f}%")
        print(f"   {'-'*15}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")
        print(f"   {'TOTAL':15s} | {total_llm:6d} |")
    
    # Tempos
    print(f"\n⏱️  DISTRIBUIÇÃO DE TEMPO DE PROCESSAMENTO:")
    if processing_times:
        print(f"   Empresas com tempo medido: {len(processing_times)}")
        print(f"   Mínimo:  {min(processing_times):.1f}s")
        print(f"   Máximo:  {max(processing_times):.1f}s")
        print(f"   Média:   {statistics.mean(processing_times):.1f}s")
        print(f"   Mediana: {statistics.median(processing_times):.1f}s")
        if len(processing_times) > 1:
            print(f"   Desvio:  {statistics.stdev(processing_times):.1f}s")
        
        # Faixas
        print(f"\n   📊 Distribuição por faixas:")
        ranges = [(0, 10), (10, 30), (30, 60), (60, 120), (120, 180), (180, 300), (300, float('inf'))]
        for low, high in ranges:
            count = sum(1 for t in processing_times if low <= t < high)
            pct = count / len(processing_times) * 100
            if high == float('inf'):
                label = f">= {low}s"
            else:
                label = f"{low:3d}-{high:3d}s"
            bar = "█" * int(pct / 2)
            print(f"   {label:10s}: {count:4d} ({pct:5.1f}%) {bar}")
    else:
        print("   Não foi possível calcular tempos")
    
    # Chunks
    print(f"\n📦 ESTATÍSTICAS DE CHUNKS:")
    print(f"   Total processados: {total_chunks_processed}")
    chunks_list = [c['chunks'] for c in company_events.values() if c['chunks'] > 0]
    if chunks_list:
        print(f"   Média por empresa: {statistics.mean(chunks_list):.1f}")
        print(f"   Máximo: {max(chunks_list)}")
    
    # Retries
    print(f"\n🔄 RETRIES E PROBLEMAS:")
    print(f"   Total retries: {retries}")
    print(f"   Rate limits: {rate_limits}")
    
    # Top empresas mais lentas
    sorted_companies = sorted(
        [(cnpj, c) for cnpj, c in company_events.items() if c['start_time'] and c['end_time']],
        key=lambda x: (x[1]['end_time'] - x[1]['start_time']).total_seconds(),
        reverse=True
    )[:10]
    
    if sorted_companies:
        print(f"\n🐢 TOP 10 EMPRESAS MAIS LENTAS:")
        for i, (cnpj, ce) in enumerate(sorted_companies, 1):
            duration = (ce['end_time'] - ce['start_time']).total_seconds()
            status = "✅" if ce['llm_ok'] and not ce['errors'] else "❌"
            print(f"   {i:2d}. {status} {duration:6.1f}s | {cnpj}")
    
    # Empresas com erros
    error_companies = [(cnpj, ce) for cnpj, ce in company_events.items() if ce['errors']]
    if error_companies:
        print(f"\n❌ EMPRESAS COM ERROS ({len(error_companies)}):")
        for cnpj, ce in error_companies[:15]:
            errors = ", ".join(ce['errors'][:3])
            print(f"   • {cnpj} | {errors}")
        if len(error_companies) > 15:
            print(f"   ... e mais {len(error_companies) - 15}")
    
    print("\n" + "="*80)
    print("✅ ANÁLISE CONCLUÍDA")
    print("="*80)
    
    return {
        "total_companies": total_companies,
        "inferred_success": inferred_success,
        "inferred_failed": total_companies - inferred_success,
        "success_rate": inferred_success / max(total_companies, 1) * 100,
        "llm_distribution": dict(llm_provider_calls),
        "error_types": dict(error_types),
        "processing_times": processing_times
    }

if __name__ == "__main__":
    import sys
    log_file = sys.argv[1] if len(sys.argv) > 1 else "log_500_new.json"
    
    try:
        stats = analyze_logs(log_file)
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {log_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao parsear JSON: {e}")
        sys.exit(1)
