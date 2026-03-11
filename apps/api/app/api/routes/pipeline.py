"""Pipeline observability API routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.pipeline.queue import enqueue_job

router = APIRouter(prefix="/pipeline")


@router.get("/jobs")
async def list_pipeline_jobs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    status_filter = ""
    if status:
        status_filter = "WHERE status = CAST(:status AS app.job_status)"
        params["status"] = status

    result = await session.execute(
        text(
            f"""
            SELECT
                id, job_type, status::text, priority,
                source_object_type, source_object_id,
                input_json, output_json, error_text,
                created_at, started_at, finished_at
            FROM app.pipeline_jobs
            {status_filter}
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "jobs": [
            {
                "id": str(r["id"]),
                "jobType": r["job_type"],
                "status": r["status"],
                "priority": r["priority"],
                "sourceObjectType": r["source_object_type"],
                "sourceObjectId": str(r["source_object_id"]) if r["source_object_id"] else None,
                "inputJson": r["input_json"],
                "outputJson": r["output_json"],
                "errorText": r["error_text"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                "startedAt": r["started_at"].isoformat() if r["started_at"] else None,
                "finishedAt": r["finished_at"].isoformat() if r["finished_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/agent-runs")
async def list_agent_runs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            SELECT
                id, agent_name, model_name, status::text,
                input_json, output_json,
                cost_estimate_usd, latency_ms,
                source_object_type, source_object_id,
                created_at, finished_at, error_text
            FROM app.agent_runs
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    rows = result.mappings().all()
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "runs": [
            {
                "id": str(r["id"]),
                "agentName": r["agent_name"],
                "modelName": r["model_name"],
                "status": r["status"],
                "costEstimateUsd": float(r["cost_estimate_usd"]) if r["cost_estimate_usd"] else None,
                "latencyMs": r["latency_ms"],
                "sourceObjectType": r["source_object_type"],
                "sourceObjectId": str(r["source_object_id"]) if r["source_object_id"] else None,
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                "finishedAt": r["finished_at"].isoformat() if r["finished_at"] else None,
                "errorText": r["error_text"],
            }
            for r in rows
        ],
    }


@router.post("/reprocess/{document_id}")
async def reprocess_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    # Verify document exists
    result = await session.execute(
        text(
            """
            SELECT id, title, body_text, document_type::text
            FROM app.documents
            WHERE id = CAST(:document_id AS uuid)
            """
        ),
        {"document_id": document_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Find source_key
    source_result = await session.execute(
        text(
            """
            SELECT s.source_key FROM app.documents d
            JOIN app.sources s ON s.id = d.source_id
            WHERE d.id = CAST(:document_id AS uuid)
            """
        ),
        {"document_id": document_id},
    )
    source_row = source_result.mappings().first()
    source_key = source_row["source_key"] if source_row else "unknown"

    job_id = await enqueue_job(
        session,
        job_type="event_extraction",
        source_object_type="document",
        source_object_id=document_id,
        input_json={
            "document_id": document_id,
            "title": row["title"],
            "body_text": row["body_text"] or row["title"],
            "document_type": row["document_type"],
            "source_key": source_key,
        },
        priority=50,
    )
    await session.commit()

    return {
        "jobId": job_id,
        "documentId": document_id,
        "status": "queued",
    }
