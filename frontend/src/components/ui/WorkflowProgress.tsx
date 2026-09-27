import type { ProgressStep, ProgressStepState } from "../ProgressStrip";

/**
 * The pursuit lifecycle, drawn as a progression rather than a row of boxes.
 *
 * ## What this replaces
 *
 * Seven equal-weight bordered segments, each with a dot, a label and a status
 * line, laid out across the top of the workspace. Everything was the same
 * size, so nothing was ranked: the step you are on looked exactly like the
 * step you finished an hour ago and the step you cannot reach yet. It read as
 * a build dashboard, which is what it was.
 *
 * ## The lifecycle is the repository's, not a new one
 *
 * `workspaceProgress.buildProgressSteps` already defines the canonical
 * sequence - profile, opportunity, requirements, score, pursuit, forms, trust
 * - and every state transition in it is derived from API responses. Inventing
 * a second lifecycle for presentation would have created two answers to
 * "where am I", so this component takes the existing `ProgressStep[]`
 * unchanged and only decides how to show it.
 *
 * ## Why the current step is found rather than passed
 *
 * The caller would have to re-derive it, and a presentation layer deriving
 * progress independently is how a spine ends up disagreeing with the cards
 * beneath it. "Current" is the first step that is not complete, which is the
 * same rule the workflow itself follows.
 */

const TONE: Record<ProgressStepState, "done" | "active" | "todo" | "warn" | "bad"> = {
  not_started: "todo",
  needs_setup: "todo",
  locked: "todo",
  ready: "todo",
  in_review: "active",
  complete: "done",
  needs_attention: "warn",
  error: "bad",
};

/** Spoken status, so the state survives greyscale and colour blindness. */
const TONE_WORD: Record<string, string> = {
  done: "Complete",
  active: "In progress",
  todo: "Not started",
  warn: "Needs attention",
  bad: "Problem",
};

export interface WorkflowProgressProps {
  steps: ProgressStep[];
  /** Heading above the track. Omitted when the track sits inside a section. */
  title?: string;
}

export function WorkflowProgress({ steps, title }: WorkflowProgressProps) {
  const firstIncomplete = steps.findIndex((s) => s.state !== "complete");
  const currentIndex = firstIncomplete === -1 ? steps.length - 1 : firstIncomplete;
  const completed = steps.filter((s) => s.state === "complete").length;

  return (
    <section className="nf-flow" aria-label={title ?? "Pursuit workflow"}>
      <div className="nf-flow-head">
        <p className="nf-flow-title">{title ?? "Pursuit workflow"}</p>
        <p className="nf-flow-count">
          <strong>{completed}</strong> of {steps.length} complete
        </p>
      </div>

      <ol className="nf-flow-track">
        {steps.map((s, index) => {
          const tone = TONE[s.state];
          const isCurrent = index === currentIndex && tone !== "done";
          return (
            <li
              key={s.id}
              className="nf-flow-step"
              data-tone={tone}
              data-current={isCurrent}
              aria-current={isCurrent ? "step" : undefined}
            >
              {/* The connector belongs to the step that follows it, so the
                  track ends cleanly instead of trailing a line into nothing. */}
              {index > 0 ? <span className="nf-flow-link" aria-hidden="true" /> : null}

              <span className="nf-flow-marker" aria-hidden="true">
                {tone === "done" ? "✓" : tone === "bad" ? "!" : index + 1}
              </span>

              <span className="nf-flow-text">
                <span className="nf-flow-label">{s.shortLabel}</span>
                <span className="nf-flow-summary">{s.lineSummary}</span>
              </span>

              <span className="nf-visually-hidden">
                {s.label}: {TONE_WORD[tone]}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
