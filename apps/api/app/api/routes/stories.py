from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import fetch_story_detail
from app.db.session import get_session
from app.schemas.stories import StoryDetailResponse

router = APIRouter(prefix="/stories")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def story_detail(
    story_id: str,
    session: SessionDep,
) -> StoryDetailResponse:
    story = await fetch_story_detail(session, story_id)
    return StoryDetailResponse(generatedAt=datetime.now(timezone.utc), story=story)
