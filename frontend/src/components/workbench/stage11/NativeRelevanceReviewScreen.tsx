import { WorkbenchStateBadges, extractOverclaimBlocked } from "../WorkbenchStateBadges";
import { str } from "../workbenchFormat";
import type { AsyncList } from "../stage11Types";

const EIGHT_LABELS = [
  "native_specific",
  "tribal_government_specific",
  "indigenous_community_relevant",
  "native_entity_eligible_broad",
  "broadly_eligible_potentially_relevant",
  "weak_native_relevance",
  "uncertain_relevance",
  "irrelevant",
];

export function NativeRelevanceReviewScreen({
  advisoryBundle,
}: {
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
}) {
  const block = advisoryBundle.data?.native_relevance_preview as
    | Record<string, unknown>
    | undefined;
  const previews = (block?.previews as Record<string, unknown>[] | undefined) ?? [];

  return (
    <section className="nf-card nf-card-pad nf-wb-screen" data-screen="native-relevance-review">
      <h2 className="nf-card-title">Native relevance review</h2>
      <p className="nf-card-one-liner">
        Evidence-based labels ({EIGHT_LABELS.length} labels) + confidence — presentation
        only; no scoring changes.
      </p>
      {advisoryBundle.loading ? (
        <p className="nf-muted">Loading native relevance preview…</p>
      ) : advisoryBundle.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {advisoryBundle.error}
        </div>
      ) : (
        <div className="nf-wb-stack">
          {previews.map((p) => {
            const cls = p.classification as Record<string, unknown> | undefined;
            const expl = p.explanation as Record<string, unknown> | undefined;
            return (
              <article key={str(p.fixture_key)} className="nf-wb-preview-card">
                <h3 className="nf-wb-preview-title">{str(p.fixture_key)}</h3>
                <WorkbenchStateBadges
                  matchLabel={str(cls?.classification_label)}
                  humanReviewRequired={cls?.human_review_required === true}
                  overclaimBlocked={extractOverclaimBlocked(p)}
                />
                <dl className="nf-wb-dl">
                  <dt>Label</dt>
                  <dd>{str(cls?.classification_label) || "—"}</dd>
                  <dt>Confidence</dt>
                  <dd>{str(cls?.confidence) || "—"}</dd>
                  <dt>Operator next check</dt>
                  <dd>{str(expl?.operator_next_check) || "—"}</dd>
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
