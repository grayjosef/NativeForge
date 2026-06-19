import { str } from "../../stage12GuidedFlowTypes";

interface ActivationReadinessPreviewStepProps {
  payload: Record<string, unknown>;
}

export function ActivationReadinessPreviewStep({
  payload,
}: ActivationReadinessPreviewStepProps) {
  const previews = (payload.source_previews as Record<string, unknown>[]) ?? [];
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="activation-readiness-preview"
    >
      <h2 className="nf-card-title">Activation readiness (preview only)</h2>
      <p className="nf-card-one-liner nf-alert nf-alert--info">
        Preview only — no source activation execution. Human gate required.
      </p>
      <ul className="nf-stage12-list">
        {previews.map((p) => (
          <li key={str(p.source_fixture_key)}>
            <strong>{str(p.source_name)}</strong>
            <span className="nf-muted">
              {" "}
              · readiness: {str(p.activation_readiness_preview)}
              {p.may_activate_now === false ? " · blocked" : ""}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
