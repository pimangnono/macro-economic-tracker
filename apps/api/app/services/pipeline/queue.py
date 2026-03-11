from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def enqueue_job(
    session: AsyncSession,
    *,
    job_type: str,
    source_object_type: str | None = None,
    source_object_id: str | None = None,
    input_json: dict[str, Any] | None = None,
    priority: int = 100,
) -> str:
    result = await session.execute(
        text(
            """
            INSERT INTO app.pipeline_jobs (
                job_type, status, priority,
                source_object_type, source_object_id, input_json
            )
            VALUES (
                :job_type,
                CAST('queued' AS app.job_status),
                :priority,
                :source_object_type,
                CAST(:source_object_id AS uuid),
                CAST(:input_json AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "job_type": job_type,
            "priority": priority,
            "source_object_type": source_object_type,
            "source_object_id": source_object_id,
            "input_json": json.dumps(input_json or {}),
        },
    )
    return str(result.scalar_one())


async def claim_next_job(
    session: AsyncSession,
    job_types: list[str] | None = None,
) -> dict[str, Any] | None:
    type_filter = ""
    params: dict[str, Any] = {}
    if job_types:
        placeholders = ", ".join(f":jt_{i}" for i in range(len(job_types)))
        type_filter = f"AND job_type IN ({placeholders})"
        for i, jt in enumerate(job_types):
            params[f"jt_{i}"] = jt

    result = await session.execute(
        text(
            f"""
            UPDATE app.pipeline_jobs
            SET status = CAST('running' AS app.job_status),
                started_at = now()
            WHERE id = (
                SELECT id FROM app.pipeline_jobs
                WHERE status = CAST('queued' AS app.job_status)
                  {type_filter}
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, job_type, source_object_type, source_object_id, input_json, priority
            """
        ),
        params,
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "job_type": row["job_type"],
        "source_object_type": row["source_object_type"],
        "source_object_id": str(row["source_object_id"]) if row["source_object_id"] else None,
        "input_json": row["input_json"] if isinstance(row["input_json"], dict) else {},
        "priority": row["priority"],
    }


async def complete_job(
    session: AsyncSession,
    job_id: str,
    output_json: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text(
            """
            UPDATE app.pipeline_jobs
            SET status = CAST('completed' AS app.job_status),
                output_json = CAST(:output_json AS jsonb),
                finished_at = now()
            WHERE id = CAST(:job_id AS uuid)
            """
        ),
        {"job_id": job_id, "output_json": json.dumps(output_json or {})},
    )


async def fail_job(
    session: AsyncSession,
    job_id: str,
    error_text: str,
) -> None:
    await session.execute(
        text(
            """
            UPDATE app.pipeline_jobs
            SET status = CAST('failed' AS app.job_status),
                error_text = :error_text,
                finished_at = now()
            WHERE id = CAST(:job_id AS uuid)
            """
        ),
        {"job_id": job_id, "error_text": error_text[:4000]},
    )
