from fastapi import APIRouter

from app.api.routes import auth, health, inbox, ingestion, notes, notifications, pipeline, stories, stream, tracks, workspaces

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(inbox.router, tags=["inbox"])
api_router.include_router(tracks.router, tags=["tracks"])
api_router.include_router(stories.router, tags=["stories"])
api_router.include_router(notes.router, tags=["notes"])
api_router.include_router(stream.router, tags=["events"])
api_router.include_router(ingestion.router, tags=["ingestion"])
api_router.include_router(notifications.router, tags=["notifications"])
api_router.include_router(workspaces.router, tags=["workspaces"])
api_router.include_router(pipeline.router, tags=["pipeline"])
