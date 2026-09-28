import type { ReactNode } from "react";

import { MissionControl, type MissionControlPayload } from "../components/MissionControl";
import type { ProgressStep } from "../components/ProgressStrip";
import { EmptyState } from "../components/StateView";
import { VerificationTiers, buildTiers } from "../components/VerificationTiers";
import { WorkflowProgress } from "../components/ui/WorkflowProgress";
import {
  ActionCard,
  CardGrid,
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
} from "../components/ui/primitives";
import { deadlineTone, formatDeadline, daysUntil } from "../lib/dates";
import { humanEntity } from "../lib/entityTypes";

/**
 * Workspace: the page that answers "what needs my attention" before it
 * answers anything else.
 *
 * ## What it replaced
 *
 * Seven stacked cards in the order an engineer builds them - profile, then
 * opportunity, then requirements, then score, then pursuit, then forms, then
 * trust - each with its own buttons. It was a correct rendering of the
 * pipeline and a poor rendering of a working day. Nothing on it said what was
 * due, what was blocked, or which of the seven the customer should look at
 * first; the customer had to read all seven to find out.
 *
 * The pipeline is still here, because the guided flow is how the product
 * actually works. It is now below the answers rather than instead of them.
 *
 * ## Every number is measured or absent
 *
 * There is no placeholder data on this page. A metric with nothing behind it
 * renders as an em dash with a note saying why, never as a zero: zero is a
 * measurement, and claiming one that was never taken is the single most
 * damaging thing a funding-intelligence product can do. `formatCount` exists
 * to make the honest option the easy one.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

/** A count that was taken, or an em dash for one that was not. */
function formatCount(value: number | null | undefined): string {
  return typeof value === "number" ? String(value) : "—";
}

export interface WorkspacePageProps {
  organizationName: string | null;
  entityType: string | null;
  identityVerified: boolean;
  hasProfile: boolean;

  steps: ProgressStep[];

  sparks: Record<string, unknown>[];
  selectedSparkId: string;
  onSelectSpark: (id: string) => void;

  requirementsCount: number;
  reviewSummary: Record<string, unknown> | null;
  score: Record<string, unknown> | null;

  pursuit: Record<string, unknown> | null;
  formPackage: Record<string, unknown> | null;

  trustVersion: string | null;
  auditCount: number | null;

  /** The single next action, already resolved by the workflow model. */
  nextHeadline: string;
  nextDetail: string;
  nextActionLabel: string | null;
  onNextAction: () => void;
  busy: boolean;

  /** The existing guided cards, rendered by the caller. */
  workflow: ReactNode;
  /** Guidance and trust column. */
  aside: ReactNode;

  onGoTo: (navId: string) => void;
  missionControl?: MissionControlPayload | null;
  onOpenOpportunity?: (sparkId: string) => void;
}

