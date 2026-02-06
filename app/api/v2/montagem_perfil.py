"""
Endpoint Montagem Perfil v2 - Enfileira job de perfil (processamento pelo worker).
Todo o processamento é feito pelo worker que consome a fila queue_profile.
Responde 202 Accepted para evitar timeout no gateway/n8n.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.schemas.v2.profile import ProfileRequest, ProfileResponse
from app.services.queue_service import get_queue_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/montagem_perfil", response_model=ProfileResponse)
async def montar_perfil(request: ProfileRequest) -> JSONResponse:
    """
    Enfileira a montagem de perfil para o cnpj_basico.
    O processamento (chunks -> LLM -> merge -> save) é feito pelo worker.
    Retorna 202 Accepted imediatamente; use GET /v2/queue_profile/metrics ou polling para status.
    """
    try:
        logger.info("Requisição Montagem Perfil recebida: cnpj=%s", request.cnpj_basico)
        queue = get_queue_service()
        await queue.enqueue(request.cnpj_basico)
        payload = ProfileResponse(
            success=True,
            message=f"Requisição de montagem de perfil aceita para CNPJ {request.cnpj_basico}. Processamento em background.",
            cnpj_basico=request.cnpj_basico,
            status="accepted",
        )
        return JSONResponse(status_code=202, content=payload.model_dump())
    except Exception as e:
        logger.error("Erro ao aceitar requisição Montagem Perfil: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao aceitar requisição: {str(e)}",
        )
