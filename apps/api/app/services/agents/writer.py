"""Writer Agent — generates evidence-backed narrative sentences for episodes."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agents.base import BaseAgent
from app.services.llm.client import chat_completion
from app.services.pipeline.queue import enqueue_job

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a macro-economic intelligence writer. Given a story and supporting evidence,
write three concise sections:

1. what_changed — One or two sentences on the factual development.
2. why_it_matters — One or two sentences on the macro significance.
3. what_to_watch — One or two sentences on the forward-looking implications.

RULES:
- Every sentence MUST be grounded in the provided evidence.
- Cite evidence by span_id (e.g. [span:abc123]).
- Be precise, neutral, and concise. No speculation beyond what evidence supports.
- Write for a professional macro analyst audience.

Return JSON:
{
  "what_changed": "...",
  "why_it_matters": "...",
  "what_to_watch": "...",
  "sentences": [
    {"text": "...", "section": "what_changed", "cited_span_ids": ["span_id_1"]},
    ...
  ]
}
"""


class WriterAgent(BaseAgent[dict[str, Any], dict[str, Any]]):
    @property
    def agent_name(self) -> str:
        return "writer"

    @property
    def model_name(self) -> str:
        return get_settings().openai_complex_model

    async def run_impl(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        story_id = input_data["story_id"]
        episode_id = input_data["episode_id"]
        event_ids = input_data.get("event_ids", [])
        document_id = input_data.get("document_id")

        # Fetch evidence spans
        evidence_spans = await self._fetch_evidence_spans(
            session, document_id=document_id, event_ids=event_ids
        )

        # Fetch story context
        story_context = await self._fetch_story_context(session, story_id=story_id)

        # Build LLM prompt
        evidence_text = "\n".join(
            f"[span:{span['id'][:8]}] {span['quote_text']}"
            for span in evidence_spans
        )

        user_content = (
            f"Story: {story_context.get('title', 'Unknown')}\n"
            f"State: {story_context.get('story_state', 'unknown')}\n"
            f"Episode headline: {input_data.get('title', story_context.get('title', ''))}\n\n"
            f"Evidence spans:\n{evidence_text or 'No evidence spans available.'}"
        )

        raw_response, usage = await chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model=self.model_name,
            temperature=0.3,
            max_tokens=1536,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("[%s] Failed to parse writer LLM response", trace_id)
            return {"written": False, "episode_id": episode_id}

        what_changed = parsed.get("what_changed", "")
        why_it_matters = parsed.get("why_it_matters", "")
        what_to_watch = parsed.get("what_to_watch", "")
        sentences = parsed.get("sentences", [])

        # Update episode
        await self._update_episode(
            session,
            episode_id=episode_id,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            what_to_watch=what_to_watch,
        )

        # Update story summary
        summary_text = " ".join(filter(None, [what_changed, why_it_matters, what_to_watch]))
        await self._update_story_summary(
            session,
            story_id=story_id,
            summary_text=summary_text,
            summary_json={
                "what_changed": what_changed,
                "why_it_matters": why_it_matters,
                "what_to_watch": what_to_watch,
            },
        )

        # Insert generated sentences
        sentence_ids: list[str] = []
        span_id_map = {span["id"][:8]: span["id"] for span in evidence_spans}

        for order, sentence_data in enumerate(sentences, start=1):
            sentence_text = sentence_data.get("text", "")
            if not sentence_text:
                continue

            sentence_id = await self._upsert_generated_sentence(
                session,
                story_id=story_id,
                episode_id=episode_id,
                sentence_order=order,
                sentence_text=sentence_text,
            )
            sentence_ids.append(sentence_id)

            # Link to cited evidence
            for cited_ref in sentence_data.get("cited_span_ids", []):
                full_span_id = span_id_map.get(cited_ref.replace("span:", ""))
                if full_span_id:
                    await self._link_sentence_evidence(
                        session, sentence_id=sentence_id, span_id=full_span_id
                    )

        # Enqueue verifier
        if sentence_ids:
            await enqueue_job(
                session,
                job_type="verifier",
                source_object_type="episode",
                source_object_id=episode_id,
                input_json={
                    "episode_id": episode_id,
                    "story_id": story_id,
                    "generated_sentence_ids": sentence_ids,
                },
                priority=60,
            )

        return {
            "written": True,
            "episode_id": episode_id,
            "story_id": story_id,
            "sentence_count": len(sentence_ids),
            "usage": usage,
        }

    async def _fetch_evidence_spans(
        self,
        session: AsyncSession,
        *,
        document_id: str | None,
        event_ids: list[str],
    ) -> list[dict[str, Any]]:
        spans: list[dict[str, Any]] = []

        # From document
        if document_id:
            result = await session.execute(
                text(
                    """
                    SELECT id::text, quote_text FROM app.evidence_spans
                    WHERE document_id = CAST(:document_id AS uuid)
                    ORDER BY created_at ASC LIMIT 20
                    """
                ),
                {"document_id": document_id},
            )
            spans.extend(dict(r) for r in result.mappings().all())

        # From events
        for event_id in event_ids:
            result = await session.execute(
                text(
                    """
                    SELECT es.id::text, es.quote_text
                    FROM app.event_evidence ee
                    JOIN app.evidence_spans es ON es.id = ee.evidence_span_id
                    WHERE ee.event_id = CAST(:event_id AS uuid)
                    """
                ),
                {"event_id": event_id},
            )
            for r in result.mappings().all():
                if not any(s["id"] == r["id"] for s in spans):
                    spans.append(dict(r))

        return spans[:20]

    async def _fetch_story_context(
        self, session: AsyncSession, *, story_id: str
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT title, story_state::text, summary_text
                FROM app.stories WHERE id = CAST(:story_id AS uuid)
                """
            ),
            {"story_id": story_id},
        )
        row = result.mappings().first()
        if row:
            return dict(row)
        return {}

    async def _update_episode(
        self,
        session: AsyncSession,
        *,
        episode_id: str,
        what_changed: str,
        why_it_matters: str,
        what_to_watch: str,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.episodes
                SET what_changed = :what_changed,
                    why_it_matters = :why_it_matters,
                    what_to_watch = :what_to_watch,
                    created_by_agent = 'writer'
                WHERE id = CAST(:episode_id AS uuid)
                """
            ),
            {
                "episode_id": episode_id,
                "what_changed": what_changed,
                "why_it_matters": why_it_matters,
                "what_to_watch": what_to_watch,
            },
        )

    async def _update_story_summary(
        self,
        session: AsyncSession,
        *,
        story_id: str,
        summary_text: str,
        summary_json: dict[str, str],
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.stories
                SET summary_text = :summary_text,
                    summary_json = CAST(:summary_json AS jsonb)
                WHERE id = CAST(:story_id AS uuid)
                """
            ),
            {
                "story_id": story_id,
                "summary_text": summary_text,
                "summary_json": json.dumps(summary_json),
            },
        )

    async def _upsert_generated_sentence(
        self,
        session: AsyncSession,
        *,
        story_id: str,
        episode_id: str,
        sentence_order: int,
        sentence_text: str,
    ) -> str:
        result = await session.execute(
            text(
                """
                INSERT INTO app.generated_sentences (
                    story_id, episode_id, sentence_order,
                    sentence_text, verdict, model_name
                )
                VALUES (
                    CAST(:story_id AS uuid),
                    CAST(:episode_id AS uuid),
                    :sentence_order,
                    :sentence_text,
                    CAST('unknown' AS app.claim_support_status),
                    :model_name
                )
                ON CONFLICT (episode_id, sentence_order) DO UPDATE
                SET sentence_text = EXCLUDED.sentence_text,
                    model_name = EXCLUDED.model_name,
                    verdict = CAST('unknown' AS app.claim_support_status)
                RETURNING id
                """
            ),
            {
                "story_id": story_id,
                "episode_id": episode_id,
                "sentence_order": sentence_order,
                "sentence_text": sentence_text,
                "model_name": self.model_name,
            },
        )
        return str(result.scalar_one())

    async def _link_sentence_evidence(
        self, session: AsyncSession, *, sentence_id: str, span_id: str
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.generated_sentence_evidence (
                    generated_sentence_id, evidence_span_id, support_status
                )
                VALUES (
                    CAST(:sentence_id AS uuid),
                    CAST(:span_id AS uuid),
                    CAST('supported' AS app.claim_support_status)
                )
                ON CONFLICT (generated_sentence_id, evidence_span_id) DO NOTHING
                """
            ),
            {"sentence_id": sentence_id, "span_id": span_id},
        )
