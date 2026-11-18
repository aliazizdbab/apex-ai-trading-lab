from __future__ import annotations

import logging
import signal
import time

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("apex.worker")

_RUNNING = True


def _handle_signal(signum, _frame) -> None:
    logger.info("Received signal %s; shutting down worker gracefully.", signum)
    global _RUNNING
    _RUNNING = False


def run_worker_loop(poll_interval_seconds: float = 10.0) -> None:
    """Run Phase 2 worker loop verifying database connectivity until stopped."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    settings = get_settings()
    logger.info("APEX Phase 2 worker starting (redis_url=%s)", settings.redis_url)

    while _RUNNING:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            logger.debug("Worker heartbeat OK")
        except Exception as exc:
            logger.error("Worker heartbeat database check failed: %s", exc)

        slept = 0.0
        while _RUNNING and slept < poll_interval_seconds:
            time.sleep(0.5)
            slept += 0.5

    logger.info("APEX Phase 2 worker stopped.")


if __name__ == "__main__":
    run_worker_loop()
