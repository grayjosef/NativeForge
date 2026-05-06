export type ProgressStepState =
  | "not_started"
  | "needs_setup"
  | "locked"
  | "ready"
  | "in_review"
  | "complete"
  | "needs_attention"
  | "error";

export interface ProgressStep {
  id: string;
  label: string;
  shortLabel: string;
  state: ProgressStepState;
  /** Short status line under the step label */
  lineSummary: string;
}

/** User-facing spine labels — avoid “Error” unless something actually failed */
const STATE_tone: Record<
  ProgressStepState,
  "neutral" | "positive" | "warn" | "bad" | "muted"
> = {
  not_started: "muted",
  needs_setup: "neutral",
  locked: "muted",
  ready: "neutral",
  in_review: "neutral",
  complete: "positive",
  needs_attention: "warn",
  error: "bad",
};

export function ProgressStrip({ steps }: { steps: ProgressStep[] }) {
  return (
    <nav className="nf-spine" aria-label="Pursuit workflow">
      <div className="nf-spine-rail">
        <div className="nf-spine-line" aria-hidden="true" />
        <ol className="nf-spine-steps">
          {steps.map((s) => (
            <li key={s.id} className="nf-spine-item">
              <div
                className={`nf-spine-segment nf-spine-segment--${s.state} nf-spine-tone--${STATE_tone[s.state]}`}
              >
                <span className="nf-spine-dot" aria-hidden="true" />
                <span className="nf-spine-label">{s.shortLabel}</span>
                <span className="nf-spine-summary">{s.lineSummary}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}
