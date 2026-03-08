from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import fetch_recent_notifications
from app.db.session import get_session
from app.schemas.dashboard import RecentNotificationsResponse

router = APIRouter(prefix="/notifications")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
WorkspaceIdParam = Annotated[str | None, Query(alias="workspaceId")]
RecentLimitParam = Annotated[int, Query(ge=1, le=50)]


@router.get("/recent", response_model=RecentNotificationsResponse)
async def recent_notifications(
    session: SessionDep,
    workspace_id: WorkspaceIdParam = None,
    limit: RecentLimitParam = 8,
) -> RecentNotificationsResponse:
    items = await fetch_recent_notifications(session, workspace_id=workspace_id, limit=limit)
    return RecentNotificationsResponse(
        generatedAt=datetime.now(timezone.utc),
        items=items,
    )
