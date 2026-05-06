import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import { walkRowEvidenceLinks } from "./priorityEvidence";
import { str } from "./workbenchFormat";

export interface AsyncList<T = unknown> {
  loading: boolean;
  error: string | null;
  data: T;
}

interface ReviewQueueCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  block: AsyncList<Record<string, unknown>[] | null>;
}

export function ReviewQueueCard({
  baseUrl,
  plane,
  orgId,
  block,
}: ReviewQueueCardProps) {
  const { loading, error, data } = block;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-review-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-review-heading" className="nf-card-title">
          Review queue snapshot
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Open discovery review items (queued work for operators).
      </p>
      {loading ? (
        <p className="nf-muted">Loading review queue…</p>
      ) : error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">
            No review items currently queued.
          </p>
        </div>
      ) : (
        <div className="nf-wb-table-wrap">
          <table className="nf-wb-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Recommended</th>
                <th>Priority</th>
                <th>Links</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => {
                const id = str(r.id);
                const ty = str(r.review_item_type);
                const rec = str(
                  r.recommended_action ??
                    r.recommended_operator_action ??
                    r.suggested_action,
                );
                const pri = str(r.priority ?? r.severity);
                const spark = r.grant_spark_id;
                const src = r.source_registry_id;
                const cand = r.intake_candidate_id;
                return (
                  <tr key={id || ty}>
                    <td>{ty || "—"}</td>
                    <td>{str(r.review_status ?? r.status)}</td>
                    <td>{rec || "—"}</td>
                    <td>{pri || "—"}</td>
                    <td className="nf-wb-td-links">
                      <span className="nf-wb-inline-meta">
                        {looksLikeUuid(spark)
                          ? `Spark ${String(spark).slice(0, 8)}…`
                          : ""}
                        {looksLikeUuid(src)
                          ? ` Source ${String(src).slice(0, 8)}…`
                          : ""}
                        {looksLikeUuid(cand)
                          ? ` Candidate ${String(cand).slice(0, 8)}…`
                          : ""}
                      </span>
                      <div className="nf-wb-evidence-row">
                        {looksLikeUuid(id) ? (
                          <EvidenceJsonLink
                            baseUrl={baseUrl}
                            plane={plane}
                            orgId={orgId}
                            kind="review-items"
                            id={id}
                          >
                            Evidence · item
                          </EvidenceJsonLink>
                        ) : null}
                        {walkRowEvidenceLinks(r).map((l) => (
                          <EvidenceJsonLink
                            key={l.key}
                            baseUrl={baseUrl}
                            plane={plane}
                            orgId={orgId}
                            kind={l.kind}
                            id={l.id}
                          >
                            Evidence · {l.short}
                          </EvidenceJsonLink>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
