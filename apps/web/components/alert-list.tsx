"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { markNotificationRead, muteNotification, type RecentNotificationItem } from "@/lib/api";

export function AlertList({ items }: { items: RecentNotificationItem[] }) {
  const { data: session } = useSession();
  const router = useRouter();

  async function handleRead(notificationId: string) {
    if (!session?.accessToken) {
      return;
    }
    await markNotificationRead(session.accessToken, notificationId);
    router.refresh();
  }

  async function handleMute(notificationId: string) {
    if (!session?.accessToken) {
      return;
    }
    await muteNotification(session.accessToken, notificationId);
    router.refresh();
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Alert center</p>
          <h2>State-change notifications</h2>
        </div>
      </div>
      <ul className="notification-list">
        {items.length === 0 ? <li>No alerts yet.</li> : null}
        {items.map((item) => (
          <li key={item.id} className="alert-item">
            <div>
              <strong>{item.title}</strong>
              <p>{item.bodyText ?? "No body text"}</p>
            </div>
            <div className="alert-actions">
              {item.trackId ? <Link href={`/tracks/${item.trackId}`}>Track</Link> : null}
              {item.storyId ? <Link href={`/stories/${item.storyId}`}>Story</Link> : null}
              <button className="ghost-button" type="button" onClick={() => handleRead(item.id)}>
                Mark read
              </button>
              <button className="ghost-button" type="button" onClick={() => handleMute(item.id)}>
                Mute track
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
