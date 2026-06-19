import type { Stage12StepId } from "../../stage12GuidedFlowTypes";

interface Stage12GuidedStepperProps {
  current: Stage12StepId;
  onSelect: (step: Stage12StepId) => void;
  steps: { id: Stage12StepId; label: string }[];
}

export function Stage12GuidedStepper({
  current,
  onSelect,
  steps,
}: Stage12GuidedStepperProps) {
  return (
    <nav className="nf-stage12-stepper" aria-label="Stage 12 guided demo steps">
      <ol className="nf-stage12-stepper-list">
        {steps.map((s, i) => (
          <li key={s.id}>
            <button
              type="button"
              className={`nf-stage12-step${current === s.id ? " nf-stage12-step--active" : ""}`}
              aria-current={current === s.id ? "step" : undefined}
              onClick={() => onSelect(s.id)}
            >
              <span className="nf-stage12-step-num">{i + 1}</span>
              <span className="nf-stage12-step-label">{s.label}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
