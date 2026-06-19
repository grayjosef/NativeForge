import type { Plane } from "../../../m0Flow";
import { EvidenceJsonLink } from "../EvidenceJsonLink";
import { looksLikeUuid } from "../evidenceUrls";
import { str } from "../workbenchFormat";
import type { AsyncList } from "../stage11Types";

interface SourceReviewQueueScreenProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  reviewItems: AsyncList<Record<string, unknown>[] | null>;
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
}

export function SourceReviewQueueScreen({
  baseUrl,
  plane,
  orgId,
  reviewItems,
  advisoryBundle,
}: SourceReviewQueueScreenProps) {
  const { loading, error, data } = reviewItems;

  return (
    <section className="nf-card nf-card-pad nf-wb-screen" data-screen="source-review-queue">
      <h2 className="nf-card-title">Source review queue</h2>
      <p className="nf-card-one-liner">
        Open discovery review items from the local database (read-only).
      </p>
      {advisoryBundle.data ? (
        <p className="nf-muted nf-wb-advisory-hint">
          Advisory bundle loaded — synthetic intake previews available in Discovery
          intake tab.
        </p>
      ) : null}
      {loading ? (
        <p className="nf-muted">Loading review queue…</p>
      ) : error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : !data || data.length === 0 ? (
        <p className="nf-muted">No review items currently queued.</p>
      ) : (
        <table className="nf-wb-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={str(r.id)}>
                <td>{str(r.review_item_type) || "—"}</td>
                <td>{str(r.queue_status) || str(r.status) || "—"}</td>
                <td>{str(r.priority ?? r.severity) || "—"}</td>
                <td>
                  {looksLikeUuid(r.id) ? (
                    <EvidenceJsonLink
                      baseUrl={baseUrl}
                      plane={plane}
                      orgId={orgId}
                      kind="review-items"
                      id={str(r.id)}
                    >
                      Evidence · item
                    </EvidenceJsonLink>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
