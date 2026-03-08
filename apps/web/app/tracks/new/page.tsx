import { EmptyState } from "@/components/empty-state";
import { SummaryFrame } from "@/components/summary-frame";
import { TrackCreateForm } from "@/components/track-create-form";
import { getTrackBootstrap } from "@/lib/api";

export default async function NewTrackPage() {
  const bootstrap = await getTrackBootstrap();

  if (!bootstrap || bootstrap.workspaces.length === 0) {
    return (
      <EmptyState
        title="Track creation unavailable"
        body="The API is reachable, but no workspaces are available yet. Run the migration and seed steps first."
      />
    );
  }

  return (
    <div className="detail-layout">
      <section className="detail-hero">
        <div>
          <p className="eyebrow">Tracks / New</p>
          <h2>Create a monitoring object, not a saved search</h2>
          <p>
            This writes directly to the FastAPI backend and creates a real `app.tracks`
            record in Postgres.
          </p>
        </div>
      </section>

      <SummaryFrame
        summary={{
          whatChanged: "Track creation is now wired to the production API contract.",
          whyItMatters: "This is where the product starts moving from read-only to operable.",
          whatToWatch: "Next step is routing source documents into stories and episodes.",
        }}
      />

      <TrackCreateForm bootstrap={bootstrap} />
    </div>
  );
}
