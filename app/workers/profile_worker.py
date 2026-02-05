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
from app.core.logging_utils import setup_logging
from app.services.queue_service import get_queue_service
from app.services.profile_builder.run_profile_job import run_profile_job

setup_logging()
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
SLEEP_WHEN_EMPTY = 2.0
LOG_ALIVE_EVERY_N_EMPTY = 30


async def run_worker():
    """Loop principal: claim -> process -> ack/fail."""
    queue = get_queue_service()
    logger.info("Profile worker started, worker_id=%s", WORKER_ID)
    empty_cycles = 0
    while True:
        job = await queue.claim(WORKER_ID)
        if not job:
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
        job_id, cnpj_basico = job
        logger.info("Profile worker claimed job id=%s cnpj=%s", job_id, cnpj_basico)
        try:
            await run_profile_job(cnpj_basico)
            await queue.ack(job_id)
            logger.info("Profile job id=%s cnpj=%s done", job_id, cnpj_basico)
        except Exception as e:
            logger.exception("Job %s (cnpj=%s) failed: %s", job_id, cnpj_basico, e)
            await queue.fail(job_id, str(e))


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
        loop.run_until_complete(close_pool())
        loop.close()
        logger.info("Profile worker stopped.")


if __name__ == "__main__":
    main()
