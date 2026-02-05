"""
Serviço de fila durável para descoberta de site (queue_discovery).
1 job = 1 empresa = LLM analisa serper_results e grava website_discovery.
"""
import logging
from typing import Optional, Tuple, Dict, Any

import asyncpg
from app.core.database import get_pool

logger = logging.getLogger(__name__)

SCHEMA = "busca_fornecedor"


class QueueDiscoveryService:
    """Operações assíncronas sobre busca_fornecedor.queue_discovery."""

    async def enqueue(self, cnpj_basico: str) -> bool:
        """Insere job na fila se não existir job ativo. Retorna True se inseriu."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            check = await conn.fetchrow(
                f"""
                SELECT id FROM "{SCHEMA}".queue_discovery
                WHERE cnpj_basico = $1 AND status IN ('queued', 'processing')
                LIMIT 1
                """,
                cnpj_basico,
            )
            if check:
                logger.debug(f"Queue discovery: job ativo já existe cnpj_basico={cnpj_basico}")
                return False
            try:
                await conn.execute(
                    f"""
                    INSERT INTO "{SCHEMA}".queue_discovery (cnpj_basico)
                    VALUES ($1)
                    """,
                    cnpj_basico,
                )
                logger.info(f"Queue discovery: enqueued cnpj_basico={cnpj_basico}")
                return True
            except asyncpg.UniqueViolationError:
                # Concorrência: outro request inseriu o mesmo cnpj entre o SELECT e o INSERT
                logger.debug(f"Queue discovery: duplicate (race) cnpj_basico={cnpj_basico}")
                return False

    async def claim(self, worker_id: str) -> Optional[Tuple[int, str]]:
        """Reserva um job queued. Retorna (id, cnpj_basico) ou None."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"""
                    WITH picked AS (
                        SELECT id FROM "{SCHEMA}".queue_discovery
                        WHERE status = 'queued' AND available_at <= now()
                        ORDER BY id
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE "{SCHEMA}".queue_discovery q
                    SET status = 'processing',
                        locked_at = now(),
                        locked_by = $1,
                        updated_at = now()
                    FROM picked
                    WHERE q.id = picked.id
                    RETURNING q.id, q.cnpj_basico
                    """,
                    worker_id,
                )
                if row:
                    return (row["id"], row["cnpj_basico"])
                return None

    async def ack(self, job_id: int) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE "{SCHEMA}".queue_discovery
                SET status = 'done', last_error = NULL, updated_at = now()
                WHERE id = $1
                """,
                job_id,
            )
            logger.debug(f"Queue discovery: ack job_id={job_id}")

    async def fail(self, job_id: int, error_message: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE "{SCHEMA}".queue_discovery
                SET
                    attempts = attempts + 1,
                    status = CASE WHEN attempts + 1 >= max_attempts THEN 'failed' ELSE 'queued' END,
                    available_at = CASE WHEN attempts + 1 >= max_attempts THEN now() ELSE now() + (attempts + 1) * interval '30 seconds' END,
                    last_error = $2,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = now()
                WHERE id = $1
                """,
                job_id,
                (error_message or "")[:5000],
            )
            logger.warning(f"Queue discovery: fail job_id={job_id}")

    async def get_metrics(self) -> Dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END), 0)::int AS queued_count,
                    COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0)::int AS processing_count,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0)::int AS failed_count,
                    EXTRACT(EPOCH FROM (now() - MIN(CASE WHEN status = 'queued' THEN created_at END))) AS oldest_job_age_seconds
                FROM "{SCHEMA}".queue_discovery
                """
            )
            if not row:
                return {"queued_count": 0, "processing_count": 0, "failed_count": 0, "oldest_job_age_seconds": None}
            return {
                "queued_count": row["queued_count"] or 0,
                "processing_count": row["processing_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "oldest_job_age_seconds": float(row["oldest_job_age_seconds"]) if row["oldest_job_age_seconds"] is not None else None,
            }


_queue_discovery_service: Optional[QueueDiscoveryService] = None


def get_queue_discovery_service() -> QueueDiscoveryService:
    global _queue_discovery_service
    if _queue_discovery_service is None:
        _queue_discovery_service = QueueDiscoveryService()
    return _queue_discovery_service
