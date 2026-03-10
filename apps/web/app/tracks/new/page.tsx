import { EmptyState } from "@/components/empty-state";
import { SummaryFrame } from "@/components/summary-frame";
import { TrackWizard } from "@/components/track-wizard";
import { getTrackBootstrap } from "@/lib/api";
import { getRequiredSession } from "@/lib/auth";

export default async function NewTrackPage() {
  const session = await getRequiredSession();
  const bootstrap = await getTrackBootstrap(
    session.accessToken,
    session.backendUser?.defaultWorkspaceId ?? undefined,
  );

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
          <h2>Create a mode-aware monitoring object</h2>
          <p>
            The creation flow now captures alert sensitivity, evidence strictness, and watchlist
            context instead of acting like a bare saved-search form.
          </p>
        </div>
      </section>

      <SummaryFrame
        summary={{
          whatChanged: "Track creation now acts like a beta workflow wizard.",
          whyItMatters: "It captures the operating assumptions the downstream inbox and alerts need.",
          whatToWatch: "Use the description and watchlist fields to make the first episode matching more precise.",
        }}
      />

      <TrackWizard
        bootstrap={bootstrap}
        defaultWorkspaceId={session.backendUser?.defaultWorkspaceId ?? undefined}
      />
    </div>
  );
}
