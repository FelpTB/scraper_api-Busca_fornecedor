"""
Endpoint Montagem Perfil v2 - Enfileira job de perfil (processamento pelo worker).
Todo o processamento é feito pelo worker que consome a fila queue_profile.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.v2.profile import ProfileRequest, ProfileResponse
from app.services.queue_service import get_queue_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/montagem_perfil", response_model=ProfileResponse)
async def montar_perfil(request: ProfileRequest) -> ProfileResponse:
    """
    Enfileira a montagem de perfil para o cnpj_basico.
    O processamento (chunks -> LLM -> merge -> save) é feito pelo worker.
    """
    try:
        logger.info("Requisição Montagem Perfil recebida: cnpj=%s", request.cnpj_basico)
        queue = get_queue_service()
        await queue.enqueue(request.cnpj_basico)
        return ProfileResponse(
            success=True,
            message=f"Requisição de montagem de perfil aceita para CNPJ {request.cnpj_basico}. Processamento em background.",
            cnpj_basico=request.cnpj_basico,
            status="accepted",
        )
    except Exception as e:
        logger.error("Erro ao aceitar requisição Montagem Perfil: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao aceitar requisição: {str(e)}",
        )
