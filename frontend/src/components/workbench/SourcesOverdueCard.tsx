import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import { str } from "./workbenchFormat";

interface SourcesOverdueCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  overdue: {
    loading: boolean;
    error: string | null;
    data: Record<string, unknown>[] | null;
  };
  freshness: {
    loading: boolean;
    error: string | null;
    data: Record<string, unknown> | null;
  };
}

export function SourcesOverdueCard({
  baseUrl,
  plane,
  orgId,
  overdue,
  freshness,
}: SourcesOverdueCardProps) {
  const loading = overdue.loading || freshness.loading;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-sources-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-sources-heading" className="nf-card-title">
          Overdue / failing sources
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Sources past check windows plus a freshness summary from the engine.
      </p>
      {loading ? (
        <p className="nf-muted">Loading source health…</p>
      ) : (
        <SourcesBody
          baseUrl={baseUrl}
          plane={plane}
          orgId={orgId}
          overdueBlock={overdue}
          freshnessBlock={freshness}
        />
      )}
    </section>
  );
}

function SourcesBody({
  baseUrl,
  plane,
  orgId,
  overdueBlock,
  freshnessBlock,
}: {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  overdueBlock: SourcesOverdueCardProps["overdue"];
  freshnessBlock: SourcesOverdueCardProps["freshness"];
}) {
  const overdueList = overdueBlock.data ?? [];
  const fresh = freshnessBlock.data;
  const healthMap =
    fresh && typeof fresh.by_source_health_status === "object"
      ? (fresh.by_source_health_status as Record<string, unknown>)
      : null;

  return (
    <>
      {freshnessBlock.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          Freshness summary: {freshnessBlock.error}
        </div>
      ) : null}
      {fresh ? (
        <dl className="nf-dl nf-dl-tight nf-wb-freshness">
          <div>
            <dt>Active sources</dt>
            <dd>{str(fresh.active_source_count) || "—"}</dd>
          </div>
          <div>
            <dt>Overdue (summary)</dt>
            <dd>{str(fresh.overdue_count) || "—"}</dd>
          </div>
          <div>
            <dt>Due for check</dt>
            <dd>{str(fresh.due_for_check_count) || "—"}</dd>
          </div>
        </dl>
      ) : null}
      {healthMap ? (
        <div className="nf-wb-kv-block">
          <p className="nf-muted nf-wb-kv-label">By health status</p>
          <ul className="nf-wb-kv-list">
            {Object.entries(healthMap).map(([k, v]) => (
              <li key={k}>
                <code className="nf-code-inline">{k}</code> · {str(v)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {overdueBlock.error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          Overdue sources: {overdueBlock.error}
        </div>
      ) : null}
      {!overdueBlock.error && overdueList.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No overdue sources.</p>
          <p className="nf-empty-hint">
            When checks slip past their window, they appear here with schedule
            metadata.
          </p>
        </div>
      ) : overdueBlock.error ? null : (
        <div className="nf-wb-table-wrap">
          <table className="nf-wb-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Health</th>
                <th>Last check</th>
                <th>Next due</th>
                <th>Failures</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {overdueList.map((s) => {
                const id = str(s.id);
                const name = str(s.source_name);
                return (
                  <tr key={id || name}>
                    <td>{name || "—"}</td>
                    <td>{str(s.source_health_status) || "—"}</td>
                    <td>{str(s.last_checked_at) || "—"}</td>
                    <td>{str(s.next_check_due_at) || "—"}</td>
                    <td>{str(s.consecutive_failure_count ?? "0")}</td>
                    <td>
                      {looksLikeUuid(id) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="sources"
                          id={id}
                        >
                          JSON
                        </EvidenceJsonLink>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
