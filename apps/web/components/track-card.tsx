import Link from "next/link";

import { LiveBoardTrackItem } from "@/lib/api";

import { StatusPill } from "./status-pill";

function toneFromScore(score: number): "neutral" | "positive" | "warning" | "critical" {
  if (score >= 0.8) {
    return "critical";
  }
  if (score >= 0.55) {
    return "warning";
  }
  if (score >= 0.35) {
    return "positive";
  }
  return "neutral";
}

export function TrackCard({ item }: { item: LiveBoardTrackItem }) {
  const leadStory = item.stories[0];

  return (
    <article className="track-card">
      <div className="track-card__header">
        <div>
          <p className="eyebrow">{item.mode.replaceAll("_", " ")}</p>
          <h2>{item.trackName}</h2>
        </div>
        <StatusPill tone={toneFromScore(leadStory?.priorityScore ?? 0)}>
          {leadStory?.storyState ?? "draft"}
        </StatusPill>
      </div>

      <div className="track-card__summary">
        <p>{item.topSummary?.whatChanged ?? "No story has been promoted into the live board yet."}</p>
      </div>

      <ul className="story-list">
        {item.stories.slice(0, 3).map((story) => (
          <li key={story.storyId} className="story-list__item">
            <div>
              <Link href={`/stories/${story.storyId}`}>{story.title}</Link>
              <p>{story.whyItMatters ?? story.headline ?? "Awaiting narrative enrichment."}</p>
            </div>
            <div className="story-list__metrics">
              <span>Heat {story.hotnessScore.toFixed(2)}</span>
              <span>Conf {story.confidenceScore.toFixed(2)}</span>
            </div>
          </li>
        ))}
      </ul>

      <div className="track-card__footer">
        <span>{item.storyCount} promoted stories</span>
        <Link href={`/tracks/${item.trackId}`}>Open track</Link>
      </div>
    </article>
  );
}

