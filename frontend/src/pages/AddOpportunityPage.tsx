import { useMemo, useState } from "react";

import { StateView } from "../components/StateView";
import { PageHeader, Section, StatusBadge } from "../components/ui/primitives";
import type { CustomerState } from "../customerState";
import {
  EMPTY_INTAKE,
  INTAKE_STAGES,
  applyUrlRead,
  findExisting,
  type IntakeDraft,
  type UrlReadResult,
} from "../lib/opportunityIntake";

/**
 * Bring in an opportunity the customer already has.
 *
 * ## Three ways in, and none of them is the only one
 *
 * A link can now be read: `customer_supplied_url` is an authorized network
 * purpose, and the request goes through address classification, per-hop
 * redirect validation, content-type and size limits and the same politeness
 * rules every other fetch obeys.
 *
 * A file the customer already has is read the same way, through the same
 * reader, and also stored nowhere: the text comes back for review and the
 * ordinary create path makes the record.
 *
 * Reading can still fail, and the page treats that as ordinary rather than
 * exceptional, because for scanned PDFs and script-built pages it is. Pasting
 * the notice stays exactly where it was, at the same size, as the path that
 * always works. What the customer came for - who to contact, where to submit,
 * when it is due - comes out of the same extraction whichever way it arrived.
 *
 * ## No imported-grants silo
 *
 * The wizard produces the body the ordinary create endpoint takes. What comes
 * out is an opportunity, indistinguishable from a discovered one everywhere
 * except in the `source` field that records where it came from.
 */

const STEPS = ["What is it?", "Where are you?", "Review"] as const;

export interface AddOpportunityPageProps {
  /** Opportunities this organization already tracks, for duplicate checking. */
  tracked: Record<string, unknown>[];
  busy: boolean;
  error: CustomerState | null;
  /** Creates the opportunity. Resolves to its id, or null when it failed. */
  onCreate: (draft: IntakeDraft) => Promise<string | null>;
  /**
   * Reads a public page the customer named. Resolves to null when the request
   * itself failed, which is a different thing from the server declining to
   * open the address - that comes back as a result with a reason in it.
   */
  onReadUrl: (url: string) => Promise<UrlReadResult | null>;
  /** Reads a notice the customer has as a file. Same contract as the link. */
  onReadDocument: (file: File) => Promise<UrlReadResult | null>;
  /** Opens an opportunity the customer already tracks. */
  onOpenExisting: (id: string) => void;
  onCancel: () => void;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : value != null ? String(value) : "";
}

