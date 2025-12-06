"""
Debug do Discovery - Salva queries e resultados do Serper para análise.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def debug_single_company(nome_fantasia: str, razao_social: str, site_esperado: str, municipio: str = ""):
    """Debug de uma única empresa."""
    from app.services.discovery.discovery_service import search_google_serper
    
    print(f"\n{'='*80}")
    print(f"EMPRESA: {nome_fantasia}")
    print(f"RAZÃO SOCIAL: {razao_social}")
    print(f"SITE ESPERADO: {site_esperado}")
    print(f"{'='*80}")
    
    results_all = []
    
    # Query 1: Nome Fantasia
    if nome_fantasia:
        q1 = f'{nome_fantasia} {municipio} site oficial'.strip()
        print(f"\n📝 QUERY 1: {q1}")
        results1 = await search_google_serper(q1)
        print(f"   Resultados: {len(results1)}")
        results_all.extend(results1)
        
        # Mostrar top 5 resultados
        for i, r in enumerate(results1[:5]):
            link = r.get('link', '')
            title = r.get('title', '')[:50]
            # Verificar se o site esperado está nos resultados
            match = "✅ MATCH!" if site_esperado and any(s in link for s in site_esperado.split('/')[2:3]) else ""
            print(f"   {i+1}. {link[:60]} {match}")
    
    # Query 2: Razão Social
    if razao_social:
        clean_rs = razao_social.replace(" LTDA", "").replace(" S.A.", "").replace(" EIRELI", "")
        clean_rs = clean_rs.replace(" ME", "").replace(" EPP", "").strip()
        q2 = f'{clean_rs} {municipio} site oficial'.strip()
        print(f"\n📝 QUERY 2: {q2}")
        results2 = await search_google_serper(q2)
        print(f"   Resultados: {len(results2)}")
        
        for i, r in enumerate(results2[:5]):
            link = r.get('link', '')
            match = "✅ MATCH!" if site_esperado and any(s in link for s in site_esperado.split('/')[2:3]) else ""
            print(f"   {i+1}. {link[:60]} {match}")
    
    # Verificar se o site esperado está em algum resultado
    site_dominio = site_esperado.replace('http://', '').replace('https://', '').split('/')[0] if site_esperado else ''
    encontrado = any(site_dominio in r.get('link', '') for r in results_all)
    
    print(f"\n🔍 ANÁLISE:")
    print(f"   Site esperado: {site_esperado}")
    print(f"   Domínio: {site_dominio}")
    print(f"   Encontrado nos resultados: {'✅ SIM' if encontrado else '❌ NÃO'}")
    
    return {
        "empresa": nome_fantasia,
        "site_esperado": site_esperado,
        "encontrado_serper": encontrado,
        "total_resultados": len(results_all)
    }


async def debug_failed_companies():
    """Debug das empresas que falharam."""
    
    # Empresas problemáticas identificadas
    empresas_debug = [
        {"nome": "12M", "razao": "12M LTDA", "site": "http://12m.com.br/", "municipio": ""},
        {"nome": "FZ MED", "razao": "FZ MED COMERCIO DE PRODUTOS MEDICOS", "site": "http://aderefix.com", "municipio": ""},
        {"nome": "CALTECH", "razao": "CALTECH COMERCIO E SERVICOS", "site": "http://bahiamineiracao.com.br/", "municipio": ""},
        {"nome": "4M ENGENHARIA", "razao": "4M ENGENHARIA LTDA", "site": "http://4mengenharia.com.br/", "municipio": ""},
        {"nome": "CARROCERIAS ROMI", "razao": "CARROCERIAS ROMI", "site": "fabrica.carroceriasromi.com.br/carrocerias/", "municipio": ""},
        {"nome": "2B TRANSPORTES E LOGISTICAS", "razao": "2B TRANSPORTES E LOGISTICAS", "site": "http://2beng.com.br/", "municipio": ""},
        {"nome": "ALIANZA MANUTENCAO & TECNOLOGIA", "razao": "ALIANZA MANUTENCAO & TECNOLOGIA", "site": "http://allianzautomacao.com.br/", "municipio": ""},
        {"nome": "RCM DIAGNOSTICO", "razao": "RCM DIAGNOSTICO", "site": "http://amazonservice.net.br/", "municipio": ""},
    ]
    
    print("="*80)
    print("DEBUG DE DISCOVERY - EMPRESAS QUE FALHARAM")
    print("="*80)
    
    resultados = []
    
    for emp in empresas_debug:
        result = await debug_single_company(
            emp["nome"], emp["razao"], emp["site"], emp["municipio"]
        )
        resultados.append(result)
        await asyncio.sleep(0.5)  # Evitar rate limit
    
    # Salvar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"tests/reports/debug_discovery_{timestamp}.json", "w") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    # Resumo
    print("\n" + "="*80)
    print("RESUMO DO DEBUG")
    print("="*80)
    
    encontrados = sum(1 for r in resultados if r["encontrado_serper"])
    print(f"\nEmpresas analisadas: {len(resultados)}")
    print(f"Site encontrado pelo Serper: {encontrados}")
    print(f"Site NÃO encontrado pelo Serper: {len(resultados) - encontrados}")
    
    print("\n🔍 CONCLUSÃO:")
    if encontrados < len(resultados) / 2:
        print("   O problema está no SERPER - não está retornando os sites nas buscas")
    else:
        print("   O problema está no LLM - Serper encontra mas LLM não seleciona")


if __name__ == "__main__":
    asyncio.run(debug_failed_companies())

