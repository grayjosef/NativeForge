export interface ScoreCardProps {
  sparkSelected: boolean;
  score: Record<string, unknown> | null;
  busy: boolean;
  error: string | null;
  statusChip: string;
  locked: boolean;
  onScore: () => void;
  onRefreshLatest: () => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

function num(v: unknown): string {
  if (typeof v === "number" && !Number.isNaN(v)) {
    return v.toFixed(1);
  }
  return "—";
}

export function ScoreCard({
  sparkSelected,
  score,
  busy,
  error,
  statusChip,
  locked,
  onScore,
  onRefreshLatest,
}: ScoreCardProps) {
  const gentleNotice =
    error &&
    /no readiness score|no score|not loaded yet/i.test(error)
      ? error
      : null;
  const hardError = error && !gentleNotice ? error : null;

  return (
    <section
      className={`nf-card nf-card-pad ${locked ? "nf-card--locked" : ""}`}
      aria-labelledby="nf-score-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-score-heading" className="nf-card-title">
          Pursuit readiness
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">
        Advisory score — not a guarantee of funding.
      </p>
      {locked ? (
        <p className="nf-locked-note">Complete NOFO requirements first.</p>
      ) : null}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={!sparkSelected || busy || locked}
          onClick={() => void onScore()}
        >
          Score this opportunity
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={!sparkSelected || busy || locked}
          onClick={() => void onRefreshLatest()}
        >
          Load latest score
        </button>
      </div>
      {score ? (
        <div className="nf-score-panel">
          <div className="nf-score-big">
            <span className="nf-score-number">{num(score.composite)}</span>
            <span className="nf-score-caption">Composite (advisory)</span>
          </div>
          <p className="nf-score-rec">
            <strong>Recommendation:</strong> {str(score.recommendation) || "—"}
          </p>
          {score.disqualified ? (
            <div className="nf-alert nf-alert--warn" role="status">
              Flagged for staff review:{" "}
              {str(score.disqualification_reason) || "See explanation."}
            </div>
          ) : null}
          {score.explanation_text ? (
            <p className="nf-muted">{str(score.explanation_text)}</p>
          ) : null}
        </div>
      ) : (
        !locked && (
          <div className="nf-empty nf-empty--calm">
            <p className="nf-empty-title">Score when your checklist is ready.</p>
          </div>
        )
      )}
      {gentleNotice ? (
        <p className="nf-callout nf-callout--muted">{gentleNotice}</p>
      ) : null}
      {hardError ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {hardError}
        </div>
      ) : null}
    </section>
  );
}
