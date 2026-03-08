from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import EvidenceSnippet, SourceSnippet, SummaryFrame
from app.schemas.dashboard import RecentNotificationItem
from app.schemas.stories import EpisodeDetail, StoryDetail
from app.schemas.tracks import (
    BootstrapOption,
    BootstrapResponse,
    LiveBoardTrackItem,
    StoryPreview,
    TrackDetail,
    TrackMetrics,
)


def _iso_uuid(value: Any) -> str:
    return str(value)


def _summary_from_row(row: dict[str, Any]) -> SummaryFrame | None:
    if (
        not row.get("what_changed")
        and not row.get("why_it_matters")
        and not row.get("what_to_watch")
    ):
        return None
    return SummaryFrame(
        what_changed=row.get("what_changed"),
        why_it_matters=row.get("why_it_matters"),
        what_to_watch=row.get("what_to_watch"),
    )


def _story_preview_from_row(row: dict[str, Any]) -> StoryPreview:
    return StoryPreview(
        storyId=_iso_uuid(row["story_id"]),
        title=row["story_title"],
        storyState=row["story_state"],
        hotnessScore=float(row["hotness_score"] or 0),
        confidenceScore=float(row["confidence_score"] or 0),
        contradictionScore=float(row["contradiction_score"] or 0),
        latestEpisodeId=_iso_uuid(row["latest_episode_id"]) if row["latest_episode_id"] else None,
        latestEpisodeType=row["episode_type"],
        headline=row["headline"],
        whatChanged=row["what_changed"],
        whyItMatters=row["why_it_matters"],
        whatToWatch=row["what_to_watch"],
        episodeCreatedAt=row["episode_created_at"],
        priorityScore=float(row["priority_score"] or 0),
        relevanceScore=float(row["relevance_score"] or 0),
    )


async def fetch_live_board(
    session: AsyncSession,
    workspace_id: str | None,
    limit: int,
) -> list[LiveBoardTrackItem]:
    query = text(
        """
        SELECT *
        FROM app.v_track_live_board
        WHERE (CAST(:workspace_id AS uuid) IS NULL OR workspace_id = CAST(:workspace_id AS uuid))
        ORDER BY priority_score DESC NULLS LAST, episode_created_at DESC NULLS LAST
        LIMIT :limit
        """
    )
    result = await session.execute(query, {"workspace_id": workspace_id, "limit": limit})
    rows = [dict(row) for row in result.mappings().all()]

    grouped: OrderedDict[str, LiveBoardTrackItem] = OrderedDict()
    for row in rows:
        track_id = _iso_uuid(row["track_id"])
        preview = _story_preview_from_row(row)
        item = grouped.get(track_id)
        if item is None:
            item = LiveBoardTrackItem(
                trackId=track_id,
                trackName=row["track_name"],
                mode=row["mode"],
                storyCount=0,
                topSummary=_summary_from_row(row),
                stories=[],
            )
            grouped[track_id] = item
        item.stories.append(preview)
        item.story_count = len(item.stories)
        if item.top_summary is None:
            item.top_summary = _summary_from_row(row)

    return list(grouped.values())


async def fetch_track_bootstrap(session: AsyncSession) -> BootstrapResponse:
    workspaces_result = await session.execute(
        text(
            """
            SELECT id, name, slug
            FROM app.workspaces
            ORDER BY created_at ASC
            LIMIT 20
            """
        )
    )
    workspaces = [
        BootstrapOption(
            id=_iso_uuid(row["id"]),
            label=row["name"],
            value=row["slug"],
        )
        for row in workspaces_result.mappings().all()
    ]

    return BootstrapResponse(
        workspaces=workspaces,
        modes=[
            BootstrapOption(
                id="scheduled_release",
                label="Scheduled Release",
                value="scheduled_release",
            ),
            BootstrapOption(
                id="policy_communication",
                label="Policy Communication",
                value="policy_communication",
            ),
            BootstrapOption(
                id="breaking_shock",
                label="Breaking Shock",
                value="breaking_shock",
            ),
            BootstrapOption(
                id="slow_burn_theme",
                label="Slow-burn Theme",
                value="slow_burn_theme",
            ),
            BootstrapOption(
                id="watchlist_exposure",
                label="Watchlist / Exposure",
                value="watchlist_exposure",
            ),
            BootstrapOption(id="custom", label="Custom", value="custom"),
        ],
        states=[
            BootstrapOption(id="draft", label="Draft", value="draft"),
            BootstrapOption(id="active", label="Active", value="active"),
            BootstrapOption(id="paused", label="Paused", value="paused"),
        ],
    )


