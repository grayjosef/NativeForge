import { useMemo, useState } from "react";

import { ActivationReadinessPreviewStep } from "./ActivationReadinessPreviewStep";
import { EvidenceAuditTrailStep } from "./EvidenceAuditTrailStep";
import { NativeRelevanceStep } from "./NativeRelevanceStep";
import { OperatorDecisionStep } from "./OperatorDecisionStep";
import { OpportunityIntakeStep } from "./OpportunityIntakeStep";
import { ProfileMatchReadinessStep } from "./ProfileMatchReadinessStep";
import { SourceDiscoveryStep } from "./SourceDiscoveryStep";
import { SourceQualityReviewStep } from "./SourceQualityReviewStep";
import { Stage12GuidedStepper } from "./Stage12GuidedStepper";
import {
  STAGE12_STEPS,
  type AsyncBlock,
  type Stage12StepId,
  str,
} from "../../stage12GuidedFlowTypes";

export interface Stage12GuidedDemoProps {
  guidedPath: AsyncBlock<Record<string, unknown> | null>;
  onReset?: () => void;
}

export function Stage12GuidedDemo({ guidedPath, onReset }: Stage12GuidedDemoProps) {
  const [step, setStep] = useState<Stage12StepId>("source-discovery");
  const { loading, error, data } = guidedPath;

  const stepMap = useMemo(() => {
    const map = new Map<Stage12StepId, Record<string, unknown>>();
    if (!data) {
      return map;
    }
    const steps = (data.steps as Record<string, unknown>[]) ?? [];
    for (const s of steps) {
      const id = str(s.step_id) as Stage12StepId;
      map.set(id, (s.payload as Record<string, unknown>) ?? {});
    }
    return map;
  }, [data]);

  if (loading) {
    return <p className="nf-muted">Loading Stage 12 guided demo path…</p>;
  }
  if (error) {
    return (
      <div className="nf-alert nf-alert--error" role="alert">
        {error}
      </div>
    );
  }
  if (!data) {
    return <p className="nf-muted">No guided demo path available.</p>;
  }

  const payload = stepMap.get(step) ?? {};

  return (
    <div className="nf-stage12-guided" data-nf-stage12-demo="1">
      <header className="nf-stage12-header">
        <h1 className="nf-stage12-title">Future-state demo path (Stage 12)</h1>
        <p className="nf-muted">
          Isolated fictional dataset · preview only · no activation execution
        </p>
        {onReset ? (
          <button type="button" className="nf-btn nf-btn-secondary" onClick={onReset}>
            Reset guided demo
          </button>
        ) : null}
      </header>
      <Stage12GuidedStepper current={step} onSelect={setStep} steps={STAGE12_STEPS} />
      <div className="nf-stage12-step-panel">
        {step === "source-discovery" ? <SourceDiscoveryStep payload={payload} /> : null}
        {step === "source-quality-review" ? (
          <SourceQualityReviewStep payload={payload} />
        ) : null}
        {step === "activation-readiness-preview" ? (
          <ActivationReadinessPreviewStep payload={payload} />
        ) : null}
        {step === "opportunity-intake" ? <OpportunityIntakeStep payload={payload} /> : null}
        {step === "native-relevance-review" ? <NativeRelevanceStep payload={payload} /> : null}
        {step === "profile-match-readiness" ? (
          <ProfileMatchReadinessStep payload={payload} />
        ) : null}
        {step === "operator-decision" ? <OperatorDecisionStep payload={payload} /> : null}
        {step === "evidence-audit-trail" ? <EvidenceAuditTrailStep payload={payload} /> : null}
      </div>
    </div>
  );
}