export function AddOpportunityPage(props: AddOpportunityPageProps) {
  const {
    tracked,
    busy,
    error,
    onCreate,
    onReadUrl,
    onReadDocument,
    onOpenExisting,
    onCancel,
  } = props;

  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<IntakeDraft>({ ...EMPTY_INTAKE });
  const [showError, setShowError] = useState(false);
  const [reading, setReading] = useState(false);
  const [readResult, setReadResult] = useState<UrlReadResult | null>(null);
  const [docReading, setDocReading] = useState(false);
  const [docResult, setDocResult] = useState<UrlReadResult | null>(null);
  const [docName, setDocName] = useState("");

  const set = <K extends keyof IntakeDraft>(key: K, value: IntakeDraft[K]) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  const duplicate = useMemo(() => findExisting(draft, tracked), [draft, tracked]);
  const titleMissing = !draft.title.trim();

  const next = () => {
    if (step === 0 && titleMissing) {
      setShowError(true);
      return;
    }
    setShowError(false);
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const read = async () => {
    const target = draft.url.trim();
    if (!target || reading) return;
    setReading(true);
    setReadResult(null);
    try {
      const result = await onReadUrl(target);
      setReadResult(result);
      if (result) setDraft((prev) => applyUrlRead(prev, result));
    } finally {
      setReading(false);
    }
  };

  const readDocument = async (file: File | null) => {
    if (!file || docReading) return;
    setDocName(file.name);
    setDocReading(true);
    setDocResult(null);
    try {
      const result = await onReadDocument(file);
      setDocResult(result);
      if (result) setDraft((prev) => applyUrlRead(prev, result));
    } finally {
      setDocReading(false);
    }
  };

  const create = async () => {
    const id = await onCreate(draft);
    if (id) onOpenExisting(id);
  };

  const stage = INTAKE_STAGES.find((s) => s.id === draft.stageId);

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Find funding"
        title="Add an opportunity"
        lead="A grant you already know about belongs in the same place as the ones NativeForge finds."
        actions={
          <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={onCancel}>
            Cancel
          </button>
        }
      />

      <ol className="nf-onboard-track" aria-label="Progress">
        {STEPS.map((title, i) => (
          <li
            key={title}
            className="nf-onboard-tick"
            data-state={i < step ? "done" : i === step ? "current" : "todo"}
            aria-current={i === step ? "step" : undefined}
          >
            <span className="nf-visually-hidden">{title}</span>
          </li>
        ))}
      </ol>

      {error ? <StateView state={error} /> : null}

      {/* ------------------------------------------------------ step one */}
      {step === 0 ? (
        <Section
          title="What is it?"
          lead="Whatever you have. NativeForge will report anything you leave out as unknown rather than guessing."
        >
          {showError && titleMissing ? (
            <StateView
              state={{
                tone: "blocked",
                title: "One thing first",
                body: "Give the opportunity a title so you can find it again.",
              }}
              inline
            />
          ) : null}

          <div className="nf-field">
            <label htmlFor="in-title">Opportunity title</label>
            <input
              id="in-title"
              className="nf-input"
              value={draft.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </div>

          <div className="nf-field-row">
            <div className="nf-field">
              <label htmlFor="in-funder">Funder</label>
              <input
                id="in-funder"
                className="nf-input"
                value={draft.funder}
                onChange={(e) => set("funder", e.target.value)}
                placeholder="HUD, BIA, a foundation…"
              />
            </div>
            <div className="nf-field">
              <label htmlFor="in-program">Program</label>
              <input
                id="in-program"
                className="nf-input"
                value={draft.program}
                onChange={(e) => set("program", e.target.value)}
              />
            </div>
          </div>

          <div className="nf-field-row">
            <div className="nf-field">
              <label htmlFor="in-number">Opportunity number</label>
              <input
                id="in-number"
                className="nf-input"
                value={draft.opportunityNumber}
                onChange={(e) => set("opportunityNumber", e.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="nf-field">
              <label htmlFor="in-deadline">Application deadline</label>
              <input
                id="in-deadline"
                type="date"
                className="nf-input"
                value={draft.deadline}
                onChange={(e) => set("deadline", e.target.value)}
              />
            </div>
          </div>

          <div className="nf-field">
            <label htmlFor="in-url">Link to the opportunity</label>
            <div className="nf-input-with-action">
              <input
                id="in-url"
                className="nf-input"
                value={draft.url}
                onChange={(e) => {
                  set("url", e.target.value);
                  setReadResult(null);
                }}
                placeholder="https://…"
              />
              <button
                type="button"
                className="nf-btn nf-btn-secondary"
                onClick={() => void read()}
                disabled={!draft.url.trim() || reading || busy}
              >
                {reading ? "Reading…" : "Read the page"}
              </button>
            </div>
            <p className="nf-field-help">
              Recorded so your team can get back to it. NativeForge can open a public page
              over a secure link and read the notice out of it — it will not open a private
              address, and some documents it cannot read at all.
            </p>
            {readResult ? <ReadOutcome result={readResult} kind="link" /> : null}
          </div>

          <div className="nf-field">
            <label htmlFor="in-document">Or upload the notice</label>
            <input
              id="in-document"
              type="file"
              className="nf-input"
              accept=".pdf,.htm,.html,.txt,application/pdf,text/html,text/plain"
              disabled={docReading || busy}
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                setDocResult(null);
                void readDocument(file);
              }}
            />
            <p className="nf-field-help">
              A PDF, a saved web page or a text file. NativeForge reads it and hands the
              text back — the file itself is not stored.
            </p>
            {docReading ? (
              <p className="nf-field-help" role="status">
                Reading {docName}…
              </p>
            ) : null}
            {docResult ? <ReadOutcome result={docResult} kind="document" /> : null}
          </div>

          <div className="nf-field">
            <label htmlFor="in-notice">Paste the notice</label>
            <textarea
              id="in-notice"
              className="nf-textarea"
              rows={8}
              value={draft.noticeText}
              onChange={(e) => set("noticeText", e.target.value)}
              placeholder="Paste the text of the funding notice, if you have it."
            />
            <p className="nf-field-help">
              This is the part that pays off. NativeForge reads pasted notice text the same way
              it reads any other: it will pull out the requirements, the contacts and the
              submission route, and cite where each came from.
            </p>
          </div>

          {duplicate.existing ? (
            <StateView
              state={{
                tone: "blocked",
                title: "You are already tracking this",
                body: `“${str(duplicate.existing.opportunity_title)}” matches by ${duplicate.reason}. Opening it avoids two records of the same competition with two different deadlines.`,
                actionLabel: "Open the one you have",
              }}
              onAction={() => onOpenExisting(str(duplicate.existing?.id))}
            />
          ) : null}
        </Section>
      ) : null}

      {/* ------------------------------------------------------ step two */}
      {step === 1 ? (
        <Section
          title="Where are you with it?"
          lead="So NativeForge picks up from where you actually are, rather than starting you at the beginning."
        >
          <div className="nf-radio-list" role="radiogroup" aria-label="Current stage">
            {INTAKE_STAGES.map((s) => (
              <label key={s.id} className="nf-radio" data-checked={draft.stageId === s.id}>
                <input
                  type="radio"
                  name="stage"
                  value={s.id}
                  checked={draft.stageId === s.id}
                  onChange={() => set("stageId", s.id)}
                />
                <span className="nf-radio-text">
                  <span className="nf-radio-label">{s.label}</span>
                  <span className="nf-radio-help">{s.help}</span>
                </span>
              </label>
            ))}
          </div>

          <div className="nf-field">
            <label htmlFor="in-notes">Anything your team should know</label>
            <textarea
              id="in-notes"
              className="nf-textarea"
              rows={3}
              value={draft.notes}
              onChange={(e) => set("notes", e.target.value)}
              placeholder="Optional"
            />
          </div>
        </Section>
      ) : null}

      {/* ---------------------------------------------------- step three */}
      {step === 2 ? (
        <Section
          title="Check this over"
          lead="Anything blank stays blank, and NativeForge will say so rather than filling it in."
          aside={<StatusBadge tone="info">Added by your organization</StatusBadge>}
        >
          <dl className="nf-review">
            <Row label="Title" value={draft.title} />
            <Row label="Funder" value={draft.funder} />
            <Row label="Program" value={draft.program} />
            <Row label="Opportunity number" value={draft.opportunityNumber} />
            <Row label="Deadline" value={draft.deadline} />
            <Row label="Link" value={draft.url} />
            <Row
              label="Notice text"
              value={
                draft.noticeText.trim()
                  ? `${draft.noticeText.trim().length.toLocaleString()} characters — NativeForge will read this`
                  : ""
              }
            />
            <Row
              label="Where the notice came from"
              value={
                draft.noticeText.trim()
                  ? readResult?.readable
                    ? "Read from the link above"
                    : docResult?.readable
                      ? `Read from ${docName}`
                      : "Pasted by your organization"
                  : ""
              }
            />
            <Row label="Stage" value={stage?.label ?? ""} />
          </dl>

          <p className="nf-note">
            NativeForge records this as stated by your organization. Nothing here is treated as
            independently verified, and nothing about your pursuit is visible to anyone outside
            it.
          </p>
        </Section>
      ) : null}

      <div className="nf-onboard-actions">
        <button
          type="button"
          className="nf-btn nf-btn-ghost"
          onClick={() => (step === 0 ? onCancel() : setStep((s) => s - 1))}
          disabled={busy}
        >
          {step === 0 ? "Cancel" : "Back"}
        </button>
        {step < STEPS.length - 1 ? (
          <button type="button" className="nf-btn nf-btn-primary" onClick={next} disabled={busy}>
            Continue
          </button>
        ) : (
          <button
            type="button"
            className="nf-btn nf-btn-primary"
            onClick={() => void create()}
            disabled={busy}
          >
            {busy ? "Adding…" : "Add opportunity"}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * What happened when NativeForge tried to read the link.
 *
 * Three outcomes, kept apart. A refusal is blocked, a document that opened
 * but could not be read is a warning, and a page that was read with doubt
 * attached says so while still counting as a success - because it is one, and
 * burying the caveat is how a customer ends up trusting a half-read document.
 */
function ReadOutcome({
  result,
  kind,
}: {
  result: UrlReadResult;
  kind: "link" | "document";
}) {
  const link = kind === "link";
  if (!result.fetched) {
    return (
      <StateView
        state={{
          tone: "blocked",
          title: link
            ? "NativeForge did not open that link"
            : "NativeForge cannot read that file",
          body: result.message,
        }}
        inline
      />
    );
  }
  if (!result.readable) {
    return (
      <StateView
        state={{ tone: "partial", title: "Opened, but not readable", body: result.message }}
        inline
      />
    );
  }
  return (
    <StateView
      state={{
        tone: result.message ? "partial" : "success",
        title: link ? "Notice read from the link" : "Notice read from the file",
        body:
          result.message ||
          "The text is below. Check it over — NativeForge will pull the contacts, the submission route and the deadline out of it.",
      }}
      inline
    />
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const given = value.trim();
  return (
    <div className="nf-review-row">
      <dt>{label}</dt>
      <dd>
        <span data-empty={given ? undefined : "true"}>{given || "Not provided"}</span>
      </dd>
    </div>
  );
}
