import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import { walkRefsForRow } from "./priorityEvidence";
import { str } from "./workbenchFormat";

export interface AsyncLedgerSummary {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
}

export interface AsyncLedgerList {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
}

interface OperatorLedgerCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  summary: AsyncLedgerSummary;
  list: AsyncLedgerList;
}

export function OperatorLedgerCard({
  baseUrl,
  plane,
  orgId,
  summary,
  list,
}: OperatorLedgerCardProps) {
  const loading = summary.loading || list.loading;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-ledger-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-ledger-heading" className="nf-card-title">
          Open operator ledger actions
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Open rows from the operator actions ledger (read-only in this view).
      </p>
      {loading ? (
        <p className="nf-muted">Loading ledger…</p>
      ) : (
        <>
          {summary.error ? (
            <div className="nf-alert nf-alert--error" role="alert">
              Ledger summary: {summary.error}
            </div>
          ) : null}
          {list.error ? (
            <div className="nf-alert nf-alert--error" role="alert">
              Open actions list: {list.error}
            </div>
          ) : null}
          <LedgerBody
            baseUrl={baseUrl}
            plane={plane}
            orgId={orgId}
            summary={summary.data}
            list={list.data}
          />
        </>
      )}
    </section>
  );
}

function LedgerBody({
  baseUrl,
  plane,
  orgId,
  summary,
  list,
}: {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  summary: Record<string, unknown> | null;
  list: Record<string, unknown> | null;
}) {
  const openCount =
    summary && summary.open_operator_actions != null
      ? Number(summary.open_operator_actions)
      : null;
  const actionsRaw = list?.operator_actions;
  const rows =
    list && Array.isArray(actionsRaw)
      ? (actionsRaw as Record<string, unknown>[])
      : [];

  return (
    <>
      {summary &&
      typeof openCount === "number" &&
      !Number.isNaN(openCount) ? (
        <p className="nf-card-summary">
          <strong>{openCount}</strong> open operator{" "}
          {openCount === 1 ? "action" : "actions"} (summary).
        </p>
      ) : null}
      {!list ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">Could not load open actions.</p>
        </div>
      ) : rows.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No open operator actions.</p>
        </div>
      ) : (
        <div className="nf-wb-table-wrap">
          <table className="nf-wb-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Severity</th>
                <th>Assigned</th>
                <th>Due</th>
                <th>Title</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const id = str(r.id);
                const title = str(r.action_title ?? r.title);
                return (
                  <tr key={id || title}>
                    <td>{str(r.status)}</td>
                    <td>{str(r.severity)}</td>
                    <td>{str(r.assigned_to) || "—"}</td>
                    <td>{str(r.due_at) || "—"}</td>
                    <td>{title || "—"}</td>
                    <td className="nf-wb-td-evidence">
                      {looksLikeUuid(id) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="operator-actions"
                          id={id}
                        >
                          JSON
                        </EvidenceJsonLink>
                      ) : (
                        "—"
                      )}
                      {walkRefsForRow(r.refs).map((l) => (
                        <EvidenceJsonLink
                          key={l.key}
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind={l.kind}
                          id={l.id}
                        >
                          {l.short}
                        </EvidenceJsonLink>
                      ))}
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