export function WorkspacePage(props: WorkspacePageProps) {
  const {
    organizationName,
    entityType,
    identityVerified,
    hasProfile,
    steps,
    sparks,
    selectedSparkId,
    onSelectSpark,
    requirementsCount,
    reviewSummary,
    score,
    pursuit,
    formPackage,
    trustVersion,
    auditCount,
    nextHeadline,
    nextDetail,
    nextActionLabel,
    onNextAction,
    busy,
    workflow,
    aside,
    onGoTo,
    missionControl = null,
    onOpenOpportunity,
  } = props;

  const attention = steps.filter(
    (s) => s.state === "needs_attention" || s.state === "error",
  );

  // Deadlines come off the opportunities themselves. Sparks without a parsable
  // deadline are dropped rather than sorted to the end under a fabricated
  // date, and the count below says how many were dropped.
  const dated = sparks
    .map((s) => ({ spark: s, days: daysUntil(str(s.application_deadline)) }))
    .filter((x): x is { spark: Record<string, unknown>; days: number } => x.days !== null)
    .sort((a, b) => a.days - b.days);
  const undated = sparks.length - dated.length;

  const tasks = Array.isArray(pursuit?.tasks) ? (pursuit?.tasks as Record<string, unknown>[]) : [];
  const tasksDone = tasks.filter((t) => str(t.status) === "done").length;

  const reviewPending =
    reviewSummary && typeof reviewSummary.pending_count === "number"
      ? (reviewSummary.pending_count as number)
      : null;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Workspace"
        title={organizationName?.trim() || "Your organization"}
        lead={
          hasProfile
            ? "What needs your attention, what matches you, and what is due."
            : "Complete your organization profile and NativeForge can begin evaluating opportunities for you."
        }
        actions={
          <>
            {entityType ? (
              <StatusBadge tone="info">{humanEntity(entityType)}</StatusBadge>
            ) : null}
            {/* The most common thing a customer arrives wanting to do:
                put a grant they already know about into NativeForge. */}
            {hasProfile ? (
              <button
                type="button"
                className="nf-btn nf-btn-primary nf-btn-sm"
                onClick={() => onGoTo("add_opportunity")}
              >
                Add an opportunity
              </button>
            ) : null}
          </>
        }
      />

      <MissionControl
        data={missionControl}
        onGoTo={onGoTo}
        onOpenOpportunity={onOpenOpportunity ?? (() => undefined)}
      />

      {/* ------------------------------------------ attention and measurement
          Side by side above 1200px.
          Stacked, "Action required" was a single card stretched to 1113px
          holding a four-word title and one sentence, with the rest of the
          viewport empty to its right; then "At a glance" repeated the shape
          below it. Two half-empty full-width bands where one dense row of
          answers belongs. Below 1200px they stack, because two columns of
          260px cards is the cramped failure rather than the empty one. */}
      <div className="nf-workspace-top">
      <Section
        title="Action required"
        lead="Everything here is waiting on a decision or a step from you."
        aside={
          attention.length > 0 ? (
            <StatusBadge tone="warn">{attention.length} needing attention</StatusBadge>
          ) : null
        }
      >
        <CardGrid min={260} max={null}>
          {nextActionLabel ? (
            <ActionCard
              title={nextHeadline}
              body={nextDetail}
              badge="Next step"
              tone="neutral"
              actionLabel={busy ? "Working…" : nextActionLabel}
              onAction={onNextAction}
              disabled={busy}
            />
          ) : null}
          {attention.map((s) => (
            <ActionCard
              key={s.id}
              title={s.label}
              body={s.lineSummary}
              tone={s.state === "error" ? "bad" : "warn"}
              badge={s.state === "error" ? "Problem" : "Attention"}
            />
          ))}
          {!nextActionLabel && attention.length === 0 ? (
            <EmptyState
              title="Nothing is waiting on you."
              body="Every step NativeForge can take on its own is current."
              inline
            />
          ) : null}
        </CardGrid>
      </Section>

      {/* ------------------------------------------------------- at a glance */}
      <Section title="At a glance" lead="Measured from your organization's own data.">
        <MetricRow>
          <MetricCard
            label="Opportunities tracked"
            value={formatCount(sparks.length)}
            note={undated > 0 ? `${undated} without a stated deadline` : undefined}
            onClick={() => onGoTo("opportunities")}
          />
          <MetricCard
            label="Requirements extracted"
            value={formatCount(requirementsCount)}
            note={
              requirementsCount === 0
                ? "From the selected opportunity's notice"
                : undefined
            }
            onClick={() => onGoTo("documents")}
          />
          <MetricCard
            label="Active pursuits"
            value={formatCount(pursuit ? 1 : 0)}
            note={tasks.length > 0 ? `${tasksDone} of ${tasks.length} tasks done` : undefined}
            onClick={() => onGoTo("pursuits")}
          />
          <MetricCard
            label="Audit events"
            value={formatCount(auditCount)}
            note={auditCount === null ? "Not loaded" : "Recorded for your organization"}
            onClick={() => onGoTo("trust")}
          />
        </MetricRow>
      </Section>
      </div>

      {/* ---------------------------------------------------- organization */}
      <Section
        title="Organization readiness"
        lead="What NativeForge knows about you, and how it knows it."
        aside={
          <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => onGoTo("organization")}>
            Open organization
          </button>
        }
      >
        <VerificationTiers tiers={buildTiers({ identityVerified, hasProfile })} />
      </Section>

      {/* ------------------------------------------------ upcoming deadlines */}
      <Section
        title="Upcoming deadlines"
        lead="Application deadlines stated by the funding notice."
      >
        {dated.length === 0 ? (
          <EmptyState
            title="No dated opportunities yet."
            body={
              sparks.length > 0
                ? "The opportunities you are tracking do not state an application deadline."
                : "Deadlines appear here once you are tracking an opportunity."
            }
            inline
          />
        ) : (
          <ul className="nf-deadline-list">
            {dated.slice(0, 5).map(({ spark, days }) => {
              const id = str(spark.id);
              return (
                <li key={id} className="nf-deadline" data-tone={deadlineTone(days)}>
                  <button
                    type="button"
                    className="nf-deadline-main"
                    onClick={() => onSelectSpark(id)}
                    aria-current={id === selectedSparkId ? "true" : undefined}
                  >
                    <span className="nf-deadline-title">
                      {str(spark.opportunity_title) || `Opportunity ${id.slice(0, 8)}`}
                    </span>
                    <span className="nf-deadline-meta">
                      {[str(spark.agency), str(spark.program_name)].filter(Boolean).join(" · ") ||
                        "Funder not stated"}
                    </span>
                  </button>
                  <span className="nf-deadline-when">
                    <span className="nf-deadline-days">{formatDeadline(days)}</span>
                    <span className="nf-deadline-date">
                      {str(spark.application_deadline).slice(0, 10)}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      {/* ------------------------------------------------------- evidence */}
      <Section
        title="Evidence health"
        lead="What NativeForge has read, and what it has not."
        aside={
          <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => onGoTo("documents")}>
            Open documents
          </button>
        }
      >
        <MetricRow>
          <MetricCard
            label="Requirements read"
            value={formatCount(requirementsCount)}
            tone={requirementsCount > 0 ? "positive" : "muted"}
          />
          <MetricCard
            label="Awaiting human review"
            value={formatCount(reviewPending)}
            tone={reviewPending && reviewPending > 0 ? "warn" : "muted"}
            note={reviewPending === null ? "Review summary not loaded" : undefined}
          />
          <MetricCard
            label="Readiness score"
            value={score && typeof score.composite === "number" ? String(score.composite) : "—"}
            tone={score ? "neutral" : "muted"}
            note={score ? "Advisory only" : "Not scored yet"}
          />
          <MetricCard
            label="Form preview"
            value={formPackage ? "Prepared" : "—"}
            tone={formPackage ? "positive" : "muted"}
            note={formPackage ? "Internal review only" : "Not prepared"}
          />
        </MetricRow>
        <p className="nf-note">
          A document NativeForge could not read is reported as unread, never as empty. Silence in a
          notice it failed to open proves nothing about what the notice requires.
        </p>
      </Section>

      {/* -------------------------------------------------------- workflow */}
      <Section
        title="Guided pursuit workflow"
        lead="The sequence from organization profile to a reviewable application package."
      >
        <WorkflowProgress
          steps={steps}
          title="Pursuit workflow"
          onStepActivate={(step) => {
            if (step.view) onGoTo(step.view);
          }}
        />
        <div className="nf-layout">
          <div className="nf-workflow">{workflow}</div>
          <aside className="nf-sidecol" aria-label="Guidance and trust">
            {aside}
          </aside>
        </div>
      </Section>

      <p className="nf-note nf-note--quiet">
        Trust manifest {trustVersion ? trustVersion : "not loaded"}.
      </p>
    </div>
  );
}

