"""
Router principal para API v2.
Agrupa todos os endpoints v2 em um único router.
"""
from fastapi import APIRouter
from app.api.v2 import serper, encontrar_site, scrape, montagem_perfil, queue_profile, queue_discovery

# Criar router principal
router = APIRouter()

# Endpoint de health check e documentação
@router.get("/")
async def v2_root():
    """Endpoint raiz da API v2 - lista endpoints disponíveis (4 processos + filas)."""
    return {
        "version": "v2",
        "status": "ok",
        "endpoints": {
            "serper": "POST /v2/serper",
            "encontrar_site": "POST /v2/encontrar_site",
            "scrape": "POST /v2/scrape",
            "montagem_perfil": "POST /v2/montagem_perfil",
            "queue_discovery_enqueue": "POST /v2/queue_discovery/enqueue",
            "queue_discovery_enqueue_batch": "POST /v2/queue_discovery/enqueue_batch",
            "queue_discovery_metrics": "GET /v2/queue_discovery/metrics",
            "queue_profile_enqueue": "POST /v2/queue_profile/enqueue",
            "queue_profile_enqueue_batch": "POST /v2/queue_profile/enqueue_batch",
            "queue_profile_metrics": "GET /v2/queue_profile/metrics",
        },
        "docs": "/docs"
    }

# Incluir todos os routers v2
router.include_router(serper.router, tags=["v2-serper"])
router.include_router(encontrar_site.router, tags=["v2-discovery"])
router.include_router(scrape.router, tags=["v2-scrape"])
router.include_router(montagem_perfil.router, tags=["v2-profile"])
router.include_router(queue_discovery.router, prefix="/queue_discovery", tags=["v2-queue-discovery"])
router.include_router(queue_profile.router, prefix="/queue_profile", tags=["v2-queue-profile"])

__all__ = ["router"]

