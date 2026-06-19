import { WorkbenchStateBadges, extractUnknownCount } from "../WorkbenchStateBadges";
import { str } from "../workbenchFormat";
import type { AsyncList } from "../stage11Types";

export function OrgApplicantProfileScreen({
  advisoryBundle,
}: {
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
}) {
  const block = advisoryBundle.data?.org_applicant_profile_preview as
    | Record<string, unknown>
    | undefined;
  const previews = (block?.previews as Record<string, unknown>[] | undefined) ?? [];

  return (
    <section className="nf-card nf-card-pad nf-wb-screen" data-screen="org-applicant-profile">
      <h2 className="nf-card-title">Org / applicant profile</h2>
      <p className="nf-card-one-liner">
        Provenance-first profile view — UNKNOWN fields and review status shown honestly.
        Nothing reaches verified without explicit operator action.
      </p>
      {advisoryBundle.loading ? (
        <p className="nf-muted">Loading profile preview…</p>
      ) : advisoryBundle.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {advisoryBundle.error}
        </div>
      ) : (
        <div className="nf-wb-stack">
          {previews.map((p) => (
            <article key={str(p.fixture_key)} className="nf-wb-preview-card">
              <h3 className="nf-wb-preview-title">{str(p.fixture_key)}</h3>
              <WorkbenchStateBadges
                humanReviewRequired={p.human_review_required === true}
                unknownFieldCount={extractUnknownCount(p)}
              />
              <dl className="nf-wb-dl">
                <dt>Review status</dt>
                <dd>{str(p.review_status) || "—"}</dd>
                <dt>Application readiness</dt>
                <dd>{str(p.application_readiness) || "—"}</dd>
                <dt>Legal name</dt>
                <dd>
                  {str(
                    (p.profile_record as Record<string, unknown> | undefined)
                      ?.profile_fields
                      ? ((p.profile_record as Record<string, unknown>)
                          .profile_fields as Record<string, unknown>)?.legal_name
                      : undefined,
                  ) || "UNKNOWN"}
                </dd>
              </dl>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