async def fetch_track_detail(session: AsyncSession, track_id: str) -> TrackDetail:
    detail_query = text(
        """
        SELECT
            t.id,
            t.name,
            t.slug,
            t.description,
            t.mode,
            t.state,
            t.memory_window_days,
            t.alert_policy,
            COUNT(ts.story_id) FILTER (WHERE ts.removed_at IS NULL) AS story_count,
            COUNT(ts.story_id) FILTER (
                WHERE ts.removed_at IS NULL
                  AND s.story_state IN ('emerging', 'developing', 'confirmed', 'contested')
            ) AS active_story_count,
            MAX(s.last_seen_at) AS last_activity_at
        FROM app.tracks t
        LEFT JOIN app.track_stories ts ON ts.track_id = t.id
        LEFT JOIN app.stories s ON s.id = ts.story_id
        WHERE t.id = CAST(:track_id AS uuid)
        GROUP BY t.id
        """
    )
    detail_result = await session.execute(detail_query, {"track_id": track_id})
    row = detail_result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    summary_query = text(
        """
        SELECT what_changed, why_it_matters, what_to_watch
        FROM app.v_track_live_board
        WHERE track_id = CAST(:track_id AS uuid)
        ORDER BY priority_score DESC NULLS LAST, episode_created_at DESC NULLS LAST
        LIMIT 1
        """
    )
    summary_result = await session.execute(summary_query, {"track_id": track_id})
    summary_row = summary_result.mappings().first()

    return TrackDetail(
        trackId=_iso_uuid(row["id"]),
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        mode=row["mode"],
        state=row["state"],
        memoryWindowDays=row["memory_window_days"],
        alertPolicy=row["alert_policy"] or {},
        topSummary=_summary_from_row(dict(summary_row)) if summary_row else None,
        metrics=TrackMetrics(
            storyCount=int(row["story_count"] or 0),
            activeStoryCount=int(row["active_story_count"] or 0),
            lastActivityAt=row["last_activity_at"],
        ),
    )


async def fetch_track_stories(
    session: AsyncSession,
    track_id: str,
    limit: int,
) -> list[StoryPreview]:
    query = text(
        """
        SELECT *
        FROM app.v_track_live_board
        WHERE track_id = CAST(:track_id AS uuid)
        ORDER BY priority_score DESC NULLS LAST, episode_created_at DESC NULLS LAST
        LIMIT :limit
        """
    )
    result = await session.execute(query, {"track_id": track_id, "limit": limit})
    return [_story_preview_from_row(dict(row)) for row in result.mappings().all()]


def _episode_from_row(row: dict[str, Any]) -> EpisodeDetail:
    return EpisodeDetail(
        episodeId=_iso_uuid(row["id"]),
        episodeType=row["episode_type"],
        headline=row["headline"],
        stateFrom=row["state_from"],
        stateTo=row["state_to"],
        summary=SummaryFrame(
            what_changed=row["what_changed"],
            why_it_matters=row["why_it_matters"],
            what_to_watch=row["what_to_watch"],
        ),
        significanceScore=float(row["significance_score"] or 0),
        confidenceScore=float(row["confidence_score"] or 0),
        contradictionScore=float(row["contradiction_score"] or 0),
        createdAt=row["created_at"],
    )


