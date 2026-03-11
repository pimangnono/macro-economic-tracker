"""Story Matcher Agent — assigns events/documents to stories via entity overlap."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agents.base import BaseAgent
from app.services.llm.client import chat_completion
from app.services.pipeline.alerts import maybe_generate_alerts
from app.services.pipeline.queue import enqueue_job

logger = logging.getLogger(__name__)

TIEBREAKER_PROMPT = """\
You are a macro-economic story-matching system.
Given a new event and two candidate stories, decide which story the event belongs to.

Event:
{event_desc}

Story A (id={story_a_id}):
Title: {story_a_title}
State: {story_a_state}

Story B (id={story_b_id}):
Title: {story_b_title}
State: {story_b_state}

Return JSON: {{"chosen_story_id": "<id>", "reason": "<brief reason>"}}
If neither story is a good match, return {{"chosen_story_id": "new", "reason": "<reason>"}}
"""


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:72] or "story"


class StoryMatcherAgent(BaseAgent[dict[str, Any], dict[str, Any]]):
    @property
    def agent_name(self) -> str:
        return "story_matcher"

    @property
    def model_name(self) -> str:
        return get_settings().openai_default_model

    async def run_impl(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        event_id = input_data["event_id"]
        document_id = input_data["document_id"]
        title = input_data.get("title", "")
        event_type = input_data.get("event_type", "other")
        actor = input_data.get("actor", "")
        object_text = input_data.get("object_text", "")

        # Step 1: Get document's entity IDs
        entity_rows = await session.execute(
            text(
                """
                SELECT entity_id::text FROM app.document_entities
                WHERE document_id = CAST(:document_id AS uuid)
                ORDER BY salience_score DESC
                """
            ),
            {"document_id": document_id},
        )
        entity_ids = [str(r["entity_id"]) for r in entity_rows.mappings().all()]

        # Step 2: Get document's workspace(s) via existing story_documents or tracks
        workspace_id = await self._resolve_workspace(session, document_id)
        if not workspace_id:
            return {"matched": False, "reason": "no_workspace", "event_id": event_id}

        # Step 3: Find candidate stories with entity overlap in same workspace
        candidates = await self._find_candidate_stories(
            session, workspace_id=workspace_id, entity_ids=entity_ids
        )

        # Step 4: Score candidates
        scored = []
        for candidate in candidates:
            overlap = set(candidate["entity_ids"]) & set(entity_ids)
            total = set(candidate["entity_ids"]) | set(entity_ids)
            score = len(overlap) / max(len(total), 1)
            scored.append({**candidate, "score": score, "overlap_count": len(overlap)})

        scored.sort(key=lambda c: c["score"], reverse=True)

        # Step 5: Match logic
        story_id: str | None = None
        is_new = False
        match_method = "rule"

        if scored and scored[0]["score"] > 0.6:
            story_id = scored[0]["story_id"]
        elif (
            len(scored) >= 2
            and scored[0]["score"] > 0.3
            and abs(scored[0]["score"] - scored[1]["score"]) < 0.1
        ):
            # LLM tiebreaker
            story_id, match_method = await self._llm_tiebreaker(
                session,
                event_desc=f"{actor} {title} ({event_type}): {object_text}",
                story_a=scored[0],
                story_b=scored[1],
                trace_id=trace_id,
            )
        elif scored and scored[0]["score"] > 0.3:
            story_id = scored[0]["story_id"]
        else:
            # Create new story
            story_id = await self._create_story(
                session,
                workspace_id=workspace_id,
                title=title,
                event_type=event_type,
                document_id=document_id,
            )
            is_new = True

        if story_id == "new" or story_id is None:
            story_id = await self._create_story(
                session,
                workspace_id=workspace_id,
                title=title,
                event_type=event_type,
                document_id=document_id,
            )
            is_new = True

        # Step 6: Link event to story
        await self._link_event_to_story(session, event_id=event_id, story_id=story_id)

        # Step 7: Link story to document
        await self._ensure_story_document(
            session, story_id=story_id, document_id=document_id, method=match_method
        )

        # Step 8: Link entity IDs to story
        for eid in entity_ids:
            await self._ensure_story_entity(session, story_id=story_id, entity_id=eid)

        # Step 9: Link to matching tracks
        await self._link_to_tracks(
            session, story_id=story_id, entity_ids=entity_ids, workspace_id=workspace_id
        )

        # Step 10: Create episode
        previous_state = None if is_new else await self._get_story_state(session, story_id)
        new_state = self._infer_state(event_type, is_new)
        if not is_new:
            await self._update_story_state(session, story_id=story_id, new_state=new_state)

        episode_id = await self._create_episode(
            session,
            story_id=story_id,
            title=title,
            event_type=event_type,
            state_from=previous_state,
            state_to=new_state,
        )

        # Step 11: Link episode to document
        await self._ensure_episode_document(
            session, episode_id=episode_id, document_id=document_id
        )

        # Step 12: Generate alerts for state transitions
        await maybe_generate_alerts(
            session,
            story_id=story_id,
            episode_id=episode_id,
            state_from=previous_state,
            state_to=new_state,
        )

        # Step 13: Enqueue writer job
        await enqueue_job(
            session,
            job_type="writer",
            source_object_type="episode",
            source_object_id=episode_id,
            input_json={
                "story_id": story_id,
                "episode_id": episode_id,
                "event_ids": [event_id],
                "document_id": document_id,
            },
            priority=70,
        )

        return {
            "matched": True,
            "is_new_story": is_new,
            "story_id": story_id,
            "episode_id": episode_id,
            "match_method": match_method,
            "event_id": event_id,
        }

    async def _resolve_workspace(self, session: AsyncSession, document_id: str) -> str | None:
        # Try from existing story_documents
        result = await session.execute(
            text(
                """
                SELECT s.workspace_id::text
                FROM app.story_documents sd
                JOIN app.stories s ON s.id = sd.story_id
                WHERE sd.document_id = CAST(:document_id AS uuid)
                LIMIT 1
                """
            ),
            {"document_id": document_id},
        )
        row = result.mappings().first()
        if row:
            return str(row["workspace_id"])

        # Fallback: use the first workspace
        result = await session.execute(
            text("SELECT id::text FROM app.workspaces ORDER BY created_at ASC LIMIT 1")
        )
        row = result.mappings().first()
        return str(row["id"]) if row else None

    async def _find_candidate_stories(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        entity_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not entity_ids:
            return []

        placeholders = ", ".join(f"CAST(:eid_{i} AS uuid)" for i in range(len(entity_ids)))
        params: dict[str, Any] = {"workspace_id": workspace_id}
        for i, eid in enumerate(entity_ids):
            params[f"eid_{i}"] = eid

        result = await session.execute(
            text(
                f"""
                SELECT s.id::text AS story_id, s.title, s.story_state::text,
                       ARRAY_AGG(se.entity_id::text) AS entity_ids
                FROM app.stories s
                JOIN app.story_entities se ON se.story_id = s.id
                WHERE s.workspace_id = CAST(:workspace_id AS uuid)
                  AND s.story_state NOT IN ('closed', 'cooling')
                  AND s.last_seen_at > now() - INTERVAL '30 days'
                  AND se.entity_id IN ({placeholders})
                GROUP BY s.id, s.title, s.story_state
                ORDER BY COUNT(se.entity_id) DESC
                LIMIT 10
                """
            ),
            params,
        )
        return [
            {
                "story_id": str(row["story_id"]),
                "title": row["title"],
                "story_state": row["story_state"],
                "entity_ids": list(row["entity_ids"]) if row["entity_ids"] else [],
            }
            for row in result.mappings().all()
        ]

    async def _llm_tiebreaker(
        self,
        session: AsyncSession,
        *,
        event_desc: str,
        story_a: dict[str, Any],
        story_b: dict[str, Any],
        trace_id: str,
    ) -> tuple[str, str]:
        prompt = TIEBREAKER_PROMPT.format(
            event_desc=event_desc,
            story_a_id=story_a["story_id"],
            story_a_title=story_a["title"],
            story_a_state=story_a["story_state"],
            story_b_id=story_b["story_id"],
            story_b_title=story_b["title"],
            story_b_state=story_b["story_state"],
        )
        try:
            raw, _ = await chat_completion(
                [{"role": "user", "content": prompt}],
                model=self.model_name,
                temperature=0.1,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            chosen = parsed.get("chosen_story_id", "new")
            if chosen in (story_a["story_id"], story_b["story_id"]):
                return chosen, "llm"
            return "new", "llm"
        except Exception:
            logger.warning("[%s] LLM tiebreaker failed, using top candidate", trace_id)
            return story_a["story_id"], "rule"

    async def _create_story(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        title: str,
        event_type: str,
        document_id: str,
    ) -> str:
        slug = f"{_slugify(title)}-{document_id[:8]}"
        state = self._infer_state(event_type, is_new=True)
        result = await session.execute(
            text(
                """
                INSERT INTO app.stories (
                    workspace_id, dominant_mode, title, slug,
                    story_state, first_seen_at, last_seen_at, state_changed_at,
                    hotness_score, novelty_score, contradiction_score,
                    confidence_score, source_diversity_score, metadata
                )
                VALUES (
                    CAST(:workspace_id AS uuid),
                    CAST('custom' AS app.track_mode),
                    :title, :slug,
                    CAST(:story_state AS app.story_state),
                    now(), now(), now(),
                    0.5, 0.8, 0.05, 0.6, 0.3,
                    CAST(:metadata AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": workspace_id,
                "title": title,
                "slug": slug,
                "story_state": state,
                "metadata": json.dumps({"created_by": "story_matcher", "document_id": document_id}),
            },
        )
        return str(result.scalar_one())

    def _infer_state(self, event_type: str, is_new: bool) -> str:
        if event_type in ("data_release", "policy_decision"):
            return "confirmed"
        if event_type in ("speech_statement", "forecast"):
            return "developing"
        return "emerging" if is_new else "developing"

    async def _link_event_to_story(
        self, session: AsyncSession, *, event_id: str, story_id: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.events
                SET story_id = CAST(:story_id AS uuid)
                WHERE id = CAST(:event_id AS uuid)
                """
            ),
            {"event_id": event_id, "story_id": story_id},
        )

    async def _ensure_story_document(
        self, session: AsyncSession, *, story_id: str, document_id: str, method: str
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.story_documents (story_id, document_id, assignment_score, assignment_method, is_primary, metadata)
                VALUES (
                    CAST(:story_id AS uuid), CAST(:document_id AS uuid),
                    0.7, CAST(:method AS app.assignment_method), false,
                    CAST(:metadata AS jsonb)
                )
                ON CONFLICT (story_id, document_id) DO UPDATE
                SET assignment_score = GREATEST(app.story_documents.assignment_score, EXCLUDED.assignment_score)
                """
            ),
            {
                "story_id": story_id,
                "document_id": document_id,
                "method": method,
                "metadata": json.dumps({"assigned_by": "story_matcher"}),
            },
        )

    async def _ensure_story_entity(
        self, session: AsyncSession, *, story_id: str, entity_id: str
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.story_entities (story_id, entity_id, role, salience_score)
                VALUES (CAST(:story_id AS uuid), CAST(:entity_id AS uuid), 'mentioned', 0.5)
                ON CONFLICT (story_id, entity_id, role) DO UPDATE
                SET last_seen_at = now()
                """
            ),
            {"story_id": story_id, "entity_id": entity_id},
        )

    async def _link_to_tracks(
        self,
        session: AsyncSession,
        *,
        story_id: str,
        entity_ids: list[str],
        workspace_id: str,
    ) -> None:
        if not entity_ids:
            return
        placeholders = ", ".join(f"CAST(:eid_{i} AS uuid)" for i in range(len(entity_ids)))
        params: dict[str, Any] = {"workspace_id": workspace_id}
        for i, eid in enumerate(entity_ids):
            params[f"eid_{i}"] = eid

        result = await session.execute(
            text(
                f"""
                SELECT DISTINCT te.track_id::text
                FROM app.track_entities te
                JOIN app.tracks t ON t.id = te.track_id
                WHERE t.workspace_id = CAST(:workspace_id AS uuid)
                  AND t.state = CAST('active' AS app.track_state)
                  AND te.entity_id IN ({placeholders})
                """
            ),
            params,
        )
        for row in result.mappings().all():
            track_id = str(row["track_id"])
            await session.execute(
                text(
                    """
                    INSERT INTO app.track_stories (track_id, story_id, relevance_score, priority_score, reason, added_at)
                    VALUES (CAST(:track_id AS uuid), CAST(:story_id AS uuid), 0.6, 0.5, 'entity_overlap', now())
                    ON CONFLICT (track_id, story_id) DO UPDATE
                    SET relevance_score = GREATEST(app.track_stories.relevance_score, EXCLUDED.relevance_score),
                        removed_at = NULL
                    """
                ),
                {"track_id": track_id, "story_id": story_id},
            )

    async def _get_story_state(self, session: AsyncSession, story_id: str) -> str | None:
        result = await session.execute(
            text(
                "SELECT story_state::text FROM app.stories WHERE id = CAST(:story_id AS uuid)"
            ),
            {"story_id": story_id},
        )
        row = result.mappings().first()
        return row["story_state"] if row else None

    async def _update_story_state(
        self, session: AsyncSession, *, story_id: str, new_state: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.stories
                SET story_state = CASE
                        WHEN story_state IN ('confirmed', 'contested') THEN story_state
                        ELSE CAST(:new_state AS app.story_state)
                    END,
                    last_seen_at = now(),
                    state_changed_at = CASE
                        WHEN story_state <> CAST(:new_state AS app.story_state) THEN now()
                        ELSE state_changed_at
                    END
                WHERE id = CAST(:story_id AS uuid)
                """
            ),
            {"story_id": story_id, "new_state": new_state},
        )

    async def _create_episode(
        self,
        session: AsyncSession,
        *,
        story_id: str,
        title: str,
        event_type: str,
        state_from: str | None,
        state_to: str,
    ) -> str:
        episode_type_map = {
            "policy_decision": "official_release",
            "data_release": "official_release",
            "speech_statement": "speaker_comment",
            "market_move": "market_reaction",
            "forecast": "follow_up",
        }
        episode_type = episode_type_map.get(event_type, "new_signal")
        result = await session.execute(
            text(
                """
                INSERT INTO app.episodes (
                    story_id, episode_type, headline,
                    state_from, state_to,
                    significance_score, confidence_score,
                    started_at, created_by_agent
                )
                VALUES (
                    CAST(:story_id AS uuid),
                    CAST(:episode_type AS app.episode_type),
                    :headline, :state_from, :state_to,
                    0.7, 0.6, now(), 'story_matcher'
                )
                RETURNING id
                """
            ),
            {
                "story_id": story_id,
                "episode_type": episode_type,
                "headline": title,
                "state_from": state_from,
                "state_to": state_to,
            },
        )
        return str(result.scalar_one())

    async def _ensure_episode_document(
        self, session: AsyncSession, *, episode_id: str, document_id: str
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.episode_documents (episode_id, document_id, role)
                VALUES (CAST(:episode_id AS uuid), CAST(:document_id AS uuid), 'supporting')
                ON CONFLICT (episode_id, document_id, role) DO NOTHING
                """
            ),
            {"episode_id": episode_id, "document_id": document_id},
        )
