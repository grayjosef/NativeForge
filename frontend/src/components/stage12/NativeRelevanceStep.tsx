import { WorkbenchStateBadges } from "../workbench/WorkbenchStateBadges";
import { str } from "../../stage12GuidedFlowTypes";

interface NativeRelevanceStepProps {
  payload: Record<string, unknown>;
}

export function NativeRelevanceStep({ payload }: NativeRelevanceStepProps) {
  const previews = (payload.relevance_previews as Record<string, unknown>[]) ?? [];
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="native-relevance-review"
    >
      <h2 className="nf-card-title">Native relevance review</h2>
      <p className="nf-card-one-liner">
        Evidence + labels — broad vs native-specific surfaced honestly.
      </p>
      <ul className="nf-stage12-list">
        {previews.map((p) => {
          const cls = (p.classification as Record<string, unknown>) ?? {};
          return (
            <li key={str(p.fixture_key)}>
              <strong>{str(p.fixture_key)}</strong>
              <WorkbenchStateBadges
                humanReviewRequired={cls.human_review_required === true}
                matchLabel={str(cls.classification_label)}
                overclaimBlocked={
                  ((cls.overclaim_guard as Record<string, unknown>) ?? {})
                    .overclaim_blocked === true
                }
              />
              <span className="nf-muted"> confidence: {str(cls.confidence)}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
