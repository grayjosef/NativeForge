import { str } from "./workbenchFormat";

export interface AsyncRecord {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
}

interface CoverageGapsCardProps {
  intel: AsyncRecord;
  recs: AsyncRecord;
}

export function CoverageGapsCard({ intel, recs }: CoverageGapsCardProps) {
  const loading = intel.loading || recs.loading;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-coverage-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-coverage-heading" className="nf-card-title">
          Coverage gaps + source recommendations
        </h2>
      </div>
      <p className="nf-card-one-liner">
        NativeForge prioritizes Native-specific and Native-relevant grants, and
        also surfaces broader opportunities where Native governments and
        Native-serving organizations may be eligible — Native-first, not
        Native-only.
      </p>
      {loading ? (
        <p className="nf-muted">Loading coverage intelligence…</p>
      ) : (
        <>
          {intel.error ? (
            <div className="nf-alert nf-alert--error" role="alert">
              Coverage intelligence: {intel.error}
            </div>
          ) : null}
          {recs.error ? (
            <div className="nf-alert nf-alert--error" role="alert">
              Source recommendations: {recs.error}
            </div>
          ) : null}
          <CoverageBody intel={intel.data} recs={recs.data} />
        </>
      )}
    </section>
  );
}

function topGaps(intel: Record<string, unknown> | null, limit = 8) {
  const g = intel?.coverage_gaps ?? intel?.gaps;
  if (!Array.isArray(g)) {
    return [];
  }
  return g.slice(0, limit) as Record<string, unknown>[];
}

function topRecs(recblock: Record<string, unknown> | null, limit = 8) {
  const r = recblock?.source_recommendations;
  if (!Array.isArray(r)) {
    return [];
  }
  return r.slice(0, limit) as Record<string, unknown>[];
}

function CoverageBody({
  intel,
  recs,
}: {
  intel: Record<string, unknown> | null;
  recs: Record<string, unknown> | null;
}) {
  const gaps = intel ? topGaps(intel) : [];
  const recommendations = recs ? topRecs(recs) : [];

  return (
    <>
      {intel ? (
        <div className="nf-wb-score-grid">
          <div>
            <p className="nf-muted">Coverage score</p>
            <p className="nf-wb-score">{str(intel.coverage_score) || "—"}</p>
          </div>
          <div>
            <p className="nf-muted">Freshness</p>
            <p className="nf-wb-score">{str(intel.freshness_score) || "—"}</p>
          </div>
          <div>
            <p className="nf-muted">Reliability</p>
            <p className="nf-wb-score">{str(intel.reliability_score) || "—"}</p>
          </div>
          <div>
            <p className="nf-muted">Yield</p>
            <p className="nf-wb-score">{str(intel.yield_score) || "—"}</p>
          </div>
        </div>
      ) : null}
      <h3 className="nf-card-subtitle">Top gaps</h3>
      {!intel ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">
            No coverage gaps returned by the engine.
          </p>
        </div>
      ) : gaps.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">
            No coverage gaps returned by the engine.
          </p>
        </div>
      ) : (
        <ul className="nf-wb-bullet-list">
          {gaps.map((g, i) => (
            <li key={str(g.gap_id ?? g.title ?? i)}>
              <strong>{str(g.title ?? g.gap_type ?? "Gap")}</strong>
              {g.severity ? (
                <span className="nf-chip nf-wb-gap-sev">{str(g.severity)}</span>
              ) : null}
              <span className="nf-wb-gap-rationale">
                {str(g.rationale ?? g.summary ?? "")}
              </span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="nf-card-subtitle">Top source recommendations</h3>
      {!recs ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No recommendations available.</p>
        </div>
      ) : recommendations.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No recommendations available.</p>
        </div>
      ) : (
        <ul className="nf-wb-bullet-list">
          {recommendations.map((r, i) => (
            <li key={str(r.recommendation_id ?? r.title ?? i)}>
              <strong>{str(r.title ?? "Recommendation")}</strong>
              <span className="nf-wb-gap-rationale">{str(r.rationale)}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
