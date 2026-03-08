import Link from "next/link";

import { StoryPreview } from "@/lib/api";

import { StatusPill } from "./status-pill";

export function StoryTable({ stories }: { stories: StoryPreview[] }) {
  return (
    <div className="table-shell">
      <div className="table-shell__head">
        <span>Story</span>
        <span>State</span>
        <span>Priority</span>
        <span>Last change</span>
      </div>
      {stories.map((story) => (
        <div className="table-shell__row" key={story.storyId}>
          <div>
            <Link href={`/stories/${story.storyId}`}>{story.title}</Link>
            <p>{story.whatChanged ?? story.headline ?? "Awaiting episode summary."}</p>
          </div>
          <StatusPill>{story.storyState}</StatusPill>
          <span>{story.priorityScore.toFixed(2)}</span>
          <span>{story.episodeCreatedAt ? new Date(story.episodeCreatedAt).toLocaleString() : "n/a"}</span>
        </div>
      ))}
    </div>
  );
}

