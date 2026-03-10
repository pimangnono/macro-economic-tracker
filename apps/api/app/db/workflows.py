from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import fetch_track_detail, fetch_track_stories
from app.schemas.common import SummaryFrame
from app.schemas.inbox import InboxItem, ModeData, TrackCanvasResponse, TrackListItem, UpcomingEventItem
from app.schemas.notes import NoteDetail
from app.schemas.snapshots import SnapshotDetail


def _iso(value: Any) -> str:
    return str(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _note_from_row(row: dict[str, Any]) -> NoteDetail:
    return NoteDetail(
        id=_iso(row["id"]),
        workspaceId=_iso(row["workspace_id"]),
        authorUserId=_iso(row["author_user_id"]) if row["author_user_id"] else None,
        authorName=row.get("author_name"),
        scope=row["scope"],
        trackId=_iso(row["track_id"]) if row["track_id"] else None,
        storyId=_iso(row["story_id"]) if row["story_id"] else None,
        episodeId=_iso(row["episode_id"]) if row["episode_id"] else None,
        evidenceSpanId=_iso(row["evidence_span_id"]) if row["evidence_span_id"] else None,
        bodyMd=row["body_md"],
        pinned=bool(row["pinned"]),
        metadata=row.get("metadata") or {},
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _snapshot_from_row(row: dict[str, Any]) -> SnapshotDetail:
    summary_json = row["summary_json"] or {}
    return SnapshotDetail(
        id=_iso(row["id"]),
        trackId=_iso(row["track_id"]),
        snapshotAt=row["snapshot_at"],
        summaryText=row["summary_text"],
        summary=SummaryFrame(
            whatChanged=summary_json.get("whatChanged"),
            whyItMatters=summary_json.get("whyItMatters"),
            whatToWatch=summary_json.get("whatToWatch"),
        )
        if summary_json
        else None,
        metrics=row["metrics_json"] or {},
        artifactManifest=row["artifact_manifest"] or {},
        createdByAgent=row["created_by_agent"],
        createdAt=row["created_at"],
    )


async def insert_pipeline_job(
    session: AsyncSession,
    *,
    job_type: str,
    source_object_type: str,
    source_object_id: str,
    input_json: dict[str, Any],
    output_json: dict[str, Any] | None = None,
    status: str = "completed",
) -> str:
    result = await session.execute(
        text(
            """
            INSERT INTO app.pipeline_jobs (
                job_type,
                status,
                source_object_type,
                source_object_id,
                input_json,
                output_json,
                started_at,
                finished_at
            )
            VALUES (
                :job_type,
                CAST(:status AS app.job_status),
                :source_object_type,
                CAST(:source_object_id AS uuid),
                CAST(:input_json AS jsonb),
                CAST(:output_json AS jsonb),
                now(),
                now()
            )
            RETURNING id
            """
        ),
        {
            "job_type": job_type,
            "status": status,
            "source_object_type": source_object_type,
            "source_object_id": source_object_id,
            "input_json": json.dumps(input_json),
            "output_json": json.dumps(output_json or {}),
        },
    )
    await session.commit()
    return _iso(result.scalar_one())


async def fetch_track_list(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    scope: str = "all",
) -> list[TrackListItem]:
    scope_sql = ""
    params: dict[str, Any] = {"workspace_id": workspace_id, "user_id": user_id}
    if scope == "mine":
        scope_sql = "AND t.owner_user_id = CAST(:user_id AS uuid)"
    elif scope == "team":
        scope_sql = "AND (t.owner_user_id IS NULL OR t.owner_user_id <> CAST(:user_id AS uuid))"

    result = await session.execute(
        text(
            f"""
            SELECT
                t.id,
                t.workspace_id,
                t.name,
                t.slug,
                t.mode,
                t.state,
                owner.display_name AS owner_name,
                COUNT(DISTINCT ts.story_id) FILTER (WHERE ts.removed_at IS NULL) AS story_count,
                COUNT(DISTINCT ts.story_id) FILTER (
                    WHERE ts.removed_at IS NULL
                      AND s.story_state IN ('emerging', 'developing', 'confirmed', 'contested')
                ) AS active_story_count,
                COUNT(DISTINCT n.id) FILTER (WHERE n.read_at IS NULL) AS unread_count,
                MAX(s.last_seen_at) AS last_activity_at
            FROM app.tracks t
            LEFT JOIN app.users owner ON owner.id = t.owner_user_id
            LEFT JOIN app.track_stories ts ON ts.track_id = t.id
            LEFT JOIN app.stories s ON s.id = ts.story_id
            LEFT JOIN app.notifications n
              ON n.track_id = t.id
             AND (n.user_id = CAST(:user_id AS uuid) OR n.user_id IS NULL)
            WHERE t.workspace_id = CAST(:workspace_id AS uuid)
              {scope_sql}
            GROUP BY t.id, owner.display_name
            ORDER BY
                CASE WHEN t.owner_user_id = CAST(:user_id AS uuid) THEN 0 ELSE 1 END,
                MAX(s.last_seen_at) DESC NULLS LAST,
                t.updated_at DESC
            """
        ),
        params,
    )
    return [
        TrackListItem(
            trackId=_iso(row["id"]),
            workspaceId=_iso(row["workspace_id"]),
            name=row["name"],
            slug=row["slug"],
            mode=row["mode"],
            state=row["state"],
            ownerName=row["owner_name"],
            storyCount=int(row["story_count"] or 0),
            activeStoryCount=int(row["active_story_count"] or 0),
            unreadCount=int(row["unread_count"] or 0),
            lastActivityAt=row["last_activity_at"],
        )
        for row in result.mappings().all()
    ]


async def fetch_inbox_items(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    limit: int = 24,
) -> list[InboxItem]:
    result = await session.execute(
        text(
            """
            SELECT
                n.id,
                n.workspace_id,
                n.track_id,
                t.name AS track_name,
                n.story_id,
                s.title AS story_title,
                n.episode_id,
                e.headline AS episode_headline,
                t.mode,
                s.story_state AS state,
                n.reason,
                COALESCE(ts.priority_score, 0.0) AS priority_score,
                COALESCE(s.confidence_score, 0.0) AS confidence_score,
                COALESCE(s.contradiction_score, 0.0) AS contradiction_score,
                n.created_at,
                e.what_changed,
                e.why_it_matters,
                e.what_to_watch,
                episode_source.source_name,
                n.read_at IS NOT NULL AS is_read
            FROM app.notifications n
            LEFT JOIN app.tracks t ON t.id = n.track_id
            LEFT JOIN app.stories s ON s.id = n.story_id
            LEFT JOIN app.episodes e ON e.id = n.episode_id
            LEFT JOIN app.track_stories ts
              ON ts.track_id = n.track_id
             AND ts.story_id = n.story_id
            LEFT JOIN LATERAL (
                SELECT src.display_name AS source_name
                FROM app.episode_documents ed
                JOIN app.documents d ON d.id = ed.document_id
                LEFT JOIN app.sources src ON src.id = d.source_id
                WHERE ed.episode_id = n.episode_id
                ORDER BY d.published_at DESC NULLS LAST, d.created_at DESC
                LIMIT 1
            ) AS episode_source ON true
            WHERE n.workspace_id = CAST(:workspace_id AS uuid)
              AND (n.user_id = CAST(:user_id AS uuid) OR n.user_id IS NULL)
            ORDER BY
                n.read_at ASC NULLS FIRST,
                COALESCE(ts.priority_score, 0.0) DESC,
                n.created_at DESC
            LIMIT :limit
            """
        ),
        {"workspace_id": workspace_id, "user_id": user_id, "limit": limit},
    )
    return [
        InboxItem(
            id=_iso(row["id"]),
            workspaceId=_iso(row["workspace_id"]),
            trackId=_iso(row["track_id"]) if row["track_id"] else None,
            trackName=row["track_name"],
            storyId=_iso(row["story_id"]) if row["story_id"] else None,
            storyTitle=row["story_title"],
            episodeId=_iso(row["episode_id"]) if row["episode_id"] else None,
            episodeHeadline=row["episode_headline"],
            mode=row["mode"],
            state=row["state"],
            reason=row["reason"],
            priorityScore=float(row["priority_score"] or 0),
            confidenceScore=float(row["confidence_score"] or 0),
            contradictionScore=float(row["contradiction_score"] or 0),
            createdAt=row["created_at"],
            whatChanged=row["what_changed"],
            whyItMatters=row["why_it_matters"],
            whatToWatch=row["what_to_watch"],
            sourceName=row["source_name"],
            isRead=bool(row["is_read"]),
        )
        for row in result.mappings().all()
    ]


async def fetch_upcoming_events(
    session: AsyncSession,
    *,
    workspace_id: str,
    track_id: str | None = None,
    limit: int = 8,
) -> list[UpcomingEventItem]:
    track_filter = ""
    params: dict[str, Any] = {"workspace_id": workspace_id, "limit": limit}
    if track_id is not None:
        track_filter = "AND ts.track_id = CAST(:track_id AS uuid)"
        params["track_id"] = track_id

    result = await session.execute(
        text(
            f"""
            SELECT DISTINCT
                d.id,
                d.title,
                d.published_at,
                d.document_type,
                src.display_name AS source_name,
                d.canonical_url
            FROM app.track_stories ts
            JOIN app.story_documents sd ON sd.story_id = ts.story_id
            JOIN app.documents d ON d.id = sd.document_id
            LEFT JOIN app.sources src ON src.id = d.source_id
            JOIN app.tracks t ON t.id = ts.track_id
            WHERE d.document_type = CAST('calendar_event' AS app.document_type)
              AND t.workspace_id = CAST(:workspace_id AS uuid)
              {track_filter}
            ORDER BY d.published_at ASC NULLS LAST
            LIMIT :limit
            """
        ),
        params,
    )
    return [
        UpcomingEventItem(
            id=_iso(row["id"]),
            title=row["title"],
            publishedAt=row["published_at"],
            documentType=row["document_type"],
            sourceName=row["source_name"],
            canonicalUrl=row["canonical_url"],
        )
        for row in result.mappings().all()
    ]


async def fetch_notes(
    session: AsyncSession,
    *,
    workspace_id: str | None = None,
    track_id: str | None = None,
    story_id: str | None = None,
    episode_id: str | None = None,
    evidence_span_id: str | None = None,
    limit: int = 24,
) -> list[NoteDetail]:
    result = await session.execute(
        text(
            """
            SELECT
                n.*,
                u.display_name AS author_name
            FROM app.notes n
            LEFT JOIN app.users u ON u.id = n.author_user_id
            WHERE (:workspace_id IS NULL OR n.workspace_id = CAST(:workspace_id AS uuid))
              AND (:track_id IS NULL OR n.track_id = CAST(:track_id AS uuid))
              AND (:story_id IS NULL OR n.story_id = CAST(:story_id AS uuid))
              AND (:episode_id IS NULL OR n.episode_id = CAST(:episode_id AS uuid))
              AND (:evidence_span_id IS NULL OR n.evidence_span_id = CAST(:evidence_span_id AS uuid))
            ORDER BY n.pinned DESC, n.updated_at DESC
            LIMIT :limit
            """
        ),
        {
            "workspace_id": workspace_id,
            "track_id": track_id,
            "story_id": story_id,
            "episode_id": episode_id,
            "evidence_span_id": evidence_span_id,
            "limit": limit,
        },
    )
    return [_note_from_row(dict(row)) for row in result.mappings().all()]


async def fetch_note(session: AsyncSession, *, note_id: str) -> NoteDetail:
    result = await session.execute(
        text(
            """
            SELECT
                n.*,
                u.display_name AS author_name
            FROM app.notes n
            LEFT JOIN app.users u ON u.id = n.author_user_id
            WHERE n.id = CAST(:note_id AS uuid)
            """
        ),
        {"note_id": note_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_from_row(dict(row))


async def _note_workspace_id(
    session: AsyncSession,
    *,
    track_id: str | None,
    story_id: str | None,
    episode_id: str | None,
    evidence_span_id: str | None,
) -> tuple[str, dict[str, str | None]]:
    if track_id:
        result = await session.execute(
            text("SELECT workspace_id FROM app.tracks WHERE id = CAST(:id AS uuid)"),
            {"id": track_id},
        )
        workspace_id = result.scalar()
        if workspace_id is None:
            raise HTTPException(status_code=404, detail="Track not found")
        return str(workspace_id), {
            "track_id": track_id,
            "story_id": story_id,
            "episode_id": episode_id,
            "evidence_span_id": evidence_span_id,
        }
    if story_id:
        result = await session.execute(
            text("SELECT workspace_id FROM app.stories WHERE id = CAST(:id AS uuid)"),
            {"id": story_id},
        )
        workspace_id = result.scalar()
        if workspace_id is None:
            raise HTTPException(status_code=404, detail="Story not found")
        return str(workspace_id), {
            "track_id": track_id,
            "story_id": story_id,
            "episode_id": episode_id,
            "evidence_span_id": evidence_span_id,
        }
    if episode_id:
        result = await session.execute(
            text(
                """
                SELECT s.workspace_id, e.story_id
                FROM app.episodes e
                JOIN app.stories s ON s.id = e.story_id
                WHERE e.id = CAST(:id AS uuid)
                """
            ),
            {"id": episode_id},
        )
        row = result.mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        return str(row["workspace_id"]), {
            "track_id": track_id,
            "story_id": _iso(row["story_id"]),
            "episode_id": episode_id,
            "evidence_span_id": evidence_span_id,
        }
    if evidence_span_id:
        result = await session.execute(
            text(
                """
                SELECT s.workspace_id
                FROM app.evidence_spans es
                JOIN app.generated_sentence_evidence gse ON gse.evidence_span_id = es.id
                JOIN app.generated_sentences gs ON gs.id = gse.generated_sentence_id
                JOIN app.stories s ON s.id = gs.story_id
                WHERE es.id = CAST(:id AS uuid)
                LIMIT 1
                """
            ),
            {"id": evidence_span_id},
        )
        workspace_id = result.scalar()
        if workspace_id is None:
            raise HTTPException(status_code=404, detail="Evidence span not found")
        return str(workspace_id), {
            "track_id": track_id,
            "story_id": story_id,
            "episode_id": episode_id,
            "evidence_span_id": evidence_span_id,
        }
    raise HTTPException(status_code=400, detail="A note target is required")


async def create_note(
    session: AsyncSession,
    *,
    author_user_id: str,
    scope: str,
    track_id: str | None,
    story_id: str | None,
    episode_id: str | None,
    evidence_span_id: str | None,
    body_md: str,
    pinned: bool,
    metadata: dict[str, Any],
) -> NoteDetail:
    workspace_id, resolved_ids = await _note_workspace_id(
        session,
        track_id=track_id,
        story_id=story_id,
        episode_id=episode_id,
        evidence_span_id=evidence_span_id,
    )
    result = await session.execute(
        text(
            """
            INSERT INTO app.notes (
                workspace_id,
                author_user_id,
                scope,
                track_id,
                story_id,
                episode_id,
                evidence_span_id,
                body_md,
                pinned,
                metadata
            )
            VALUES (
                CAST(:workspace_id AS uuid),
                CAST(:author_user_id AS uuid),
                CAST(:scope AS app.note_scope),
                CAST(:track_id AS uuid),
                CAST(:story_id AS uuid),
                CAST(:episode_id AS uuid),
                CAST(:evidence_span_id AS uuid),
                :body_md,
                :pinned,
                CAST(:metadata AS jsonb)
            )
            RETURNING *
            """
        ),
        {
            "workspace_id": workspace_id,
            "author_user_id": author_user_id,
            "scope": scope,
            "track_id": resolved_ids["track_id"],
            "story_id": resolved_ids["story_id"],
            "episode_id": resolved_ids["episode_id"],
            "evidence_span_id": resolved_ids["evidence_span_id"],
            "body_md": body_md,
            "pinned": pinned,
            "metadata": json.dumps(metadata),
        },
    )
    row = dict(result.mappings().one())
    row["author_name"] = None
    await session.commit()
    return _note_from_row(row)


async def update_note(
    session: AsyncSession,
    *,
    note_id: str,
    body_md: str | None,
    pinned: bool | None,
    metadata: dict[str, Any] | None,
) -> NoteDetail:
    result = await session.execute(
        text(
            """
            UPDATE app.notes
            SET
                body_md = COALESCE(:body_md, body_md),
                pinned = COALESCE(:pinned, pinned),
                metadata = COALESCE(CAST(:metadata AS jsonb), metadata),
                updated_at = now()
            WHERE id = CAST(:note_id AS uuid)
            RETURNING *
            """
        ),
        {
            "note_id": note_id,
            "body_md": body_md,
            "pinned": pinned,
            "metadata": json.dumps(metadata) if metadata is not None else None,
        },
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    author = await session.execute(
        text("SELECT display_name FROM app.users WHERE id = CAST(:id AS uuid)"),
        {"id": row["author_user_id"]},
    )
    payload = dict(row)
    payload["author_name"] = author.scalar()
    await session.commit()
    return _note_from_row(payload)


async def delete_note(session: AsyncSession, *, note_id: str) -> None:
    result = await session.execute(
        text("DELETE FROM app.notes WHERE id = CAST(:note_id AS uuid) RETURNING id"),
        {"note_id": note_id},
    )
    if result.scalar() is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await session.commit()


async def fetch_track_snapshots(
    session: AsyncSession,
    *,
    track_id: str,
    limit: int = 10,
) -> list[SnapshotDetail]:
    result = await session.execute(
        text(
            """
            SELECT *
            FROM app.track_snapshots
            WHERE track_id = CAST(:track_id AS uuid)
            ORDER BY snapshot_at DESC
            LIMIT :limit
            """
        ),
        {"track_id": track_id, "limit": limit},
    )
    return [_snapshot_from_row(dict(row)) for row in result.mappings().all()]


async def insert_track_snapshot(
    session: AsyncSession,
    *,
    track_id: str,
    summary_text: str,
    summary_json: dict[str, Any],
    metrics_json: dict[str, Any],
    created_by_agent: str,
    artifact_manifest: dict[str, Any],
) -> SnapshotDetail:
    result = await session.execute(
        text(
            """
            INSERT INTO app.track_snapshots (
                track_id,
                summary_text,
                summary_json,
                metrics_json,
                created_by_agent,
                artifact_manifest
            )
            VALUES (
                CAST(:track_id AS uuid),
                :summary_text,
                CAST(:summary_json AS jsonb),
                CAST(:metrics_json AS jsonb),
                :created_by_agent,
                CAST(:artifact_manifest AS jsonb)
            )
            RETURNING *
            """
        ),
        {
            "track_id": track_id,
            "summary_text": summary_text,
            "summary_json": json.dumps(summary_json),
            "metrics_json": json.dumps(metrics_json),
            "created_by_agent": created_by_agent,
            "artifact_manifest": json.dumps(artifact_manifest),
        },
    )
    await session.commit()
    return _snapshot_from_row(dict(result.mappings().one()))


async def mark_notification_read(
    session: AsyncSession,
    *,
    notification_id: str,
    user_id: str,
) -> None:
    result = await session.execute(
        text(
            """
            UPDATE app.notifications
            SET read_at = COALESCE(read_at, now())
            WHERE id = CAST(:notification_id AS uuid)
              AND (user_id = CAST(:user_id AS uuid) OR user_id IS NULL)
            RETURNING id
            """
        ),
        {"notification_id": notification_id, "user_id": user_id},
    )
    if result.scalar() is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    await session.commit()


async def mute_track_for_notification(
    session: AsyncSession,
    *,
    notification_id: str,
    user_id: str,
) -> None:
    result = await session.execute(
        text(
            """
            SELECT track_id
            FROM app.notifications
            WHERE id = CAST(:notification_id AS uuid)
              AND (user_id = CAST(:user_id AS uuid) OR user_id IS NULL)
            """
        ),
        {"notification_id": notification_id, "user_id": user_id},
    )
    track_id = result.scalar()
    if track_id is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    await session.execute(
        text(
            """
            INSERT INTO app.user_track_preferences (user_id, track_id, muted, digest_mode)
            VALUES (CAST(:user_id AS uuid), CAST(:track_id AS uuid), true, 'quiet')
            ON CONFLICT (user_id, track_id) DO UPDATE
            SET muted = true,
                digest_mode = 'quiet',
                last_seen_at = now()
            """
        ),
        {"user_id": user_id, "track_id": _iso(track_id)},
    )
    await session.commit()


async def fetch_story_contradictions(
    session: AsyncSession,
    *,
    story_id: str,
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT DISTINCT
                gs.id AS sentence_id,
                gs.sentence_text,
                gs.verdict,
                es.id AS evidence_span_id,
                es.quote_text,
                src.display_name AS source_name,
                gse.support_status
            FROM app.generated_sentences gs
            JOIN app.generated_sentence_evidence gse ON gse.generated_sentence_id = gs.id
            JOIN app.evidence_spans es ON es.id = gse.evidence_span_id
            JOIN app.documents d ON d.id = es.document_id
            LEFT JOIN app.sources src ON src.id = d.source_id
            WHERE gs.story_id = CAST(:story_id AS uuid)
              AND (
                    gse.support_status IN ('contradicted', 'mixed')
                    OR gs.verdict IN ('contradicted', 'mixed')
                )
            ORDER BY gs.sentence_order ASC, es.id ASC
            """
        ),
        {"story_id": story_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def fetch_track_canvas(
    session: AsyncSession,
    *,
    track_id: str,
) -> TrackCanvasResponse:
    track = await fetch_track_detail(session, track_id)
    stories = await fetch_track_stories(session, track_id=track_id, limit=12)
    notes = await fetch_notes(session, track_id=track_id, limit=10)
    snapshots = await fetch_track_snapshots(session, track_id=track_id, limit=5)

    workspace_result = await session.execute(
        text("SELECT workspace_id FROM app.tracks WHERE id = CAST(:track_id AS uuid)"),
        {"track_id": track_id},
    )
    workspace_id = workspace_result.scalar()
    upcoming_events = await fetch_upcoming_events(
        session,
        workspace_id=_iso(workspace_id),
        track_id=track_id,
        limit=6,
    )

    quotes_result = await session.execute(
        text(
            """
            SELECT DISTINCT
                es.id,
                es.quote_text,
                src.display_name AS source_name,
                gse.support_status
            FROM app.track_stories ts
            JOIN app.generated_sentences gs ON gs.story_id = ts.story_id
            JOIN app.generated_sentence_evidence gse ON gse.generated_sentence_id = gs.id
            JOIN app.evidence_spans es ON es.id = gse.evidence_span_id
            JOIN app.documents d ON d.id = es.document_id
            LEFT JOIN app.sources src ON src.id = d.source_id
            WHERE ts.track_id = CAST(:track_id AS uuid)
            ORDER BY es.id
            LIMIT 6
            """
        ),
        {"track_id": track_id},
    )
    quotes = [
        {
            "id": _iso(row["id"]),
            "quoteText": row["quote_text"],
            "sourceName": row["source_name"],
            "supportStatus": row["support_status"],
        }
        for row in quotes_result.mappings().all()
    ]

    reaction_result = await session.execute(
        text(
            """
            SELECT metric_name, direction, value_numeric, unit, observed_at
            FROM app.market_reactions mr
            JOIN app.track_stories ts ON ts.story_id = mr.story_id
            WHERE ts.track_id = CAST(:track_id AS uuid)
            ORDER BY observed_at DESC
            LIMIT 8
            """
        ),
        {"track_id": track_id},
    )
    reactions = [dict(row) for row in reaction_result.mappings().all()]

    snapshot_blocks = [
        snapshot.model_dump(by_alias=True) for snapshot in snapshots
    ]
    mode_data = ModeData(
        kind=track.mode,
        blocks={
            "quotes": quotes,
            "upcomingEvents": [item.model_dump(by_alias=True) for item in upcoming_events],
            "recentSnapshots": snapshot_blocks,
            "marketReactions": reactions,
            "storyline": [item.model_dump(by_alias=True) for item in stories[:6]],
        },
    )
    return TrackCanvasResponse(
        generatedAt=_now(),
        track=track,
        stories=stories,
        notes=notes,
        snapshots=snapshots,
        upcomingEvents=upcoming_events,
        modeData=mode_data,
    )
