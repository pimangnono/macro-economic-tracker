from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import fetch_track_detail
from app.schemas.tracks import NoteDetail, NoteResponse, TrackDetail


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "track"


async def _workspace_exists(session: AsyncSession, workspace_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM app.workspaces WHERE id = CAST(:workspace_id AS uuid)"),
        {"workspace_id": workspace_id},
    )
    return result.scalar() == 1


async def _ensure_unique_track_slug(
    session: AsyncSession,
    workspace_id: str,
    base_slug: str,
    exclude_track_id: str | None = None,
) -> str:
    slug = base_slug
    suffix = 1

    while True:
        result = await session.execute(
            text(
                """
                SELECT id
                FROM app.tracks
                WHERE workspace_id = CAST(:workspace_id AS uuid)
                  AND slug = :slug
                  AND (:exclude_track_id IS NULL OR id <> CAST(:exclude_track_id AS uuid))
                LIMIT 1
                """
            ),
            {
                "workspace_id": workspace_id,
                "slug": slug,
                "exclude_track_id": exclude_track_id,
            },
        )
        if result.first() is None:
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"


async def create_track(
    session: AsyncSession,
    *,
    workspace_id: str,
    owner_user_id: str | None,
    name: str,
    description: str | None,
    mode: str,
    state: str,
    memory_window_days: int,
    alert_policy: dict[str, Any],
    evidence_policy: dict[str, Any],
) -> TrackDetail:
    if not await _workspace_exists(session, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")

    slug = await _ensure_unique_track_slug(session, workspace_id, _slugify(name))
    await session.execute(
        text(
            """
            INSERT INTO app.tracks (
                workspace_id,
                owner_user_id,
                name,
                slug,
                description,
                mode,
                state,
                alert_policy,
                evidence_policy,
                memory_window_days
            )
            VALUES (
                CAST(:workspace_id AS uuid),
                CAST(:owner_user_id AS uuid),
                :name,
                :slug,
                :description,
                CAST(:mode AS app.track_mode),
                CAST(:state AS app.track_state),
                CAST(:alert_policy AS jsonb),
                CAST(:evidence_policy AS jsonb),
                :memory_window_days
            )
            """
        ),
        {
            "workspace_id": workspace_id,
            "owner_user_id": owner_user_id,
            "name": name,
            "slug": slug,
            "description": description,
            "mode": mode,
            "state": state,
            "alert_policy": json.dumps(alert_policy),
            "evidence_policy": json.dumps(evidence_policy),
            "memory_window_days": memory_window_days,
        },
    )

    result = await session.execute(
        text(
            """
            SELECT id
            FROM app.tracks
            WHERE workspace_id = CAST(:workspace_id AS uuid)
              AND slug = :slug
            """
        ),
        {"workspace_id": workspace_id, "slug": slug},
    )
    track_id = str(result.scalar_one())
    await session.commit()
    return await fetch_track_detail(session, track_id)


async def update_track(
    session: AsyncSession,
    *,
    track_id: str,
    name: str | None,
    description: str | None,
    mode: str | None,
    state: str | None,
    memory_window_days: int | None,
) -> TrackDetail:
    current_result = await session.execute(
        text(
            """
            SELECT id, workspace_id, name
            FROM app.tracks
            WHERE id = CAST(:track_id AS uuid)
            """
        ),
        {"track_id": track_id},
    )
    current = current_result.mappings().first()
    if current is None:
        raise HTTPException(status_code=404, detail="Track not found")

    next_name = name or current["name"]
    next_slug = await _ensure_unique_track_slug(
        session,
        str(current["workspace_id"]),
        _slugify(next_name),
        exclude_track_id=track_id,
    )

    await session.execute(
        text(
            """
            UPDATE app.tracks
            SET
                name = :name,
                slug = :slug,
                description = COALESCE(:description, description),
                mode = COALESCE(CAST(:mode AS app.track_mode), mode),
                state = COALESCE(CAST(:state AS app.track_state), state),
                memory_window_days = COALESCE(:memory_window_days, memory_window_days)
            WHERE id = CAST(:track_id AS uuid)
            """
        ),
        {
            "track_id": track_id,
            "name": next_name,
            "slug": next_slug,
            "description": description,
            "mode": mode,
            "state": state,
            "memory_window_days": memory_window_days,
        },
    )
    await session.commit()
    return await fetch_track_detail(session, track_id)


async def update_track_alert_policy(
    session: AsyncSession,
    *,
    track_id: str,
    alert_policy: dict[str, Any],
) -> TrackDetail:
    result = await session.execute(
        text(
            """
            UPDATE app.tracks
            SET alert_policy = CAST(:alert_policy AS jsonb)
            WHERE id = CAST(:track_id AS uuid)
            RETURNING id
            """
        ),
        {"track_id": track_id, "alert_policy": json.dumps(alert_policy)},
    )
    if result.first() is None:
        raise HTTPException(status_code=404, detail="Track not found")
    await session.commit()
    return await fetch_track_detail(session, track_id)


async def create_track_note(
    session: AsyncSession,
    *,
    track_id: str,
    author_user_id: str | None,
    body_md: str,
    pinned: bool,
) -> NoteResponse:
    track_result = await session.execute(
        text(
            """
            SELECT workspace_id
            FROM app.tracks
            WHERE id = CAST(:track_id AS uuid)
            """
        ),
        {"track_id": track_id},
    )
    track_row = track_result.mappings().first()
    if track_row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    insert_result = await session.execute(
        text(
            """
            INSERT INTO app.notes (
                workspace_id,
                author_user_id,
                scope,
                track_id,
                body_md,
                pinned
            )
            VALUES (
                CAST(:workspace_id AS uuid),
                CAST(:author_user_id AS uuid),
                CAST('track' AS app.note_scope),
                CAST(:track_id AS uuid),
                :body_md,
                :pinned
            )
            RETURNING id, workspace_id, track_id, body_md, pinned, created_at, updated_at
            """
        ),
        {
            "workspace_id": str(track_row["workspace_id"]),
            "author_user_id": author_user_id,
            "track_id": track_id,
            "body_md": body_md,
            "pinned": pinned,
        },
    )
    note = insert_result.mappings().one()
    await session.commit()
    return NoteResponse(
        note=NoteDetail(
            id=str(note["id"]),
            workspaceId=str(note["workspace_id"]),
            trackId=str(note["track_id"]),
            bodyMd=note["body_md"],
            pinned=note["pinned"],
            createdAt=note["created_at"],
            updatedAt=note["updated_at"],
        )
    )
