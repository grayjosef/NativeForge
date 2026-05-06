export interface TrustCenterCardProps {
  manifest: Record<string, unknown> | null;
  auditCount: number | null;
  reviewSummary: Record<string, unknown> | null;
  exportHint: string | null;
  busy: boolean;
  error: string | null;
  statusChip: string;
  onRefresh: () => void;
  onExportDownload: () => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function TrustCenterCard({
  manifest,
  auditCount,
  reviewSummary,
  exportHint,
  busy,
  error,
  statusChip,
  onRefresh,
  onExportDownload,
}: TrustCenterCardProps) {
  const sub =
    manifest?.submission_policy &&
    typeof manifest.submission_policy === "object"
      ? (manifest.submission_policy as Record<string, unknown>)
      : null;
  const autoSubmit = sub?.automatic_submission_enabled;
  const reviewGate =
    manifest?.review_gate_policy &&
    typeof manifest.review_gate_policy === "object"
      ? (manifest.review_gate_policy as Record<string, unknown>)
      : null;
  const reviewRequired =
    reviewGate?.generated_form_previews_are_non_final !== false;

  return (
    <section
      className="nf-rail-card nf-rail-card--trust"
      aria-labelledby="nf-trust-heading"
    >
      <div className="nf-trust-mark" aria-hidden="true" />
      <div className="nf-card-head-row">
        <h2 id="nf-trust-heading" className="nf-rail-card-title">
          Trust &amp; sovereignty
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-rail-card-lead nf-trust-lead-short">
        Data sovereignty is built in — exports belong to your organization.
      </p>

      <div className="nf-trust-tiles">
        <div className="nf-trust-tile">
          <span className="nf-trust-tile-label">Auto-submit</span>
          <strong className="nf-trust-tile-value">
            {autoSubmit === undefined
              ? "—"
              : autoSubmit
                ? "On"
                : "Off"}
          </strong>
        </div>
        <div className="nf-trust-tile">
          <span className="nf-trust-tile-label">Review</span>
          <strong className="nf-trust-tile-value">
            {reviewRequired ? "Required" : "—"}
          </strong>
        </div>
        <div className="nf-trust-tile">
          <span className="nf-trust-tile-label">Export</span>
          <strong className="nf-trust-tile-value">Available</strong>
        </div>
        <div className="nf-trust-tile">
          <span className="nf-trust-tile-label">Trust manifest</span>
          <strong className="nf-trust-tile-value">
            {str(manifest?.manifest_schema_version) || "—"}
          </strong>
        </div>
      </div>

      <div className="nf-rail-card-actions nf-rail-card-actions--stack">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-trust nf-btn-block-sm"
          disabled={busy}
          onClick={() => void onExportDownload()}
        >
          Export organization snapshot
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={busy}
          onClick={() => void onRefresh()}
        >
          Refresh Trust Center
        </button>
      </div>

      <dl className="nf-trust-meta">
        <div>
          <dt>Audit events (sample)</dt>
          <dd>{auditCount ?? "—"}</dd>
        </div>
        <div>
          <dt>Review artifacts</dt>
          <dd>
            {reviewSummary?.review_artifact_count != null
              ? str(reviewSummary.review_artifact_count)
              : "—"}
          </dd>
        </div>
      </dl>

      {exportHint ? (
        <p className="nf-callout nf-callout--success">{exportHint}</p>
      ) : null}

      {error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
