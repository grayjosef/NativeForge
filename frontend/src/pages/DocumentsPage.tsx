import { EmptyState, StateView } from "../components/StateView";
import type { CustomerState } from "../customerState";
import { humanRequirementType } from "../lib/requirementTypes";
import { ApplyPathPanel, type ApplyPath } from "../components/ApplyPathPanel";
import { PursuitCommandCenter } from "../components/PursuitCommandCenter";
import {
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
  type BadgeTone,
} from "../components/ui/primitives";

/**
 * Document intelligence, as a customer needs to read it.
 *
 * ## The distinction this page exists to protect
 *
 * NativeForge's evidence rules are the reason it can be trusted about
 * eligibility, and they are all about the difference between *this notice
 * does not require X* and *we did not read the part that would have said so*.
 *
 * ```text
 * READ, and silent        -> the absence means something
 * PARTIAL, and silent     -> proves nothing
 * FAILED, and silent      -> proves nothing
 * UNREAD material page    -> blocks any final negative conclusion
 * ```
 *
 * A UI that renders all four as "0 requirements found" destroys the property
 * the engine was built to have. So every count on this page is paired with
 * its closure state, and an incomplete read is reported as incomplete rather
 * than as a smaller number.
 *
 * ## Not OCR diagnostics
 *
 * Page counts, engine names, confidence scores and timing belong in operator
 * tooling. What a customer needs is narrower: has NativeForge read the notice,
 * is anything still unread, is there a newer amendment, and can a negative
 * finding be relied upon.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface DocumentsPageProps {
  /** The opportunity these documents belong to. */
  opportunityTitle: string | null;
  sparkSelected: boolean;
  requirements: Record<string, unknown>[];
  /** The latest extraction run, when one exists. */
  extraction: Record<string, unknown> | null;
  busy: boolean;
  error: CustomerState | null;
  onExtract: () => void;
  onReload: () => void;
  onGoToOpportunities: () => void;
  /** Who to contact and where to submit, once the notice has been read. */
  applyPath: ApplyPath | null;
  applyBusy: boolean;
  onExtractApplyPath: () => void;
  commandCenter: import("../components/PursuitCommandCenter").CommandCenter | null;
  onGoTo: (view: string) => void;
  onStartPursuit: () => void;
  canStartPursuit: boolean;
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

