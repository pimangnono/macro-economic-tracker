import { SourceHealthItem } from "@/lib/api";

import { StatusPill } from "./status-pill";

function toneFromStatus(status: string): "neutral" | "positive" | "warning" | "critical" {
  if (status === "healthy") {
    return "positive";
  }
  if (status === "running" || status === "stale") {
    return "warning";
  }
  if (status === "failing") {
    return "critical";
  }
  return "neutral";
}

export function SourceHealthPanel({ items }: { items: SourceHealthItem[] }) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Source health</p>
          <h2>Public feed ingestion</h2>
        </div>
      </div>

      <ul className="source-health-list">
        {items.map((item) => (
          <li key={item.sourceKey}>
            <div className="source-health-list__row">
              <div>
                <strong>{item.displayName}</strong>
                <p>
                  {item.documentType.replaceAll("_", " ")} via {item.feedKind.toUpperCase()}
                </p>
              </div>
              <StatusPill tone={toneFromStatus(item.status)}>{item.status}</StatusPill>
            </div>
            <div className="source-health-list__meta">
              <span>
                {item.lastSuccessAt
                  ? `Last success ${new Date(item.lastSuccessAt).toLocaleString()}`
                  : "No successful pull yet"}
              </span>
              <span>
                {item.discoveredCount} discovered / {item.insertedCount} inserted
              </span>
              {item.errorText ? <span>{item.errorText}</span> : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
