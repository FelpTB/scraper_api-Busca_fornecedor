"""
Serviço de fila durável para processamento de perfil (queue_profile).
Baseado em Postgres: enqueue, claim, ack, fail, métricas.
1 job = 1 empresa = todos os chunks = 1 perfil.
"""
import logging
from typing import Optional, Tuple, Dict, Any, List

import asyncpg
from app.core.database import get_pool

logger = logging.getLogger(__name__)

SCHEMA = "busca_fornecedor"


class QueueProfileService:
    """Operações assíncronas sobre busca_fornecedor.queue_profile."""

    async def enqueue(self, cnpj_basico: str) -> bool:
        """
        Insere job na fila se não existir job ativo para o cnpj_basico.
        Retorna True se inseriu, False se já havia job ativo.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            check = await conn.fetchrow(
                f"""
                SELECT id FROM "{SCHEMA}".queue_profile
                WHERE cnpj_basico = $1 AND status IN ('queued', 'processing')
                LIMIT 1
                """,
                cnpj_basico,
            )
            if check:
                logger.debug(f"Queue: job ativo já existe para cnpj_basico={cnpj_basico}")
                return False
            try:
                await conn.execute(
                    f"""
                    INSERT INTO "{SCHEMA}".queue_profile (cnpj_basico)
                    VALUES ($1)
                    """,
                    cnpj_basico,
                )
                logger.info(f"Queue: enqueued cnpj_basico={cnpj_basico}")
                return True
            except asyncpg.UniqueViolationError:
                logger.debug(f"Queue: duplicate (race) cnpj_basico={cnpj_basico}")
                return False

    async def claim(self, worker_id: str, limit: int = 1) -> List[Tuple[int, str]]:
        """
        Reserva até `limit` jobs queued com available_at <= now().
        Retorna lista de (id, cnpj_basico). Usa FOR UPDATE SKIP LOCKED.
        """
        if limit < 1:
            return []
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    f"""
                    WITH picked AS (
                        SELECT id FROM "{SCHEMA}".queue_profile
                        WHERE status = 'queued' AND available_at <= now()
                        ORDER BY id
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE "{SCHEMA}".queue_profile q
                    SET status = 'processing',
                        locked_at = now(),
                        locked_by = $1,
                        updated_at = now()
                    FROM picked
                    WHERE q.id = picked.id
                    RETURNING q.id, q.cnpj_basico
                    """,
                    worker_id,
                    limit,
                )
                return [(r["id"], r["cnpj_basico"]) for r in rows]

    async def ack(self, job_id: int) -> None:
        """Marca job como concluído com sucesso."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE "{SCHEMA}".queue_profile
                SET status = 'done',
                    last_error = NULL,
                    updated_at = now()
                WHERE id = $1
                """,
                job_id,
            )
            logger.debug(f"Queue: ack job_id={job_id}")

    async def fail(self, job_id: int, error_message: str) -> None:
        """
        Incrementa attempts; se >= max_attempts marca failed, senão volta para queued
        com available_at = now() + (attempts * 30s).
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE "{SCHEMA}".queue_profile
                SET
                    attempts = attempts + 1,
                    status = CASE
                        WHEN attempts + 1 >= max_attempts THEN 'failed'
                        ELSE 'queued'
                    END,
                    available_at = CASE
                        WHEN attempts + 1 >= max_attempts THEN now()
                        ELSE now() + (attempts + 1) * interval '30 seconds'
                    END,
                    last_error = $2,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = now()
                WHERE id = $1
                """,
                job_id,
                error_message[:5000] if error_message else None,
            )
            logger.warning(f"Queue: fail job_id={job_id}, error={error_message[:200]}")

    async def get_metrics(self) -> Dict[str, Any]:
        """Retorna contagens por status e idade do job mais antigo em queued."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END), 0)::int AS queued_count,
                    COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0)::int AS processing_count,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0)::int AS failed_count,
                    EXTRACT(EPOCH FROM (now() - MIN(CASE WHEN status = 'queued' THEN created_at END))) AS oldest_job_age_seconds
                FROM "{SCHEMA}".queue_profile
                """
            )
            if not row:
                return {
                    "queued_count": 0,
                    "processing_count": 0,
                    "failed_count": 0,
                    "oldest_job_age_seconds": None,
                }
            return {
                "queued_count": row["queued_count"] or 0,
                "processing_count": row["processing_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "oldest_job_age_seconds": float(row["oldest_job_age_seconds"]) if row["oldest_job_age_seconds"] is not None else None,
            }


_queue_service: Optional[QueueProfileService] = None


def get_queue_service() -> QueueProfileService:
    """Singleton do serviço de fila."""
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueProfileService()
    return _queue_service
