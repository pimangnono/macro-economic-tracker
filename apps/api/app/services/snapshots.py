from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import fetch_track_detail, fetch_track_stories
from app.db.workflows import fetch_notes, insert_pipeline_job, insert_track_snapshot
from app.schemas.common import SummaryFrame
from app.schemas.snapshots import SnapshotDetail
from app.services.storage import store_binary_artifact, store_json_artifact, store_text_artifact


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_snapshot_markdown(
    *,
    track_name: str,
    summary: SummaryFrame | None,
    stories: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> str:
    lines = [f"# {track_name} briefing", ""]
    if summary is not None:
        lines.extend(
            [
                "## Summary",
                f"- What changed: {summary.what_changed or 'n/a'}",
                f"- Why it matters: {summary.why_it_matters or 'n/a'}",
                f"- What to watch: {summary.what_to_watch or 'n/a'}",
                "",
            ]
        )

    lines.append("## Stories")
    if not stories:
        lines.append("- No linked stories yet.")
    else:
        for item in stories:
            lines.append(f"- {item['title']} ({item['storyState']})")
    lines.append("")

    lines.append("## Notes")
    if not notes:
        lines.append("- No handoff notes yet.")
    else:
        for note in notes[:5]:
            lines.append(f"- {note['bodyMd']}")
    return "\n".join(lines).strip()


def render_snapshot_pdf(markdown: str) -> bytes:
    lines = markdown.splitlines()[:24]
    content_lines = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
    first = True
    for line in lines:
        escaped = _escape_pdf_text(line)
        if first:
            content_lines.append(f"({escaped}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("utf-8")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length %d >> stream\n%s\nendstream endobj" % (len(stream), stream),
    ]

    body = [b"%PDF-1.4\n"]
    offsets: list[int] = [0]
    cursor = len(body[0])
    for obj in objects:
        offsets.append(cursor)
        payload = obj + b"\n"
        body.append(payload)
        cursor += len(payload)

    xref_start = cursor
    xref_lines = [b"xref", f"0 {len(offsets)}".encode("ascii"), b"0000000000 65535 f "]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n ".encode("ascii"))
    trailer = [
        b"trailer",
        f"<< /Size {len(offsets)} /Root 1 0 R >>".encode("ascii"),
        b"startxref",
        str(xref_start).encode("ascii"),
        b"%%EOF",
    ]
    return b"".join(body + [b"\n".join(xref_lines) + b"\n", b"\n".join(trailer)])


async def build_track_snapshot(
    session: AsyncSession,
    *,
    track_id: str,
    created_by_agent: str,
) -> SnapshotDetail:
    job_id = await insert_pipeline_job(
        session,
        job_type="snapshot_export",
        source_object_type="track",
        source_object_id=track_id,
        input_json={},
    )
    track = await fetch_track_detail(session, track_id)
    stories = await fetch_track_stories(session, track_id=track_id, limit=12)
    notes = await fetch_notes(session, track_id=track_id, limit=12)

    summary = track.top_summary or SummaryFrame()
    summary_text = summary.what_changed or f"{track.name} snapshot created."
    metrics = {
        "storyCount": track.metrics.story_count,
        "activeStoryCount": track.metrics.active_story_count,
        "lastActivityAt": track.metrics.last_activity_at.isoformat()
        if track.metrics.last_activity_at
        else None,
    }
    json_payload = {
        "track": track.model_dump(by_alias=True),
        "stories": [item.model_dump(by_alias=True) for item in stories],
        "notes": [item.model_dump(by_alias=True) for item in notes],
        "generatedAt": _now().isoformat(),
    }
    markdown = render_snapshot_markdown(
        track_name=track.name,
        summary=summary,
        stories=[item.model_dump(by_alias=True) for item in stories],
        notes=[item.model_dump(by_alias=True) for item in notes],
    )
    pdf_bytes = render_snapshot_pdf(markdown)

    artifact_manifest = {
        "json": store_json_artifact("json", json_payload, f"snapshots/{track.slug}-{job_id}.json").to_manifest(),
        "markdown": store_text_artifact(
            "markdown",
            markdown,
            f"snapshots/{track.slug}-{job_id}.md",
            content_type="text/markdown",
        ).to_manifest(),
        "pdf": store_binary_artifact(
            "pdf",
            pdf_bytes,
            f"snapshots/{track.slug}-{job_id}.pdf",
            content_type="application/pdf",
        ).to_manifest(),
    }
    snapshot = await insert_track_snapshot(
        session,
        track_id=track_id,
        summary_text=summary_text,
        summary_json=summary.model_dump(by_alias=True),
        metrics_json=metrics,
        created_by_agent=created_by_agent,
        artifact_manifest=artifact_manifest,
    )
    await insert_pipeline_job(
        session,
        job_type="snapshot_export.completed",
        source_object_type="track_snapshot",
        source_object_id=snapshot.id,
        input_json={"parentJobId": job_id},
    )
    return snapshot
