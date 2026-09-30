import { useEffect, useState } from "react";
import {
  getDemoWorkspaceSummary,
  type DemoWorkspaceSummary,
} from "../demoWorkspaceApiClient";
import { interpretError } from "../friendlyError";

type Props = {
  baseUrl: string;
  displayName: string | null;
  onUpgrade: () => void;
};

export function DemoWorkspacePage({ baseUrl, displayName, onUpgrade }: Props) {
  const [summary, setSummary] = useState<DemoWorkspaceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openHelp, setOpenHelp] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await getDemoWorkspaceSummary(baseUrl);
        if (!cancelled) setSummary(data);
      } catch (e) {
        if (!cancelled) setError(interpretError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  if (error) {
    return (
      <section className="nf-panel">
        <h2>Demo workspace unavailable</h2>
        <p>{error}</p>
      </section>
    );
  }

  if (!summary) {
    return (
      <section className="nf-panel" role="status">
        <p>Loading NativeForge Demo Workspace…</p>
      </section>
    );
  }

  const opportunities = summary.find.opportunities as Array<Record<string, unknown>>;

  return (
    <div className="nf-demo-workspace" data-testid="demo-workspace">
      <header className="nf-panel nf-demo-workspace-hero">
        <p className="nf-env nf-demo-workspace-badge">{summary.environment_label}</p>
        <h1>{summary.title}</h1>
        <p className="nf-lead">{summary.tagline}</p>
        <p>{summary.introduction}</p>
        {displayName ? (
          <p className="nf-muted">
            Signed in as {displayName}. This workspace uses demonstration records only.
          </p>
        ) : null}
        <button type="button" className="nf-btn nf-btn-primary" onClick={onUpgrade}>
          {summary.upgrade.cta_label}
        </button>
        <p className="nf-muted nf-demo-upgrade-note">{summary.upgrade.summary}</p>
      </header>

      <section className="nf-panel" aria-labelledby="demo-find-heading">
        <h2 id="demo-find-heading">FIND — {summary.find.headline}</h2>
        <p className="nf-muted">
          Illustrative opportunities only. Not active funding announcements.
        </p>
        <ul className="nf-list">
          {opportunities.slice(0, 4).map((row) => (
            <li key={String(row.canonical_id ?? row.recommendation_id)}>
              <strong>{String(row.title ?? "Opportunity")}</strong>
              <span className="nf-muted"> — {String(row.funder_name ?? "")}</span>
              {row.deadline ? (
                <span className="nf-muted"> · Deadline {String(row.deadline)}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="nf-panel" aria-labelledby="demo-pursue-heading">
        <h2 id="demo-pursue-heading">PURSUE — {summary.pursue.headline}</h2>
        <p className="nf-muted">
          Example pursuit workflow with requirements, tasks, and deadlines.
        </p>
        <pre className="nf-code-block">{JSON.stringify(summary.pursue.pursuit, null, 2)}</pre>
      </section>

      <section className="nf-panel" aria-labelledby="demo-govern-heading">
        <h2 id="demo-govern-heading">GOVERN — {summary.govern.headline}</h2>
        <p className="nf-muted">Accountability, provenance, and review concepts.</p>
      </section>

      <section className="nf-panel" aria-labelledby="demo-learn-heading">
        <h2 id="demo-learn-heading">Learn as you explore</h2>
        <ul className="nf-list">
          {summary.education.map((card) => (
            <li key={card.id}>
              <button
                type="button"
                className="nf-btn nf-btn-ghost"
                aria-expanded={openHelp === card.id}
                onClick={() => setOpenHelp(openHelp === card.id ? null : card.id)}
              >
                {card.title}
              </button>
              {openHelp === card.id ? <p>{card.body}</p> : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
