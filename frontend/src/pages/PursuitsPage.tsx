import { EmptyState, StateView } from "../components/StateView";
import type { CustomerState } from "../customerState";
import {
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
} from "../components/ui/primitives";
import { deadlineTone, formatDeadline } from "../lib/dates";
import { humanDisqualification } from "../lib/entityTypes";
import { PursuitCommandCenter, type CommandCenter } from "../components/PursuitCommandCenter";

/**
 * The pursuit workspace: one application, and what it is waiting on.
 *
 * ## One next action, at the top
 *
 * A pursuit has tasks, a deadline, requirements, a readiness score and a form
 * package, and showing all five with equal weight leaves the customer to work
 * out which to do first. The first incomplete task is stated as *the* next
 * action; everything else is reference.
 *
 * ## Readiness is advisory and labelled as such
 *
 * The score is a heuristic over an extracted checklist. Presenting it as a
 * probability of award - which is what an unlabelled number out of a hundred
 * reads as - would be a claim nothing in the engine supports.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface PursuitsPageProps {
  pursuit: Record<string, unknown> | null;
  opportunityTitle: string | null;
  score: Record<string, unknown> | null;
  formPackage: Record<string, unknown> | null;
  busy: boolean;
  error: CustomerState | null;
  canOpen: boolean;
  /** Days until the opportunity closes, or null when it states no deadline. */
  deadlineDays: number | null;
  onOpenPursuit: () => void;
  onToggleTask: (taskId: string, currentStatus: string) => void;
  onRefresh: () => void;
  onCreateFormPackage: () => void;
  onGoToOpportunities: () => void;
  commandCenter: CommandCenter | null;
  onGoTo: (view: string) => void;
  onRecordInteraction: (body: {
    interaction_type: string;
    subject?: string;
    notes?: string;
    owner_label?: string;
    follow_up_at?: string;
    contact_id?: string;
    status?: string;
  }) => Promise<void>;
}

