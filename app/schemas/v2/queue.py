"""
Schemas Pydantic para endpoints de fila queue_profile v2.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QueueEnqueueRequest(BaseModel):
    """Request para enfileirar um CNPJ."""
    cnpj_basico: str = Field(
        ...,
        description="CNPJ básico da empresa (8 dígitos)",
        min_length=8,
        max_length=8,
    )
    model_config = ConfigDict(
        json_schema_extra={"example": {"cnpj_basico": "12345678"}}
    )


class QueueEnqueueResponse(BaseModel):
    """Resposta do enqueue (único)."""
    enqueued: bool = Field(..., description="True se o job foi inserido na fila")
    cnpj_basico: str = Field(..., description="CNPJ básico")
    message: Optional[str] = Field(None, description="Mensagem quando enqueued=False")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"enqueued": True, "cnpj_basico": "12345678", "message": None}
        }
    )


class QueueEnqueueBatchRequest(BaseModel):
    """Request para enfileirar vários CNPJs."""
    cnpj_basicos: List[str] = Field(
        default_factory=list,
        description="Lista de CNPJs básicos (8 dígitos cada)",
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"cnpj_basicos": ["12345678", "87654321"]}
        }
    )


class QueueEnqueueBatchResponse(BaseModel):
    """Resposta do enqueue em lote."""
    enqueued: int = Field(..., description="Quantidade de jobs enfileirados")
    skipped: int = Field(..., description="Quantidade já com job ativo ou inexistentes")
    model_config = ConfigDict(
        json_schema_extra={"example": {"enqueued": 2, "skipped": 0}}
    )


class QueueMetricsResponse(BaseModel):
    """Métricas da fila."""
    queued_count: int = Field(..., description="Jobs aguardando processamento")
    processing_count: int = Field(..., description="Jobs em execução")
    failed_count: int = Field(..., description="Jobs falhados definitivamente")
    oldest_job_age_seconds: Optional[float] = Field(
        None,
        description="Idade em segundos do job queued mais antigo",
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queued_count": 10,
                "processing_count": 2,
                "failed_count": 0,
                "oldest_job_age_seconds": 120.5,
            }
        }
    )
