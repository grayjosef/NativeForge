import { str } from "../workbenchFormat";
import type { AsyncList } from "../stage11Types";

export function DiscoveryIntakeReviewScreen({
  advisoryBundle,
}: {
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
}) {
  const intake = advisoryBundle.data?.intake_preview as
    | Record<string, unknown>
    | undefined;
  const previews = (intake?.previews as Record<string, unknown>[] | undefined) ?? [];

  return (
    <section className="nf-card nf-card-pad nf-wb-screen" data-screen="discovery-intake-review">
      <h2 className="nf-card-title">Discovery / intake review</h2>
      <p className="nf-card-one-liner">
        Stage 5 hardened opportunity previews (synthetic fixtures, advisory only).
      </p>
      {advisoryBundle.loading ? (
        <p className="nf-muted">Loading intake advisory preview…</p>
      ) : advisoryBundle.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {advisoryBundle.error}
        </div>
      ) : previews.length === 0 ? (
        <p className="nf-muted">No intake previews in advisory bundle.</p>
      ) : (
        <ul className="nf-wb-list">
          {previews.map((p) => (
            <li key={str(p.fixture_key)}>
              <strong>{str(p.fixture_key)}</strong>
              {" — intake status: "}
              {str(
                (p.intake_status as Record<string, unknown> | undefined)?.status ??
                  (p as Record<string, unknown>).status,
              ) || "preview"}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
