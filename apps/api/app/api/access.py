from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.db.auth import build_current_user, fetch_user_id_by_session_hash
from app.db.session import get_session
from app.schemas.auth import CurrentUser

ROLE_ORDER = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass(slots=True)
class AuthContext:
    user: CurrentUser
    session_token_hash: str


async def _session_from_authorization(
    authorization: str | None,
    session: AsyncSession,
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_hash = hash_session_token(token)
    user_id = await fetch_user_id_by_session_hash(session, token_hash)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Session expired")
    return AuthContext(user=await build_current_user(session, user_id), session_token_hash=token_hash)


async def require_auth_context(
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    return await _session_from_authorization(authorization, session)


def _role_value(role: str | None) -> int:
    return ROLE_ORDER.get(role or "viewer", 0)


def ensure_workspace_role(user: CurrentUser, workspace_id: str, minimum_role: str) -> None:
    for workspace in user.workspaces:
        if workspace.id == workspace_id and _role_value(workspace.role) >= _role_value(minimum_role):
            return
    raise HTTPException(status_code=403, detail="Workspace access denied")


def resolve_workspace_id(
    user: CurrentUser,
    workspace_id: str | None,
    minimum_role: str = "viewer",
) -> str:
    resolved = workspace_id or user.default_workspace_id
    if resolved is None:
        raise HTTPException(status_code=403, detail="No workspace available")
    ensure_workspace_role(user, resolved, minimum_role)
    return resolved


async def ensure_track_access(
    session: AsyncSession,
    user: CurrentUser,
    track_id: str,
    minimum_role: str = "viewer",
) -> str:
    result = await session.execute(
        text(
            """
            SELECT workspace_id
            FROM app.tracks
            WHERE id = CAST(:track_id AS uuid)
            """
        ),
        {"track_id": track_id},
    )
    workspace_id = result.scalar()
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Track not found")
    resolved = str(workspace_id)
    ensure_workspace_role(user, resolved, minimum_role)
    return resolved


async def ensure_story_access(
    session: AsyncSession,
    user: CurrentUser,
    story_id: str,
    minimum_role: str = "viewer",
) -> str:
    result = await session.execute(
        text(
            """
            SELECT workspace_id
            FROM app.stories
            WHERE id = CAST(:story_id AS uuid)
            """
        ),
        {"story_id": story_id},
    )
    workspace_id = result.scalar()
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Story not found")
    resolved = str(workspace_id)
    ensure_workspace_role(user, resolved, minimum_role)
    return resolved


async def ensure_episode_access(
    session: AsyncSession,
    user: CurrentUser,
    episode_id: str,
    minimum_role: str = "viewer",
) -> str:
    result = await session.execute(
        text(
            """
            SELECT s.workspace_id
            FROM app.episodes e
            JOIN app.stories s ON s.id = e.story_id
            WHERE e.id = CAST(:episode_id AS uuid)
            """
        ),
        {"episode_id": episode_id},
    )
    workspace_id = result.scalar()
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    resolved = str(workspace_id)
    ensure_workspace_role(user, resolved, minimum_role)
    return resolved


async def ensure_evidence_access(
    session: AsyncSession,
    user: CurrentUser,
    evidence_span_id: str,
    minimum_role: str = "viewer",
) -> str:
    result = await session.execute(
        text(
            """
            SELECT s.workspace_id
            FROM app.evidence_spans es
            JOIN app.generated_sentence_evidence gse ON gse.evidence_span_id = es.id
            JOIN app.generated_sentences gs ON gs.id = gse.generated_sentence_id
            JOIN app.stories s ON s.id = gs.story_id
            WHERE es.id = CAST(:evidence_span_id AS uuid)
            LIMIT 1
            """
        ),
        {"evidence_span_id": evidence_span_id},
    )
    workspace_id = result.scalar()
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Evidence span not found")
    resolved = str(workspace_id)
    ensure_workspace_role(user, resolved, minimum_role)
    return resolved


WorkspaceQuery = str | None


def workspace_query(alias: str = "workspaceId") -> Query:
    return Query(default=None, alias=alias)
