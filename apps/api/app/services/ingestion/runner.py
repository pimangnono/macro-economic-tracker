from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.ingestion import IngestionPullResponse
from app.services.enrichment import record_story_enrichment
from app.services.ingestion.sources import SourceDefinition, get_source_definition
from app.services.pipeline.queue import enqueue_job as _enqueue_pipeline_job

STOPWORDS = {
    "about",
    "after",
    "again",
    "agency",
    "amid",
    "analyst",
    "announces",
    "another",
    "before",
    "board",
    "comment",
    "comments",
    "committee",
    "decision",
    "economic",
    "economics",
    "expected",
    "following",
    "further",
    "governor",
    "governors",
    "group",
    "keeps",
    "latest",
    "macro",
    "meeting",
    "more",
    "next",
    "outlook",
    "path",
    "policy",
    "press",
    "release",
    "releases",
    "report",
    "reports",
    "said",
    "says",
    "schedule",
    "series",
    "statement",
    "summary",
    "than",
    "that",
    "their",
    "this",
    "track",
    "update",
    "watch",
    "with",
}
HIGH_SIGNAL_TOKENS = {
    "bls",
    "cpi",
    "cuts",
    "ecb",
    "employment",
    "fomc",
    "gdp",
    "inflation",
    "payrolls",
    "pce",
    "ppi",
    "rates",
    "recession",
    "shelter",
    "tariffs",
    "unemployment",
    "yield",
    "yields",
}
MACRO_ALIASES = {
    "consumer price index": "cpi",
    "euro area": "eurozone",
    "federal reserve": "fed",
    "federal open market committee": "fomc",
    "personal consumption expenditures": "pce",
    "producer price index": "ppi",
    "press conference": "press conference",
    "bureau of labor statistics": "bls",
    "european central bank": "ecb",
}


@dataclass(frozen=True)
class FeedItem:
    external_id: str
    url: str
    title: str
    body_text: str
    author: str | None
    published_at: datetime | None
    language: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class TrackCandidate:
    track_id: str
    workspace_id: str
    name: str
    description: str | None
    mode: str


@dataclass(frozen=True)
class TrackMatch:
    track_id: str
    workspace_id: str
    score: float
    reason: str
    mode: str


@dataclass(frozen=True)
class ItemProcessResult:
    inserted_count: int
    updated_count: int
    track_ids: set[str]
    story_ids: set[str]
    episode_ids: set[str]


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "story"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_text(value: str | None) -> str:
    text_value = (value or "").lower()
    for source, target in MACRO_ALIASES.items():
        text_value = text_value.replace(source, target)
    return re.sub(r"\s+", " ", text_value).strip()


def _tokenize(value: str | None) -> set[str]:
    text_value = _normalize_text(value)
    tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_+-]{1,}", text_value)
        if token not in STOPWORDS and len(token) >= 2
    }
    return tokens


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _parse_ics_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%Y%m%d":
            return parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _extract_link(item: ElementTree.Element) -> str:
    for child in item:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        text_value = _text(child)
        if text_value:
            return text_value
    return ""


def _parse_rss_feed(source: SourceDefinition, payload: str) -> list[FeedItem]:
    root = ElementTree.fromstring(payload)
    items: list[FeedItem] = []
    entry_nodes = [
        node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}
    ]

    for node in entry_nodes:
        title = _text(next((child for child in node if _local_name(child.tag) == "title"), None))
        description = _text(
            next(
                (
                    child
                    for child in node
                    if _local_name(child.tag) in {"description", "summary", "content"}
                ),
                None,
            )
        )
        link = _extract_link(node)
        guid = _text(next((child for child in node if _local_name(child.tag) in {"guid", "id"}), None))
        author = _text(
            next(
                (
                    child
                    for child in node
                    if _local_name(child.tag) in {"author", "creator", "dc:creator"}
                ),
                None,
            )
        )
        published_raw = _text(
            next(
                (
                    child
                    for child in node
                    if _local_name(child.tag) in {"pubDate", "published", "updated"}
                ),
                None,
            )
        )
        body_text = _strip_html(description)
        resolved_link = link.strip() or urljoin(source.base_url, guid.strip())
        if not title or not resolved_link:
            continue

        items.append(
            FeedItem(
                external_id=guid.strip() or resolved_link,
                url=resolved_link,
                title=title,
                body_text=body_text,
                author=author or None,
                published_at=_parse_datetime(published_raw),
                language="en",
                raw_payload={
                    "title": title,
                    "description": description,
                    "link": resolved_link,
                    "guid": guid,
                    "author": author,
                    "published_at": published_raw,
                },
            )
        )

    return items


def _unfold_ics_lines(payload: str) -> list[str]:
    lines = payload.splitlines()
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
            continue
        unfolded.append(line)
    return unfolded


