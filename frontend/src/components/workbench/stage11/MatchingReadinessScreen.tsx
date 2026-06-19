import { WorkbenchStateBadges } from "../WorkbenchStateBadges";
import { str } from "../workbenchFormat";
import type { AsyncList } from "../stage11Types";

export function MatchingReadinessScreen({
  advisoryBundle,
}: {
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
}) {
  const block = advisoryBundle.data?.matching_readiness_preview as
    | Record<string, unknown>
    | undefined;
  const records = (block?.records as Record<string, unknown>[] | undefined) ?? [];

  return (
    <section className="nf-card nf-card-pad nf-wb-screen" data-screen="matching-readiness">
      <h2 className="nf-card-title">Matching + readiness</h2>
      <p className="nf-card-one-liner">
        Fit dimensions, blockers, missing data, and next actions — consumes canonical{" "}
        <code>eligibility_fit_assessment_*</code> layer (no duplicate scoring).
      </p>
      {advisoryBundle.loading ? (
        <p className="nf-muted">Loading matching + readiness preview…</p>
      ) : advisoryBundle.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {advisoryBundle.error}
        </div>
      ) : (
        <div className="nf-wb-stack">
          {records.map((r) => {
            const match = r.match_evaluation as Record<string, unknown> | undefined;
            const readiness = r.readiness_evaluation as Record<string, unknown> | undefined;
            const dims = match?.match_dimensions as Record<string, unknown> | undefined;
            const blockers = dims?.blockers as Record<string, unknown> | undefined;
            const missing = dims?.missing_data as Record<string, unknown> | undefined;
            const recGuard = match?.applicant_recommendation_guard as
              | Record<string, unknown>
              | undefined;
            const eligGuard = readiness?.eligibility_guard as
              | Record<string, unknown>
              | undefined;
            return (
              <article key={str(r.fixture_key)} className="nf-wb-preview-card">
                <h3 className="nf-wb-preview-title">{str(r.fixture_key)}</h3>
                <WorkbenchStateBadges
                  matchLabel={str(r.match_label)}
                  readinessLabel={str(r.readiness_label)}
                  humanReviewRequired={recGuard?.recommendation_blocked === true}
                  claimBlocked={eligGuard?.eligibility_blocked === true}
                />
                <dl className="nf-wb-dl">
                  <dt>Blockers</dt>
                  <dd>
                    {((blockers?.blocker_codes as string[]) ?? []).join(", ") || "none"}
                  </dd>
                  <dt>Missing data</dt>
                  <dd>
                    {((missing?.missing_data_flags as string[]) ?? []).join(", ") ||
                      "none"}
                  </dd>
                  <dt>Next actions</dt>
                  <dd>
                    {((r.next_actions as Record<string, unknown>[]) ?? [])
                      .map((a) => str(a.topic))
                      .join(", ") || "—"}
                  </dd>
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