export function PursuitsPage(props: PursuitsPageProps) {
  const {
    pursuit,
    opportunityTitle,
    score,
    formPackage,
    busy,
    error,
    canOpen,
    deadlineDays,
    onOpenPursuit,
    onToggleTask,
    onRefresh,
    onCreateFormPackage,
    onGoToOpportunities,
    commandCenter,
    onGoTo,
    onRecordInteraction,
  } = props;

  // The detail endpoint answers `{pursuit, tasks, calendar_events}`, so the
  // pursuit's own fields are a level down. Reading them off the envelope gave
  // an em dash for the stage and "No stated deadline" for an opportunity that
  // states one - the page looked like the backend held nothing, when it was
  // the unwrapping that was missing.
  const record = (pursuit?.pursuit ?? pursuit ?? null) as Record<string, unknown> | null;
  const tasks = Array.isArray(pursuit?.tasks)
    ? (pursuit?.tasks as Record<string, unknown>[])
    : [];
  const done = tasks.filter((t) => str(t.status) === "done");
  const nextTask = tasks.find((t) => str(t.status) !== "done") ?? null;
  // The deadline belongs to the opportunity, not to the pursuit, so it comes
  // in from the caller rather than being looked for on a record that has
  // never carried one.
  const days = deadlineDays;

  // A disqualification is a finding, not a score of nought.
  //
  // `composite: 0` with `recommendation: "disqualified"` was rendering as a
  // readiness of 0 with no explanation, which reads as the engine failing to
  // evaluate rather than as it having evaluated and found a hard eligibility
  // problem. Those are opposite messages to a grants office.
  const disqualified = Boolean(score?.disqualified);
  const composite =
    score && typeof score.composite === "number" ? String(score.composite) : "—";

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Pursue"
        title="Pursuits"
        lead="Applications in progress, and what each one is waiting on."
        actions={
          pursuit ? (
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onRefresh}
              disabled={busy}
            >
              Refresh
            </button>
          ) : null
        }
      />

      {error ? <StateView state={error} /> : null}

      {commandCenter ? (
        <PursuitCommandCenter
          center={commandCenter}
          onGoTo={onGoTo}
          onStartPursuit={onOpenPursuit}
          canStartPursuit={canOpen}
          onRecordInteraction={onRecordInteraction}
        />
      ) : null}

      {!pursuit ? (
        <EmptyState
          title="No pursuit is open."
          body={
            canOpen
              ? "Opening a pursuit creates the task list, the deadline anchors and the application package for an opportunity."
              : "Score an opportunity first. NativeForge opens a pursuit against an opportunity it has evaluated."
          }
          actionLabel={canOpen ? "Open a pursuit" : "Choose an opportunity"}
          onAction={canOpen ? onOpenPursuit : onGoToOpportunities}
        />
      ) : (
        <>
          <Section
            title={opportunityTitle || "Active pursuit"}
            lead="Everything below belongs to this application."
            aside={
              days !== null ? (
                <StatusBadge tone={deadlineTone(days)}>{formatDeadline(days)}</StatusBadge>
              ) : (
                <StatusBadge tone="muted">No stated deadline</StatusBadge>
              )
            }
          >
            {/* A blocking finding belongs above the task list, not beside it
                as a number. NativeForge evaluated this opportunity and found
                an eligibility rule it cannot satisfy; working the checklist
                will not change that, so the page says so before the checklist
                invites anyone to start. */}
            {disqualified ? (
              <StateView
                state={{
                  tone: "blocked",
                  title: "Eligibility is not met",
                  body:
                    humanDisqualification(str(score?.disqualification_reason)) ||
                    humanDisqualification(str(score?.explanation_text)) ||
                    "NativeForge found an eligibility requirement this organization does not currently meet. The tasks below still apply if that changes.",
                }}
              />
            ) : null}

            {nextTask ? (
              <div className="nf-next-action">
                <p className="nf-next-action-label">Next action</p>
                <p className="nf-next-action-title">
                  {str(nextTask.title) || str(nextTask.name) || "Continue the application"}
                </p>
                {str(nextTask.description) ? (
                  <p className="nf-next-action-body">{str(nextTask.description)}</p>
                ) : null}
                <button
                  type="button"
                  className="nf-btn nf-btn-primary nf-btn-sm"
                  onClick={() => onToggleTask(str(nextTask.id), str(nextTask.status))}
                  disabled={busy}
                >
                  Mark done
                </button>
              </div>
            ) : (
              <div className="nf-next-action" data-tone="done">
                <p className="nf-next-action-label">Next action</p>
                <p className="nf-next-action-title">
                  {tasks.length > 0
                    ? "Every task is complete. A person still has to review the package before anything is filed."
                    : "This pursuit has no tasks yet."}
                </p>
              </div>
            )}

            <MetricRow>
              <MetricCard
                label="Tasks complete"
                value={tasks.length > 0 ? `${done.length} / ${tasks.length}` : "—"}
                tone={tasks.length > 0 && done.length === tasks.length ? "positive" : "neutral"}
              />
              <MetricCard
                label="Status"
                value={str(record?.status) || "—"}
                tone="neutral"
              />
              <MetricCard
                label={disqualified ? "Eligibility" : "Readiness"}
                value={disqualified ? "Blocked" : composite}
                tone={disqualified ? "warn" : score ? "neutral" : "muted"}
                note={
                  disqualified
                    ? "An eligibility rule is unmet — see below"
                    : "Advisory, not a likelihood of award"
                }
              />
              <MetricCard
                label="Application package"
                value={formPackage ? "Prepared" : "—"}
                tone={formPackage ? "positive" : "muted"}
                note="Internal review only"
              />
            </MetricRow>
          </Section>

          <Section
            title="Tasks"
            lead="Generated from the notice's requirements and its deadline."
            aside={<span className="nf-count">{tasks.length} tasks</span>}
          >
            {tasks.length === 0 ? (
              <EmptyState
                title="No tasks on this pursuit."
                body="Tasks are created from extracted requirements. Read the notice and they will appear here."
                inline
              />
            ) : (
              <ul className="nf-task-list">
                {tasks.map((t, i) => {
                  const id = str(t.id) || String(i);
                  const status = str(t.status);
                  const isDone = status === "done";
                  return (
                    <li key={id} className="nf-task" data-done={isDone}>
                      <label className="nf-task-check">
                        <input
                          type="checkbox"
                          checked={isDone}
                          disabled={busy}
                          onChange={() => onToggleTask(id, status)}
                        />
                        <span className="nf-task-title">
                          {str(t.title) || str(t.name) || `Task ${i + 1}`}
                        </span>
                      </label>
                      {str(t.due_at) ? (
                        <span className="nf-task-due">{str(t.due_at).slice(0, 10)}</span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section
            title="Application package"
            lead="An SF-424 preview your team reviews. NativeForge does not submit it."
            aside={
              <button
                type="button"
                className="nf-btn nf-btn-secondary nf-btn-sm"
                onClick={onCreateFormPackage}
                disabled={busy}
              >
                {formPackage ? "Regenerate preview" : "Create preview"}
              </button>
            }
          >
            {formPackage ? (
              <p className="nf-note">
                A preview package exists for this pursuit. It is prepared from your organization
                profile and the extracted requirements, and it is not a filing.
              </p>
            ) : (
              <EmptyState
                title="No package prepared."
                body="A preview fills the SF-424 fields NativeForge can derive and leaves the rest for a person."
                inline
              />
            )}
          </Section>
        </>
      )}
    </div>
  );
}
