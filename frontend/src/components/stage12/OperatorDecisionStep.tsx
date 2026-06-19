import { WorkbenchStateBadges } from "../workbench/WorkbenchStateBadges";
import { str } from "../../stage12GuidedFlowTypes";

interface OperatorDecisionStepProps {
  payload: Record<string, unknown>;
}

export function OperatorDecisionStep({ payload }: OperatorDecisionStepProps) {
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="operator-decision"
    >
      <h2 className="nf-card-title">Operator decision</h2>
      <p className="nf-card-one-liner">
        Nothing reaches verified/approved without explicit operator action.
      </p>
      <dl className="nf-stage12-dl">
        <dt>Primary opportunity</dt>
        <dd>{str(payload.primary_opportunity_fixture_key)}</dd>
        <dt>Match label</dt>
        <dd>{str(payload.match_label)}</dd>
        <dt>Readiness label</dt>
        <dd>{str(payload.readiness_label)}</dd>
        <dt>Verified / approved</dt>
        <dd>{payload.verified_or_approved === true ? "yes" : "no — operator required"}</dd>
      </dl>
      <WorkbenchStateBadges
        humanReviewRequired={payload.needs_operator_review === true}
        matchLabel={str(payload.match_label)}
      />
    </section>
  );
}
