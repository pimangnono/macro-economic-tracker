from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.queries import fetch_source_health_snapshot
from app.schemas.dashboard import SourceHealthItem
from app.services.ingestion.sources import list_source_infos


def _derive_status(
    *,
    last_run_status: str | None,
    last_success_at: datetime | None,
) -> str:
    if last_run_status == "running":
        return "running"
    if last_run_status == "failed":
        return "failing"
    if last_success_at is None:
        return "idle"

    settings = get_settings()
    stale_after = max(settings.ingestion_schedule_interval_seconds * 4, 3600)
    if last_success_at < datetime.now(timezone.utc) - timedelta(seconds=stale_after):
        return "stale"
    return "healthy"


async def build_source_health_items(session: AsyncSession) -> list[SourceHealthItem]:
    rows = await fetch_source_health_snapshot(session)
    by_source_key = {row["source_key"]: row for row in rows}
    items: list[SourceHealthItem] = []

    for source in list_source_infos():
        row = by_source_key.get(source.source_key)
        items.append(
            SourceHealthItem(
                sourceKey=source.source_key,
                displayName=source.display_name,
                sourceType=source.source_type,
                documentType=source.document_type,
                feedKind=source.feed_kind,
                feedUrl=source.feed_url,
                status=_derive_status(
                    last_run_status=row.get("last_run_status") if row else None,
                    last_success_at=row.get("last_success_at") if row else None,
                ),
                isActive=bool(row["is_active"]) if row is not None else True,
                lastRunStatus=row.get("last_run_status") if row else None,
                lastRunStartedAt=row.get("last_run_started_at") if row else None,
                lastRunFinishedAt=row.get("last_run_finished_at") if row else None,
                lastSuccessAt=row.get("last_success_at") if row else None,
                lastPublishedAt=row.get("last_published_at") if row else None,
                discoveredCount=int(row.get("discovered_count") or 0) if row else 0,
                insertedCount=int(row.get("inserted_count") or 0) if row else 0,
                updatedCount=int(row.get("updated_count") or 0) if row else 0,
                failedCount=int(row.get("failed_count") or 0) if row else 0,
                errorText=row.get("error_text") if row else None,
            )
        )

    return items
