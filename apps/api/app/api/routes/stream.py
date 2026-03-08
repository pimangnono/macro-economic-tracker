from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.stream import stream_outbox

router = APIRouter(prefix="/events")

WorkspaceIdParam = Annotated[str | None, Query(alias="workspaceId")]
AfterParam = Annotated[datetime | None, Query()]
LastEventIdParam = Annotated[str | None, Header(alias="Last-Event-ID")]


@router.get("/stream")
async def event_stream(
    workspace_id: WorkspaceIdParam = None,
    after: AfterParam = None,
    last_event_id: LastEventIdParam = None,
) -> EventSourceResponse:
    settings = get_settings()
    cursor = after
    if cursor is None and last_event_id:
        try:
            cursor = datetime.fromisoformat(last_event_id)
        except ValueError:
            cursor = None

    return EventSourceResponse(
        stream_outbox(SessionLocal, workspace_id=workspace_id, after=cursor),
        ping=settings.sse_ping_seconds,
    )
