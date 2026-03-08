from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import asyncpg

from app.core.config import ROOT_DIR, get_settings

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version text PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


def _migration_files() -> list[Path]:
    root_files = [ROOT_DIR / "db_schema.sql"]
    incremental = sorted((ROOT_DIR / "migrations").glob("*.sql"))
    return [path for path in [*root_files, *incremental] if path.exists()]


def _checksum(contents: str) -> str:
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()


def _normalize_asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def run() -> None:
    settings = get_settings()
    connection = await asyncpg.connect(_normalize_asyncpg_dsn(settings.database_url))
    try:
        await connection.execute(MIGRATION_TABLE_SQL)

        for path in _migration_files():
            version = path.relative_to(ROOT_DIR).as_posix()
            sql = path.read_text(encoding="utf-8")
            checksum = _checksum(sql)

            existing = await connection.fetchrow(
                """
                SELECT checksum
                FROM public.schema_migrations
                WHERE version = $1
                """,
                version,
            )

            if existing and existing["checksum"] == checksum:
                print(f"Skipping {version} (already applied)")
                continue

            if existing and existing["checksum"] != checksum:
                raise RuntimeError(
                    f"Migration checksum mismatch for {version}. "
                    "Create a new migration instead of editing an applied file."
                )

            print(f"Applying {version}")
            await connection.execute(sql)
            await connection.execute(
                """
                INSERT INTO public.schema_migrations (version, checksum)
                VALUES ($1, $2)
                """,
                version,
                checksum,
            )
    finally:
        await connection.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

