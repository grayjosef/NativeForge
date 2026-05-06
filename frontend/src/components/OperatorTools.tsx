import type { RunnerLogStep } from "../m0LiveDemoRunner";

export interface OperatorToolsProps {
  open: boolean;
  onToggle: () => void;
  runnerBusy: boolean;
  runnerSteps: RunnerLogStep[];
  orgOk: boolean;
  onRunSequence: () => void;
}

export function OperatorTools({
  open,
  onToggle,
  runnerBusy,
  runnerSteps,
  orgOk,
  onRunSequence,
}: OperatorToolsProps) {
  return (
    <aside className={`nf-operator ${open ? "nf-operator--open" : ""}`}>
      <button
        type="button"
        className="nf-operator-toggle"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="nf-operator-toggle-label">Advanced · Operator</span>
        <span className="nf-operator-chevron">{open ? "▼" : "▶"}</span>
      </button>
      {open ? (
        <div className="nf-operator-body">
          <p className="nf-muted nf-operator-intro">
            Internal demo tools — not part of the grant workflow.
          </p>
          <div className="nf-operator-actions">
            <button
              type="button"
              className="nf-btn nf-btn-secondary"
              disabled={!orgOk || runnerBusy}
              onClick={() => void onRunSequence()}
            >
              {runnerBusy ? "Running…" : "Run demo workflow"}
            </button>
          </div>
          {runnerSteps.length > 0 ? (
            <div className="nf-runner-scroll" aria-live="polite">
              <table className="nf-runner-table">
                <thead>
                  <tr>
                    <th scope="col">Step</th>
                    <th scope="col">API path</th>
                    <th scope="col">Status</th>
                    <th scope="col">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {runnerSteps.map((row) => (
                    <tr
                      key={row.key}
                      className={`nf-runner-row nf-runner-row--${row.status}`}
                    >
                      <td data-label="Step">{row.name}</td>
                      <td data-label="Path">
                        <code className="nf-code">{row.pathLine}</code>
                      </td>
                      <td data-label="Status">{row.status}</td>
                      <td data-label="Detail">
                        {row.error ? (
                          <span className="nf-runner-err">{row.error}</span>
                        ) : (
                          (row.summary ?? "—")
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="nf-operator-link-rows">
            <a
              className="nf-link-row"
              href="/docs"
              target="_blank"
              rel="noreferrer"
            >
              API documentation
            </a>
            <span className="nf-link-row nf-link-row--muted">
              Operator checklist — see{" "}
              <code className="nf-code-inline">docs/m0-demo-operator-checklist.md</code>{" "}
              in the repo
            </span>
          </div>
          <div className="nf-operator-cli">
            <p className="nf-muted nf-operator-cli-label">Local commands</p>
            <pre className="nf-cli-block nf-cli-block--compact">
              {`nf-up
nf-status
nf-reset
nf-down`}
            </pre>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
