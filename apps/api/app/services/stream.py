from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.queries import fetch_outbox_events

settings = get_settings()


async def stream_outbox(
    session_factory,
    workspace_id: str | None,
    after: datetime | None,
):
    cursor = after
    while True:
        async with session_factory() as session:
            events = await fetch_outbox_events(session, workspace_id=workspace_id, after=cursor)

        if events:
            for event in events:
                cursor = event["created_at"]
                yield {
                    "event": event["event_type"],
                    "id": cursor.isoformat(),
                    "data": json.dumps(
                        {
                            "id": str(event["id"]),
                            "aggregateType": event["aggregate_type"],
                            "aggregateId": str(event["aggregate_id"]),
                            "workspaceId": str(event["workspace_id"]),
                            "payload": event["payload"],
                            "createdAt": cursor.isoformat(),
                        }
                    ),
                }
        else:
            yield {
                "event": "heartbeat",
                "data": json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
            }
