import { EmptyState } from "./StateView";
import { Section, StatusBadge, type BadgeTone } from "./ui/primitives";

/**
 * How to apply, and who to ask.
 *
 * The two questions that follow "should we apply?" - *who do I deal with* and
 * *what exactly do I do next* - were answerable only by reading a ninety-page
 * notice. This is the answer, with the section of the document it came from
 * attached to each fact.
 *
 * ## Roles are kept apart
 *
 * The program officer who can say whether a project is in scope is rarely the
 * person who can unstick a portal upload, and neither decides the award.
 * Grouping every address under one "Contact" heading is how a customer sends
 * a technical question to a program officer and loses a week. Where the
 * notice did not state a role, the contact appears under "Role not stated" -
 * a worse answer than a classified one, and a far better one than a confident
 * guess.
 *
 * ## Completeness is shown, not implied
 *
 * A portal URL with no deadline is not a submission path you can rely on, so
 * the panel says `Partial` and lists what is missing rather than presenting
 * an incomplete route as if it were finished.
 */

export interface ApplyContact {
  id: string;
  role: string;
  name: string | null;
  title: string | null;
  office: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  provenance_kind: string;
  source_document: string | null;
  source_section: string | null;
  superseded: boolean;
}

export interface ApplySubmission {
  method: string;
  portal_name: string | null;
  submission_url: string | null;
  package_url: string | null;
  recipient_email: string | null;
  recipient_office: string | null;
  deadline_at: string | null;
  deadline_timezone: string | null;
  submission_instructions: string | null;
  completeness: string;
  completeness_reasons: string[];
  source_document: string | null;
  source_section: string | null;
}

export interface ApplyPath {
  contacts: ApplyContact[];
  submission: ApplySubmission | null;
  extraction_performed: boolean;
}

const ROLE_LABEL: Record<string, string> = {
  program: "Program questions",
  application_support: "Technical and application support",
  grants_management: "Grants management",
  submission_support: "Submission support",
  financial: "Budget and finance",
  award_decision: "Award decisions",
  general_office: "General office",
  unknown: "Role not stated",
};

/** The order a grants office actually needs them in. */
const ROLE_ORDER = [
  "program",
  "application_support",
  "submission_support",
  "grants_management",
  "financial",
  "award_decision",
  "general_office",
  "unknown",
];

const METHOD_LABEL: Record<string, string> = {
  grants_gov: "Grants.gov",
  agency_portal: "Agency portal",
  state_portal: "State portal",
  foundation_portal: "Funder portal",
  email: "Email",
  mail: "Mail",
  invitation_only: "By invitation",
  other: "Other",
  unknown: "Not stated",
};

const COMPLETENESS: Record<string, { label: string; tone: BadgeTone }> = {
  verified: { label: "Confirmed", tone: "positive" },
  partial: { label: "Partial", tone: "warn" },
  unclear: { label: "Not found", tone: "muted" },
  review_required: { label: "Needs review", tone: "bad" },
};

/** Reason codes from the extractor, as sentences. */
const REASON_COPY: Record<string, string> = {
  no_portal_or_recipient_identified:
    "The notice does not name a portal or an address to send the application to.",
  no_submission_deadline_found:
    "No submission date was found. A time without a date is not a deadline.",
  submission_method_not_stated: "The notice does not say how applications are submitted.",
  no_submission_instructions_found:
    "NativeForge found no submission instructions in what it has read of this notice.",
  no_notice_text_available: "NativeForge has not read this opportunity's notice yet.",
};

/**
 * A citation short enough to read.
 *
 * Section headings are usually two or three words. Occasionally the line the
 * extractor matched is a wrapped sentence - "Questions about award
 * notifications should be directed to the Office of" - which is a correct
 * citation and an unreadable one. Truncating is a display decision only: the
 * stored record keeps the full text and the character offset.
 */
