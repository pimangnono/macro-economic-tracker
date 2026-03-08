from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ingestion import pull_source
from app.services.ingestion.sources import SOURCE_DEFINITIONS


async def run_cycle() -> None:
    settings = get_settings()
    source_keys = settings.ingestion_schedule_sources or list(SOURCE_DEFINITIONS.keys())

    for source_key in source_keys:
        async with SessionLocal() as session:
            try:
                result = await pull_source(
                    session,
                    source_key=source_key,
                    limit=settings.ingestion_pull_limit,
                )
                print(
                    f"[{datetime.now(timezone.utc).isoformat()}] pulled {source_key}: "
                    f"discovered={result.discovered_count} inserted={result.inserted_count} "
                    f"updated={result.updated_count} failed={result.failed_count}"
                )
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                print(
                    f"[{datetime.now(timezone.utc).isoformat()}] pull failed for {source_key}: {exc}"
                )


async def run_forever() -> None:
    settings = get_settings()
    if settings.ingestion_startup_delay_seconds > 0:
        await asyncio.sleep(settings.ingestion_startup_delay_seconds)

    while True:
        await run_cycle()
        await asyncio.sleep(settings.ingestion_schedule_interval_seconds)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
