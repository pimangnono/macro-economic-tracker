from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import AuthContext, require_auth_context, resolve_workspace_id
from app.db.queries import fetch_recent_notifications
from app.db.session import get_session
from app.db.workflows import mark_notification_read, mute_track_for_notification
from app.schemas.dashboard import NotificationActionResponse, RecentNotificationsResponse

router = APIRouter(prefix="/notifications")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
WorkspaceIdParam = Annotated[str | None, Query(alias="workspaceId")]
RecentLimitParam = Annotated[int, Query(ge=1, le=50)]
AuthDep = Annotated[AuthContext, Depends(require_auth_context)]


@router.get("/recent", response_model=RecentNotificationsResponse)
async def recent_notifications(
    session: SessionDep,
    auth: AuthDep,
    workspace_id: WorkspaceIdParam = None,
    limit: RecentLimitParam = 8,
) -> RecentNotificationsResponse:
    resolved_workspace_id = resolve_workspace_id(auth.user, workspace_id, "viewer")
    items = await fetch_recent_notifications(
        session,
        workspace_id=resolved_workspace_id,
        limit=limit,
        user_id=auth.user.id,
    )
    return RecentNotificationsResponse(
        generatedAt=datetime.now(timezone.utc),
        items=items,
    )


@router.post("/{notification_id}/read", response_model=NotificationActionResponse)
async def notification_read(
    notification_id: str,
    session: SessionDep,
    auth: AuthDep,
) -> NotificationActionResponse:
    await mark_notification_read(session, notification_id=notification_id, user_id=auth.user.id)
    return NotificationActionResponse()


@router.post("/{notification_id}/mute", response_model=NotificationActionResponse)
async def notification_mute(
    notification_id: str,
    session: SessionDep,
    auth: AuthDep,
) -> NotificationActionResponse:
    await mute_track_for_notification(session, notification_id=notification_id, user_id=auth.user.id)
    return NotificationActionResponse()
