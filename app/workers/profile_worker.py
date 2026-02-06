"""
Worker de processamento da fila queue_profile.
Processo separado: claim -> run_profile_job -> ack/fail.
Execute com: python -m app.workers.profile_worker
"""
import asyncio
import logging
import os
import signal
import socket
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

print("[profile_worker] Process starting (python -m app.workers.profile_worker)", flush=True)
sys.stdout.flush()
sys.stderr.flush()

from app.core.database import get_pool, close_pool
from app.core.config import settings
from app.core.logging_utils import setup_logging
from app.services.queue_service import get_queue_service
from app.services.database_service import get_db_service
from app.services.profile_builder.run_profile_job import run_profile_job

setup_logging()
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
CLAIM_BATCH_SIZE = getattr(settings, "CLAIM_BATCH_SIZE", 10)
SLEEP_WHEN_EMPTY = 2.0
LOG_ALIVE_EVERY_N_EMPTY = 30


async def run_worker():
    """Loop principal: claim batch -> fetch chunks batch -> process cada job -> ack/fail."""
    queue = get_queue_service()
    db_service = get_db_service()
    logger.info(
        "Profile worker started, worker_id=%s, claim_batch_size=%s",
        WORKER_ID,
        CLAIM_BATCH_SIZE,
    )
    empty_cycles = 0
    while True:
        jobs = await queue.claim(WORKER_ID, limit=CLAIM_BATCH_SIZE)
        if not jobs:
            empty_cycles += 1
            if empty_cycles > 0 and empty_cycles % LOG_ALIVE_EVERY_N_EMPTY == 0:
                m = await queue.get_metrics()
                logger.info(
                    "Profile worker alive, queue empty (queued=%s, processing=%s)",
                    m.get("queued_count", 0),
                    m.get("processing_count", 0),
                )
            await asyncio.sleep(SLEEP_WHEN_EMPTY)
            continue
        empty_cycles = 0
        cnpj_list = [cnpj for _, cnpj in jobs]
        chunks_by_cnpj = await db_service.get_chunks_batch(cnpj_list)
        for job_id, cnpj_basico in jobs:
            logger.info("Profile worker processing job id=%s cnpj=%s", job_id, cnpj_basico)
            try:
                chunks_data = chunks_by_cnpj.get(cnpj_basico, [])
                await run_profile_job(cnpj_basico, chunks_data=chunks_data)
                await queue.ack(job_id)
                logger.info("Profile job id=%s cnpj=%s done", job_id, cnpj_basico)
            except Exception as e:
                logger.exception("Job %s (cnpj=%s) failed: %s", job_id, cnpj_basico, e)
                await queue.fail(job_id, str(e))
            finally:
                # Conexões usadas em run_profile_job, queue.ack/fail e get_chunks_batch
                # são liberadas ao sair de cada async with pool.acquire(); nada a manter aqui.
                pass


def main():
    print("[profile_worker] main() entered, creating event loop", flush=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    worker_task = None

    def shutdown():
        nonlocal worker_task
        if worker_task and not worker_task.done():
            logger.info("Shutting down worker...")
            worker_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    async def run():
        logger.info("Profile worker connecting to database...")
        await get_pool()
        logger.info("Profile worker database connected, starting claim loop")
        return await run_worker()

    try:
        worker_task = loop.create_task(run())
        loop.run_until_complete(worker_task)
    except asyncio.CancelledError:
        logger.info("Profile worker cancelled")
    except Exception as e:
        logger.exception("Profile worker crashed: %s", e)
        raise
    finally:
        try:
            loop.run_until_complete(close_pool())
        except Exception as e:
            logger.warning("Erro ao fechar pool no shutdown: %s", e)
        loop.close()
        logger.info("Profile worker stopped.")


if __name__ == "__main__":
    main()
