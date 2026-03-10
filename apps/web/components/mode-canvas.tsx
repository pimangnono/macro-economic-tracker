import type { TrackCanvasResponse } from "@/lib/api";

const MODE_COPY: Record<
  string,
  {
    title: string;
    storyline: string;
    evidence: string;
    events: string;
    reactions: string;
  }
> = {
  scheduled_release: {
    title: "Release canvas",
    storyline: "Release ladder",
    evidence: "Official evidence",
    events: "Upcoming prints",
    reactions: "Market pricing",
  },
  policy_communication: {
    title: "Policy canvas",
    storyline: "Speaker storyline",
    evidence: "Communication evidence",
    events: "Upcoming appearances",
    reactions: "Rates repricing",
  },
  slow_burn_theme: {
    title: "Theme canvas",
    storyline: "Structural storyline",
    evidence: "Accumulating evidence",
    events: "Catalysts",
    reactions: "Cross-asset spillover",
  },
  breaking_shock: {
    title: "Shock canvas",
    storyline: "Situation timeline",
    evidence: "Verified facts",
    events: "Next checkpoints",
    reactions: "Stress signals",
  },
  watchlist_exposure: {
    title: "Exposure canvas",
    storyline: "Exposure storyline",
    evidence: "Portfolio evidence",
    events: "Risk triggers",
    reactions: "PnL-sensitive moves",
  },
  custom: {
    title: "Custom canvas",
    storyline: "Storyline",
    evidence: "Evidence signals",
    events: "Upcoming events",
    reactions: "Market reactions",
  },
};

export function ModeCanvas({ data }: { data: TrackCanvasResponse }) {
  const copy = MODE_COPY[data.modeData.kind] ?? MODE_COPY.custom;
  const blocks = data.modeData.blocks;
  const storyline = (blocks.storyline as Array<{ title: string; storyState: string }> | undefined) ?? [];
  const quotes =
    (blocks.quotes as Array<{ id: string; quoteText: string; sourceName?: string; supportStatus?: string }> | undefined) ??
    [];
  const upcomingEvents =
    (blocks.upcomingEvents as Array<{ id: string; title: string; publishedAt?: string; sourceName?: string }> | undefined) ??
    [];
  const snapshots = (blocks.recentSnapshots as Array<{ id: string; summaryText?: string }> | undefined) ?? [];
  const marketReactions =
    (blocks.marketReactions as Array<{ metric_name?: string; direction?: string; value_numeric?: number; unit?: string }> | undefined) ??
    [];

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">{data.modeData.kind.replaceAll("_", " ")}</p>
          <h2>{copy.title}</h2>
        </div>
      </div>
      <div className="canvas-grid">
        <article className="canvas-card">
          <h3>{copy.storyline}</h3>
          <ul>
            {storyline.length === 0 ? <li>No linked stories yet.</li> : null}
            {storyline.map((item, index) => (
              <li key={`${item.title}-${index}`}>{item.title} | {item.storyState}</li>
            ))}
          </ul>
        </article>
        <article className="canvas-card">
          <h3>{copy.evidence}</h3>
          <ul>
            {quotes.length === 0 ? <li>No extracted evidence quotes yet.</li> : null}
            {quotes.map((quote) => (
              <li key={quote.id}>
                "{quote.quoteText}" {quote.sourceName ? `| ${quote.sourceName}` : ""}
              </li>
            ))}
          </ul>
        </article>
        <article className="canvas-card">
          <h3>{copy.events}</h3>
          <ul>
            {upcomingEvents.length === 0 ? <li>No calendar-linked events yet.</li> : null}
            {upcomingEvents.map((item) => (
              <li key={item.id}>
                {item.title}
                {item.publishedAt ? ` | ${new Date(item.publishedAt).toLocaleString()}` : ""}
              </li>
            ))}
          </ul>
        </article>
        <article className="canvas-card">
          <h3>{copy.reactions}</h3>
          <ul>
            {marketReactions.length === 0 ? <li>No market reactions stored yet.</li> : null}
            {marketReactions.map((item, index) => (
              <li key={`${item.metric_name}-${index}`}>
                {item.metric_name ?? "metric"} {item.direction ?? ""} {item.value_numeric ?? ""}
                {item.unit ? ` ${item.unit}` : ""}
              </li>
            ))}
          </ul>
        </article>
        <article className="canvas-card">
          <h3>Recent snapshots</h3>
          <ul>
            {snapshots.length === 0 ? <li>No snapshots yet.</li> : null}
            {snapshots.map((item) => (
              <li key={item.id}>{item.summaryText ?? "Snapshot generated"}</li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}
