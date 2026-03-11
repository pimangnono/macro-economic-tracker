"""Verifier Agent — checks that generated sentences are supported by evidence."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agents.base import BaseAgent
from app.services.llm.client import chat_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a verification system for macro-economic intelligence.
For each generated sentence and its linked evidence, determine if the evidence supports the claim.

For each sentence, output a verdict:
- "supported" — evidence directly backs the claim
- "inferred" — evidence is consistent but the sentence draws a reasonable inference
- "weak" — evidence is tangentially related but doesn't strongly support
- "contradicted" — evidence contradicts the claim

Return JSON:
{
  "verdicts": [
    {"sentence_id": "...", "verdict": "supported|inferred|weak|contradicted", "reason": "..."},
    ...
  ]
}
"""


class VerifierAgent(BaseAgent[dict[str, Any], dict[str, Any]]):
    @property
    def agent_name(self) -> str:
        return "verifier"

    @property
    def model_name(self) -> str:
        return get_settings().openai_default_model

    async def run_impl(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        episode_id = input_data["episode_id"]
        story_id = input_data.get("story_id")
        sentence_ids = input_data.get("generated_sentence_ids", [])

        if not sentence_ids:
            return {"verified": 0, "episode_id": episode_id}

        # Fetch sentences with their evidence
        sentence_evidence_pairs = await self._fetch_sentences_with_evidence(session, sentence_ids)
        if not sentence_evidence_pairs:
            return {"verified": 0, "episode_id": episode_id}

        # Build verification prompt
        items_text = ""
        for pair in sentence_evidence_pairs:
            evidence_list = "\n".join(
                f"  - [span:{e['span_id'][:8]}] {e['quote_text']}"
                for e in pair["evidence"]
            )
            items_text += (
                f"\nSentence (id={pair['sentence_id'][:8]}):\n"
                f"  \"{pair['sentence_text']}\"\n"
                f"Evidence:\n{evidence_list or '  (no evidence linked)'}\n"
            )

        raw_response, usage = await chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": items_text},
            ],
            model=self.model_name,
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("[%s] Failed to parse verifier response", trace_id)
            return {"verified": 0, "episode_id": episode_id}

        verdicts = parsed.get("verdicts", [])
        contradiction_count = 0
        verified_count = 0

        # Build lookup for sentence_id short -> full
        short_to_full = {sid[:8]: sid for sid in sentence_ids}

        for verdict_data in verdicts:
            raw_sid = verdict_data.get("sentence_id", "")
            sentence_id = short_to_full.get(raw_sid, raw_sid)
            verdict = verdict_data.get("verdict", "unknown")

            if verdict not in ("supported", "inferred", "weak", "contradicted"):
                verdict = "unknown"

            if verdict == "contradicted":
                contradiction_count += 1

            # Update sentence verdict
            await self._update_sentence_verdict(session, sentence_id=sentence_id, verdict=verdict)
            verified_count += 1

            # Update evidence link status
            if verdict in ("supported", "inferred", "weak", "contradicted"):
                await self._update_evidence_support_status(
                    session, sentence_id=sentence_id, status=verdict
                )

        # Update story contradiction score if contradictions found
        if contradiction_count > 0 and story_id:
            total = max(len(verdicts), 1)
            contradiction_score = min(contradiction_count / total, 1.0)
            await self._update_story_contradiction(
                session, story_id=story_id, score=contradiction_score
            )

        return {
            "verified": verified_count,
            "contradictions": contradiction_count,
            "episode_id": episode_id,
            "usage": usage,
        }

    async def _fetch_sentences_with_evidence(
        self, session: AsyncSession, sentence_ids: list[str]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for sid in sentence_ids:
            sent_result = await session.execute(
                text(
                    """
                    SELECT id::text, sentence_text FROM app.generated_sentences
                    WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": sid},
            )
            sent_row = sent_result.mappings().first()
            if not sent_row:
                continue

            ev_result = await session.execute(
                text(
                    """
                    SELECT es.id::text AS span_id, es.quote_text
                    FROM app.generated_sentence_evidence gse
                    JOIN app.evidence_spans es ON es.id = gse.evidence_span_id
                    WHERE gse.generated_sentence_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": sid},
            )
            evidence = [dict(r) for r in ev_result.mappings().all()]

            results.append({
                "sentence_id": str(sent_row["id"]),
                "sentence_text": sent_row["sentence_text"],
                "evidence": evidence,
            })

        return results

    async def _update_sentence_verdict(
        self, session: AsyncSession, *, sentence_id: str, verdict: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.generated_sentences
                SET verdict = CAST(:verdict AS app.claim_support_status)
                WHERE id = CAST(:sentence_id AS uuid)
                """
            ),
            {"sentence_id": sentence_id, "verdict": verdict},
        )

    async def _update_evidence_support_status(
        self, session: AsyncSession, *, sentence_id: str, status: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.generated_sentence_evidence
                SET support_status = CAST(:status AS app.claim_support_status)
                WHERE generated_sentence_id = CAST(:sentence_id AS uuid)
                """
            ),
            {"sentence_id": sentence_id, "status": status},
        )

    async def _update_story_contradiction(
        self, session: AsyncSession, *, story_id: str, score: float
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.stories
                SET contradiction_score = GREATEST(contradiction_score, :score)
                WHERE id = CAST(:story_id AS uuid)
                """
            ),
            {"story_id": story_id, "score": score},
        )
