from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(slots=True)
class ServiceHealth:
    ok: bool
    detail: str


async def check_database(engine: AsyncEngine) -> ServiceHealth:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('app.tracks') IS NOT NULL AS schema_ready")
            )
            schema_ready = bool(result.scalar())
        if not schema_ready:
            return ServiceHealth(ok=False, detail="schema missing")
        return ServiceHealth(ok=True, detail="ok")
    except Exception as exc:  # pragma: no cover - defensive guard
        return ServiceHealth(ok=False, detail=str(exc))


async def check_redis(redis_url: str) -> ServiceHealth:
    client = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        pong = await client.ping()
        return ServiceHealth(ok=bool(pong), detail="ok" if pong else "ping failed")
    except Exception as exc:  # pragma: no cover - defensive guard
        return ServiceHealth(ok=False, detail=str(exc))
    finally:
        await client.aclose()

