from fastapi import APIRouter

from app.api.routes import health, ingestion, notifications, stories, stream, tracks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(tracks.router, tags=["tracks"])
api_router.include_router(stories.router, tags=["stories"])
api_router.include_router(stream.router, tags=["events"])
api_router.include_router(ingestion.router, tags=["ingestion"])
api_router.include_router(notifications.router, tags=["notifications"])
