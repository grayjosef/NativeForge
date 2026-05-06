export interface FormPreviewCardProps {
  pursuitId: string;
  pkg: Record<string, unknown> | null;
  busy: boolean;
  error: string | null;
  statusChip: string;
  locked: boolean;
  onCreatePreview: () => void;
  onRefresh: () => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

function collectPreviewNotes(sf: unknown): string[] {
  if (!sf || typeof sf !== "object") {
    return [];
  }
  const fields = (sf as { fields?: Record<string, { value?: unknown }> }).fields;
  if (!fields || typeof fields !== "object") {
    return [];
  }
  const notes: string[] = [];
  for (const [k, cell] of Object.entries(fields)) {
    if (!cell || typeof cell !== "object") {
      continue;
    }
    const val = (cell as { value?: unknown }).value;
    if (val === null || val === undefined || val === "") {
      notes.push(`Field ${k} is empty in preview`);
    }
  }
  return notes.slice(0, 8);
}

export function FormPreviewCard({
  pursuitId,
  pkg,
  busy,
  error,
  statusChip,
  locked,
  onCreatePreview,
  onRefresh,
}: FormPreviewCardProps) {
  const preview = pkg?.sf424_preview as Record<string, unknown> | undefined;
  const notes = collectPreviewNotes(preview);

  return (
    <section
      className={`nf-card nf-card-pad ${locked ? "nf-card--locked" : ""}`}
      aria-labelledby="nf-forms-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-forms-heading" className="nf-card-title">
          SF-424 preview
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">Staff review snapshot — not a filing.</p>
      {locked ? (
        <p className="nf-locked-note">Open a pursuit first.</p>
      ) : (
        <p className="nf-callout nf-callout--warn nf-callout--inline">
          Preview only. Not submitted.
        </p>
      )}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={!pursuitId || busy || locked}
          onClick={() => void onCreatePreview()}
        >
          Create SF-424 preview package
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={!pursuitId || busy || locked}
          onClick={() => void onRefresh()}
        >
          Refresh package
        </button>
      </div>
      {!locked && pkg ? (
        <div className="nf-preview-status">
          <p>
            <strong>Engine:</strong> {str(pkg.package_engine) || "—"}
          </p>
          {notes.length > 0 ? (
            <div className="nf-preview-gaps">
              <strong>Fields to review</strong>
              <ul>
                {notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="nf-muted">No empty fields flagged.</p>
          )}
        </div>
      ) : null}
      {!locked && !pkg ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">Create a preview after your pursuit is open.</p>
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
