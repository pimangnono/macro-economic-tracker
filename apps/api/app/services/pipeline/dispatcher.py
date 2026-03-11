from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

JOB_TYPE_EVENT_EXTRACTION = "event_extraction"
JOB_TYPE_ENTITY_LINKING = "entity_linking"
JOB_TYPE_STORY_MATCHING = "story_matching"
JOB_TYPE_WRITER = "writer"
JOB_TYPE_VERIFIER = "verifier"

ALL_JOB_TYPES = [
    JOB_TYPE_EVENT_EXTRACTION,
    JOB_TYPE_ENTITY_LINKING,
    JOB_TYPE_STORY_MATCHING,
    JOB_TYPE_WRITER,
    JOB_TYPE_VERIFIER,
]


async def dispatch_job(session: AsyncSession, job: dict[str, Any]) -> dict[str, Any]:
    """Route a pipeline job to the correct agent and return its output."""
    job_type = job["job_type"]
    input_json = job["input_json"]

    if job_type == JOB_TYPE_EVENT_EXTRACTION:
        from app.services.agents.event_extractor import EventExtractorAgent

        agent = EventExtractorAgent()
        return await agent.run(
            session,
            input_json,
            source_object_type="document",
            source_object_id=input_json.get("document_id"),
        )

    if job_type == JOB_TYPE_ENTITY_LINKING:
        from app.services.agents.entity_linker import EntityLinkerAgent

        agent = EntityLinkerAgent()
        return await agent.run(
            session,
            input_json,
            source_object_type="document",
            source_object_id=input_json.get("document_id"),
        )

    if job_type == JOB_TYPE_STORY_MATCHING:
        from app.services.agents.story_matcher import StoryMatcherAgent

        agent = StoryMatcherAgent()
        return await agent.run(
            session,
            input_json,
            source_object_type="event",
            source_object_id=input_json.get("event_id"),
        )

    if job_type == JOB_TYPE_WRITER:
        from app.services.agents.writer import WriterAgent

        agent = WriterAgent()
        return await agent.run(
            session,
            input_json,
            source_object_type="episode",
            source_object_id=input_json.get("episode_id"),
        )

    if job_type == JOB_TYPE_VERIFIER:
        from app.services.agents.verifier import VerifierAgent

        agent = VerifierAgent()
        return await agent.run(
            session,
            input_json,
            source_object_type="episode",
            source_object_id=input_json.get("episode_id"),
        )

    raise ValueError(f"Unknown job type: {job_type}")
