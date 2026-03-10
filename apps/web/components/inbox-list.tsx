import Link from "next/link";

import type { InboxItem } from "@/lib/api";

import { StatusPill } from "./status-pill";

export function InboxList({ items }: { items: InboxItem[] }) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Inbox</p>
          <h2>Episode-first feed</h2>
        </div>
      </div>
      {items.length === 0 ? (
        <p className="panel-copy">No unread state changes yet.</p>
      ) : (
        <ul className="inbox-list">
          {items.map((item) => (
            <li key={item.id} className="inbox-item">
              <div className="inbox-item__header">
                <div>
                  <p className="eyebrow">{item.mode?.replaceAll("_", " ") ?? "track"}</p>
                  <h3>{item.trackName ?? item.storyTitle ?? "Update"}</h3>
                </div>
                <StatusPill>{item.state ?? item.reason}</StatusPill>
              </div>
              <p>{item.whatChanged ?? item.episodeHeadline ?? item.storyTitle ?? "State change"}</p>
              <div className="inbox-item__meta">
                <span>Priority {item.priorityScore.toFixed(2)}</span>
                <span>Conf {item.confidenceScore.toFixed(2)}</span>
                <span>Contr {item.contradictionScore.toFixed(2)}</span>
              </div>
              <div className="track-card__footer">
                {item.trackId ? <Link href={`/tracks/${item.trackId}`}>Open track</Link> : null}
                {item.storyId ? <Link href={`/stories/${item.storyId}`}>Verify story</Link> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
