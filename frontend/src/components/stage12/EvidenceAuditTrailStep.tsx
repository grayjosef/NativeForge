import { str } from "../../stage12GuidedFlowTypes";

interface EvidenceAuditTrailStepProps {
  payload: Record<string, unknown>;
}

export function EvidenceAuditTrailStep({ payload }: EvidenceAuditTrailStepProps) {
  const events = (payload.audit_events as Record<string, unknown>[]) ?? [];
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="evidence-audit-trail"
    >
      <h2 className="nf-card-title">Evidence / audit trail</h2>
      <p className="nf-card-one-liner">
        Synthetic audit preview — local demo namespace only.
      </p>
      <ul className="nf-stage12-list">
        {events.map((e, i) => (
          <li key={`${str(e.step_id)}-${i}`}>
            {str(e.event_type)} · {str(e.step_id)}
            {e.synthetic === true ? (
              <span className="nf-muted"> (synthetic)</span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
