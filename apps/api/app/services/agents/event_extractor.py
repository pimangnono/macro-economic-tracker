"""Event Extractor Agent — extracts structured events from documents via LLM."""
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
You are a macro-economic event extractor. Given a document, extract structured events.

For each event, output:
- event_type: one of (policy_decision, data_release, speech_statement, market_move, appointment, regulation, forecast, other)
- actor: the person or institution performing the action (e.g. "Federal Reserve", "Jerome Powell")
- action_verb: a concise verb phrase (e.g. "raised interest rates", "released CPI data")
- object_text: what the action applies to (e.g. "federal funds rate", "March 2026 CPI")
- polarity: positive, negative, neutral, or mixed
- confidence: a float between 0.0 and 1.0
- quote_text: the verbatim sentence(s) from the document that support this event

Return a JSON object: {"events": [...]}
If no meaningful events can be extracted, return {"events": []}.
"""


class EventExtractorAgent(BaseAgent[dict[str, Any], dict[str, Any]]):
    @property
    def agent_name(self) -> str:
        return "event_extractor"

    @property
    def model_name(self) -> str:
        return get_settings().openai_complex_model

    async def run_impl(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        document_id = input_data["document_id"]
        title = input_data.get("title", "")
        body_text = input_data.get("body_text", "")
        document_type = input_data.get("document_type", "")
        source_key = input_data.get("source_key", "")

        user_content = (
            f"Document type: {document_type}\n"
            f"Source: {source_key}\n"
            f"Title: {title}\n\n"
            f"Body:\n{body_text[:6000]}"
        )

        raw_response, usage = await chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model=self.model_name,
            temperature=0.1,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("[%s] Failed to parse LLM response as JSON", trace_id)
            return {"events_created": 0, "document_id": document_id}

        events = parsed.get("events", [])
        if not events:
            return {"events_created": 0, "document_id": document_id}

        event_ids: list[str] = []
        evidence_span_ids: list[str] = []

        for event_data in events:
            quote_text = (event_data.get("quote_text") or "").strip()
            span_id = None
            if quote_text:
                span_id = await self._ensure_evidence_span(
                    session, document_id=document_id, quote_text=quote_text[:500]
                )
                if span_id:
                    evidence_span_ids.append(span_id)

            event_id = await self._insert_event(
                session, document_id=document_id, event_data=event_data
            )
            event_ids.append(event_id)

            if span_id:
                await self._link_event_evidence(session, event_id=event_id, span_id=span_id)

            # Enqueue downstream jobs for each event
            await enqueue_job(
                session,
                job_type="entity_linking",
                source_object_type="document",
                source_object_id=document_id,
                input_json={
                    "document_id": document_id,
                    "event_id": event_id,
                    "actor": event_data.get("actor"),
                    "object_text": event_data.get("object_text"),
                    "title": title,
                    "body_text": body_text[:3000],
                },
                priority=90,
            )
            await enqueue_job(
                session,
                job_type="story_matching",
                source_object_type="event",
                source_object_id=event_id,
                input_json={
                    "event_id": event_id,
                    "document_id": document_id,
                    "title": title,
                    "event_type": event_data.get("event_type", "other"),
                    "actor": event_data.get("actor"),
                    "object_text": event_data.get("object_text"),
                },
                priority=80,
            )

        return {
            "events_created": len(event_ids),
            "event_ids": event_ids,
            "evidence_span_ids": evidence_span_ids,
            "document_id": document_id,
            "usage": usage,
        }

    async def _ensure_evidence_span(
        self, session: AsyncSession, *, document_id: str, quote_text: str
    ) -> str | None:
        if not quote_text:
            return None
        existing = await session.execute(
            text(
                """
                SELECT id FROM app.evidence_spans
                WHERE document_id = CAST(:document_id AS uuid)
                  AND quote_text = :quote_text
                LIMIT 1
                """
            ),
            {"document_id": document_id, "quote_text": quote_text},
        )
        row = existing.mappings().first()
        if row:
            return str(row["id"])

        result = await session.execute(
            text(
                """
                INSERT INTO app.evidence_spans (
                    document_id, quote_text, char_start, char_end,
                    sentence_start, sentence_end, metadata
                )
                VALUES (
                    CAST(:document_id AS uuid), :quote_text, 0, :char_end,
                    1, 1, CAST(:metadata AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "document_id": document_id,
                "quote_text": quote_text,
                "char_end": len(quote_text),
                "metadata": json.dumps({"kind": "llm_extracted"}),
            },
        )
        return str(result.scalar_one())

    async def _insert_event(
        self, session: AsyncSession, *, document_id: str, event_data: dict[str, Any]
    ) -> str:
        result = await session.execute(
            text(
                """
                INSERT INTO app.events (
                    document_id, event_type, action_verb, object_text,
                    polarity, confidence_score, payload
                )
                VALUES (
                    CAST(:document_id AS uuid),
                    :event_type, :action_verb, :object_text,
                    :polarity, :confidence_score,
                    CAST(:payload AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "document_id": document_id,
                "event_type": event_data.get("event_type", "other"),
                "action_verb": event_data.get("action_verb", "unknown"),
                "object_text": event_data.get("object_text"),
                "polarity": event_data.get("polarity", "neutral"),
                "confidence_score": min(float(event_data.get("confidence", 0.5)), 1.0),
                "payload": json.dumps(
                    {"actor": event_data.get("actor"), "raw": event_data}
                ),
            },
        )
        return str(result.scalar_one())

    async def _link_event_evidence(
        self, session: AsyncSession, *, event_id: str, span_id: str
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.event_evidence (event_id, evidence_span_id, support_status, score)
                VALUES (
                    CAST(:event_id AS uuid),
                    CAST(:span_id AS uuid),
                    CAST('supported' AS app.claim_support_status),
                    0.9
                )
                ON CONFLICT (event_id, evidence_span_id) DO NOTHING
                """
            ),
            {"event_id": event_id, "span_id": span_id},
        )
