import { EpisodeDetail } from "@/lib/api";

import { StatusPill } from "./status-pill";

export function EpisodeTimeline({ episodes }: { episodes: EpisodeDetail[] }) {
  return (
    <section className="timeline">
      <div className="section-header">
        <div>
          <p className="eyebrow">Episode timeline</p>
          <h2>State-change history</h2>
        </div>
      </div>
      <ul>
        {episodes.map((episode) => (
          <li key={episode.episodeId} className="timeline__item">
            <div className="timeline__marker" />
            <div className="timeline__body">
              <div className="timeline__headline">
                <h3>{episode.headline}</h3>
                <StatusPill>{episode.episodeType}</StatusPill>
              </div>
              <p>{episode.summary.whatChanged ?? "No episode narrative available."}</p>
              <div className="timeline__meta">
                <span>{new Date(episode.createdAt).toLocaleString()}</span>
                <span>Confidence {episode.confidenceScore.toFixed(2)}</span>
                <span>Contradiction {episode.contradictionScore.toFixed(2)}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

