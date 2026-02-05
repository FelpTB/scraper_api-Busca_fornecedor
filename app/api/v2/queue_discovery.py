"""
Endpoints da fila de descoberta de site (queue_discovery).
Enfileiramento e métricas; processamento é feito pelo discovery_worker.
"""
import logging
from fastapi import APIRouter, Body

from app.schemas.v2.queue import (
    QueueEnqueueRequest,
    QueueEnqueueResponse,
    QueueEnqueueBatchRequest,
    QueueEnqueueBatchResponse,
    QueueMetricsResponse,
)
from app.services.queue_discovery_service import get_queue_discovery_service
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/enqueue", response_model=QueueEnqueueResponse)
async def enqueue(request: QueueEnqueueRequest):
    """Enfileira um job de discovery para o cnpj_basico."""
    queue = get_queue_discovery_service()
    enqueued = await queue.enqueue(request.cnpj_basico)
    payload = {
        "enqueued": enqueued,
        "cnpj_basico": request.cnpj_basico,
        "message": None if enqueued else "Job ativo já existe para este CNPJ",
    }
    return JSONResponse(status_code=201 if enqueued else 200, content=payload)


@router.post("/enqueue_batch", response_model=QueueEnqueueBatchResponse)
async def enqueue_batch(
    request: QueueEnqueueBatchRequest | None = Body(None),
) -> QueueEnqueueBatchResponse:
    """Enfileira em lote os cnpj_basicos enviados (1 job por CNPJ)."""
    queue = get_queue_discovery_service()
    cnpj_list = (request.cnpj_basicos or []) if request else []
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
    """Métricas da fila de discovery (queued, processing, failed)."""
    queue = get_queue_discovery_service()
    m = await queue.get_metrics()
    return QueueMetricsResponse(
        queued_count=m["queued_count"],
        processing_count=m["processing_count"],
        failed_count=m["failed_count"],
        oldest_job_age_seconds=m.get("oldest_job_age_seconds"),
    )
