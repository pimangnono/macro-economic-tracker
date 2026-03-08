from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.db.health import check_database, check_redis
from app.db.session import engine
from app.schemas.common import APIStatus

router = APIRouter()


@router.get("/health/live", response_model=APIStatus)
async def live() -> APIStatus:
    return APIStatus(status="ok", timestamp=datetime.now(timezone.utc))


@router.get("/health/ready", response_model=APIStatus)
async def ready(response: Response) -> APIStatus:
    settings = get_settings()
    database = await check_database(engine)
    redis = await check_redis(settings.redis_url)
    overall_ok = database.ok and redis.ok
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return APIStatus(
        status="ok" if overall_ok else "degraded",
        timestamp=datetime.now(timezone.utc),
        services={"database": database.detail, "redis": redis.detail},
    )

