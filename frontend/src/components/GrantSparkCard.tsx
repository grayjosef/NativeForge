export type SparkRow = Record<string, unknown>;

export interface GrantSparkCardProps {
  sparks: SparkRow[];
  selectedSparkId: string;
  onSelectSpark: (id: string) => void;
  detail: SparkRow | null;
  busy: boolean;
  error: string | null;
  statusChip: string;
  profileReady: boolean;
  onRefreshList: () => void;
  onCreateDemoSpark: () => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function GrantSparkCard({
  sparks,
  selectedSparkId,
  onSelectSpark,
  detail,
  busy,
  error,
  statusChip,
  profileReady,
  onRefreshList,
  onCreateDemoSpark,
}: GrantSparkCardProps) {
  const locked = !profileReady;
  const title =
    detail && str(detail.opportunity_title)
      ? str(detail.opportunity_title)
      : null;
  const program =
    [str(detail?.agency), str(detail?.program_name)].filter(Boolean).join(" · ") ||
    "—";
  const deadline = str(detail?.application_deadline) || "—";
  const stage = str(detail?.pipeline_stage) || "—";
  const tags = Array.isArray(detail?.eligibility_tags)
    ? (detail?.eligibility_tags as string[])
    : [];

  return (
    <section
      className={`nf-card nf-card-pad ${locked ? "nf-card--locked" : ""}`}
      aria-labelledby="nf-spark-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-spark-heading" className="nf-card-title">
          Grant Sparks
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">
        Start with a demo opportunity or select an existing Spark.
      </p>
      {locked ? (
        <p className="nf-locked-note">
          Complete your tribal profile first — then you can add opportunities.
        </p>
      ) : null}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={busy || locked}
          onClick={() => void onCreateDemoSpark()}
        >
          Add demo opportunity
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={busy || locked}
          onClick={() => void onRefreshList()}
        >
          Refresh list
        </button>
      </div>
      {!locked && sparks.length > 0 ? (
        <div className="nf-field">
          <label htmlFor="spark-select">Active opportunity</label>
          <select
            id="spark-select"
            className="nf-select"
            value={selectedSparkId}
            onChange={(e) => onSelectSpark(e.target.value)}
          >
            <option value="">None selected</option>
            {sparks.map((s) => {
              const id = str(s.id);
              const ot =
                str(s.opportunity_title) || `Opportunity ${id.slice(0, 8)}`;
              return (
                <option key={id} value={id}>
                  {ot}
                </option>
              );
            })}
          </select>
        </div>
      ) : null}
      {!locked && sparks.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">Ready when you are.</p>
          <p className="nf-empty-hint">
            Add a demo opportunity to continue the guided workflow.
          </p>
        </div>
      ) : null}
      {!locked && !detail && sparks.length > 0 && !selectedSparkId ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No active opportunity selected.</p>
          <p className="nf-empty-hint">
            Pick one from the list, or add a new demo opportunity.
          </p>
        </div>
      ) : null}
      {detail ? (
        <div className="nf-spark-detail">
          {title ? <h3 className="nf-card-subtitle">{title}</h3> : null}
          <dl className="nf-dl nf-dl-tight">
            <div>
              <dt>Program</dt>
              <dd>{program}</dd>
            </div>
            <div>
              <dt>Application deadline</dt>
              <dd>{deadline}</dd>
            </div>
            <div>
              <dt>Stage</dt>
              <dd>{stage}</dd>
            </div>
          </dl>
          {tags.length > 0 ? (
            <ul className="nf-tag-row">
              {tags.map((t) => (
                <li key={t} className="nf-tag">
                  {t}
                </li>
              ))}
            </ul>
          ) : null}
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