async def fetch_story_detail(session: AsyncSession, story_id: str) -> StoryDetail:
    story_query = text(
        """
        SELECT
            s.id,
            s.title,
            s.story_state,
            s.dominant_mode,
            s.hotness_score,
            s.novelty_score,
            s.contradiction_score,
            s.confidence_score
        FROM app.stories s
        WHERE s.id = CAST(:story_id AS uuid)
        """
    )
    story_result = await session.execute(story_query, {"story_id": story_id})
    row = story_result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Story not found")

    episodes_query = text(
        """
        SELECT
            e.id,
            e.episode_type,
            e.headline,
            e.state_from,
            e.state_to,
            e.what_changed,
            e.why_it_matters,
            e.what_to_watch,
            e.significance_score,
            e.confidence_score,
            e.contradiction_score,
            e.created_at
        FROM app.episodes e
        WHERE e.story_id = CAST(:story_id AS uuid)
        ORDER BY e.created_at DESC
        LIMIT 10
        """
    )
    episodes_result = await session.execute(episodes_query, {"story_id": story_id})
    episode_rows = [dict(item) for item in episodes_result.mappings().all()]
    episodes = [_episode_from_row(item) for item in episode_rows]
    latest_episode = episodes[0] if episodes else None

    sources: list[SourceSnippet] = []
    evidence: list[EvidenceSnippet] = []
    if latest_episode is not None:
        source_query = text(
            """
            SELECT
                d.id,
                d.title,
                src.display_name AS source_name,
                src.source_type,
                d.published_at,
                d.document_type
            FROM app.episode_documents ed
            JOIN app.documents d ON d.id = ed.document_id
            LEFT JOIN app.sources src ON src.id = d.source_id
            WHERE ed.episode_id = CAST(:episode_id AS uuid)
            ORDER BY d.published_at DESC NULLS LAST
            LIMIT 8
            """
        )
        source_result = await session.execute(
            source_query, {"episode_id": latest_episode.episode_id}
        )
        sources = [
            SourceSnippet(
                id=_iso_uuid(item["id"]),
                title=item["title"],
                source_name=item["source_name"],
                source_type=item["source_type"],
                published_at=item["published_at"],
                document_type=item["document_type"],
            )
            for item in source_result.mappings().all()
        ]

        evidence_query = text(
            """
            SELECT DISTINCT
                es.id,
                es.quote_text,
                src.display_name AS source_name,
                src.source_type,
                gse.support_status
            FROM app.generated_sentences gs
            JOIN app.generated_sentence_evidence gse ON gse.generated_sentence_id = gs.id
            JOIN app.evidence_spans es ON es.id = gse.evidence_span_id
            JOIN app.documents d ON d.id = es.document_id
            LEFT JOIN app.sources src ON src.id = d.source_id
            WHERE gs.episode_id = CAST(:episode_id AS uuid)
            ORDER BY es.id
            LIMIT 10
            """
        )
        evidence_result = await session.execute(
            evidence_query, {"episode_id": latest_episode.episode_id}
        )
        evidence = [
            EvidenceSnippet(
                id=_iso_uuid(item["id"]),
                quote_text=item["quote_text"],
                source_name=item["source_name"],
                source_type=item["source_type"],
                support_status=item["support_status"],
            )
            for item in evidence_result.mappings().all()
        ]

    summary = latest_episode.summary if latest_episode else SummaryFrame()

    return StoryDetail(
        storyId=_iso_uuid(row["id"]),
        title=row["title"],
        state=row["story_state"],
        dominantMode=row["dominant_mode"],
        scores={
            "hotness": float(row["hotness_score"] or 0),
            "novelty": float(row["novelty_score"] or 0),
            "contradiction": float(row["contradiction_score"] or 0),
            "confidence": float(row["confidence_score"] or 0),
        },
        summary=summary,
        latestEpisode=latest_episode,
        episodes=episodes,
        sources=sources,
        evidence=evidence,
    )


