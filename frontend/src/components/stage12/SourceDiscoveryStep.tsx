import { str } from "../../stage12GuidedFlowTypes";

interface SourceDiscoveryStepProps {
  payload: Record<string, unknown>;
}

export function SourceDiscoveryStep({ payload }: SourceDiscoveryStepProps) {
  const sources = (payload.sources as Record<string, unknown>[]) ?? [];
  return (
    <section className="nf-card nf-card-pad nf-stage12-step" data-step="source-discovery">
      <h2 className="nf-card-title">Source discovery</h2>
      <p className="nf-card-one-liner">
        Fictional namespaced demo sources — isolated from production data.
      </p>
      <ul className="nf-stage12-list">
        {sources.map((s) => (
          <li key={str(s.fixture_key)}>
            <strong>{str(s.source_name)}</strong>
            <span className="nf-muted"> · {str(s.source_type)} · {str(s.quality_posture)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
