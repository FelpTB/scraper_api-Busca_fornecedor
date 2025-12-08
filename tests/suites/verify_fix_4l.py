import asyncio
import aiohttp
import json
import os

API_URL = "http://localhost:8000/analyze"
API_KEY = os.getenv("API_ACCESS_TOKEN", "buscafornecedor-api")

async def test_4l():
    payload = {
        "url": "http://4lmecanizacao.com.br/",
        "razao_social": "4L Mecanizacao Agricola"
    }
    
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    print(f"🚀 Iniciando teste para {payload['url']}...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=payload, headers=headers, timeout=300) as response:
                if response.status == 200:
                    result = await response.json()
                    print("\n✅ SUCESSO! Perfil gerado:")
                    print("-" * 50)
                    
                    # Exibir campos principais
                    identity = result.get("identity", {})
                    print(f"Nome: {identity.get('company_name')}")
                    print(f"Descrição: {identity.get('description')}")
                    
                    offerings = result.get("offerings", {})
                    print(f"\nServiços: {offerings.get('services')}")
                    
                    sources = result.get("sources", [])
                    print(f"\n📚 Fontes visitadas ({len(sources)}):")
                    for s in sources:
                        print(f"   - {s}")
                        
                    # Verificar se visitou subpáginas
                    if len(sources) > 3: # Geralmente google + home + index + subpages
                        print("\n✅ SUCESSO: Visitou subpáginas!")
                    else:
                        print("\n⚠️ AVISO: Parece ter visitado poucas páginas. Verifique a lista acima.")
                        
                else:
                    print(f"❌ ERRO API: {response.status}")
                    text = await response.text()
                    print(text)
        except Exception as e:
            print(f"❌ ERRO DE CONEXÃO: {e}")

if __name__ == "__main__":
    asyncio.run(test_4l())

