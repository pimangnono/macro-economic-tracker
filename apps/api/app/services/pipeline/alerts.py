"""Alert generation — creates notifications and event_outbox rows on state transitions."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Deterministic state transition rules that warrant alerts
ALERTABLE_TRANSITIONS = {
    ("emerging", "developing"),
    ("developing", "confirmed"),
    ("emerging", "confirmed"),
    (None, "contested"),
    ("emerging", "contested"),
    ("developing", "contested"),
    ("confirmed", "contested"),
}


async def maybe_generate_alerts(
    session: AsyncSession,
    *,
    story_id: str,
    episode_id: str,
    state_from: str | None,
    state_to: str,
) -> int:
    """Check if state transition should trigger alerts. Returns count of notifications created."""
    if (state_from, state_to) not in ALERTABLE_TRANSITIONS:
        return 0

    # Fetch story + workspace info
    story_result = await session.execute(
        text(
            """
            SELECT s.id, s.workspace_id, s.title
            FROM app.stories s
            WHERE s.id = CAST(:story_id AS uuid)
            """
        ),
        {"story_id": story_id},
    )
    story_row = story_result.mappings().first()
    if not story_row:
        return 0

    workspace_id = str(story_row["workspace_id"])
    story_title = story_row["title"]

    # Determine reason
    if state_to == "contested":
        reason = "contradiction_increased"
    elif state_to == "confirmed":
        reason = "official_confirmation_added"
    else:
        reason = "story_state_changed"

    # Post to event_outbox
    await session.execute(
        text(
            """
            INSERT INTO app.event_outbox (
                workspace_id, event_type, aggregate_type, aggregate_id, payload
            )
            VALUES (
                CAST(:workspace_id AS uuid),
                'story.state_changed',
                'story',
                CAST(:story_id AS uuid),
                CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "workspace_id": workspace_id,
            "story_id": story_id,
            "payload": json.dumps({
                "story_id": story_id,
                "episode_id": episode_id,
                "state_from": state_from,
                "state_to": state_to,
                "title": story_title,
            }),
        },
    )

    # Find track owners tracking this story
    track_result = await session.execute(
        text(
            """
            SELECT t.id::text AS track_id, t.name, t.owner_user_id::text, t.alert_policy
            FROM app.track_stories ts
            JOIN app.tracks t ON t.id = ts.track_id
            WHERE ts.story_id = CAST(:story_id AS uuid)
              AND ts.removed_at IS NULL
              AND t.state = CAST('active' AS app.track_state)
            """
        ),
        {"story_id": story_id},
    )

    notification_count = 0
    for row in track_result.mappings().all():
        track_row = dict(row)
        alert_policy = track_row.get("alert_policy") or {}
        delivery = alert_policy.get("delivery", "in_app") if isinstance(alert_policy, dict) else "in_app"
        if delivery != "in_app":
            continue

        dedup_key = f"{reason}:{track_row['track_id']}:{story_id}:{episode_id}"
        title = f"{track_row['name']}: {story_title}"
        body_text = f"Story state changed from {state_from or 'new'} to {state_to}."
        payload: dict[str, Any] = {
            "trackId": track_row["track_id"],
            "storyId": story_id,
            "episodeId": episode_id,
            "stateFrom": state_from,
            "stateTo": state_to,
        }

        await session.execute(
            text(
                """
                INSERT INTO app.notifications (
                    workspace_id, user_id, track_id, story_id, episode_id,
                    reason, channel, dedup_key, title, body_text, payload, scheduled_for
                )
                VALUES (
                    CAST(:workspace_id AS uuid),
                    CAST(:user_id AS uuid),
                    CAST(:track_id AS uuid),
                    CAST(:story_id AS uuid),
                    CAST(:episode_id AS uuid),
                    CAST(:reason AS app.notification_reason),
                    CAST('in_app' AS app.notification_channel),
                    :dedup_key, :title, :body_text,
                    CAST(:payload AS jsonb), now()
                )
                ON CONFLICT (channel, dedup_key) DO UPDATE
                SET title = EXCLUDED.title,
                    body_text = EXCLUDED.body_text,
                    payload = app.notifications.payload || EXCLUDED.payload,
                    scheduled_for = EXCLUDED.scheduled_for
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": track_row.get("owner_user_id"),
                "track_id": track_row["track_id"],
                "story_id": story_id,
                "episode_id": episode_id,
                "reason": reason,
                "dedup_key": dedup_key,
                "title": title,
                "body_text": body_text,
                "payload": json.dumps(payload),
            },
        )
        notification_count += 1

    return notification_count