function citation(section: string, max = 52): string {
  const trimmed = section.trim();
  if (trimmed.length <= max) return trimmed;
  const cut = trimmed.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

function formatDeadline(iso: string | null, zone: string | null): string | null {
  if (!iso) return null;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  const date = when.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const time = when.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  // The funder's own clock, because that is the instruction the customer has
  // to meet. Converting it to the reader's local time would be technically
  // accurate and practically misleading.
  return zone ? `${date}, ${time} ${zone}` : `${date}, ${time}`;
}

export function ApplyPathPanel({
  path,
  busy,
  onExtract,
  canExtract,
}: {
  path: ApplyPath | null;
  busy: boolean;
  onExtract: () => void;
  canExtract: boolean;
}) {
  const submission = path?.submission ?? null;
  const contacts = (path?.contacts ?? []).filter((c) => !c.superseded);
  const state = COMPLETENESS[submission?.completeness ?? "unclear"];

  const grouped = ROLE_ORDER.map((role) => ({
    role,
    label: ROLE_LABEL[role] ?? role,
    items: contacts.filter((c) => c.role === role),
  })).filter((group) => group.items.length > 0);

  return (
    <>
      <Section
        title="How to apply"
        lead="The route this application takes, read from the funding notice."
        aside={
          <>
            <StatusBadge tone={state.tone}>{state.label}</StatusBadge>
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onExtract}
              disabled={busy || !canExtract}
            >
              {busy ? "Reading…" : path ? "Re-read notice" : "Find submission path"}
            </button>
          </>
        }
      >
        {!submission ? (
          <EmptyState
            title="No submission path found yet."
            body={
              REASON_COPY[submission === null ? "no_submission_instructions_found" : ""] ??
              "NativeForge has not found submission instructions in what it has read of this notice."
            }
            actionLabel={canExtract ? "Find submission path" : undefined}
            onAction={canExtract ? onExtract : undefined}
          />
        ) : (
          <>
            <dl className="nf-apply">
              <div className="nf-apply-row">
                <dt>Submit through</dt>
                <dd>
                  <span className="nf-apply-strong">
                    {submission.portal_name ?? METHOD_LABEL[submission.method] ?? "—"}
                  </span>
                  {submission.submission_url ? (
                    <a
                      className="nf-btn nf-btn-secondary nf-btn-sm"
                      href={submission.submission_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      Open portal
                    </a>
                  ) : null}
                  {submission.recipient_email ? (
                    <a
                      className="nf-btn nf-btn-secondary nf-btn-sm"
                      href={`mailto:${submission.recipient_email}`}
                    >
                      {submission.recipient_email}
                    </a>
                  ) : null}
                </dd>
              </div>
              <div className="nf-apply-row">
                <dt>Deadline</dt>
                <dd>
                  <span className="nf-apply-strong">
                    {formatDeadline(submission.deadline_at, submission.deadline_timezone) ??
                      submission.submission_instructions ??
                      "Not stated"}
                  </span>
                </dd>
              </div>
              {submission.source_section ? (
                <div className="nf-apply-row">
                  <dt>Found in</dt>
                  <dd>
                    <span className="nf-apply-source">
                      {submission.source_document
                        ? `${submission.source_document} — ${citation(submission.source_section)}`
                        : citation(submission.source_section)}
                    </span>
                  </dd>
                </div>
              ) : null}
            </dl>

            {submission.completeness_reasons.length > 0 ? (
              <ul className="nf-apply-gaps">
                {submission.completeness_reasons.map((reason) => (
                  <li key={reason}>{REASON_COPY[reason] ?? reason.replace(/_/g, " ")}</li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </Section>

      <Section
        title="Contacts"
        lead="Grouped by the job the notice says each one does."
        aside={<span className="nf-count">{contacts.length} found</span>}
      >
        {grouped.length === 0 ? (
          <EmptyState
            title="No contacts found yet."
            body="NativeForge records a contact only where the notice gives a way to reach somebody. Reading the notice will look for them."
            inline
          />
        ) : (
          grouped.map((group) => (
            <div key={group.role} className="nf-contact-group">
              <p className="nf-contact-role">{group.label}</p>
              <ul className="nf-contact-list">
                {group.items.map((c) => (
                  <li key={c.id} className="nf-contact">
                    <div className="nf-contact-who">
                      <p className="nf-contact-name">{c.name ?? c.office ?? "Contact"}</p>
                      {c.title || c.office ? (
                        <p className="nf-contact-title">
                          {[c.title, c.name ? c.office : null].filter(Boolean).join(" · ")}
                        </p>
                      ) : null}
                      {c.source_section ? (
                        <p className="nf-contact-source">From “{citation(c.source_section)}”</p>
                      ) : null}
                    </div>
                    <div className="nf-contact-reach">
                      {c.email ? (
                        <a className="nf-contact-link" href={`mailto:${c.email}`}>
                          {c.email}
                        </a>
                      ) : null}
                      {c.phone ? (
                        <a className="nf-contact-link" href={`tel:${c.phone.replace(/[^\d+]/g, "")}`}>
                          {c.phone}
                        </a>
                      ) : null}
                      {/* Stated, not styled away. A contact the customer typed
                          in is useful and is not evidence about the
                          opportunity, and only the second kind could ever be
                          shown to another organization. */}
                      {c.provenance_kind === "customer_provided" ? (
                        <StatusBadge tone="info">Added by your organization</StatusBadge>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
        <p className="nf-note nf-note--quiet">
          NativeForge does not contact funders on your behalf.
        </p>
      </Section>
    </>
  );
}
