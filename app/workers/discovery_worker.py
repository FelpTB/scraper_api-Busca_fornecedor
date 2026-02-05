"""
Worker de processamento da fila queue_discovery (encontrar_site).
Processo separado: claim -> run_discovery_job -> ack/fail.
Execute com: python -m app.workers.discovery_worker
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

# Log imediato para confirmar que o processo do worker subiu (antes de qualquer import pesado)
print("[discovery_worker] Process starting (python -m app.workers.discovery_worker)", flush=True)
sys.stdout.flush()
sys.stderr.flush()

from app.core.database import get_pool, close_pool
from app.core.logging_utils import setup_logging
from app.services.queue_discovery_service import get_queue_discovery_service
from app.services.discovery.run_discovery_job import run_discovery_job

setup_logging()
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-discovery-{os.getpid()}")
SLEEP_WHEN_EMPTY = 2.0
LOG_ALIVE_EVERY_N_EMPTY = 30  # A cada ~60s sem job, log "alive"


async def run_worker():
    """Loop principal: claim -> run_discovery_job -> ack/fail."""
    queue = get_queue_discovery_service()
    logger.info("Discovery worker started, worker_id=%s", WORKER_ID)
    empty_cycles = 0
    while True:
        job = await queue.claim(WORKER_ID)
        if not job:
            empty_cycles += 1
            if empty_cycles > 0 and empty_cycles % LOG_ALIVE_EVERY_N_EMPTY == 0:
                m = await queue.get_metrics()
                logger.info(
                    "Discovery worker alive, queue empty (queued=%s, processing=%s)",
                    m.get("queued_count", 0),
                    m.get("processing_count", 0),
                )
            await asyncio.sleep(SLEEP_WHEN_EMPTY)
            continue
        empty_cycles = 0
        job_id, cnpj_basico = job
        logger.info("Discovery worker claimed job id=%s cnpj=%s", job_id, cnpj_basico)
        try:
            await run_discovery_job(cnpj_basico)
            await queue.ack(job_id)
            logger.info("Discovery job id=%s cnpj=%s done", job_id, cnpj_basico)
        except Exception as e:
            logger.exception("Discovery job %s (cnpj=%s) failed: %s", job_id, cnpj_basico, e)
            await queue.fail(job_id, str(e))


def main():
    print("[discovery_worker] main() entered, creating event loop", flush=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    worker_task = None

    def shutdown():
        nonlocal worker_task
        if worker_task and not worker_task.done():
            logger.info("Shutting down discovery worker...")
            worker_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    async def run():
        logger.info("Discovery worker connecting to database...")
        await get_pool()
        logger.info("Discovery worker database connected, starting claim loop")
        return await run_worker()

    try:
        worker_task = loop.create_task(run())
        loop.run_until_complete(worker_task)
    except asyncio.CancelledError:
        logger.info("Discovery worker cancelled")
    except Exception as e:
        logger.exception("Discovery worker crashed: %s", e)
        raise
    finally:
        loop.run_until_complete(close_pool())
        loop.close()
        logger.info("Discovery worker stopped.")


if __name__ == "__main__":
    main()
