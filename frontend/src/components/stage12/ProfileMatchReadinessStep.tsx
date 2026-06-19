import { WorkbenchStateBadges } from "../workbench/WorkbenchStateBadges";
import { str } from "../../stage12GuidedFlowTypes";

interface ProfileMatchReadinessStepProps {
  payload: Record<string, unknown>;
}

export function ProfileMatchReadinessStep({ payload }: ProfileMatchReadinessStepProps) {
  const profile = (payload.profile_preview as Record<string, unknown>) ?? {};
  const records = (payload.match_records as Record<string, unknown>[]) ?? [];
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="profile-match-readiness"
    >
      <h2 className="nf-card-title">Profile match + readiness</h2>
      <p className="nf-card-one-liner">
        Canonical readiness_label — no final eligibility without operator review.
      </p>
      <div className="nf-stage12-profile-summary">
        <p>
          <strong>{str(profile.fixture_key)}</strong>
        </p>
        <WorkbenchStateBadges
          humanReviewRequired={profile.human_review_required === true}
          readinessLabel={str(profile.readiness_label)}
          unknownFieldCount={
            ((profile.evaluation as Record<string, unknown>) ?? {}).unknown_field_count as
              | number
              | undefined
          }
        />
      </div>
      <ul className="nf-stage12-list">
        {records.map((r) => (
          <li key={str(r.fixture_key)}>
            {str(r.fixture_key)} — match: {str(r.match_label)}, readiness:{" "}
            {str(r.readiness_label)}
          </li>
        ))}
      </ul>
    </section>
  );
}
