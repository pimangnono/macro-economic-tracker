import Link from "next/link";

import { RecentNotificationItem } from "@/lib/api";

import { StatusPill } from "./status-pill";

function notificationHref(item: RecentNotificationItem): string | null {
  if (item.storyId) {
    return `/stories/${item.storyId}`;
  }
  if (item.trackId) {
    return `/tracks/${item.trackId}`;
  }
  return null;
}

export function NotificationList({ items }: { items: RecentNotificationItem[] }) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">In-app alerts</p>
          <h2>Recent notifications</h2>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="panel-copy">
          No in-app notifications yet. New story promotions and official confirmations will
          appear here once the worker starts pulling sources.
        </p>
      ) : (
        <ul className="notification-list">
          {items.map((item) => {
            const href = notificationHref(item);
            return (
              <li key={item.id}>
                <div className="notification-list__row">
                  <div>
                    {href ? <Link href={href}>{item.title}</Link> : <strong>{item.title}</strong>}
                    <p>{item.bodyText ?? "Notification body not available."}</p>
                  </div>
                  <StatusPill tone="positive">{item.reason.replaceAll("_", " ")}</StatusPill>
                </div>
                <div className="notification-list__meta">
                  <span>{new Date(item.createdAt).toLocaleString()}</span>
                  {item.trackName ? <span>{item.trackName}</span> : null}
                  <span>{item.channel}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
