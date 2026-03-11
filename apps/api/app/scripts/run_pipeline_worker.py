"""Pipeline worker — polls pipeline_jobs and dispatches to agents."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.pipeline.dispatcher import ALL_JOB_TYPES, dispatch_job
from app.services.pipeline.queue import claim_next_job, complete_job, fail_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline_worker")

POLL_INTERVAL_SECONDS = 2.0


async def run_cycle() -> bool:
    """Claim and process one job. Returns True if work was done."""
    async with SessionLocal() as session:
        job = await claim_next_job(session, job_types=ALL_JOB_TYPES)
        await session.commit()

    if job is None:
        return False

    job_id = job["id"]
    job_type = job["job_type"]
    logger.info("[%s] Processing %s job %s", _ts(), job_type, job_id)

    async with SessionLocal() as session:
        try:
            output = await dispatch_job(session, job)
            await complete_job(session, job_id, output)
            await session.commit()
            logger.info("[%s] Completed %s job %s", _ts(), job_type, job_id)
        except Exception as exc:
            await session.rollback()
            async with SessionLocal() as err_session:
                await fail_job(err_session, job_id, str(exc))
                await err_session.commit()
            logger.exception("[%s] Failed %s job %s: %s", _ts(), job_type, job_id, exc)

    return True


async def run_forever() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not set — pipeline worker will not start.")
        sys.exit(1)

    if not settings.pipeline_enabled:
        logger.warning("Pipeline is disabled (PIPELINE_ENABLED=false). Exiting.")
        sys.exit(0)

    logger.info("Pipeline worker starting (model=%s)", settings.openai_complex_model)

    while True:
        try:
            did_work = await run_cycle()
        except Exception:
            logger.exception("Unexpected error in pipeline worker cycle")
            did_work = False

        if not did_work:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


if __name__ == "__main__":
    asyncio.run(run_forever())