def _unescape_ics(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_ics_feed(source: SourceDefinition, payload: str) -> list[FeedItem]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in _unfold_ics_lines(payload):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key_part, raw_value = line.split(":", 1)
        key = key_part.split(";", 1)[0]
        current[key] = raw_value

    items: list[FeedItem] = []
    for event in events:
        title = _unescape_ics(event.get("SUMMARY", "")).strip()
        description = _unescape_ics(event.get("DESCRIPTION", "")).strip()
        url = _unescape_ics(event.get("URL", "")).strip()
        uid = _unescape_ics(event.get("UID", "")).strip()
        published_at = _parse_ics_datetime(event.get("DTSTART"))
        if not title:
            continue

        resolved_url = url or urljoin(source.base_url, f"/schedule/{uid or _slugify(title)}")
        items.append(
            FeedItem(
                external_id=uid or resolved_url,
                url=resolved_url,
                title=title,
                body_text=description,
                author=source.display_name,
                published_at=published_at,
                language="en",
                raw_payload=event,
            )
        )

    return items


async def _fetch_feed_items(source: SourceDefinition, *, limit: int) -> list[FeedItem]:
    settings = get_settings()
    headers = {"User-Agent": settings.ingestion_http_user_agent}
    timeout = httpx.Timeout(settings.ingestion_http_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        response = await client.get(source.feed_url)
        response.raise_for_status()
        payload = response.text

    if source.feed_kind == "rss":
        items = _parse_rss_feed(source, payload)
    elif source.feed_kind == "ics":
        items = _parse_ics_feed(source, payload)
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported feed kind: {source.feed_kind}")

    items.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


def _document_text(item: FeedItem) -> str:
    return " ".join(part for part in [item.title, item.body_text] if part).strip()


def _document_type_boost(track_mode: str, document_type: str) -> float:
    if track_mode == "scheduled_release" and document_type in {"press_release", "calendar_event"}:
        return 0.35
    if track_mode == "policy_communication" and document_type == "speech":
        return 0.35
    return 0.0


def _track_match_score(track: TrackCandidate, item: FeedItem, document_type: str) -> TrackMatch | None:
    document_text = _document_text(item)
    document_tokens = _tokenize(document_text)
    track_tokens = _tokenize(" ".join(part for part in [track.name, track.description or ""] if part))
    overlap = sorted(document_tokens & track_tokens)
    if not overlap:
        return None

    score = sum(1.0 if token in HIGH_SIGNAL_TOKENS else 0.35 for token in overlap)
    normalized_document = _normalize_text(document_text)
    normalized_name = _normalize_text(track.name)
    if normalized_name and normalized_name in normalized_document:
        score += 0.75
    score += _document_type_boost(track.mode, document_type)

    if score < 1.0:
        return None

    reason = ", ".join(overlap[:4])
    return TrackMatch(
        track_id=track.track_id,
        workspace_id=track.workspace_id,
        score=min(score, 2.5),
        reason=reason,
        mode=track.mode,
    )


async def _load_active_tracks(session: AsyncSession) -> list[TrackCandidate]:
    result = await session.execute(
        text(
            """
            SELECT id, workspace_id, name, description, mode
            FROM app.tracks
            WHERE state = CAST('active' AS app.track_state)
            ORDER BY created_at ASC
            """
        )
    )
    return [
        TrackCandidate(
            track_id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            name=row["name"],
            description=row["description"],
            mode=row["mode"],
        )
        for row in result.mappings().all()
    ]


async def _ensure_source(session: AsyncSession, source: SourceDefinition) -> str:
    payload = json.dumps({"feed_kind": source.feed_kind, "requires_api_key": source.requires_api_key})
    result = await session.execute(
        text(
            """
            INSERT INTO app.sources (
                source_key,
                display_name,
                source_type,
                base_url,
                rss_url,
                default_language,
                trust_score,
                is_active,
                metadata
            )
            VALUES (
                :source_key,
                :display_name,
                CAST(:source_type AS app.source_type),
                :base_url,
                :rss_url,
                'en',
                :trust_score,
                true,
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (source_key) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                source_type = EXCLUDED.source_type,
                base_url = EXCLUDED.base_url,
                rss_url = EXCLUDED.rss_url,
                trust_score = EXCLUDED.trust_score,
                is_active = true,
                metadata = app.sources.metadata || EXCLUDED.metadata
            RETURNING id
            """
        ),
        {
            "source_key": source.source_key,
            "display_name": source.display_name,
            "source_type": source.source_type,
            "base_url": source.base_url,
            "rss_url": source.feed_url if source.feed_kind == "rss" else None,
            "trust_score": source.trust_score,
            "metadata": payload,
        },
    )
    return str(result.scalar_one())


async def _create_ingestion_run(session: AsyncSession, source_id: str, source_key: str) -> str:
    result = await session.execute(
        text(
            """
            INSERT INTO app.ingestion_runs (source_id, status, metadata)
            VALUES (
                CAST(:source_id AS uuid),
                CAST('running' AS app.job_status),
                CAST(:metadata AS jsonb)
            )
            RETURNING id
            """
        ),
        {"source_id": source_id, "metadata": json.dumps({"source_key": source_key})},
    )
    return str(result.scalar_one())


async def _finish_ingestion_run(
    session: AsyncSession,
    *,
    run_id: str,
    status: str,
    discovered_count: int,
    inserted_count: int,
    updated_count: int,
    failed_count: int,
    error_text: str | None,
) -> None:
    await session.execute(
        text(
            """
            UPDATE app.ingestion_runs
            SET
                status = CAST(:status AS app.job_status),
                finished_at = now(),
                discovered_count = :discovered_count,
                inserted_count = :inserted_count,
                updated_count = :updated_count,
                failed_count = :failed_count,
                error_text = :error_text
            WHERE id = CAST(:run_id AS uuid)
            """
        ),
        {
            "run_id": run_id,
            "status": status,
            "discovered_count": discovered_count,
            "inserted_count": inserted_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "error_text": error_text,
        },
    )


async def _update_cursor(
    session: AsyncSession,
    *,
    source_id: str,
    latest_published_at: datetime | None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.ingestion_cursors (
                source_id,
                cursor_key,
                last_published_at,
                last_success_at
            )
            VALUES (
                CAST(:source_id AS uuid),
                'default',
                :last_published_at,
                now()
            )
            ON CONFLICT (source_id, cursor_key) DO UPDATE
            SET last_published_at = GREATEST(
                    COALESCE(app.ingestion_cursors.last_published_at, CAST('epoch' AS timestamptz)),
                    COALESCE(EXCLUDED.last_published_at, CAST('epoch' AS timestamptz))
                ),
                last_success_at = EXCLUDED.last_success_at
            """
        ),
        {"source_id": source_id, "last_published_at": latest_published_at},
    )


async def _upsert_raw_document(
    session: AsyncSession,
    *,
    source_id: str,
    ingestion_run_id: str,
    item: FeedItem,
) -> tuple[str, bool]:
    existing = await session.execute(
        text(
            """
            SELECT id
            FROM app.raw_documents
            WHERE source_id = CAST(:source_id AS uuid)
              AND (url = :url OR (:external_id <> '' AND external_id = :external_id))
            """
        ),
        {
            "source_id": source_id,
            "url": item.url,
            "external_id": item.external_id,
        },
    )
    row = existing.mappings().first()
    payload = json.dumps(item.raw_payload)
    content_hash = _sha256(
        "|".join(
            [
                item.external_id,
                item.url,
                item.title,
                item.body_text,
                item.published_at.isoformat() if item.published_at else "",
            ]
        )
    )
    if row is None:
        inserted = await session.execute(
            text(
                """
                INSERT INTO app.raw_documents (
                    source_id,
                    ingestion_run_id,
                    external_id,
                    url,
                    title_raw,
                    body_raw,
                    author_raw,
                    published_at,
                    language,
                    content_hash,
                    raw_payload
                )
                VALUES (
                    CAST(:source_id AS uuid),
                    CAST(:ingestion_run_id AS uuid),
                    :external_id,
                    :url,
                    :title_raw,
                    :body_raw,
                    :author_raw,
                    :published_at,
                    :language,
                    :content_hash,
                    CAST(:raw_payload AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "source_id": source_id,
                "ingestion_run_id": ingestion_run_id,
                "external_id": item.external_id,
                "url": item.url,
                "title_raw": item.title,
                "body_raw": item.body_text,
                "author_raw": item.author,
                "published_at": item.published_at,
                "language": item.language,
                "content_hash": content_hash,
                "raw_payload": payload,
            },
        )
        return str(inserted.scalar_one()), True

    await session.execute(
        text(
            """
            UPDATE app.raw_documents
            SET
                ingestion_run_id = CAST(:ingestion_run_id AS uuid),
                external_id = :external_id,
                title_raw = :title_raw,
                body_raw = :body_raw,
                author_raw = :author_raw,
                published_at = COALESCE(:published_at, published_at),
                fetched_at = now(),
                language = COALESCE(:language, language),
                content_hash = :content_hash,
                raw_payload = CAST(:raw_payload AS jsonb)
            WHERE id = CAST(:raw_document_id AS uuid)
            """
        ),
        {
            "raw_document_id": str(row["id"]),
            "ingestion_run_id": ingestion_run_id,
            "external_id": item.external_id,
            "title_raw": item.title,
            "body_raw": item.body_text,
            "author_raw": item.author,
            "published_at": item.published_at,
            "language": item.language,
            "content_hash": content_hash,
            "raw_payload": payload,
        },
    )
    return str(row["id"]), False


async def _upsert_document(
    session: AsyncSession,
    *,
    source: SourceDefinition,
    source_id: str,
    raw_document_id: str,
    item: FeedItem,
) -> tuple[str, bool]:
    canonical_url_hash = _sha256(item.url)
    dedup_hash = _sha256(f"{source.source_key}|{item.url}")
    metadata = json.dumps(
        {
            "ingested_via": "feed",
            "source_key": source.source_key,
            "feed_kind": source.feed_kind,
            "external_id": item.external_id,
        }
    )
    existing = await session.execute(
        text(
            """
            SELECT id
            FROM app.documents
            WHERE dedup_hash = :dedup_hash
            """
        ),
        {"dedup_hash": dedup_hash},
    )
    row = existing.mappings().first()
    if row is None:
        inserted = await session.execute(
            text(
                """
                INSERT INTO app.documents (
                    canonical_url,
                    canonical_url_hash,
                    source_id,
                    primary_raw_document_id,
                    document_type,
                    title,
                    body_text,
                    teaser_text,
                    author_name,
                    published_at,
                    first_seen_at,
                    language,
                    source_priority,
                    dedup_hash,
                    metadata
                )
                VALUES (
                    :canonical_url,
                    :canonical_url_hash,
                    CAST(:source_id AS uuid),
                    CAST(:primary_raw_document_id AS uuid),
                    CAST(:document_type AS app.document_type),
                    :title,
                    :body_text,
                    :teaser_text,
                    :author_name,
                    :published_at,
                    now(),
                    :language,
                    :source_priority,
                    :dedup_hash,
                    CAST(:metadata AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "canonical_url": item.url,
                "canonical_url_hash": canonical_url_hash,
                "source_id": source_id,
                "primary_raw_document_id": raw_document_id,
                "document_type": source.document_type,
                "title": item.title,
                "body_text": item.body_text or item.title,
                "teaser_text": (item.body_text or "")[:280] or item.title,
                "author_name": item.author,
                "published_at": item.published_at,
                "language": item.language,
                "source_priority": 10 if source.source_type == "official" else 50,
                "dedup_hash": dedup_hash,
                "metadata": metadata,
            },
        )
        return str(inserted.scalar_one()), True

    await session.execute(
        text(
            """
            UPDATE app.documents
            SET
                canonical_url = :canonical_url,
                canonical_url_hash = :canonical_url_hash,
                source_id = CAST(:source_id AS uuid),
                primary_raw_document_id = CAST(:primary_raw_document_id AS uuid),
                document_type = CAST(:document_type AS app.document_type),
                title = :title,
                body_text = :body_text,
                teaser_text = :teaser_text,
                author_name = :author_name,
                published_at = COALESCE(:published_at, published_at),
                language = COALESCE(:language, language),
                source_priority = :source_priority,
                metadata = metadata || CAST(:metadata AS jsonb)
            WHERE id = CAST(:document_id AS uuid)
            """
        ),
        {
            "document_id": str(row["id"]),
            "canonical_url": item.url,
            "canonical_url_hash": canonical_url_hash,
            "source_id": source_id,
            "primary_raw_document_id": raw_document_id,
            "document_type": source.document_type,
            "title": item.title,
            "body_text": item.body_text or item.title,
            "teaser_text": (item.body_text or "")[:280] or item.title,
            "author_name": item.author,
            "published_at": item.published_at,
            "language": item.language,
            "source_priority": 10 if source.source_type == "official" else 50,
            "metadata": metadata,
        },
    )
    return str(row["id"]), False


async def _ensure_evidence_span(session: AsyncSession, *, document_id: str, item: FeedItem) -> str | None:
    quote_text = (item.body_text or item.title).strip()
    if not quote_text:
        return None
    quote_text = quote_text[:500]

    existing = await session.execute(
        text(
            """
            SELECT id
            FROM app.evidence_spans
            WHERE document_id = CAST(:document_id AS uuid)
              AND quote_text = :quote_text
            LIMIT 1
            """
        ),
        {"document_id": document_id, "quote_text": quote_text},
    )
    row = existing.mappings().first()
    if row is not None:
        return str(row["id"])

    result = await session.execute(
        text(
            """
            INSERT INTO app.evidence_spans (
                document_id,
                quote_text,
                char_start,
                char_end,
                sentence_start,
                sentence_end,
                metadata
            )
            VALUES (
                CAST(:document_id AS uuid),
                :quote_text,
                0,
                :char_end,
                1,
                1,
                CAST(:metadata AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "document_id": document_id,
            "quote_text": quote_text,
            "char_end": len(quote_text),
            "metadata": json.dumps({"kind": "ingested_lead"}),
        },
    )
    return str(result.scalar_one())


def _story_state_for(source: SourceDefinition) -> str:
    if source.document_type == "press_release":
        return "confirmed"
    if source.document_type == "speech":
        return "developing"
    if source.document_type == "calendar_event":
        return "emerging"
    return "developing"


def _episode_type_for(source: SourceDefinition) -> str:
    if source.document_type == "press_release":
        return "official_release"
    if source.document_type == "speech":
        return "speaker_comment"
    if source.document_type == "calendar_event":
        return "follow_up"
    return "new_signal"


def _build_summary(item: FeedItem, source: SourceDefinition) -> tuple[str, dict[str, str]]:
    what_changed = item.title
    why_it_matters = (
        f"{source.display_name} published a fresh {source.document_type.replace('_', ' ')}"
        " that may shift active macro narratives."
    )
    what_to_watch = "Watch for official follow-through, market reaction, and cross-source confirmation."
    summary_text = " ".join([what_changed, why_it_matters, what_to_watch])
    summary_json = {
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "what_to_watch": what_to_watch,
    }
    return summary_text, summary_json


async def _upsert_story(
    session: AsyncSession,
    *,
    workspace_id: str,
    source: SourceDefinition,
    item: FeedItem,
    track_matches: list[TrackMatch],
    document_id: str,
) -> tuple[str, bool, str | None]:
    story_slug = f"{_slugify(item.title)[:72]}-{_sha256(document_id)[:8]}"
    summary_text, summary_json = _build_summary(item, source)
    story_state = _story_state_for(source)
    dominant_mode = track_matches[0].mode if track_matches else "custom"

    existing = await session.execute(
        text(
            """
            SELECT id, story_state
            FROM app.stories
            WHERE workspace_id = CAST(:workspace_id AS uuid)
              AND slug = :slug
            """
        ),
        {"workspace_id": workspace_id, "slug": story_slug},
    )
    row = existing.mappings().first()
    metadata = json.dumps(
        {
            "primary_document_id": document_id,
            "source_key": source.source_key,
            "ingested_via": "feed",
        }
    )

    if row is None:
        result = await session.execute(
            text(
                """
                INSERT INTO app.stories (
                    workspace_id,
                    dominant_mode,
                    title,
                    slug,
                    summary_text,
                    summary_json,
                    story_state,
                    first_seen_at,
                    last_seen_at,
                    state_changed_at,
                    hotness_score,
                    novelty_score,
                    contradiction_score,
                    confidence_score,
                    source_diversity_score,
                    official_confirmation_at,
                    metadata
                )
                VALUES (
                    CAST(:workspace_id AS uuid),
                    CAST(:dominant_mode AS app.track_mode),
                    :title,
                    :slug,
                    :summary_text,
                    CAST(:summary_json AS jsonb),
                    CAST(:story_state AS app.story_state),
                    COALESCE(:published_at, now()),
                    COALESCE(:published_at, now()),
                    now(),
                    :hotness_score,
                    0.55,
                    0.05,
                    :confidence_score,
                    :source_diversity_score,
                    CASE WHEN :story_state = 'confirmed' THEN COALESCE(:published_at, now()) ELSE NULL END,
                    CAST(:metadata AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": workspace_id,
                "dominant_mode": dominant_mode,
                "title": item.title,
                "slug": story_slug,
                "summary_text": summary_text,
                "summary_json": json.dumps(summary_json),
                "story_state": story_state,
                "published_at": item.published_at,
                "hotness_score": min(track_matches[0].score / 2, 0.99),
                "confidence_score": 0.85 if source.source_type == "official" else 0.65,
                "source_diversity_score": 0.35,
                "metadata": metadata,
            },
        )
        return str(result.scalar_one()), True, None

    previous_state = row["story_state"]
    await session.execute(
        text(
            """
            UPDATE app.stories
            SET
                dominant_mode = CAST(:dominant_mode AS app.track_mode),
                title = :title,
                summary_text = :summary_text,
                summary_json = CAST(:summary_json AS jsonb),
                story_state = CASE
                    WHEN app.stories.story_state = CAST('confirmed' AS app.story_state) THEN app.stories.story_state
                    WHEN app.stories.story_state = CAST('contested' AS app.story_state) THEN app.stories.story_state
                    ELSE CAST(:story_state AS app.story_state)
                END,
                last_seen_at = GREATEST(app.stories.last_seen_at, COALESCE(:published_at, now())),
                state_changed_at = CASE
                    WHEN app.stories.story_state <> CAST(:story_state AS app.story_state) THEN now()
                    ELSE app.stories.state_changed_at
                END,
                hotness_score = GREATEST(app.stories.hotness_score, :hotness_score),
                confidence_score = GREATEST(app.stories.confidence_score, :confidence_score),
                official_confirmation_at = COALESCE(app.stories.official_confirmation_at, CASE WHEN :story_state = 'confirmed' THEN COALESCE(:published_at, now()) ELSE NULL END),
                metadata = app.stories.metadata || CAST(:metadata AS jsonb)
            WHERE id = CAST(:story_id AS uuid)
            """
        ),
        {
            "story_id": str(row["id"]),
            "dominant_mode": dominant_mode,
            "title": item.title,
            "summary_text": summary_text,
            "summary_json": json.dumps(summary_json),
            "story_state": story_state,
            "published_at": item.published_at,
            "hotness_score": min(track_matches[0].score / 2, 0.99),
            "confidence_score": 0.85 if source.source_type == "official" else 0.65,
            "metadata": metadata,
        },
    )
    return str(row["id"]), False, previous_state


async def _ensure_story_document(session: AsyncSession, *, story_id: str, document_id: str, score: float) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.story_documents (
                story_id,
                document_id,
                assignment_score,
                assignment_method,
                is_primary,
                metadata
            )
            VALUES (
                CAST(:story_id AS uuid),
                CAST(:document_id AS uuid),
                :assignment_score,
                CAST('rule' AS app.assignment_method),
                true,
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (story_id, document_id) DO UPDATE
            SET assignment_score = GREATEST(app.story_documents.assignment_score, EXCLUDED.assignment_score),
                metadata = app.story_documents.metadata || EXCLUDED.metadata
            """
        ),
        {
            "story_id": story_id,
            "document_id": document_id,
            "assignment_score": min(score / 2, 0.99),
            "metadata": json.dumps({"ingested_via": "feed"}),
        },
    )


async def _ensure_track_story(
    session: AsyncSession,
    *,
    track_match: TrackMatch,
    story_id: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.track_stories (
                track_id,
                story_id,
                relevance_score,
                priority_score,
                reason,
                added_at
            )
            VALUES (
                CAST(:track_id AS uuid),
                CAST(:story_id AS uuid),
                :relevance_score,
                :priority_score,
                :reason,
                now()
            )
            ON CONFLICT (track_id, story_id) DO UPDATE
            SET relevance_score = GREATEST(app.track_stories.relevance_score, EXCLUDED.relevance_score),
                priority_score = GREATEST(app.track_stories.priority_score, EXCLUDED.priority_score),
                reason = EXCLUDED.reason,
                removed_at = NULL
            """
        ),
        {
            "track_id": track_match.track_id,
            "story_id": story_id,
            "relevance_score": min(track_match.score / 2, 0.99),
            "priority_score": min((track_match.score + 0.35) / 2, 0.99),
            "reason": f"Keyword overlap: {track_match.reason}",
        },
    )


async def _upsert_episode(
    session: AsyncSession,
    *,
    source: SourceDefinition,
    story_id: str,
    item: FeedItem,
    previous_story_state: str | None,
) -> tuple[str, bool]:
    episode_type = _episode_type_for(source)
    existing = await session.execute(
        text(
            """
            SELECT id
            FROM app.episodes
            WHERE story_id = CAST(:story_id AS uuid)
              AND headline = :headline
            LIMIT 1
            """
        ),
        {"story_id": story_id, "headline": item.title},
    )
    row = existing.mappings().first()
    summary_text, summary_json = _build_summary(item, source)
    if row is None:
        result = await session.execute(
            text(
                """
                INSERT INTO app.episodes (
                    story_id,
                    episode_type,
                    headline,
                    state_from,
                    state_to,
                    what_changed,
                    why_it_matters,
                    what_to_watch,
                    significance_score,
                    confidence_score,
                    contradiction_score,
                    started_at,
                    created_by_agent,
                    payload
                )
                VALUES (
                    CAST(:story_id AS uuid),
                    CAST(:episode_type AS app.episode_type),
                    :headline,
                    :state_from,
                    :state_to,
                    :what_changed,
                    :why_it_matters,
                    :what_to_watch,
                    :significance_score,
                    :confidence_score,
                    0.05,
                    COALESCE(:started_at, now()),
                    'feed_ingestion',
                    CAST(:payload AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "story_id": story_id,
                "episode_type": episode_type,
                "headline": item.title,
                "state_from": previous_story_state,
                "state_to": _story_state_for(source),
                "what_changed": summary_json["what_changed"],
                "why_it_matters": summary_json["why_it_matters"],
                "what_to_watch": summary_json["what_to_watch"],
                "significance_score": 0.82 if source.source_type == "official" else 0.58,
                "confidence_score": 0.87 if source.source_type == "official" else 0.64,
                "started_at": item.published_at,
                "payload": json.dumps(
                    {
                        "source_key": source.source_key,
                        "summary_text": summary_text,
                    }
                ),
            },
        )
        return str(result.scalar_one()), True

    await session.execute(
        text(
            """
            UPDATE app.episodes
            SET
                episode_type = CAST(:episode_type AS app.episode_type),
                state_from = COALESCE(:state_from, state_from),
                state_to = COALESCE(:state_to, state_to),
                what_changed = :what_changed,
                why_it_matters = :why_it_matters,
                what_to_watch = :what_to_watch,
                significance_score = GREATEST(significance_score, :significance_score),
                confidence_score = GREATEST(confidence_score, :confidence_score),
                payload = payload || CAST(:payload AS jsonb)
            WHERE id = CAST(:episode_id AS uuid)
            """
        ),
        {
            "episode_id": str(row["id"]),
            "episode_type": episode_type,
            "state_from": previous_story_state,
            "state_to": _story_state_for(source),
            "what_changed": summary_json["what_changed"],
            "why_it_matters": summary_json["why_it_matters"],
            "what_to_watch": summary_json["what_to_watch"],
            "significance_score": 0.82 if source.source_type == "official" else 0.58,
            "confidence_score": 0.87 if source.source_type == "official" else 0.64,
            "payload": json.dumps({"source_key": source.source_key, "summary_text": summary_text}),
        },
    )
    return str(row["id"]), False


async def _ensure_episode_document(session: AsyncSession, *, episode_id: str, document_id: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.episode_documents (episode_id, document_id, role)
            VALUES (
                CAST(:episode_id AS uuid),
                CAST(:document_id AS uuid),
                'supporting'
            )
            ON CONFLICT (episode_id, document_id, role) DO NOTHING
            """
        ),
        {"episode_id": episode_id, "document_id": document_id},
    )


async def _upsert_generated_sentences(
    session: AsyncSession,
    *,
    story_id: str,
    episode_id: str,
    evidence_span_id: str | None,
    item: FeedItem,
    source: SourceDefinition,
) -> None:
    if evidence_span_id is None:
        return

    _, summary_json = _build_summary(item, source)
    sentences = [
        summary_json["what_changed"],
        summary_json["why_it_matters"],
        summary_json["what_to_watch"],
    ]
    for order, sentence in enumerate(sentences, start=1):
        result = await session.execute(
            text(
                """
                INSERT INTO app.generated_sentences (
                    story_id,
                    episode_id,
                    sentence_order,
                    sentence_text,
                    verdict,
                    model_name
                )
                VALUES (
                    CAST(:story_id AS uuid),
                    CAST(:episode_id AS uuid),
                    :sentence_order,
                    :sentence_text,
                    CAST('supported' AS app.claim_support_status),
                    'rule_based_ingestion'
                )
                ON CONFLICT (episode_id, sentence_order) DO UPDATE
                SET sentence_text = EXCLUDED.sentence_text,
                    verdict = EXCLUDED.verdict,
                    model_name = EXCLUDED.model_name
                RETURNING id
                """
            ),
            {
                "story_id": story_id,
                "episode_id": episode_id,
                "sentence_order": order,
                "sentence_text": sentence,
            },
        )
        sentence_id = str(result.scalar_one())
        await session.execute(
            text(
                """
                INSERT INTO app.generated_sentence_evidence (
                    generated_sentence_id,
                    evidence_span_id,
                    support_status
                )
                VALUES (
                    CAST(:generated_sentence_id AS uuid),
                    CAST(:evidence_span_id AS uuid),
                    CAST('supported' AS app.claim_support_status)
                )
                ON CONFLICT (generated_sentence_id, evidence_span_id) DO NOTHING
                """
            ),
            {"generated_sentence_id": sentence_id, "evidence_span_id": evidence_span_id},
        )


async def _enqueue_event(
    session: AsyncSession,
    *,
    workspace_id: str,
    story_id: str,
    episode_id: str,
    track_matches: list[TrackMatch],
    item: FeedItem,
    source: SourceDefinition,
) -> None:
    payload = json.dumps(
        {
            "track_ids": [match.track_id for match in track_matches],
            "story_id": story_id,
            "episode_id": episode_id,
            "headline": item.title,
            "source_key": source.source_key,
        }
    )
    await session.execute(
        text(
            """
            INSERT INTO app.event_outbox (
                workspace_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload
            )
            VALUES (
                CAST(:workspace_id AS uuid),
                'story.updated',
                'story',
                CAST(:story_id AS uuid),
                CAST(:payload AS jsonb)
            )
            """
        ),
        {"workspace_id": workspace_id, "story_id": story_id, "payload": payload},
    )


async def _insert_in_app_notifications(
    session: AsyncSession,
    *,
    track_matches: list[TrackMatch],
    story_id: str,
    episode_id: str,
    item: FeedItem,
    source: SourceDefinition,
    is_new_story: bool,
) -> None:
    track_rows: list[dict[str, Any]] = []
    for track_id in {match.track_id for match in track_matches}:
        result = await session.execute(
            text(
                """
                SELECT id, workspace_id, owner_user_id, name, alert_policy
                FROM app.tracks
                WHERE id = CAST(:track_id AS uuid)
                """
            ),
            {"track_id": track_id},
        )
        row = result.mappings().first()
        if row is not None:
            track_rows.append(dict(row))

    for row in track_rows:
        alert_policy = row["alert_policy"] or {}
        delivery = alert_policy.get("delivery", "in_app")
        threshold = alert_policy.get("threshold", "state_change")
        if delivery != "in_app":
            continue
        if threshold == "official_confirmation" and source.document_type != "press_release":
            continue

        reason = "story_created" if is_new_story else "story_state_changed"
        if source.document_type == "press_release":
            reason = "official_confirmation_added"
        dedup_key = f"{reason}:{row['id']}:{story_id}:{episode_id}"
        title = f"{row['name']}: {item.title}"
        body_text = (
            f"{source.display_name} published a new {source.document_type.replace('_', ' ')} "
            f"matched to {row['name']}."
        )
        await session.execute(
            text(
                """
                INSERT INTO app.notifications (
                    workspace_id,
                    user_id,
                    track_id,
                    story_id,
                    episode_id,
                    reason,
                    channel,
                    dedup_key,
                    title,
                    body_text,
                    payload,
                    scheduled_for
                )
                VALUES (
                    CAST(:workspace_id AS uuid),
                    CAST(:user_id AS uuid),
                    CAST(:track_id AS uuid),
                    CAST(:story_id AS uuid),
                    CAST(:episode_id AS uuid),
                    CAST(:reason AS app.notification_reason),
                    CAST('in_app' AS app.notification_channel),
                    :dedup_key,
                    :title,
                    :body_text,
                    CAST(:payload AS jsonb),
                    now()
                )
                ON CONFLICT (channel, dedup_key) DO UPDATE
                SET title = EXCLUDED.title,
                    body_text = EXCLUDED.body_text,
                    payload = app.notifications.payload || EXCLUDED.payload,
                    scheduled_for = EXCLUDED.scheduled_for
                """
            ),
            {
                "workspace_id": str(row["workspace_id"]),
                "user_id": str(row["owner_user_id"]) if row["owner_user_id"] else None,
                "track_id": str(row["id"]),
                "story_id": story_id,
                "episode_id": episode_id,
                "reason": reason,
                "dedup_key": dedup_key,
                "title": title,
                "body_text": body_text,
                "payload": json.dumps(
                    {
                        "trackId": str(row["id"]),
                        "storyId": story_id,
                        "episodeId": episode_id,
                        "sourceKey": source.source_key,
                    }
                ),
            },
        )


async def _process_item(
    session: AsyncSession,
    *,
    source: SourceDefinition,
    source_id: str,
    run_id: str,
    tracks: list[TrackCandidate],
    item: FeedItem,
) -> ItemProcessResult:
    raw_document_id, raw_inserted = await _upsert_raw_document(
        session,
        source_id=source_id,
        ingestion_run_id=run_id,
        item=item,
    )
    document_id, document_inserted = await _upsert_document(
        session,
        source=source,
        source_id=source_id,
        raw_document_id=raw_document_id,
        item=item,
    )

    # Enqueue LLM pipeline job for event extraction (if configured)
    settings = get_settings()
    if settings.pipeline_enabled and settings.openai_api_key:
        await _enqueue_pipeline_job(
            session,
            job_type="event_extraction",
            source_object_type="document",
            source_object_id=document_id,
            input_json={
                "document_id": document_id,
                "title": item.title,
                "body_text": item.body_text or item.title,
                "document_type": source.document_type,
                "source_key": source.source_key,
            },
            priority=100,
        )

    track_matches = [
        match
        for track in tracks
        if (match := _track_match_score(track, item, source.document_type)) is not None
    ]
    if not track_matches:
        return ItemProcessResult(
            inserted_count=int(document_inserted),
            updated_count=int(not document_inserted),
            track_ids=set(),
            story_ids=set(),
            episode_ids=set(),
        )

    evidence_span_id = await _ensure_evidence_span(session, document_id=document_id, item=item)
    grouped_matches: dict[str, list[TrackMatch]] = defaultdict(list)
    for match in sorted(track_matches, key=lambda candidate: candidate.score, reverse=True):
        grouped_matches[match.workspace_id].append(match)

    story_ids: set[str] = set()
    episode_ids: set[str] = set()
    matched_track_ids = {match.track_id for match in track_matches}

    for workspace_id, workspace_matches in grouped_matches.items():
        story_id, is_new_story, previous_story_state = await _upsert_story(
            session,
            workspace_id=workspace_id,
            source=source,
            item=item,
            track_matches=workspace_matches,
            document_id=document_id,
        )
        story_ids.add(story_id)
        await _ensure_story_document(
            session,
            story_id=story_id,
            document_id=document_id,
            score=workspace_matches[0].score,
        )
        for match in workspace_matches:
            await _ensure_track_story(session, track_match=match, story_id=story_id)

        episode_id, is_new_episode = await _upsert_episode(
            session,
            source=source,
            story_id=story_id,
            item=item,
            previous_story_state=previous_story_state,
        )
        if is_new_episode:
            episode_ids.add(episode_id)
        await _ensure_episode_document(session, episode_id=episode_id, document_id=document_id)
        await _upsert_generated_sentences(
            session,
            story_id=story_id,
            episode_id=episode_id,
            evidence_span_id=evidence_span_id,
            item=item,
            source=source,
        )
        if is_new_story or is_new_episode:
            await _enqueue_event(
                session,
                workspace_id=workspace_id,
                story_id=story_id,
                episode_id=episode_id,
                track_matches=workspace_matches,
                item=item,
                source=source,
            )
            await _insert_in_app_notifications(
                session,
                track_matches=workspace_matches,
                story_id=story_id,
                episode_id=episode_id,
                item=item,
                source=source,
                is_new_story=is_new_story,
            )
            await record_story_enrichment(
                session,
                story_id=story_id,
                track_ids=[match.track_id for match in workspace_matches],
                episode_id=episode_id,
                source_key=source.source_key,
            )

    inserted_count = int(raw_inserted or document_inserted)
    return ItemProcessResult(
        inserted_count=inserted_count,
        updated_count=int(not inserted_count),
        track_ids=matched_track_ids,
        story_ids=story_ids,
        episode_ids=episode_ids,
    )


async def pull_source(
    session: AsyncSession,
    *,
    source_key: str,
    limit: int = 10,
) -> IngestionPullResponse:
    source = get_source_definition(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    source_id = await _ensure_source(session, source)
    run_id = await _create_ingestion_run(session, source_id, source_key)
    await session.commit()

    try:
        items = await _fetch_feed_items(source, limit=limit)
    except Exception as exc:  # noqa: BLE001
        await _finish_ingestion_run(
            session,
            run_id=run_id,
            status="failed",
            discovered_count=0,
            inserted_count=0,
            updated_count=0,
            failed_count=1,
            error_text=str(exc),
        )
        await session.commit()
        raise HTTPException(status_code=502, detail=f"Failed to fetch {source_key} feed") from exc

    tracks = await _load_active_tracks(session)
    discovered_count = len(items)
    inserted_count = 0
    updated_count = 0
    failed_count = 0
    matched_track_ids: set[str] = set()
    story_ids: set[str] = set()
    episode_ids: set[str] = set()
    latest_published_at: datetime | None = None
    error_text: str | None = None

    for item in items:
        try:
            result = await _process_item(
                session,
                source=source,
                source_id=source_id,
                run_id=run_id,
                tracks=tracks,
                item=item,
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            failed_count += 1
            error_text = str(exc)
            continue

        inserted_count += result.inserted_count
        updated_count += result.updated_count
        matched_track_ids.update(result.track_ids)
        story_ids.update(result.story_ids)
        episode_ids.update(result.episode_ids)
        if item.published_at is not None and (
            latest_published_at is None or item.published_at > latest_published_at
        ):
            latest_published_at = item.published_at

    if failed_count < discovered_count or discovered_count == 0:
        await _update_cursor(
            session,
            source_id=source_id,
            latest_published_at=latest_published_at,
        )
    await _finish_ingestion_run(
        session,
        run_id=run_id,
        status="failed" if discovered_count > 0 and failed_count == discovered_count else "completed",
        discovered_count=discovered_count,
        inserted_count=inserted_count,
        updated_count=updated_count,
        failed_count=failed_count,
        error_text=error_text,
    )
    await session.commit()

    return IngestionPullResponse(
        generatedAt=_now(),
        sourceKey=source_key,
        runId=run_id,
        discoveredCount=discovered_count,
        insertedCount=inserted_count,
        updatedCount=updated_count,
        failedCount=failed_count,
        matchedTrackCount=len(matched_track_ids),
        storyCount=len(story_ids),
        episodeCount=len(episode_ids),
        latestPublishedAt=latest_published_at,
    )
