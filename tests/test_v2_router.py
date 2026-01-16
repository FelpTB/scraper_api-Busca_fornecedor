"""
Testes para app/api/v2/router.py e registro de rotas no main.py
Testa que todas as rotas v2 estão registradas corretamente.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Cria cliente de teste para a aplicação FastAPI."""
    return TestClient(app)


def test_v2_router_registrado(client):
    """Testa que router v2 está registrado no app."""
    # Verificar que rotas v2 existem
    routes = [route.path for route in app.routes]
    
    # Verificar rotas v2
    assert "/api/v2/serper" in routes
    assert "/api/v2/encontrar_site" in routes
    assert "/api/v2/scrape" in routes
    assert "/api/v2/montagem_perfil" in routes


def test_v2_serper_endpoint_existe(client):
    """Testa que endpoint /api/v2/serper existe."""
    # Tentar acessar endpoint (pode falhar por validação, mas deve existir)
    response = client.post("/api/v2/serper", json={})
    
    # Deve retornar erro de validação (não 404)
    assert response.status_code != 404
    # Pode ser 422 (validação) ou 500 (erro interno), mas não 404


def test_v2_encontrar_site_endpoint_existe(client):
    """Testa que endpoint /api/v2/encontrar_site existe."""
    response = client.post("/api/v2/encontrar_site", json={})
    
    # Deve retornar erro de validação (não 404)
    assert response.status_code != 404


def test_v2_scrape_endpoint_existe(client):
    """Testa que endpoint /api/v2/scrape existe."""
    response = client.post("/api/v2/scrape", json={})
    
    # Deve retornar erro de validação (não 404)
    assert response.status_code != 404


def test_v2_montagem_perfil_endpoint_existe(client):
    """Testa que endpoint /api/v2/montagem_perfil existe."""
    response = client.post("/api/v2/montagem_perfil", json={})
    
    # Deve retornar erro de validação (não 404)
    assert response.status_code != 404


def test_monta_perfil_original_existe(client):
    """Testa que endpoint /monta_perfil original ainda existe (retrocompatibilidade)."""
    # Verificar que rota original existe
    routes = [route.path for route in app.routes]
    
    assert "/monta_perfil" in routes


def test_root_endpoint_existe(client):
    """Testa que endpoint raiz existe."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_v2_router_tags():
    """Testa que rotas v2 têm tags corretas."""
    # Verificar tags das rotas v2
    v2_routes = [route for route in app.routes if route.path.startswith("/api/v2")]
    
    assert len(v2_routes) > 0
    
    # Verificar que todas têm tags
    for route in v2_routes:
        if hasattr(route, 'tags'):
            assert len(route.tags) > 0


def test_v2_router_prefix():
    """Testa que todas as rotas v2 têm prefixo /api/v2."""
    v2_routes = [route for route in app.routes if route.path.startswith("/api/v2")]
    
    # Deve haver pelo menos 4 rotas v2
    assert len(v2_routes) >= 4
    
    # Todas devem começar com /api/v2
    for route in v2_routes:
        assert route.path.startswith("/api/v2")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

