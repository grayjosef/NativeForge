import { str } from "../../stage12GuidedFlowTypes";

interface OpportunityIntakeStepProps {
  payload: Record<string, unknown>;
}

export function OpportunityIntakeStep({ payload }: OpportunityIntakeStepProps) {
  const previews = (payload.intake_previews as Record<string, unknown>[]) ?? [];
  const stale = (payload.stale_opportunities_shown as string[]) ?? [];
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="opportunity-intake"
    >
      <h2 className="nf-card-title">Opportunity intake</h2>
      <p className="nf-card-one-liner">
        Four fictional opportunities — stale/expired shown honestly.
      </p>
      <ul className="nf-stage12-list">
        {previews.map((p) => {
          const rec = (p.opportunity_record as Record<string, unknown>) ?? p;
          const fk = str(rec.fixture_key ?? p.fixture_key);
          const isStale = stale.includes(fk);
          return (
            <li key={fk}>
              <strong>{str(rec.opportunity_title ?? fk)}</strong>
              {isStale ? (
                <span className="nf-badge nf-badge--warn">stale / expired</span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
