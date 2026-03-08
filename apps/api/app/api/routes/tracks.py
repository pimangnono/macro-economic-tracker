from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mutations import create_track, create_track_note, update_track, update_track_alert_policy
from app.db.queries import fetch_live_board, fetch_track_bootstrap, fetch_track_detail, fetch_track_stories
from app.db.session import get_session
from app.schemas.tracks import (
    AlertPolicyRequest,
    BootstrapResponse,
    CreateNoteRequest,
    CreateTrackRequest,
    LiveBoardResponse,
    NoteResponse,
    TrackStoriesResponse,
    UpdateTrackRequest,
)

router = APIRouter(prefix="/tracks")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
WorkspaceIdParam = Annotated[str | None, Query(alias="workspaceId")]
LiveBoardLimitParam = Annotated[int, Query(ge=1, le=100)]
TrackStoriesLimitParam = Annotated[int, Query(ge=1, le=100)]


@router.get("/live-board", response_model=LiveBoardResponse)
async def live_board(
    session: SessionDep,
    workspace_id: WorkspaceIdParam = None,
    limit: LiveBoardLimitParam = 24,
) -> LiveBoardResponse:
    items = await fetch_live_board(session, workspace_id=workspace_id, limit=limit)
    return LiveBoardResponse(generatedAt=datetime.now(timezone.utc), items=items)


@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(session: SessionDep) -> BootstrapResponse:
    return await fetch_track_bootstrap(session)


@router.post("", response_model=TrackStoriesResponse, status_code=status.HTTP_201_CREATED)
async def track_create(
    payload: CreateTrackRequest,
    session: SessionDep,
) -> TrackStoriesResponse:
    track = await create_track(
        session,
        workspace_id=payload.workspace_id,
        owner_user_id=payload.owner_user_id,
        name=payload.name,
        description=payload.description,
        mode=payload.mode,
        state=payload.state,
        memory_window_days=payload.memory_window_days,
        alert_policy=payload.alert_policy,
        evidence_policy=payload.evidence_policy,
    )
    return TrackStoriesResponse(
        generatedAt=datetime.now(timezone.utc),
        track=track,
        stories=[],
    )


@router.get("/{track_id}", response_model=TrackStoriesResponse)
async def track_detail(
    track_id: str,
    session: SessionDep,
    limit: TrackStoriesLimitParam = 12,
) -> TrackStoriesResponse:
    track = await fetch_track_detail(session, track_id)
    stories = await fetch_track_stories(session, track_id=track_id, limit=limit)
    return TrackStoriesResponse(
        generatedAt=datetime.now(timezone.utc),
        track=track,
        stories=stories,
    )


@router.patch("/{track_id}", response_model=TrackStoriesResponse)
async def track_update(
    track_id: str,
    payload: UpdateTrackRequest,
    session: SessionDep,
) -> TrackStoriesResponse:
    track = await update_track(
        session,
        track_id=track_id,
        name=payload.name,
        description=payload.description,
        mode=payload.mode,
        state=payload.state,
        memory_window_days=payload.memory_window_days,
    )
    stories = await fetch_track_stories(session, track_id=track_id, limit=12)
    return TrackStoriesResponse(
        generatedAt=datetime.now(timezone.utc),
        track=track,
        stories=stories,
    )


@router.patch("/{track_id}/alert-policy", response_model=TrackStoriesResponse)
async def track_alert_policy_update(
    track_id: str,
    payload: AlertPolicyRequest,
    session: SessionDep,
) -> TrackStoriesResponse:
    track = await update_track_alert_policy(
        session,
        track_id=track_id,
        alert_policy=payload.alert_policy,
    )
    stories = await fetch_track_stories(session, track_id=track_id, limit=12)
    return TrackStoriesResponse(
        generatedAt=datetime.now(timezone.utc),
        track=track,
        stories=stories,
    )


@router.post("/{track_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def track_note_create(
    track_id: str,
    payload: CreateNoteRequest,
    session: SessionDep,
) -> NoteResponse:
    return await create_track_note(
        session,
        track_id=track_id,
        author_user_id=payload.author_user_id,
        body_md=payload.body_md,
        pinned=payload.pinned,
    )
