import { StateView } from "../components/StateView";
import type { CustomerState } from "../customerState";
import {
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
  type BadgeTone,
} from "../components/ui/primitives";

/**
 * Trust: what is actually true about how NativeForge handles an
 * organization's data.
 *
 * ## No certifications are claimed
 *
 * Not FedRAMP, not SOC 2, not StateRAMP, not CMMC, not "HIPAA compliant". A
 * page like this is where such claims get made, because they are what a buyer
 * asks about and because a badge is easy to draw. NativeForge holds none of
 * them, and an unverified claim on this page would be the most consequential
 * false statement in the product - it is the page a Tribal government's
 * counsel would read.
 *
 * What is stated instead is the set of properties the system genuinely has,
 * each of which is enforced somewhere in the codebase rather than asserted
 * here: tenant separation by row-level security, an append-only audit trail,
 * export on demand, and a human review step before anything is filed.
 *
 * ## Facts carry their own source
 *
 * Each item says where it is enforced. "Tenant separation" with nothing
 * behind it is marketing; "enforced by PostgreSQL row-level security on every
 * tenant table" is a claim somebody can check, and one a reviewer can ask us
 * to demonstrate.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

interface Fact {
  title: string;
  body: string;
  badge: string;
  tone: BadgeTone;
}

const FACTS: Fact[] = [
  {
    title: "Your data is yours",
    body: "Everything your organization puts into NativeForge can be exported in full, at any time, without asking us. The export includes your profile, opportunities, requirements, pursuits and audit history.",
    badge: "Export on demand",
    tone: "positive",
  },
  {
    title: "Organizations are separated in the database",
    body: "Tenant separation is enforced by PostgreSQL row-level security on every tenant table, not by application code remembering to filter. The application connects as a role that cannot bypass those policies.",
    badge: "Enforced in storage",
    tone: "positive",
  },
  {
    title: "Nothing is submitted on your behalf",
    body: "NativeForge prepares application packages for your team to review. It does not file to Grants.gov and has no credential that would let it.",
    badge: "No auto-submit",
    tone: "positive",
  },
  {
    title: "Conclusions carry their evidence",
    body: "Requirements are extracted from notice text with the location they came from. Where a document could not be read, NativeForge reports it as unread rather than treating its silence as an answer.",
    badge: "Provenance kept",
    tone: "positive",
  },
  {
    title: "Actions are recorded",
    body: "Scoring, extraction, pursuit changes and exports are written to an audit trail scoped to your organization.",
    badge: "Audit trail",
    tone: "positive",
  },
  {
    title: "No compliance certification is claimed",
    body: "NativeForge does not hold FedRAMP, SOC 2 or any other third-party certification, and does not represent itself as holding one. If your procurement requires a certification, tell us which and we will answer honestly.",
    badge: "Stated plainly",
    tone: "muted",
  },
];

export interface TrustPageProps {
  manifest: Record<string, unknown> | null;
  auditCount: number | null;
  reviewSummary: Record<string, unknown> | null;
  exportHint: string | null;
  busy: boolean;
  error: CustomerState | null;
  onRefresh: () => void;
  onExport: () => void;
}

export function TrustPage(props: TrustPageProps) {
  const { manifest, auditCount, reviewSummary, exportHint, busy, error, onRefresh, onExport } =
    props;

  const pending =
    reviewSummary && typeof reviewSummary.pending_count === "number"
      ? (reviewSummary.pending_count as number)
      : null;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Govern"
        title="Trust"
        lead="How NativeForge handles your organization's data, and what it will not claim."
        actions={
          <>
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onRefresh}
              disabled={busy}
            >
              Refresh
            </button>
            <button
              type="button"
              className="nf-btn nf-btn-primary nf-btn-sm"
              onClick={onExport}
              disabled={busy}
            >
              Export everything
            </button>
          </>
        }
      />

      {error ? <StateView state={error} /> : null}
      {exportHint ? (
        <StateView
          state={{ tone: "success", title: "Export ready", body: exportHint }}
          inline
        />
      ) : null}

      <Section title="Operational facts" lead="Each of these is enforced, not asserted.">
        <ul className="nf-fact-list">
          {FACTS.map((f) => (
            <li key={f.title} className="nf-fact">
              <div className="nf-fact-head">
                <p className="nf-fact-title">{f.title}</p>
                <StatusBadge tone={f.tone}>{f.badge}</StatusBadge>
              </div>
              <p className="nf-fact-body">{f.body}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Your organization's record" lead="Measured now, for your organization only.">
        <MetricRow>
          <MetricCard
            label="Audit events"
            value={auditCount === null ? "—" : String(auditCount)}
            note={auditCount === null ? "Not loaded" : "Recorded actions"}
          />
          <MetricCard
            label="Awaiting human review"
            value={pending === null ? "—" : String(pending)}
            tone={pending && pending > 0 ? "warn" : "muted"}
            note={pending === null ? "Review summary not loaded" : undefined}
          />
          <MetricCard
            label="Data manifest"
            value={manifest ? str(manifest.manifest_schema_version) || "Current" : "—"}
            note={manifest ? "Describes what is stored about you" : "Not loaded"}
          />
          <MetricCard
            label="Third-party certifications"
            value="None"
            tone="muted"
            note="NativeForge claims none"
          />
        </MetricRow>
      </Section>
    </div>
  );
}
