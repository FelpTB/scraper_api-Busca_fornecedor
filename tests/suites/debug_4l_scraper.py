import asyncio
import logging
import sys
import os

# Adicionar diretório raiz ao path
sys.path.append(os.getcwd())

from app.services.scraper.http_client import cffi_scrape_safe
# from app.services.scraper.html_parser import extract_links_and_docs # REMOVIDO
from app.services.scraper.link_selector import filter_non_html_links, prioritize_links

# Configurar logging para ver detalhes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_site():
    url = "http://4lmecanizacao.com.br/"
    print(f"\n🔍 INICIANDO DIAGNÓSTICO PARA: {url}")
    print("=" * 60)

    # 1. Teste de Acesso Básico (Raw HTML)
    print("\n1️⃣  Tentando baixar HTML da Home...")
    try:
        html, docs, links = await cffi_scrape_safe(url, proxy=None)
        
        if not html:
            print("❌ Falha: HTML vazio retornado.")
            return
            
        print(f"✅ Sucesso! HTML baixado: {len(html)} caracteres.")
        print(f"   Links brutos encontrados (parser interno): {len(links)}")
        
        # Mostrar amostra do HTML para ver estrutura de navegação
        print("\n📄 Amostra do HTML (primeiros 1000 chars):")
        print("-" * 40)
        print(html[:1000])
        print("-" * 40)
        
        # Verificar Frames/IFrames
        if "<frame" in html.lower() or "<iframe" in html.lower():
            print("\n⚠️  ALERTA: Frames/iFrames detectados no HTML!")
        
    except Exception as e:
        print(f"❌ Erro fatal ao baixar: {e}")
        return

    # 2. Análise de Links
    print("\n2️⃣  Análise Detalhada dos Links Encontrados:")
    print("-" * 60)
    
    if not links:
        print("⚠️  NENHUM link encontrado no parser padrão!")
        print("   -> Causa provável: Menu em Flash, JS puro ou Image Map.")
    else:
        print("🔗 Links Brutos (Top 10):")
        for l in list(links)[:10]:
            print(f"   - {l}")

        # Filtragem
        filtered = filter_non_html_links(links)
        print(f"\n   Links após filtro de arquivos (img/css/pdf): {len(filtered)}")
        
        prioritized = prioritize_links(filtered, url)
        print(f"   Links priorizados para visita: {len(prioritized)}")
        
        if prioritized:
            print("\n   Top Links Candidatos:")
            for l in prioritized[:5]:
                print(f"   -> {l}")
        else:
            print("\n⚠️  Todos os links foram filtrados ou considerados irrelevantes!")

    # 3. Teste de Acessibilidade de um Link Interno (se houver)
    if prioritized:
        test_link = prioritized[0]
        print(f"\n3️⃣  Testando acesso ao primeiro link interno: {test_link}")
        try:
            sub_html, _, _ = await cffi_scrape_safe(test_link, proxy=None)
            if sub_html and len(sub_html) > 100:
                print(f"✅ Sucesso! Subpágina acessível ({len(sub_html)} chars).")
            else:
                print(f"❌ Falha: Subpágina retornou vazio ou erro.")
        except Exception as e:
            print(f"❌ Erro ao acessar subpágina: {e}")

if __name__ == "__main__":
    asyncio.run(debug_site())

