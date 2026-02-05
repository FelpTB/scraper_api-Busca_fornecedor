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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.core.database import get_pool, close_pool
from app.core.logging_utils import setup_logging
from app.services.queue_service import get_queue_service
from app.services.profile_builder.run_profile_job import run_profile_job

setup_logging()
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
SLEEP_WHEN_EMPTY = 2.0


async def run_worker():
    """Loop principal: claim -> process -> ack/fail."""
    queue = get_queue_service()
    logger.info("Profile worker started, worker_id=%s", WORKER_ID)
    while True:
        job = await queue.claim(WORKER_ID)
        if not job:
            await asyncio.sleep(SLEEP_WHEN_EMPTY)
            continue
        job_id, cnpj_basico = job
        try:
            await run_profile_job(cnpj_basico)
            await queue.ack(job_id)
        except Exception as e:
            logger.exception("Job %s (cnpj=%s) failed: %s", job_id, cnpj_basico, e)
            await queue.fail(job_id, str(e))


def main():
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
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
