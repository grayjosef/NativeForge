export interface NofoRequirementsCardProps {
  sparkSelected: boolean;
  requirements: Record<string, unknown>[];
  busy: boolean;
  error: string | null;
  statusChip: string;
  locked: boolean;
  onExtract: () => void;
  onLoadRequirements: () => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function NofoRequirementsCard({
  sparkSelected,
  requirements,
  busy,
  error,
  statusChip,
  locked,
  onExtract,
  onLoadRequirements,
}: NofoRequirementsCardProps) {
  return (
    <section
      className={`nf-card nf-card-pad ${locked ? "nf-card--locked" : ""}`}
      aria-labelledby="nf-nofo-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-nofo-heading" className="nf-card-title">
          NOFO requirements
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">
        Checklist rows from your opportunity text (deterministic stub in M0).
      </p>
      {locked ? (
        <p className="nf-locked-note">Add an opportunity first.</p>
      ) : null}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={!sparkSelected || busy || locked}
          onClick={() => void onExtract()}
        >
          Extract NOFO requirements
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={!sparkSelected || busy || locked}
          onClick={() => void onLoadRequirements()}
        >
          Reload checklist
        </button>
      </div>
      {!locked && requirements.length > 0 ? (
        <p className="nf-meta-count">
          {requirements.length} item{requirements.length === 1 ? "" : "s"}
        </p>
      ) : null}
      {!locked && requirements.length > 0 ? (
        <ul className="nf-req-list">
          {requirements.map((r) => (
            <li key={str(r.id)} className="nf-req-item">
              <div className="nf-req-top">
                <span className="nf-req-title">
                  {str(r.label) || "Requirement"}
                </span>
                <span className="nf-req-meta">
                  <span className="nf-chip-sm">
                    {str(r.requirement_type) || "—"}
                  </span>
                  {r.required ? (
                    <span className="nf-chip-sm nf-chip-sm--accent">
                      Required
                    </span>
                  ) : null}
                </span>
              </div>
              {r.description ? (
                <p className="nf-req-desc">{str(r.description)}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {!locked && requirements.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">
            {sparkSelected
              ? "Extract to load your checklist."
              : "Waiting on an opportunity."}
          </p>
        </div>
      ) : null}
      {error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
