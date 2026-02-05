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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.core.database import get_pool, close_pool
from app.core.logging_utils import setup_logging
from app.services.queue_discovery_service import get_queue_discovery_service
from app.services.discovery.run_discovery_job import run_discovery_job

setup_logging()
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-discovery-{os.getpid()}")
SLEEP_WHEN_EMPTY = 2.0


async def run_worker():
    """Loop principal: claim -> run_discovery_job -> ack/fail."""
    queue = get_queue_discovery_service()
    logger.info("Discovery worker started, worker_id=%s", WORKER_ID)
    while True:
        job = await queue.claim(WORKER_ID)
        if not job:
            await asyncio.sleep(SLEEP_WHEN_EMPTY)
            continue
        job_id, cnpj_basico = job
        try:
            await run_discovery_job(cnpj_basico)
            await queue.ack(job_id)
        except Exception as e:
            logger.exception("Discovery job %s (cnpj=%s) failed: %s", job_id, cnpj_basico, e)
            await queue.fail(job_id, str(e))


def main():
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
        await get_pool()
        return await run_worker()

    try:
        worker_task = loop.create_task(run())
        loop.run_until_complete(worker_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.run_until_complete(close_pool())
        loop.close()
        logger.info("Discovery worker stopped.")


if __name__ == "__main__":
    main()
