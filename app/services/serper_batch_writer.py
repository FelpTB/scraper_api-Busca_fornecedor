"""
Writer em batch para serper_results.

Em vez de 1 conexão por INSERT (100 req/s = pico de muitas conexões), uma única
tarefa enfileira os payloads e grava em lotes com UMA conexão por lote.
Reduz drasticamente o uso de conexões e elimina "sorry, too many clients already".
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.core.database import get_pool, with_connection

logger = logging.getLogger(__name__)

SCHEMA = "busca_fornecedor"

# Tamanho máximo do lote e intervalo máximo entre flushes (segundos)
BATCH_MAX_SIZE = getattr(settings, "SERPER_BATCH_SIZE", 50) or 50
BATCH_INTERVAL_SEC = getattr(settings, "SERPER_BATCH_INTERVAL_SEC", 0.15) or 0.15


@dataclass
class SerperPayload:
    cnpj_basico: str
    results: list
    query_used: str
    company_name: Optional[str] = None
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    municipio: Optional[str] = None
    persist_if_empty: bool = False


_queue: Optional[asyncio.Queue] = None
_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


def _get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def _flush_batch(batch: List[SerperPayload]) -> None:
    if not batch:
        return
    # Filtrar payloads vazios exceto quando persist_if_empty (falha total após retries)
    to_insert = [p for p in batch if p.results or p.persist_if_empty]
    skipped = len(batch) - len(to_insert)
    if skipped:
        logger.debug(f"📦 [BATCH] Ignorando {skipped} payload(s) vazio(s) (não-falha total)")
    if not to_insert:
        return
    async def _insert_batch(conn):
        query = f"""
            INSERT INTO "{SCHEMA}".serper_results 
                (cnpj_basico, company_name, razao_social, nome_fantasia, 
                 municipio, results_json, results_count, query_used)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """
        async with conn.transaction():
            for p in to_insert:
                await conn.execute(
                    query,
                    p.cnpj_basico,
                    p.company_name,
                    p.razao_social,
                    p.nome_fantasia,
                    p.municipio,
                    json.dumps(p.results),
                    len(p.results),
                    p.query_used,
                )
        logger.info(f"📦 [BATCH] serper_results: {len(to_insert)} registros gravados (1 conexão)")

    try:
        await with_connection(_insert_batch)
    except Exception as e:
        logger.error(f"❌ [BATCH] Erro ao gravar lote de serper_results: {e}", exc_info=True)
        for p in to_insert:
            logger.warning(f"   Item perdido cnpj={p.cnpj_basico}")


async def _worker_loop() -> None:
    q = _get_queue()
    batch: List[SerperPayload] = []
    loop = asyncio.get_event_loop()
    deadline = loop.time() + BATCH_INTERVAL_SEC
    while True:
        try:
            # Flush se lote cheio ou tempo esgotado
            if len(batch) >= BATCH_MAX_SIZE or (batch and loop.time() >= deadline):
                await _flush_batch(batch)
                batch = []
                deadline = loop.time() + BATCH_INTERVAL_SEC
            wait_sec = max(0.01, min(BATCH_INTERVAL_SEC, deadline - loop.time()))
            try:
                item = await asyncio.wait_for(q.get(), timeout=wait_sec)
            except asyncio.TimeoutError:
                continue
            if item is None:
                if batch:
                    await _flush_batch(batch)
                break
            batch.append(item)
        except asyncio.CancelledError:
            if batch:
                await _flush_batch(batch)
            raise
        except Exception as e:
            logger.error(f"❌ [BATCH] Erro no worker: {e}", exc_info=True)


def enqueue_serper_payload(payload: SerperPayload) -> None:
    """Enfileira um payload para gravação em batch (não bloqueia)."""
    _get_queue().put_nowait(payload)


async def start_serper_batch_writer() -> None:
    """Inicia o worker de batch (chamar no startup da aplicação)."""
    global _task, _stop_event
    if _task is not None:
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_worker_loop())
    logger.info(
        f"📦 Serper batch writer iniciado (batch_size={BATCH_MAX_SIZE}, interval={BATCH_INTERVAL_SEC}s)"
    )


async def stop_serper_batch_writer() -> None:
    """Para o worker e grava o que restar na fila (chamar no shutdown)."""
    global _task, _queue
    if _task is None:
        return
    q = _get_queue()
    q.put_nowait(None)
    try:
        await asyncio.wait_for(_task, timeout=30.0)
    except asyncio.TimeoutError:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    logger.info("📦 Serper batch writer encerrado")
