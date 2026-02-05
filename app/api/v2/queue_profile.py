"""
Endpoints da fila de perfil (queue_profile).
Enfileiramento e métricas; processamento é feito pelo worker.
"""
import logging
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.schemas.v2.queue import (
    QueueEnqueueRequest,
    QueueEnqueueResponse,
    QueueEnqueueBatchRequest,
    QueueEnqueueBatchResponse,
    QueueMetricsResponse,
)
from app.services.queue_service import get_queue_service
from app.core.database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter()
SCHEMA = "busca_fornecedor"


@router.post("/enqueue", response_model=QueueEnqueueResponse)
async def enqueue(request: QueueEnqueueRequest):
    """
    Enfileira um job de perfil para o cnpj_basico.
    Retorna 201 se enqueued, 200 com enqueued=false se já existir job ativo.
    """
    queue = get_queue_service()
    enqueued = await queue.enqueue(request.cnpj_basico)
    payload = {
        "enqueued": enqueued,
        "cnpj_basico": request.cnpj_basico,
        "message": None if enqueued else "Job ativo já existe para este CNPJ",
    }
    return JSONResponse(
        status_code=201 if enqueued else 200,
        content=payload,
    )


@router.post("/enqueue_batch", response_model=QueueEnqueueBatchResponse)
async def enqueue_batch(
    request: QueueEnqueueBatchRequest | None = Body(None),
) -> QueueEnqueueBatchResponse:
    """
    Enfileira em lote. Se cnpj_basicos for enviado, enfileira esses CNPJs.
    Se body vazio ou não enviado, enfileira CNPJs elegíveis (com chunks e sem perfil).
    """
    queue = get_queue_service()
    if request and request.cnpj_basicos:
        cnpj_list = request.cnpj_basicos
    else:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT DISTINCT c.cnpj_basico
                FROM "{SCHEMA}".scraped_chunks c
                LEFT JOIN "{SCHEMA}".company_profile p ON p.cnpj = c.cnpj_basico
                WHERE p.id IS NULL
                """
            )
            cnpj_list = [r["cnpj_basico"] for r in rows]

    enqueued = 0
    skipped = 0
    for cnpj_basico in cnpj_list:
        if await queue.enqueue(cnpj_basico):
            enqueued += 1
        else:
            skipped += 1

    return QueueEnqueueBatchResponse(enqueued=enqueued, skipped=skipped)


@router.get("/metrics", response_model=QueueMetricsResponse)
async def get_metrics() -> QueueMetricsResponse:
    """Retorna métricas da fila (queued, processing, failed, oldest_job_age)."""
    queue = get_queue_service()
    m = await queue.get_metrics()
    return QueueMetricsResponse(
        queued_count=m["queued_count"],
        processing_count=m["processing_count"],
        failed_count=m["failed_count"],
        oldest_job_age_seconds=m.get("oldest_job_age_seconds"),
    )
