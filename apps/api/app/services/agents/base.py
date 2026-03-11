from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Abstract base for all pipeline agents.

    Subclasses implement ``agent_name``, ``model_name``, and ``run_impl``.
    The ``run`` method handles agent_runs bookkeeping, error handling, and timing.
    """

    @property
    @abstractmethod
    def agent_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def run_impl(
        self,
        session: AsyncSession,
        input_data: InputT,
        trace_id: str,
    ) -> OutputT: ...

    async def run(
        self,
        session: AsyncSession,
        input_data: InputT,
        *,
        source_object_type: str | None = None,
        source_object_id: str | None = None,
    ) -> OutputT:
        trace_id = uuid.uuid4().hex[:16]
        run_id = await self._create_run(
            session,
            input_data=input_data,
            source_object_type=source_object_type,
            source_object_id=source_object_id,
        )
        await session.commit()
        start = time.monotonic()

        try:
            result = await self.run_impl(session, input_data, trace_id)
            latency_ms = int((time.monotonic() - start) * 1000)
            await self._complete_run(session, run_id, result, latency_ms)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            latency_ms = int((time.monotonic() - start) * 1000)
            import traceback

            error_text = traceback.format_exc()
            await self._fail_run(session, run_id, error_text, latency_ms)
            await session.commit()
            raise

    async def _create_run(
        self,
        session: AsyncSession,
        *,
        input_data: Any,
        source_object_type: str | None,
        source_object_id: str | None,
    ) -> str:
        input_json = json.dumps(input_data) if not isinstance(input_data, str) else input_data
        result = await session.execute(
            text(
                """
                INSERT INTO app.agent_runs (
                    agent_name, model_name, status, input_json,
                    source_object_type, source_object_id
                )
                VALUES (
                    :agent_name, :model_name,
                    CAST('running' AS app.job_status),
                    CAST(:input_json AS jsonb),
                    :source_object_type,
                    CAST(:source_object_id AS uuid)
                )
                RETURNING id
                """
            ),
            {
                "agent_name": self.agent_name,
                "model_name": self.model_name,
                "input_json": input_json,
                "source_object_type": source_object_type,
                "source_object_id": source_object_id,
            },
        )
        return str(result.scalar_one())

    async def _complete_run(
        self,
        session: AsyncSession,
        run_id: str,
        output: Any,
        latency_ms: int,
    ) -> None:
        output_json = json.dumps(output) if not isinstance(output, str) else output
        await session.execute(
            text(
                """
                UPDATE app.agent_runs
                SET status = CAST('completed' AS app.job_status),
                    output_json = CAST(:output_json AS jsonb),
                    latency_ms = :latency_ms,
                    finished_at = now()
                WHERE id = CAST(:run_id AS uuid)
                """
            ),
            {"run_id": run_id, "output_json": output_json, "latency_ms": latency_ms},
        )

    async def _fail_run(
        self,
        session: AsyncSession,
        run_id: str,
        error_text: str,
        latency_ms: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE app.agent_runs
                SET status = CAST('failed' AS app.job_status),
                    error_text = :error_text,
                    latency_ms = :latency_ms,
                    finished_at = now()
                WHERE id = CAST(:run_id AS uuid)
                """
            ),
            {"run_id": run_id, "error_text": error_text[:4000], "latency_ms": latency_ms},
        )
