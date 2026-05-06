export interface OrgReadinessCardProps {
  busy: boolean;
  profileFields: {
    legalName?: string;
    entityType?: string;
    city?: string;
    state?: string;
    grantsContact?: string;
  } | null;
  error: string | null;
  statusChip: string;
  onCreateRefresh: () => void;
}

export function OrgReadinessCard({
  busy,
  profileFields,
  error,
  statusChip,
  onCreateRefresh,
}: OrgReadinessCardProps) {
  const hasDetails = !!profileFields;

  return (
    <section className="nf-card nf-card-pad" aria-labelledby="nf-org-heading">
      <div className="nf-card-head-row">
        <h2 id="nf-org-heading" className="nf-card-title">
          Tribal profile
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">
        Create the profile used for previews, review artifacts, and exports.
      </p>
      {hasDetails ? (
        <dl className="nf-dl nf-dl-tight">
          <div>
            <dt>Legal name</dt>
            <dd>{profileFields!.legalName ?? "—"}</dd>
          </div>
          <div>
            <dt>Entity type</dt>
            <dd>{profileFields!.entityType ?? "—"}</dd>
          </div>
          <div>
            <dt>Location</dt>
            <dd>
              {[profileFields!.city, profileFields!.state]
                .filter(Boolean)
                .join(", ") || "—"}
            </dd>
          </div>
          <div>
            <dt>Grants contact</dt>
            <dd>{profileFields!.grantsContact ?? "—"}</dd>
          </div>
        </dl>
      ) : (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">Start here on first visit.</p>
          <p className="nf-empty-hint">
            Nothing is wrong — we just need your tribal profile on file.
          </p>
        </div>
      )}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={busy}
          onClick={() => void onCreateRefresh()}
        >
          {busy ? "Saving…" : "Create tribal profile"}
        </button>
      </div>
      {error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