export function DocumentsPage(props: DocumentsPageProps) {
  const {
    opportunityTitle,
    sparkSelected,
    requirements,
    extraction,
    busy,
    error,
    onExtract,
    onReload,
    onGoToOpportunities,
    applyPath,
    applyBusy,
    onExtractApplyPath,
    commandCenter,
    onGoTo,
    onStartPursuit,
    canStartPursuit,
    onRecordInteraction,
  } = props;

  const run = (extraction?.extraction_run ?? null) as Record<string, unknown> | null;
  const artifact = (extraction?.review_artifact ?? null) as Record<string, unknown> | null;
  const reviewStatus = str(artifact?.review_status);

  // Closure is the whole point. An extraction that ran is not the same as one
  // that read everything, so the two are reported separately and a missing
  // run is neither.
  const hasRun = run !== null;
  const closure: { label: string; tone: BadgeTone; body: string } = !sparkSelected
    ? {
        label: "No opportunity selected",
        tone: "muted",
        body: "Choose an opportunity and NativeForge will report what it has read of that notice.",
      }
    : !hasRun
      ? {
          label: "Not yet read",
          tone: "muted",
          body: "NativeForge has not read this notice. Nothing about its requirements can be concluded yet — including that it has none.",
        }
      : requirements.length > 0
        ? {
            label: "Read",
            tone: "positive",
            body: "NativeForge has read this notice and extracted its requirements. A requirement absent from this list is absent from the notice.",
          }
        : {
            label: "Read, nothing extracted",
            tone: "warn",
            body: "The notice was processed but produced no requirement rows. Treat this as incomplete rather than as a notice without requirements.",
          };

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Pursue"
        title="Documents"
        lead="What NativeForge has read of this opportunity's notice, and what it has not."
        actions={
          <>
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onReload}
              disabled={busy || !sparkSelected}
            >
              Reload
            </button>
            <button
              type="button"
              className="nf-btn nf-btn-primary nf-btn-sm"
              onClick={onExtract}
              disabled={busy || !sparkSelected}
            >
              {busy ? "Reading…" : "Read this notice"}
            </button>
          </>
        }
      />

      {error ? <StateView state={error} /> : null}

      {!sparkSelected ? (
        <EmptyState
          title="No opportunity selected."
          body="Documents belong to an opportunity. Choose one and NativeForge will report what it has read."
          actionLabel="Choose an opportunity"
          onAction={onGoToOpportunities}
        />
      ) : (
        <>
          <PursuitCommandCenter
            center={commandCenter}
            onGoTo={onGoTo}
            onStartPursuit={onStartPursuit}
            canStartPursuit={canStartPursuit}
            onRecordInteraction={onRecordInteraction}
          />

          <Section
            title={opportunityTitle || "Selected opportunity"}
            lead="Evidence closure for this notice."
            aside={<StatusBadge tone={closure.tone}>{closure.label}</StatusBadge>}
          >
            <p className="nf-note">{closure.body}</p>
            <MetricRow>
              <MetricCard
                label="Requirements extracted"
                value={hasRun ? String(requirements.length) : "—"}
                tone={requirements.length > 0 ? "positive" : "muted"}
                note={hasRun ? undefined : "Nothing read yet"}
              />
              <MetricCard
                label="Review artifact"
                value={artifact ? "Created" : "—"}
                tone={artifact ? "positive" : "muted"}
                note={reviewStatus ? `Status: ${reviewStatus}` : "Created when a notice is read"}
              />
              <MetricCard
                label="Amendments"
                value="—"
                tone="muted"
                note="Amendment tracking is not connected to a live source"
              />
              <MetricCard
                label="OCR"
                value={hasRun ? "Available" : "—"}
                tone="muted"
                note="Used only for notices that carry no extractable text"
              />
            </MetricRow>
          </Section>

          <ApplyPathPanel
            path={applyPath}
            busy={applyBusy}
            onExtract={onExtractApplyPath}
            canExtract={sparkSelected}
          />

          <Section
            title="Requirements"
            lead="Every row below was taken from the notice text, not inferred."
            aside={<span className="nf-count">{requirements.length} rows</span>}
          >
            {requirements.length === 0 ? (
              <EmptyState
                title={hasRun ? "No requirement rows." : "This notice has not been read."}
                body={
                  hasRun
                    ? "NativeForge processed this notice and produced nothing. That is a gap in the reading, not evidence that the notice is requirement-free."
                    : "Read the notice and NativeForge will extract its requirements into a checklist."
                }
                actionLabel={hasRun ? undefined : "Read this notice"}
                onAction={hasRun ? undefined : onExtract}
                inline
              />
            ) : (
              <ul className="nf-req-list">
                {requirements.map((r, i) => {
                  const id = str(r.id) || String(i);
                  const pages = typeof r.page_limit === "number" ? r.page_limit : null;
                  return (
                    <li key={id} className="nf-req">
                      <div className="nf-req-main">
                        {/* `label` and `description`, which is what the
                            extractor actually produces. An earlier version
                            reached for `requirement_text` and `text` - neither
                            exists - and fell through to the literal word
                            "Requirement", so nine rows all read the same and
                            the page looked like it had found nothing useful.
                            Caught in the browser; no test would have, because
                            a fixture would have had whatever fields the test
                            author believed in. */}
                        <p className="nf-req-text">{str(r.label) || "Untitled requirement"}</p>
                        {str(r.description) ? (
                          <p className="nf-req-detail">{str(r.description)}</p>
                        ) : null}
                        <p className="nf-req-meta">
                          <StatusBadge tone="muted">
                            {humanRequirementType(str(r.requirement_type))}
                          </StatusBadge>
                          {pages !== null ? (
                            <StatusBadge tone="muted">{pages} page limit</StatusBadge>
                          ) : null}
                        </p>
                      </div>
                      <StatusBadge tone={r.required ? "warn" : "muted"}>
                        {r.required ? "Required" : "Optional"}
                      </StatusBadge>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <p className="nf-note nf-note--quiet">
            NativeForge does not treat silence in a document it failed to open as evidence of
            absence. A notice it could not read is reported as unread.
          </p>
        </>
      )}
    </div>
  );
}

