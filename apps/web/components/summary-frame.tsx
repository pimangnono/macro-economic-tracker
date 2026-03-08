import { SummaryFrame as SummaryFrameType } from "@/lib/api";

export function SummaryFrame({ summary }: { summary?: SummaryFrameType | null }) {
  return (
    <section className="summary-frame">
      <article>
        <span>What changed</span>
        <p>{summary?.whatChanged ?? "No meaningful state change has been written yet."}</p>
      </article>
      <article>
        <span>Why it matters</span>
        <p>{summary?.whyItMatters ?? "This track is live, but impact framing is still pending."}</p>
      </article>
      <article>
        <span>What to watch</span>
        <p>{summary?.whatToWatch ?? "Waiting for a clearer next catalyst or follow-through signal."}</p>
      </article>
    </section>
  );
}

