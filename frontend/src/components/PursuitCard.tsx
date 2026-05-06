export interface PursuitCardProps {
  sparkSelected: boolean;
  pursuitId: string;
  pursuit: Record<string, unknown> | null;
  busy: boolean;
  error: string | null;
  statusChip: string;
  locked: boolean;
  onOpenPursuit: () => void;
  onRefreshDetail: () => void;
  onToggleTask: (taskId: string, currentStatus: string) => void;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function PursuitCard({
  sparkSelected,
  pursuitId,
  pursuit,
  busy,
  error,
  statusChip,
  locked,
  onOpenPursuit,
  onRefreshDetail,
  onToggleTask,
}: PursuitCardProps) {
  const tasks = (pursuit?.tasks as Record<string, unknown>[]) ?? [];
  const events =
    (pursuit?.calendar_events as Record<string, unknown>[]) ?? [];

  return (
    <section
      className={`nf-card nf-card-pad ${locked ? "nf-card--locked" : ""}`}
      aria-labelledby="nf-pursuit-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-pursuit-heading" className="nf-card-title">
          Pursuit
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>
      <p className="nf-card-one-liner">
        Tasks and milestones for application prep.
      </p>
      {locked ? (
        <p className="nf-locked-note">Run a readiness score first.</p>
      ) : null}
      <div className="nf-card-actions">
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-block-sm"
          disabled={busy || locked || !sparkSelected}
          onClick={() => void onOpenPursuit()}
        >
          Open pursuit
        </button>
        <button
          type="button"
          className="nf-btn nf-btn-secondary nf-btn-block-sm"
          disabled={!pursuitId || busy || locked}
          onClick={() => void onRefreshDetail()}
        >
          Refresh pursuit
        </button>
      </div>
      {pursuitId ? (
        <details className="nf-details">
          <summary>Technical details</summary>
          <p className="nf-details-body">
            Reference <code className="nf-code">{pursuitId}</code>
          </p>
        </details>
      ) : null}

      {!locked ? (
        <>
          <h3 className="nf-card-subtitle">Tasks</h3>
          {tasks.length === 0 ? (
            <div className="nf-empty nf-empty--calm">
              <p className="nf-empty-hint">
                Tasks appear after you open a pursuit.
              </p>
            </div>
          ) : (
            <ul className="nf-task-list">
              {tasks.map((t) => {
                const id = str(t.id);
                const st = str(t.status);
                const done = st === "done";
                return (
                  <li key={id} className="nf-task-row">
                    <div className="nf-task-text">
                      <span className="nf-task-title">{str(t.title)}</span>
                      <span className="nf-task-status">
                        {st.replace("_", " ")}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="nf-btn nf-btn-outline nf-btn-touch-sm"
                      disabled={busy}
                      onClick={() => onToggleTask(id, st)}
                    >
                      {done ? "Mark active" : "Mark done"}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <h3 className="nf-card-subtitle">Calendar</h3>
          {events.length === 0 ? (
            <p className="nf-muted">No milestones yet.</p>
          ) : (
            <ul className="nf-cal-list">
              {events.map((e) => (
                <li key={str(e.id)} className="nf-cal-row">
                  <span className="nf-cal-kind">{str(e.kind)}</span>
                  <span className="nf-cal-title">{str(e.title)}</span>
                  <span className="nf-cal-when">{str(e.occurs_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
      {error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
