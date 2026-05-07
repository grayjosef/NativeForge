import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import { str } from "./workbenchFormat";

export interface ConnectorIntelBlock {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
}

interface ConnectorIntelligenceCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  block: ConnectorIntelBlock;
}

function num(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) {
    return String(v);
  }
  return str(v) || "—";
}

export function ConnectorIntelligenceCard({
  baseUrl,
  plane,
  orgId,
  block,
}: ConnectorIntelligenceCardProps) {
  const { loading, error, data } = block;
  const raw = data?.connector_intelligence;
  const ci =
    raw && typeof raw === "object"
      ? (raw as Record<string, unknown>)
      : null;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-connector-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-connector-heading" className="nf-card-title">
          Connector &amp; source-check intelligence
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Latest connector summaries stored on source-check runs: health, warnings,
        escalation hints, and intake pressure signals (offline / deterministic).
      </p>
      {loading ? (
        <p className="nf-muted">Loading connector intelligence…</p>
      ) : error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : !data ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No decision pack loaded.</p>
        </div>
      ) : !ci ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No connector intelligence block.</p>
          <p className="nf-empty-hint">
            Run a connector-backed source check to populate summaries.
          </p>
        </div>
      ) : (
        <ConnectorIntelBody
          baseUrl={baseUrl}
          plane={plane}
          orgId={orgId}
          ci={ci}
        />
      )}
    </section>
  );
}

function ConnectorIntelBody({
  baseUrl,
  plane,
  orgId,
  ci,
}: {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  ci: Record<string, unknown>;
}) {
  const rollup =
    ci.rollup && typeof ci.rollup === "object"
      ? (ci.rollup as Record<string, unknown>)
      : null;
  const ch =
    rollup?.connector_health_counts &&
    typeof rollup.connector_health_counts === "object"
      ? (rollup.connector_health_counts as Record<string, unknown>)
      : null;
  const warnings = Array.isArray(rollup?.warning_codes_ranked)
    ? (rollup.warning_codes_ranked as Record<string, unknown>[])
    : [];
  const flat = Array.isArray(ci.operator_escalation_recommendations_flat)
    ? (ci.operator_escalation_recommendations_flat as Record<string, unknown>[])
    : [];
  const perSource = Array.isArray(ci.per_source_latest_connector_run)
    ? (ci.per_source_latest_connector_run as Record<string, unknown>[])
    : [];

  return (
    <>
      {rollup ? (
        <dl className="nf-dl nf-dl-tight nf-wb-freshness">
          <div>
            <dt>Registry · degraded</dt>
            <dd>{num(rollup.registry_sources_degraded)}</dd>
          </div>
          <div>
            <dt>Registry · failing</dt>
            <dd>{num(rollup.registry_sources_failing)}</dd>
          </div>
          <div>
            <dt>Registry · stale</dt>
            <dd>{num(rollup.registry_sources_stale)}</dd>
          </div>
          <div>
            <dt>Sources w/ connector summary</dt>
            <dd>{num(rollup.sources_with_connector_summaries)}</dd>
          </div>
          <div>
            <dt>Empty connector runs</dt>
            <dd>{num(rollup.empty_connector_runs)}</dd>
          </div>
          <div>
            <dt>Duplicate-heavy sources</dt>
            <dd>{num(rollup.duplicate_heavy_sources)}</dd>
          </div>
          <div>
            <dt>Review-required pressure</dt>
            <dd>{num(rollup.review_required_heavy_sources)}</dd>
          </div>
          <div>
            <dt>Escalation rows (latest checks)</dt>
            <dd>{num(rollup.operator_escalation_rows_total)}</dd>
          </div>
        </dl>
      ) : null}

      {ch ? (
        <div className="nf-wb-kv-block">
          <p className="nf-muted nf-wb-kv-label">Latest connector health (per source)</p>
          <ul className="nf-wb-kv-list">
            {Object.entries(ch).map(([k, v]) => (
              <li key={k}>
                <code className="nf-code-inline">{k}</code> · {num(v)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {warnings.length > 0 ? (
        <div className="nf-wb-kv-block">
          <p className="nf-muted nf-wb-kv-label">Warning codes (ranked)</p>
          <ul className="nf-wb-kv-list">
            {warnings.slice(0, 16).map((w, i) => (
              <li key={`${str(w.warning_code)}-${i}`}>
                <code className="nf-code-inline">{str(w.warning_code)}</code> ·{" "}
                {num(w.occurrences)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="nf-muted nf-wb-kv-label">No connector warning codes recorded.</p>
      )}

      {flat.length > 0 ? (
        <div className="nf-wb-kv-block">
          <p className="nf-muted nf-wb-kv-label">Operator escalation recommendations</p>
          <ul className="nf-wb-kv-list">
            {flat.slice(0, 12).map((r, i) => (
              <li key={i}>
                <strong>{str(r.operator_title) || "Recommendation"}</strong>
                {str(r.operator_message) ? (
                  <span className="nf-muted"> — {str(r.operator_message)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {perSource.length > 0 ? (
        <div className="nf-wb-table-wrap">
          <table className="nf-wb-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Registry</th>
                <th>Connector</th>
                <th>Categories</th>
                <th>Last run</th>
                <th>IDs</th>
              </tr>
            </thead>
            <tbody>
              {perSource.map((row) => {
                const sid = str(row.source_registry_id);
                const scr = str(row.source_check_run_id);
                const intake = str(row.intake_run_id);
                const tags = Array.isArray(row.pressure_category_tags)
                  ? (row.pressure_category_tags as unknown[]).map((t) => str(t))
                  : [];
                return (
                  <tr key={sid || scr}>
                    <td>
                      <div>{str(row.source_name) || "—"}</div>
                      <p className="nf-muted">
                        {str(row.attention_summary) || "—"}
                      </p>
                    </td>
                    <td>{str(row.registry_health_status) || "—"}</td>
                    <td>{str(row.connector_health_status) || "—"}</td>
                    <td>
                      {tags.length ? (
                        <span className="nf-code-inline">{tags.join(", ")}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <div>{str(row.check_status) || "—"}</div>
                      <div className="nf-muted">{str(row.run_completed_at) || "—"}</div>
                    </td>
                    <td>
                      {looksLikeUuid(sid) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="sources"
                          id={sid}
                        >
                          Source
                        </EvidenceJsonLink>
                      ) : null}{" "}
                      {looksLikeUuid(scr) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="source-check-runs"
                          id={scr}
                        >
                          Check run
                        </EvidenceJsonLink>
                      ) : null}{" "}
                      {looksLikeUuid(intake) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="intake-runs"
                          id={intake}
                        >
                          Intake
                        </EvidenceJsonLink>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No per-source connector summaries yet.</p>
          <p className="nf-empty-hint">
            Connector-backed checks write summaries on source-check runs; those rows
            appear here with health, warnings, and escalation hints.
          </p>
        </div>
      )}
    </>
  );
}
