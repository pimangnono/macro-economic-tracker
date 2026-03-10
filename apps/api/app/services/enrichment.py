from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.workflows import insert_pipeline_job


async def populate_claims_from_episode(
    session: AsyncSession,
    *,
    episode_id: str,
) -> int:
    result = await session.execute(
        text(
            """
            INSERT INTO app.claims (
                story_id,
                episode_id,
                predicate,
                object_text,
                claim_text,
                support_status,
                confidence_score
            )
            SELECT
                gs.story_id,
                gs.episode_id,
                'states',
                LEFT(gs.sentence_text, 120),
                gs.sentence_text,
                gs.verdict,
                COALESCE(s.confidence_score, 0)
            FROM app.generated_sentences gs
            LEFT JOIN app.stories s ON s.id = gs.story_id
            WHERE gs.episode_id = CAST(:episode_id AS uuid)
              AND NOT EXISTS (
                  SELECT 1
                  FROM app.claims c
                  WHERE c.episode_id = gs.episode_id
                    AND c.claim_text = gs.sentence_text
              )
            """
        ),
        {"episode_id": episode_id},
    )
    await session.execute(
        text(
            """
            INSERT INTO app.claim_evidence (claim_id, evidence_span_id, support_status, score)
            SELECT
                c.id,
                gse.evidence_span_id,
                gse.support_status,
                1.0
            FROM app.claims c
            JOIN app.generated_sentences gs
              ON gs.episode_id = c.episode_id
             AND gs.sentence_text = c.claim_text
            JOIN app.generated_sentence_evidence gse ON gse.generated_sentence_id = gs.id
            WHERE c.episode_id = CAST(:episode_id AS uuid)
            ON CONFLICT (claim_id, evidence_span_id) DO NOTHING
            """
        ),
        {"episode_id": episode_id},
    )
    return result.rowcount if result.rowcount is not None and result.rowcount > 0 else 0


async def record_story_enrichment(
    session: AsyncSession,
    *,
    story_id: str,
    track_ids: list[str],
    episode_id: str,
    source_key: str,
) -> None:
    settings = get_settings()
    strategy = "openai_configured" if settings.openai_api_key else "rule_fallback"
    claims_inserted = await populate_claims_from_episode(session, episode_id=episode_id)
    await insert_pipeline_job(
        session,
        job_type="story_enrichment",
        source_object_type="story",
        source_object_id=story_id,
        input_json={
            "storyId": story_id,
            "episodeId": episode_id,
            "trackIds": track_ids,
            "sourceKey": source_key,
        },
        output_json={"strategy": strategy, "claimsInserted": claims_inserted},
    )
    await session.execute(
        text(
            """
            INSERT INTO app.agent_runs (
                agent_name,
                model_name,
                status,
                input_json,
                output_json,
                source_object_type,
                source_object_id,
                finished_at
            )
            VALUES (
                'story_enrichment',
                :model_name,
                CAST('completed' AS app.job_status),
                CAST(:input_json AS jsonb),
                CAST(:output_json AS jsonb),
                'story',
                CAST(:story_id AS uuid),
                now()
            )
            """
        ),
        {
            "model_name": settings.openai_summary_model if settings.openai_api_key else "rule_fallback",
            "input_json": json.dumps(
                {
                    "storyId": story_id,
                    "episodeId": episode_id,
                    "trackIds": track_ids,
                    "sourceKey": source_key,
                }
            ),
            "output_json": json.dumps({"strategy": strategy, "claimsInserted": claims_inserted}),
            "story_id": story_id,
        },
    )
    await session.commit()