async def fetch_outbox_events(
    session: AsyncSession,
    workspace_id: str | None,
    after: datetime | None,
) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
            id,
            workspace_id,
            event_type,
            aggregate_type,
            aggregate_id,
            payload,
            created_at
        FROM app.event_outbox
        WHERE (CAST(:workspace_id AS uuid) IS NULL OR workspace_id = CAST(:workspace_id AS uuid))
          AND (
              CAST(:after_ts AS timestamptz) IS NULL
              OR created_at > CAST(:after_ts AS timestamptz)
          )
        ORDER BY created_at ASC
        LIMIT 100
        """
    )
    result = await session.execute(
        query, {"workspace_id": workspace_id, "after_ts": after}
    )
    return [dict(item) for item in result.mappings().all()]


async def fetch_source_health_snapshot(session: AsyncSession) -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
            s.source_key,
            s.display_name,
            s.source_type,
            s.is_active,
            cursor_row.last_success_at,
            cursor_row.last_published_at,
            run_row.status AS last_run_status,
            run_row.started_at AS last_run_started_at,
            run_row.finished_at AS last_run_finished_at,
            run_row.discovered_count,
            run_row.inserted_count,
            run_row.updated_count,
            run_row.failed_count,
            run_row.error_text
        FROM app.sources s
        LEFT JOIN LATERAL (
            SELECT
                c.last_success_at,
                c.last_published_at
            FROM app.ingestion_cursors c
            WHERE c.source_id = s.id
              AND c.cursor_key = 'default'
            ORDER BY c.last_success_at DESC NULLS LAST
            LIMIT 1
        ) AS cursor_row ON true
        LEFT JOIN LATERAL (
            SELECT
                r.status,
                r.started_at,
                r.finished_at,
                r.discovered_count,
                r.inserted_count,
                r.updated_count,
                r.failed_count,
                r.error_text
            FROM app.ingestion_runs r
            WHERE r.source_id = s.id
            ORDER BY r.started_at DESC
            LIMIT 1
        ) AS run_row ON true
        ORDER BY s.display_name ASC
        """
    )
    result = await session.execute(query)
    return [dict(item) for item in result.mappings().all()]


async def fetch_recent_notifications(
    session: AsyncSession,
    workspace_id: str | None,
    limit: int,
) -> list[RecentNotificationItem]:
    query = text(
        """
        SELECT
            n.id,
            n.title,
            n.body_text,
            n.reason,
            n.channel,
            n.created_at,
            n.scheduled_for,
            n.sent_at,
            n.read_at,
            n.track_id,
            t.name AS track_name,
            n.story_id,
            s.title AS story_title,
            n.episode_id,
            e.headline AS episode_headline
        FROM app.notifications n
        LEFT JOIN app.tracks t ON t.id = n.track_id
        LEFT JOIN app.stories s ON s.id = n.story_id
        LEFT JOIN app.episodes e ON e.id = n.episode_id
        WHERE (CAST(:workspace_id AS uuid) IS NULL OR n.workspace_id = CAST(:workspace_id AS uuid))
        ORDER BY n.created_at DESC
        LIMIT :limit
        """
    )
    result = await session.execute(query, {"workspace_id": workspace_id, "limit": limit})
    return [
        RecentNotificationItem(
            id=_iso_uuid(row["id"]),
            title=row["title"],
            bodyText=row["body_text"],
            reason=row["reason"],
            channel=row["channel"],
            createdAt=row["created_at"],
            scheduledFor=row["scheduled_for"],
            sentAt=row["sent_at"],
            readAt=row["read_at"],
            trackId=_iso_uuid(row["track_id"]) if row["track_id"] else None,
            trackName=row["track_name"],
            storyId=_iso_uuid(row["story_id"]) if row["story_id"] else None,
            storyTitle=row["story_title"],
            episodeId=_iso_uuid(row["episode_id"]) if row["episode_id"] else None,
            episodeHeadline=row["episode_headline"],
        )
        for row in result.mappings().all()
    ]
