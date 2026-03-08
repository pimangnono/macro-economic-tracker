import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { NotificationList } from "@/components/notification-list";
import { SourceHealthPanel } from "@/components/source-health-panel";
import { SummaryFrame } from "@/components/summary-frame";
import { TrackCard } from "@/components/track-card";
import { getLiveBoard, getRecentNotifications, getSourceHealth } from "@/lib/api";

export default async function HomePage() {
  const [liveBoard, sourceHealth, notifications] = await Promise.all([
    getLiveBoard(),
    getSourceHealth(),
    getRecentNotifications(),
  ]);

  return (
    <div className="dashboard">
      <section className="hero">
        <div>
          <p className="eyebrow">Home / Inbox</p>
          <h2>Prioritized by state change, not article volume</h2>
        </div>
        <div className="hero__side">
          <p>
            This surface is wired to the live board, source health, and in-app notification APIs.
            The worker can now populate stories and operational status without Slack.
          </p>
          <Link className="primary-button" href="/tracks/new">
            Create a track
          </Link>
        </div>
      </section>

      <SummaryFrame
        summary={{
          whatChanged: liveBoard?.items[0]?.topSummary?.whatChanged ?? "The product scaffold is live.",
          whyItMatters:
            liveBoard?.items[0]?.topSummary?.whyItMatters ??
            "Frontend, API, Postgres schema, worker scheduling, and in-app notifications are aligned.",
          whatToWatch:
            liveBoard?.items[0]?.topSummary?.whatToWatch ??
            "Watch the source health panel and recent notifications as official feeds start landing.",
        }}
      />

      <section className="dashboard-grid">
        <SourceHealthPanel items={sourceHealth?.items ?? []} />
        <NotificationList items={notifications?.items ?? []} />
      </section>

      {!liveBoard || liveBoard.items.length === 0 ? (
        <EmptyState
          title="No promoted tracks yet"
          body="The dashboard is healthy, but the database does not contain live board rows yet. Seed data or source ingestion will make this board populate automatically."
        />
      ) : (
        <section className="card-grid">
          {liveBoard.items.map((item) => (
            <TrackCard key={item.trackId} item={item} />
          ))}
        </section>
      )}
    </div>
  );
}
