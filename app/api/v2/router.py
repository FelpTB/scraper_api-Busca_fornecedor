"""
Router principal para API v2.
Agrupa todos os endpoints v2 em um único router.
"""
from fastapi import APIRouter
from app.api.v2 import serper, encontrar_site, scrape, montagem_perfil

# Criar router principal
router = APIRouter()

# Incluir todos os routers v2
router.include_router(serper.router, tags=["v2-serper"])
router.include_router(encontrar_site.router, tags=["v2-discovery"])
router.include_router(scrape.router, tags=["v2-scrape"])
router.include_router(montagem_perfil.router, tags=["v2-profile"])

__all__ = ["router"]

