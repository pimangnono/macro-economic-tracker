from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import asyncpg

from app.core.config import get_settings

DEFAULT_WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_USER_ID = "22222222-2222-2222-2222-222222222222"

SEED_SQL = """
INSERT INTO app.users (id, email, display_name, timezone)
VALUES
  ('22222222-2222-2222-2222-222222222222', 'analyst@macrotracker.local', 'Macro Analyst', 'Asia/Singapore')
ON CONFLICT (email) DO UPDATE
SET display_name = EXCLUDED.display_name,
    timezone = EXCLUDED.timezone;

INSERT INTO app.workspaces (id, name, slug, created_by)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'Macro Desk', 'macro-desk', '22222222-2222-2222-2222-222222222222')
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name,
    created_by = EXCLUDED.created_by;

INSERT INTO app.workspace_members (workspace_id, user_id, role)
VALUES
  ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'owner')
ON CONFLICT (workspace_id, user_id) DO UPDATE
SET role = EXCLUDED.role;

INSERT INTO app.sources (id, source_key, display_name, source_type, base_url, trust_score)
VALUES
  ('33333333-3333-3333-3333-333333333331', 'fed', 'Federal Reserve', 'official', 'https://www.federalreserve.gov', 0.98),
  ('33333333-3333-3333-3333-333333333332', 'bls', 'Bureau of Labor Statistics', 'official', 'https://www.bls.gov', 0.98),
  ('33333333-3333-3333-3333-333333333333', 'reuters', 'Reuters', 'newswire', 'https://www.reuters.com', 0.92)
ON CONFLICT (source_key) DO UPDATE
SET display_name = EXCLUDED.display_name,
    source_type = EXCLUDED.source_type,
    base_url = EXCLUDED.base_url,
    trust_score = EXCLUDED.trust_score;

INSERT INTO app.documents (
  id, canonical_url, canonical_url_hash, source_id, document_type, title, body_text,
  author_name, published_at, language, source_priority, dedup_hash, metadata
)
VALUES
  (
    '44444444-4444-4444-4444-444444444441',
    'https://www.bls.gov/news.release/cpi.nr0.htm',
    'seed-cpi-url',
    '33333333-3333-3333-3333-333333333332',
    'press_release',
    'BLS CPI release shows another upside inflation surprise',
    'Headline CPI came in above consensus, with services and shelter remaining firm.',
    'BLS',
    '2026-03-06T12:30:00Z',
    'en',
    10,
    'seed-cpi-doc',
    '{"lane":"official"}'
  ),
  (
    '44444444-4444-4444-4444-444444444442',
    'https://www.reuters.com/world/us/fed-speech-example',
    'seed-fed-url',
    '33333333-3333-3333-3333-333333333333',
    'speech',
    'Fed speaker leans toward slower cuts after inflation resilience',
    'A senior Fed speaker said inflation persistence argues for patience on cuts.',
    'Reuters',
    '2026-03-06T14:10:00Z',
    'en',
    20,
    'seed-fed-doc',
    '{"lane":"policy"}'
  )
ON CONFLICT (dedup_hash) DO UPDATE
SET title = EXCLUDED.title,
    body_text = EXCLUDED.body_text,
    published_at = EXCLUDED.published_at,
    metadata = EXCLUDED.metadata;

INSERT INTO app.evidence_spans (
  id, document_id, quote_text, char_start, char_end, sentence_start, sentence_end, metadata
)
VALUES
  (
    '55555555-5555-5555-5555-555555555551',
    '44444444-4444-4444-4444-444444444441',
    'Headline CPI came in above consensus, with services and shelter remaining firm.',
    0, 78, 1, 1, '{"kind":"release"}'
  ),
  (
    '55555555-5555-5555-5555-555555555552',
    '44444444-4444-4444-4444-444444444442',
    'Inflation persistence argues for patience on cuts.',
    0, 50, 1, 1, '{"kind":"quote"}'
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.tracks (
  id, workspace_id, owner_user_id, name, slug, description, mode, state, alert_policy, memory_window_days
)
VALUES
  (
    '66666666-6666-6666-6666-666666666661',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    'US Inflation',
    'us-inflation',
    'Track CPI, PPI, Fed framing, and the inflation regime narrative.',
    'scheduled_release',
    'active',
    '{"delivery":"in_app","cadence":"immediate","threshold":"state_change"}',
    30
  ),
  (
    '66666666-6666-6666-6666-666666666662',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    'Fed 2026 easing path',
    'fed-2026-easing-path',
    'Track speeches, meeting language, and repricing of the cuts path.',
    'policy_communication',
    'active',
    '{"delivery":"in_app","cadence":"digest","threshold":"official_confirmation"}',
    45
  )
ON CONFLICT (workspace_id, slug) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    mode = EXCLUDED.mode,
    state = EXCLUDED.state,
    alert_policy = EXCLUDED.alert_policy,
    memory_window_days = EXCLUDED.memory_window_days;

INSERT INTO app.stories (
  id, workspace_id, dominant_mode, title, slug, summary_text, summary_json,
  story_state, first_seen_at, last_seen_at, state_changed_at,
  hotness_score, novelty_score, contradiction_score, confidence_score, source_diversity_score,
  official_confirmation_at, market_reaction_at, metadata
)
VALUES
  (
    '77777777-7777-7777-7777-777777777771',
    '11111111-1111-1111-1111-111111111111',
    'scheduled_release',
    'US CPI surprise keeps inflation pressure live',
    'us-cpi-surprise-keeps-inflation-pressure-live',
    'Official CPI data confirmed a hotter release and delayed easing hopes.',
    '{"what_changed":"Official CPI release came in above consensus.","why_it_matters":"The rates path may stay higher for longer.","what_to_watch":"2Y yields, Fed speakers, next PPI."}',
    'confirmed',
    '2026-03-06T12:30:00Z',
    '2026-03-06T13:20:00Z',
    '2026-03-06T13:20:00Z',
    0.89, 0.67, 0.11, 0.92, 0.71,
    '2026-03-06T12:30:00Z',
    '2026-03-06T12:40:00Z',
    '{"demo":true}'
  ),
  (
    '77777777-7777-7777-7777-777777777772',
    '11111111-1111-1111-1111-111111111111',
    'policy_communication',
    'Fed speakers push back on early cuts',
    'fed-speakers-push-back-on-early-cuts',
    'Policy communication has shifted toward patience after sticky inflation prints.',
    '{"what_changed":"A senior Fed speaker leaned more hawkish than the prior meeting tone.","why_it_matters":"Early cut expectations face renewed challenge.","what_to_watch":"Speaker follow-through, CPI revisions, fed funds futures."}',
    'developing',
    '2026-03-06T14:10:00Z',
    '2026-03-06T14:30:00Z',
    '2026-03-06T14:30:00Z',
    0.73, 0.58, 0.16, 0.77, 0.54,
    NULL,
    '2026-03-06T14:35:00Z',
    '{"demo":true}'
  )
ON CONFLICT (workspace_id, slug) DO UPDATE
SET title = EXCLUDED.title,
    summary_text = EXCLUDED.summary_text,
    summary_json = EXCLUDED.summary_json,
    story_state = EXCLUDED.story_state,
    last_seen_at = EXCLUDED.last_seen_at,
    state_changed_at = EXCLUDED.state_changed_at,
    hotness_score = EXCLUDED.hotness_score,
    contradiction_score = EXCLUDED.contradiction_score,
    confidence_score = EXCLUDED.confidence_score;

INSERT INTO app.track_stories (track_id, story_id, relevance_score, priority_score, reason, added_at)
VALUES
  (
    '66666666-6666-6666-6666-666666666661',
    '77777777-7777-7777-7777-777777777771',
    0.96, 0.95,
    'Official inflation release directly matched the track definition.',
    '2026-03-06T12:31:00Z'
  ),
  (
    '66666666-6666-6666-6666-666666666662',
    '77777777-7777-7777-7777-777777777772',
    0.88, 0.83,
    'Policy speaker language altered the expected easing path.',
    '2026-03-06T14:11:00Z'
  )
ON CONFLICT (track_id, story_id) DO UPDATE
SET relevance_score = EXCLUDED.relevance_score,
    priority_score = EXCLUDED.priority_score,
    reason = EXCLUDED.reason,
    removed_at = NULL;

INSERT INTO app.episodes (
  id, story_id, episode_type, headline, state_from, state_to,
  what_changed, why_it_matters, what_to_watch,
  significance_score, confidence_score, contradiction_score, started_at, created_at, created_by_agent, payload
)
VALUES
  (
    '88888888-8888-8888-8888-888888888881',
    '77777777-7777-7777-7777-777777777771',
    'official_release',
    'CPI release confirms prior upside inflation concerns',
    'developing',
    'confirmed',
    'Official CPI data printed above consensus and reinforced the inflation pressure narrative.',
    'A firmer print can delay the easing path and keep front-end yields elevated.',
    'Monitor Powell commentary, 2Y yield follow-through, and the next PPI release.',
    0.94, 0.93, 0.08, '2026-03-06T12:30:00Z', '2026-03-06T12:33:00Z', 'demo_seed',
    '{"mode":"scheduled_release"}'
  ),
  (
    '88888888-8888-8888-8888-888888888882',
    '77777777-7777-7777-7777-777777777772',
    'speaker_comment',
    'Fed speaker language turns more patient on cuts',
    'emerging',
    'developing',
    'A senior Fed speaker emphasized inflation persistence and a slower pace of cuts.',
    'This pushes back against aggressive easing expectations and can reprice rate-sensitive assets.',
    'Watch for follow-up speakers and fed funds futures repricing.',
    0.79, 0.81, 0.12, '2026-03-06T14:10:00Z', '2026-03-06T14:16:00Z', 'demo_seed',
    '{"mode":"policy_communication"}'
  )
ON CONFLICT (id) DO UPDATE
SET headline = EXCLUDED.headline,
    what_changed = EXCLUDED.what_changed,
    why_it_matters = EXCLUDED.why_it_matters,
    what_to_watch = EXCLUDED.what_to_watch,
    confidence_score = EXCLUDED.confidence_score,
    contradiction_score = EXCLUDED.contradiction_score,
    updated_at = now();

INSERT INTO app.episode_documents (episode_id, document_id, role)
VALUES
  ('88888888-8888-8888-8888-888888888881', '44444444-4444-4444-4444-444444444441', 'supporting'),
  ('88888888-8888-8888-8888-888888888882', '44444444-4444-4444-4444-444444444442', 'supporting')
ON CONFLICT (episode_id, document_id, role) DO NOTHING;

INSERT INTO app.generated_sentences (
  id, story_id, episode_id, sentence_order, sentence_text, verdict, model_name
)
VALUES
  (
    '99999999-9999-9999-9999-999999999991',
    '77777777-7777-7777-7777-777777777771',
    '88888888-8888-8888-8888-888888888881',
    1,
    'Official CPI data came in above consensus and confirmed renewed inflation pressure.',
    'supported',
    'demo-writer'
  ),
  (
    '99999999-9999-9999-9999-999999999992',
    '77777777-7777-7777-7777-777777777772',
    '88888888-8888-8888-8888-888888888882',
    1,
    'A senior Fed speaker signaled patience on cuts after sticky inflation prints.',
    'supported',
    'demo-writer'
  )
ON CONFLICT (episode_id, sentence_order) DO UPDATE
SET sentence_text = EXCLUDED.sentence_text,
    verdict = EXCLUDED.verdict,
    model_name = EXCLUDED.model_name;

INSERT INTO app.generated_sentence_evidence (generated_sentence_id, evidence_span_id, support_status)
VALUES
  ('99999999-9999-9999-9999-999999999991', '55555555-5555-5555-5555-555555555551', 'supported'),
  ('99999999-9999-9999-9999-999999999992', '55555555-5555-5555-5555-555555555552', 'supported')
ON CONFLICT (generated_sentence_id, evidence_span_id) DO NOTHING;

INSERT INTO app.notes (
  id, workspace_id, author_user_id, scope, track_id, story_id, body_md, pinned
)
VALUES
  (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    'track',
    '66666666-6666-6666-6666-666666666661',
    '77777777-7777-7777-7777-777777777771',
    'Monitor whether shelter disinflation fails to materialize over the next two prints.',
    true
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.notifications (
  id, workspace_id, user_id, track_id, story_id, episode_id, reason, channel, dedup_key, title, body_text, payload, created_at, scheduled_for
)
VALUES
  (
    'cccccccc-cccc-cccc-cccc-ccccccccccc1',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '66666666-6666-6666-6666-666666666661',
    '77777777-7777-7777-7777-777777777771',
    '88888888-8888-8888-8888-888888888881',
    'official_confirmation_added',
    'in_app',
    'seed:official_confirmation:us-inflation',
    'US Inflation: CPI release confirms prior upside inflation concerns',
    'An official CPI release matched the track and confirmed the hotter inflation narrative.',
    '{"trackId":"66666666-6666-6666-6666-666666666661","storyId":"77777777-7777-7777-7777-777777777771","episodeId":"88888888-8888-8888-8888-888888888881"}',
    '2026-03-06T12:33:00Z',
    '2026-03-06T12:33:00Z'
  ),
  (
    'cccccccc-cccc-cccc-cccc-ccccccccccc2',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '66666666-6666-6666-6666-666666666662',
    '77777777-7777-7777-7777-777777777772',
    '88888888-8888-8888-8888-888888888882',
    'story_state_changed',
    'in_app',
    'seed:story_state:fed-2026-easing-path',
    'Fed 2026 easing path: Fed speaker language turns more patient on cuts',
    'A policy communication episode shifted the track toward a more cautious easing narrative.',
    '{"trackId":"66666666-6666-6666-6666-666666666662","storyId":"77777777-7777-7777-7777-777777777772","episodeId":"88888888-8888-8888-8888-888888888882"}',
    '2026-03-06T14:16:00Z',
    '2026-03-06T14:16:00Z'
  )
ON CONFLICT (channel, dedup_key) DO UPDATE
SET title = EXCLUDED.title,
    body_text = EXCLUDED.body_text,
    payload = EXCLUDED.payload,
    scheduled_for = EXCLUDED.scheduled_for;

INSERT INTO app.event_outbox (
  id, workspace_id, event_type, aggregate_type, aggregate_id, payload, created_at, delivered_at
)
VALUES
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    '11111111-1111-1111-1111-111111111111',
    'story.state_changed',
    'story',
    '77777777-7777-7777-7777-777777777771',
    '{"trackId":"66666666-6666-6666-6666-666666666661","storyId":"77777777-7777-7777-7777-777777777771","headline":"CPI release confirms prior upside inflation concerns"}',
    '2026-03-06T12:33:00Z',
    NULL
  ),
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    '11111111-1111-1111-1111-111111111111',
    'story.state_changed',
    'story',
    '77777777-7777-7777-7777-777777777772',
    '{"trackId":"66666666-6666-6666-6666-666666666662","storyId":"77777777-7777-7777-7777-777777777772","headline":"Fed speaker language turns more patient on cuts"}',
    '2026-03-06T14:16:00Z',
    NULL
  )
ON CONFLICT (id) DO NOTHING;
"""


def _normalize_asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def run() -> None:
    settings = get_settings()
    connection = await asyncpg.connect(_normalize_asyncpg_dsn(settings.database_url))
    try:
        await connection.execute(SEED_SQL)
        print(
            "Seeded demo workspace",
            DEFAULT_WORKSPACE_ID,
            "for user",
            DEFAULT_USER_ID,
            "at",
            datetime.now(timezone.utc).isoformat(),
        )
    finally:
        await connection.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
