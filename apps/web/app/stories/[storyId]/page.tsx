import { EmptyState } from "@/components/empty-state";
import { EpisodeTimeline } from "@/components/episode-timeline";
import { SummaryFrame } from "@/components/summary-frame";
import { StatusPill } from "@/components/status-pill";
import { getStory } from "@/lib/api";

export default async function StoryDetailPage({
  params,
}: {
  params: Promise<{ storyId: string }>;
}) {
  const { storyId } = await params;
  const data = await getStory(storyId);

  if (!data) {
    return (
      <EmptyState
        title="Story unavailable"
        body="The API could not resolve this story. Check that Postgres is up and the story exists in `app.stories`."
      />
    );
  }

  const { story } = data;

  return (
    <div className="detail-layout">
      <section className="detail-hero">
        <div>
          <p className="eyebrow">{story.dominantMode.replaceAll("_", " ")}</p>
          <h2>{story.title}</h2>
        </div>
        <div className="pill-row">
          <StatusPill>{story.state}</StatusPill>
          <StatusPill tone="critical">Heat {story.scores.hotness.toFixed(2)}</StatusPill>
          <StatusPill tone="positive">Conf {story.scores.confidence.toFixed(2)}</StatusPill>
        </div>
      </section>

      <SummaryFrame summary={story.summary} />

      <section className="two-column">
        <section className="panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Evidence drawer</p>
              <h2>Supporting spans</h2>
            </div>
          </div>
          {story.evidence.length === 0 ? (
            <p className="panel-copy">No evidence spans have been linked to generated sentences yet.</p>
          ) : (
            <ul className="quote-list">
              {story.evidence.map((item) => (
                <li key={item.id}>
                  <blockquote>{item.quoteText}</blockquote>
                  <p>
                    {item.sourceName ?? "Unknown source"} · {item.supportStatus ?? "unknown"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Source mix</p>
              <h2>Episode documents</h2>
            </div>
          </div>
          {story.sources.length === 0 ? (
            <p className="panel-copy">No documents have been linked to the latest episode yet.</p>
          ) : (
            <ul className="source-list">
              {story.sources.map((source) => (
                <li key={source.id}>
                  <strong>{source.title}</strong>
                  <span>
                    {source.sourceName ?? "Unknown source"} · {source.sourceType ?? "unknown"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>

      <EpisodeTimeline episodes={story.episodes} />
    </div>
  );
}

