"""
Endpoint Encontrar Site v2 - Enfileira descoberta de site (LLM processado por worker).
Retorna imediatamente; o worker processa jobs da queue_discovery.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.v2.discovery import DiscoveryRequest, DiscoveryResponse
from app.services.queue_discovery_service import get_queue_discovery_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/encontrar_site", response_model=DiscoveryResponse)
async def encontrar_site(request: DiscoveryRequest) -> DiscoveryResponse:
    """
    Enfileira descoberta de site oficial da empresa (LLM analisa resultados Serper).
    O processamento é feito por workers que consomem a fila queue_discovery.
    Retorna imediatamente com status accepted.
    """
    try:
        logger.info(f"📥 Requisição Discovery recebida: cnpj={request.cnpj_basico}")
        queue = get_queue_discovery_service()
        enqueued = await queue.enqueue(request.cnpj_basico)
        if not enqueued:
            return DiscoveryResponse(
                success=True,
                message=f"CNPJ {request.cnpj_basico} já está na fila ou em processamento.",
                cnpj_basico=request.cnpj_basico,
                status="accepted",
            )
        return DiscoveryResponse(
            success=True,
            message=f"Requisição de descoberta de site aceita para CNPJ {request.cnpj_basico}. Processamento pela fila.",
            cnpj_basico=request.cnpj_basico,
            status="accepted",
        )
    except Exception as e:
        logger.error(f"❌ Erro ao enfileirar Discovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao enfileirar: {str(e)}")

