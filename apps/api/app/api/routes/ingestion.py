from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.dashboard import SourceHealthResponse
from app.schemas.ingestion import IngestionPullResponse, IngestionSourcesResponse
from app.services.ingestion import list_source_infos, pull_source
from app.services.ingestion.status import build_source_health_items

router = APIRouter(prefix="/ingestion")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PullLimitParam = Annotated[int, Query(ge=1, le=50)]


@router.get("/sources", response_model=IngestionSourcesResponse)
async def ingestion_sources() -> IngestionSourcesResponse:
    return IngestionSourcesResponse(
        generatedAt=datetime.now(timezone.utc),
        items=list_source_infos(),
    )


@router.get("/status", response_model=SourceHealthResponse)
async def ingestion_status(session: SessionDep) -> SourceHealthResponse:
    return SourceHealthResponse(
        generatedAt=datetime.now(timezone.utc),
        items=await build_source_health_items(session),
    )


@router.post("/pull/{source_key}", response_model=IngestionPullResponse)
async def ingestion_pull(
    source_key: str,
    session: SessionDep,
    limit: PullLimitParam = 10,
) -> IngestionPullResponse:
    return await pull_source(session, source_key=source_key, limit=limit)
