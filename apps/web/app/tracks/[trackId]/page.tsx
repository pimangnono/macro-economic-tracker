import { EmptyState } from "@/components/empty-state";
import { StoryTable } from "@/components/story-table";
import { SummaryFrame } from "@/components/summary-frame";
import { StatusPill } from "@/components/status-pill";
import { getTrack } from "@/lib/api";

export default async function TrackDetailPage({
  params,
}: {
  params: Promise<{ trackId: string }>;
}) {
  const { trackId } = await params;
  const data = await getTrack(trackId);

  if (!data) {
    return (
      <EmptyState
        title="Track unavailable"
        body="The API could not resolve this track. Check that Postgres is up and the track exists in the `app.tracks` table."
      />
    );
  }

  return (
    <div className="detail-layout">
      <section className="detail-hero">
        <div>
          <p className="eyebrow">{data.track.mode.replaceAll("_", " ")}</p>
          <h2>{data.track.name}</h2>
          <p>{data.track.description ?? "No description has been authored for this track yet."}</p>
        </div>
        <div className="pill-row">
          <StatusPill>{data.track.state}</StatusPill>
          <StatusPill tone="positive">{data.track.metrics.storyCount} stories</StatusPill>
          <StatusPill tone="warning">{data.track.metrics.activeStoryCount} active</StatusPill>
        </div>
      </section>

      <SummaryFrame summary={data.track.topSummary} />

      <section className="metrics-panel">
        <article>
          <span>Memory window</span>
          <strong>{data.track.memoryWindowDays} days</strong>
        </article>
        <article>
          <span>Last activity</span>
          <strong>
            {data.track.metrics.lastActivityAt
              ? new Date(data.track.metrics.lastActivityAt).toLocaleString()
              : "Awaiting first story"}
          </strong>
        </article>
        <article>
          <span>Alert policy</span>
          <strong>{Object.keys(data.track.alertPolicy ?? {}).length} configured rules</strong>
        </article>
      </section>

      {data.stories.length === 0 ? (
        <EmptyState
          title="No linked stories yet"
          body="The track exists, but no stories have been matched into `app.track_stories`."
        />
      ) : (
        <StoryTable stories={data.stories} />
      )}
    </div>
  );
}

