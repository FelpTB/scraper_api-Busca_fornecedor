#!/usr/bin/env python3
"""Teste de 10 empresas para validar distribuição de LLM providers."""

import asyncio
import aiohttp
import time
from datetime import datetime

# Configuração
API_URL = "http://localhost:8000/analyze"
API_TOKEN = "buscafornecedor-api"

# 10 empresas de teste (URLs conhecidas)
TEST_COMPANIES = [
    {"url": "https://www.ambev.com.br"},
    {"url": "https://www.vale.com"},
    {"url": "https://www.petrobras.com.br"},
    {"url": "https://www.itau.com.br"},
    {"url": "https://www.bradesco.com.br"},
    {"url": "https://www.magazineluiza.com.br"},
    {"url": "https://www.natura.com.br"},
    {"url": "https://www.embraer.com"},
    {"url": "https://www.gerdau.com"},
    {"url": "https://www.suzano.com.br"},
]

async def analyze_company(session, company, idx):
    """Faz requisição para uma empresa"""
    start = time.perf_counter()
    try:
        async with session.post(
            API_URL,
            json=company,
            headers={"X-API-Key": API_TOKEN}
        ) as response:
            status = response.status
            data = await response.json()
            duration = time.perf_counter() - start
            
            return {
                "idx": idx,
                "url": company.get("url"),
                "status": status,
                "duration": duration,
                "success": status == 200,
                "company_name": data.get("company_name", "N/A") if status == 200 else f"ERRO: {data.get('detail', 'unknown')[:30]}"
            }
    except Exception as e:
        duration = time.perf_counter() - start
        return {
            "idx": idx,
            "url": company.get("url"),
            "status": 0,
            "duration": duration,
            "success": False,
            "error": str(e)[:50]
        }

async def run_test():
    """Executa teste de 10 empresas em paralelo"""
    print("=" * 70)
    print(f"🧪 TESTE DE DISTRIBUIÇÃO LLM - {len(TEST_COMPANIES)} EMPRESAS")
    print(f"   Início: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    
    connector = aiohttp.TCPConnector(limit=20)
    timeout = aiohttp.ClientTimeout(total=300)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        start_time = time.perf_counter()
        
        tasks = [
            analyze_company(session, company, i+1)
            for i, company in enumerate(TEST_COMPANIES)
        ]
        
        print("\n📡 Enviando requisições em paralelo...")
        print("   (aguarde ~1-2 minutos)\n")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.perf_counter() - start_time
    
    print("\n" + "=" * 70)
    print("                      📊 RESULTADOS")
    print("=" * 70)
    
    success_count = 0
    total_duration = 0
    
    for r in results:
        if isinstance(r, Exception):
            print(f"  ❌ Exception: {r}")
        else:
            status_icon = "✅" if r["success"] else "❌"
            name = r.get('company_name', 'N/A')
            if len(name) > 25:
                name = name[:22] + "..."
            print(f"  {status_icon} #{r['idx']:2d} | {r['duration']:5.1f}s | {name}")
            if r["success"]:
                success_count += 1
            total_duration += r["duration"]
    
    print("\n" + "-" * 70)
    print(f"  📈 Sucesso: {success_count}/{len(TEST_COMPANIES)} ({100*success_count/len(TEST_COMPANIES):.0f}%)")
    print(f"  ⏱️  Tempo total (paralelo): {total_time:.1f}s")
    print(f"  ⚡ Tempo médio/empresa: {total_duration/len(TEST_COMPANIES):.1f}s")
    print("=" * 70)
    
    print("\n✅ Verifique server_test.log para ver a distribuição entre providers!")

if __name__ == "__main__":
    asyncio.run(run_test())

