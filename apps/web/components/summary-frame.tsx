import { SummaryFrame as SummaryFrameType } from "@/lib/api";

function SupportIndicator({ status }: { status?: string | null }) {
  if (!status || status === "unknown") return null;
  return <span className={`support-indicator support-${status}`}>{status}</span>;
}

export function SummaryFrame({
  summary,
  supportStatus,
}: {
  summary?: SummaryFrameType | null;
  supportStatus?: { whatChanged?: string; whyItMatters?: string; whatToWatch?: string } | null;
}) {
  return (
    <section className="summary-frame">
      <article>
        <span>
          What changed
          <SupportIndicator status={supportStatus?.whatChanged} />
        </span>
        <p>{summary?.whatChanged ?? "No meaningful state change has been written yet."}</p>
      </article>
      <article>
        <span>
          Why it matters
          <SupportIndicator status={supportStatus?.whyItMatters} />
        </span>
        <p>{summary?.whyItMatters ?? "This track is live, but impact framing is still pending."}</p>
      </article>
      <article>
        <span>
          What to watch
          <SupportIndicator status={supportStatus?.whatToWatch} />
        </span>
        <p>{summary?.whatToWatch ?? "Waiting for a clearer next catalyst or follow-through signal."}</p>
      </article>
    </section>
  );
}

