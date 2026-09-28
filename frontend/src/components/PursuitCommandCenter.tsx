import { useState, type FormEvent } from "react";

import type { ProgressStep, ProgressStepState } from "./ProgressStrip";
import { WorkflowProgress } from "./ui/WorkflowProgress";
import { Section, StatusBadge, type BadgeTone } from "./ui/primitives";

/**
 * The individual grant as a pursuit command center.
 *
 * Workflow stages are the Workspace sequence, derived from persisted
 * records. Contacts come from the 0068 apply-path rows. Interactions are
 * tenant-private and survive reload.
 */

export interface CommandStage {
  id: string;
  short_label: string;
  label: string;
  status: "complete" | "current" | "blocked" | "not_started" | "not_applicable";
  summary: string;
  view: string | null;
}

export interface CommandContact {
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
  superseded?: boolean;
}

export interface CommandInteraction {
  id: string;
  interaction_type: string;
  status: string;
  occurred_at: string | null;
  follow_up_at: string | null;
  subject: string | null;
  notes: string | null;
  owner_label: string | null;
  contact_id: string | null;
  funder_agency: string;
}

export interface CommandCenter {
  schema_version: string;
  mode: "discovered" | "active_pursuit";
  opportunity: {
    id: string;
    title: string;
    agency: string;
    program_name: string | null;
    source: string;
    pipeline_stage: string;
    application_deadline: string | null;
    loi_deadline: string | null;
  };
  pursuit: { id: string; status: string } | null;
  workflow: {
    derived: boolean;
    shown: boolean;
    current_stage_id: string | null;
    stages: CommandStage[];
  };
  next_action: {
    headline: string;
    detail: string;
    action_id: string;
    view: string | null;
    owner_label: string | null;
  };
  open_work: {
    open_count: number;
    blocked_count: number;
    overdue_count: number;
    tasks: { id: string; title: string; status: string; due_at: string | null }[];
    blockers: { id: string; title: string; status: string }[];
  };
  deadlines: { kind: string; label: string; occurs_at: string | null; source: string }[];
  contacts: {
    items: CommandContact[];
    extraction_performed: boolean;
    empty_message: string | null;
  };
  question_intelligence: {
    facts: { kind: string; label: string; value: string; source: string }[];
    found: boolean;
  };
  interactions: CommandInteraction[];
  institutional_memory: {
    funder_agency?: string;
    prior_pursuits: {
      grant_spark_id: string;
      title: string;
      source: string;
      pursuit_status: string;
    }[];
    prior_contacts: {
      name: string | null;
      role: string;
      email: string | null;
      from_opportunity: string;
      provenance_kind: string;
    }[];
    prior_interactions: CommandInteraction[];
  };
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

const TYPE_LABEL: Record<string, string> = {
  question_submitted: "Question submitted",
  email: "Email",
  phone_call: "Phone call",
  technical_assistance: "Technical assistance",
  office_hours: "Office hours",
  webinar: "Webinar",
  applicant_conference: "Applicant conference",
  pre_application_meeting: "Pre-application meeting",
  clarification_received: "Clarification received",
  amendment_communication: "Amendment",
  other: "Other",
};

const STAGE_STATE: Record<CommandStage["status"], ProgressStepState> = {
  complete: "complete",
  current: "in_review",
  blocked: "needs_attention",
  not_started: "not_started",
  not_applicable: "locked",
};

const INTERACTION_TYPES = Object.keys(TYPE_LABEL);

function provenanceTone(kind: string): { label: string; tone: BadgeTone } {
  if (kind === "source_document" || kind === "source_page" || kind === "evidence") {
    return { label: "From the notice", tone: "positive" };
  }
  if (kind === "customer_provided" || kind === "human") {
    return { label: "Recorded by us", tone: "neutral" };
  }
  if (kind === "model" || kind === "extracted" || kind === "ai") {
    return { label: "Suggested — needs review", tone: "warn" };
  }
  return { label: "Needs review", tone: "warn" };
}

function toProgressSteps(stages: CommandStage[]): ProgressStep[] {
  return stages.map((s) => ({
    id: s.id,
    shortLabel: s.short_label,
    label: s.label,
    state: STAGE_STATE[s.status],
    lineSummary: s.summary,
    view: s.view,
  }));
}

export interface PursuitCommandCenterProps {
  center: CommandCenter | null;
  busy?: boolean;
  onGoTo: (view: string) => void;
  onStartPursuit?: () => void;
  canStartPursuit?: boolean;
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

export function PursuitCommandCenter(props: PursuitCommandCenterProps) {
  const { center, onGoTo, onStartPursuit, canStartPursuit, onRecordInteraction } = props;
  const [type, setType] = useState("question_submitted");
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");
  const [owner, setOwner] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [contactId, setContactId] = useState("");
  const [saving, setSaving] = useState(false);

  if (!center) return null;

  const active = center.mode === "active_pursuit";
  const steps = toProgressSteps(center.workflow.stages);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await onRecordInteraction({
        interaction_type: type,
        subject: subject.trim() || undefined,
        notes: notes.trim() || undefined,
        owner_label: owner.trim() || undefined,
        follow_up_at: followUp.trim() || undefined,
        contact_id: contactId.trim() || undefined,
        status: followUp.trim() ? "awaiting_reply" : "open",
      });
      setSubject("");
      setNotes("");
      setFollowUp("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="nf-command">
      <Section
        title={center.opportunity.title || "Opportunity"}
        lead={`${center.opportunity.agency}${center.opportunity.program_name ? ` · ${center.opportunity.program_name}` : ""}`}
        aside={
          <StatusBadge tone={active ? "positive" : "muted"}>
            {active ? "Active pursuit" : "Opportunity discovered"}
          </StatusBadge>
        }
      >
        <p className="nf-note">
          {active
            ? "NativeForge is managing this pursuit from persisted work, not a cosmetic progress bar."
            : "This grant is in the database. It is not yet an active pursuit, so no chase progress is shown."}
        </p>
      </Section>

      {active ? (
        <Section
          title="Guided pursuit workflow"
          lead="Where this specific grant stands. Same sequence as Workspace, derived from records."
        >
          <WorkflowProgress
            steps={steps}
            title="This pursuit"
            onStepActivate={(step) => {
              if (step.view) onGoTo(step.view);
            }}
          />
        </Section>
      ) : (
        <Section title="Not yet pursuing" lead="Start a pursuit after scoring to initialize workflow, tasks, and calendar.">
          {onStartPursuit ? (
            <button
              type="button"
              className="nf-btn nf-btn-primary"
              onClick={onStartPursuit}
              disabled={!canStartPursuit}
            >
              {canStartPursuit ? "Start this as a pursuit" : "Score this opportunity first"}
            </button>
          ) : null}
        </Section>
      )}

      <Section
        title="What needs to happen next"
        lead={center.next_action.detail}
        aside={
          center.open_work.blocked_count > 0 ? (
            <StatusBadge tone="bad">{center.open_work.blocked_count} blocked</StatusBadge>
          ) : center.open_work.overdue_count > 0 ? (
            <StatusBadge tone="warn">{center.open_work.overdue_count} overdue</StatusBadge>
          ) : (
            <StatusBadge tone="muted">{center.open_work.open_count} open</StatusBadge>
          )
        }
      >
        <p className="nf-command-next">{center.next_action.headline}</p>
        {center.next_action.view ? (
          <button
            type="button"
            className="nf-btn nf-btn-secondary nf-btn-sm"
            onClick={() => onGoTo(center.next_action.view as string)}
          >
            Open that work
          </button>
        ) : null}
        {center.open_work.blockers.length > 0 ? (
          <ul className="nf-command-list">
            {center.open_work.blockers.map((item) => (
              <li key={item.id}>Blocked: {item.title}</li>
            ))}
          </ul>
        ) : null}
        {center.open_work.tasks.slice(0, 5).map((item) => (
          <p key={item.id} className="nf-note">
            {item.title}
            {item.due_at ? ` · due ${item.due_at.slice(0, 10)}` : ""}
          </p>
        ))}
        {center.deadlines.length > 0 ? (
          <ul className="nf-command-list">
            {center.deadlines.map((d) => (
              <li key={`${d.kind}-${d.occurs_at}`}>
                {d.label}
                {d.occurs_at ? ` · ${d.occurs_at.slice(0, 10)}` : ""}
                <span className="nf-note"> ({d.source})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="nf-note">No authoritative deadline is on file for this opportunity.</p>
        )}
      </Section>

      <Section
        title="Funder & grant contacts"
        lead="Who NativeForge can name from the notice or from your records. Missing names are not invented."
      >
        {center.contacts.items.length === 0 ? (
          <p className="nf-note">{center.contacts.empty_message}</p>
        ) : (
          <ul className="nf-command-contacts">
            {center.contacts.items.map((c) => {
              const mark = provenanceTone(c.provenance_kind);
              return (
                <li key={c.id} className="nf-command-contact">
                  <div className="nf-command-contact-head">
                    <strong>{c.name || "Name not stated"}</strong>
                    <StatusBadge tone={mark.tone}>{mark.label}</StatusBadge>
                  </div>
                  <p className="nf-note">
                    {ROLE_LABEL[c.role] || c.role}
                    {c.title ? ` · ${c.title}` : ""}
                    {c.office ? ` · ${c.office}` : ""}
                  </p>
                  {c.email ? (
                    <p>
                      <a href={`mailto:${c.email}`}>{c.email}</a>
                    </p>
                  ) : null}
                  {c.phone ? (
                    <p>
                      <a href={`tel:${c.phone}`}>{c.phone}</a>
                    </p>
                  ) : null}
                  {c.source_section ? (
                    <p className="nf-note">Source: {c.source_section}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section
        title="Questions and communication windows"
        lead="Only facts NativeForge found. A missing date is not a deadline."
      >
        {center.question_intelligence.found ? (
          <ul className="nf-command-list">
            {center.question_intelligence.facts.map((f) => (
              <li key={`${f.kind}-${f.value}`}>
                <strong>{f.label}:</strong> {f.value}
                <span className="nf-note"> ({f.source})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="nf-note">
            No question period, webinar, or applicant conference was identified in the available source materials.
          </p>
        )}
      </Section>

      <Section
        title="Interactions and correspondence"
        lead="What this organization has asked, heard, and still owes. Tenant-private."
      >
        {center.interactions.length === 0 ? (
          <p className="nf-note">No interactions recorded for this pursuit yet.</p>
        ) : (
          <ul className="nf-command-list">
            {center.interactions.map((item) => (
              <li key={item.id}>
                <strong>{TYPE_LABEL[item.interaction_type] || item.interaction_type}</strong>
                {item.subject ? ` — ${item.subject}` : ""}
                <span className="nf-note">
                  {" "}
                  {item.occurred_at ? item.occurred_at.slice(0, 10) : ""} · {item.status}
                  {item.owner_label ? ` · ${item.owner_label}` : ""}
                </span>
                {item.notes ? <p className="nf-note">{item.notes}</p> : null}
                {item.follow_up_at ? (
                  <p className="nf-note">Follow-up {item.follow_up_at.slice(0, 10)}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <form className="nf-command-form" onSubmit={(e) => void save(e)}>
          <label>
            Type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {INTERACTION_TYPES.map((value) => (
                <option key={value} value={value}>
                  {TYPE_LABEL[value]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject
            <input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label>
            Notes
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </label>
          <label>
            Internal owner
            <input value={owner} onChange={(e) => setOwner(e.target.value)} />
          </label>
          <label>
            Follow-up date
            <input
              type="date"
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
            />
          </label>
          {center.contacts.items.length > 0 ? (
            <label>
              Contact
              <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                <option value="">Not specified</option>
                {center.contacts.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.email || ROLE_LABEL[c.role] || c.role}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button type="submit" className="nf-btn nf-btn-primary nf-btn-sm" disabled={saving}>
            {saving ? "Saving…" : "Record interaction"}
          </button>
        </form>
      </Section>

      <Section
        title="What this organization already knows"
        lead={`Prior work with ${center.institutional_memory.funder_agency || "this funder"}, inside this tenant only.`}
      >
        {center.institutional_memory.prior_pursuits.length === 0 &&
        center.institutional_memory.prior_contacts.length === 0 &&
        center.institutional_memory.prior_interactions.length === 0 ? (
          <p className="nf-note">No earlier pursuits or recorded contacts with this funder in this organization.</p>
        ) : (
          <>
            {center.institutional_memory.prior_pursuits.map((p) => (
              <p key={p.grant_spark_id} className="nf-note">
                Prior pursuit: {p.title} ({p.pursuit_status}, {p.source})
              </p>
            ))}
            {center.institutional_memory.prior_contacts.map((c, i) => (
              <p key={`${c.email}-${i}`} className="nf-note">
                Known contact: {c.name || "Unnamed"} · {ROLE_LABEL[c.role] || c.role}
                {c.email ? ` · ${c.email}` : ""} — from {c.from_opportunity}
              </p>
            ))}
            {center.institutional_memory.prior_interactions.map((item) => (
              <p key={item.id} className="nf-note">
                Earlier {TYPE_LABEL[item.interaction_type] || item.interaction_type}
                {item.subject ? `: ${item.subject}` : ""}
                {item.notes ? ` — ${item.notes}` : ""}
              </p>
            ))}
          </>
        )}
      </Section>
    </div>
  );
}
