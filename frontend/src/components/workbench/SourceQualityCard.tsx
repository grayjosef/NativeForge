import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import type { ConnectorIntelBlock } from "./ConnectorIntelligenceCard";
import { str } from "./workbenchFormat";

interface SourceQualityCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  block: ConnectorIntelBlock;
}

function num(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) {
    return String(v);
  }
  return str(v) || "0";
}

function humanizeKey(s: string): string {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function posturePretty(p: string): string {
  const x = str(p).toLowerCase();
  if (!x) {
    return "—";
  }
  return x.charAt(0).toUpperCase() + x.slice(1);
}

const HEALTH_DISPLAY_ORDER: { key: string; label: string }[] = [
  { key: "healthy", label: "Healthy" },
  { key: "degraded", label: "Degraded" },
  { key: "failing", label: "Failing" },
  { key: "stale", label: "Stale" },
  { key: "empty", label: "Empty" },
  { key: "attention_needed", label: "Attention needed" },
  { key: "unknown", label: "Unchecked" },
];

const FRESHNESS_ROWS: readonly [string, string][] = [
  ["never_checked", "Never checked"],
  ["overdue_for_check", "Overdue"],
  ["missing_recent_check", "Missing recent checks"],
  ["due_but_not_overdue", "Due (not overdue)"],
];

function readCount(obj: Record<string, unknown> | null, key: string): number {
  if (!obj) {
    return 0;
  }
  const v = obj[key];
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

/** Backend uses `missing_recent_check`; some payloads may use plural. */
function freshnessValue(fc: Record<string, unknown>, key: string): number {
  if (key === "missing_recent_check") {
    return readCount(fc, "missing_recent_check") + readCount(fc, "missing_recent_checks");
  }
  return readCount(fc, key);
}

export function SourceQualityCard({
  baseUrl,
  plane,
  orgId,
  block,
}: SourceQualityCardProps) {
  const { loading, error, data } = block;
  const raw = data?.source_quality;
  const sq =
    raw && typeof raw === "object"
      ? (raw as Record<string, unknown>)
      : null;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-source-quality-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-source-quality-heading" className="nf-card-title">
          Source quality posture
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Registry coverage across NativeForge doctrine priority lanes, health and
        freshness rollups, and ranked sources that need attention next (offline,
        deterministic).
      </p>
      {loading ? (
        <p className="nf-muted">Loading source quality…</p>
      ) : error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : !data ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No decision pack loaded.</p>
        </div>
      ) : !sq ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No source quality block.</p>
          <p className="nf-empty-hint">
            Source quality is computed with the operator decision pack.
          </p>
        </div>
      ) : (
        <SourceQualityBody
          baseUrl={baseUrl}
          plane={plane}
          orgId={orgId}
          sq={sq}
        />
      )}
    </section>
  );
}

function SourceQualityBody({
  baseUrl,
  plane,
  orgId,
  sq,
}: {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  sq: Record<string, unknown>;
}) {
  const score =
    typeof sq.data_quality_score === "number" && Number.isFinite(sq.data_quality_score)
      ? sq.data_quality_score
      : null;
  const posture = str(sq.posture);
  const sourceCounts =
    sq.source_counts && typeof sq.source_counts === "object"
      ? (sq.source_counts as Record<string, unknown>)
      : null;
  const active =
    sourceCounts && typeof sourceCounts.active === "number"
      ? sourceCounts.active
      : null;

  const hc =
    sq.health_counts && typeof sq.health_counts === "object"
      ? (sq.health_counts as Record<string, unknown>)
      : null;
  const fc =
    sq.freshness_counts && typeof sq.freshness_counts === "object"
      ? (sq.freshness_counts as Record<string, unknown>)
      : null;

  const missingLanes = Array.isArray(sq.missing_lanes)
    ? (sq.missing_lanes as unknown[]).map((x) => str(x)).filter(Boolean)
    : [];
  const weakLanes = Array.isArray(sq.weak_lanes)
    ? (sq.weak_lanes as unknown[]).map((x) => str(x)).filter(Boolean)
    : [];
  const overLanes = Array.isArray(sq.overrepresented_lanes)
    ? (sq.overrepresented_lanes as unknown[]).map((x) => str(x)).filter(Boolean)
    : [];

  const attention = Array.isArray(sq.top_attention_sources)
    ? (sq.top_attention_sources as Record<string, unknown>[])
    : [];
  const gaps = Array.isArray(sq.top_coverage_gaps)
    ? (sq.top_coverage_gaps as Record<string, unknown>[])
    : [];
  const actions = Array.isArray(sq.recommended_operator_actions)
    ? (sq.recommended_operator_actions as Record<string, unknown>[])
    : [];
  const reasons = Array.isArray(sq.reason_codes)
    ? (sq.reason_codes as unknown[]).map((x) => str(x)).filter(Boolean)
    : [];

  const schemaVersion = str(sq.schema_version);

  return (
    <>
      <div className="nf-wb-score-grid">
        <div>
          <p className="nf-muted">Data quality score</p>
          <p className="nf-wb-score">{score != null ? num(score) : "—"}</p>
        </div>
        <div>
          <p className="nf-muted">Posture</p>
          <p className="nf-wb-score" style={{ fontSize: "1.05rem" }}>
            {posturePretty(posture)}
          </p>
        </div>
        <div>
          <p className="nf-muted">Active sources</p>
          <p className="nf-wb-score">{active != null ? num(active) : "—"}</p>
        </div>
        <div>
          <p className="nf-muted">Schema</p>
          <p className="nf-wb-score" style={{ fontSize: "0.95rem" }}>
            {schemaVersion || "—"}
          </p>
        </div>
      </div>

      {hc ? (
        <dl className="nf-dl nf-dl-tight nf-wb-freshness">
          {HEALTH_DISPLAY_ORDER.map(({ key, label }) => {
            const n = readCount(hc, key);
            return (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{num(n)}</dd>
              </div>
            );
          })}
        </dl>
      ) : (
        <p className="nf-muted nf-wb-kv-label">No health counts.</p>
      )}

      {fc ? (
        <>
          <p className="nf-muted nf-wb-kv-label">Freshness</p>
          <dl className="nf-dl nf-dl-tight nf-wb-freshness">
            {FRESHNESS_ROWS.map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{num(freshnessValue(fc, key))}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}

      <h3 className="nf-card-subtitle">Priority lanes</h3>
      <div className="nf-wb-kv-block">
        <p className="nf-muted nf-wb-kv-label">Missing lanes</p>
        {missingLanes.length ? (
          <ul className="nf-wb-bullet-list">
            {missingLanes.map((ln) => (
              <li key={ln}>
                <code className="nf-code-inline">{humanizeKey(ln)}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="nf-muted">None — every doctrine lane has at least one active source.</p>
        )}
      </div>
      <div className="nf-wb-kv-block">
        <p className="nf-muted nf-wb-kv-label">Weak lanes</p>
        {weakLanes.length ? (
          <ul className="nf-wb-bullet-list">
            {weakLanes.map((ln) => (
              <li key={ln}>
                <code className="nf-code-inline">{humanizeKey(ln)}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="nf-muted">None flagged.</p>
        )}
      </div>
      <div className="nf-wb-kv-block">
        <p className="nf-muted nf-wb-kv-label">Overrepresented lanes</p>
        {overLanes.length ? (
          <ul className="nf-wb-bullet-list">
            {overLanes.map((ln) => (
              <li key={ln}>
                <code className="nf-code-inline">{humanizeKey(ln)}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="nf-muted">No concentration warnings.</p>
        )}
      </div>

      <h3 className="nf-card-subtitle">Top attention sources</h3>
      {attention.length ? (
        <div className="nf-wb-table-wrap">
          <table className="nf-wb-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Health</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Link</th>
              </tr>
            </thead>
            <tbody>
              {attention.slice(0, 24).map((row, i) => {
                const sid = str(row.source_registry_id);
                const name = str(row.source_name) || "—";
                const hb = str(row.health_bucket) || "—";
                const sh = str(row.source_health_status) || "—";
                const overdue = row.is_overdue_for_check === true;
                const pri = str(row.priority_level) || "";
                const reasonParts = [
                  `Attention score ${num(row.attention_score)}`,
                  pri ? `priority ${pri}` : "",
                  overdue ? "overdue for check" : "",
                ].filter(Boolean);
                return (
                  <tr key={sid || String(i)}>
                    <td>
                      <div>{name}</div>
                      <span className="nf-muted nf-wb-inline-meta">
                        Rank {num(row.rank ?? i + 1)}
                      </span>
                    </td>
                    <td>{hb}</td>
                    <td>{sh}</td>
                    <td>{reasonParts.join(" · ") || "—"}</td>
                    <td className="nf-wb-td-links">
                      {looksLikeUuid(sid) ? (
                        <EvidenceJsonLink
                          baseUrl={baseUrl}
                          plane={plane}
                          orgId={orgId}
                          kind="sources"
                          id={sid}
                        >
                          Registry
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
      ) : (
        <p className="nf-muted">No active sources to rank.</p>
      )}

      <h3 className="nf-card-subtitle">Top coverage gaps</h3>
      {gaps.length ? (
        <ul className="nf-wb-bullet-list">
          {gaps.slice(0, 16).map((g, i) => (
            <li key={str(g.gap_id ?? g.title ?? i)}>
              <strong>{str(g.title ?? g.gap_type ?? "Gap")}</strong>
              {g.severity ? (
                <span className="nf-wb-gap-sev nf-muted"> · {str(g.severity)}</span>
              ) : null}
              {g.gap_type ? (
                <span className="nf-muted"> ({str(g.gap_type)})</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="nf-muted">No coverage gaps in this rollup.</p>
      )}

      <h3 className="nf-card-subtitle">Recommended operator actions</h3>
      {actions.length ? (
        <ul className="nf-wb-action-list" aria-label="Recommended operator actions">
          {actions.map((a, i) => {
            const actionType = str(a.action_type ?? a.action);
            const titleText =
              str(a.title).trim() || (actionType ? humanizeKey(actionType) : `Action ${i + 1}`);
            const rat = str(a.rationale);
            const pri = str(a.priority).trim();
            const focus = Array.isArray(a.focus_lanes)
              ? (a.focus_lanes as unknown[]).map((x) => humanizeKey(str(x)))
              : [];
            const affected =
              typeof a.affected_source_count === "number" && Number.isFinite(a.affected_source_count)
                ? a.affected_source_count
                : null;
            const createLedger = a.should_create_action === true;
            const legacyCount =
              typeof a.count === "number" && Number.isFinite(a.count) ? a.count : null;
            const evidence = Array.isArray(a.evidence_refs)
              ? (a.evidence_refs as unknown[]).map((x) => str(x)).filter(Boolean)
              : [];
            return (
              <li key={`${actionType}-${i}`} className="nf-wb-action-item">
                <p className="nf-wb-action-head">
                  <span className="nf-wb-rank">Step {i + 1}</span>
                  {pri ? (
                    <span className="nf-wb-meta nf-muted nf-wb-inline-meta">
                      · Priority {humanizeKey(pri)}
                    </span>
                  ) : null}
                </p>
                {actionType ? (
                  <p className="nf-muted nf-wb-inline-meta">
                    <code className="nf-code-inline">{actionType}</code>
                  </p>
                ) : null}
                <p className="nf-wb-action-title">{titleText}</p>
                {legacyCount != null ? (
                  <p className="nf-wb-meta nf-muted">Count: {num(legacyCount)}</p>
                ) : null}
                {affected != null ? (
                  <p className="nf-wb-meta nf-muted">Affected sources: {num(affected)}</p>
                ) : null}
                <p className="nf-wb-meta nf-muted">
                  {createLedger
                    ? "Eligible to create a ledger operator action (explicit opt-in)."
                    : "Recommendations only — not written to the operator ledger by default."}
                </p>
                {focus.length ? (
                  <p className="nf-wb-meta">
                    Focus lanes:{" "}
                    {focus.map((f, idx) => (
                      <span key={`${f}-${idx}`}>
                        {idx > 0 ? ", " : null}
                        <code className="nf-code-inline">{f}</code>
                      </span>
                    ))}
                  </p>
                ) : null}
                {evidence.length ? (
                  <p className="nf-wb-meta">
                    Evidence refs:{" "}
                    {evidence.slice(0, 8).map((ev, idx) => (
                      <span key={`${ev}-${idx}`}>
                        {idx > 0 ? ", " : null}
                        <code className="nf-code-inline">{ev}</code>
                      </span>
                    ))}
                    {evidence.length > 8 ? <span className="nf-muted"> …</span> : null}
                  </p>
                ) : null}
                {rat ? <p className="nf-wb-rationale">{rat}</p> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="nf-muted">No automated recommendations.</p>
      )}

      <h3 className="nf-card-subtitle">Reason codes</h3>
      {reasons.length ? (
        <ul className="nf-wb-kv-list">
          {reasons.map((r) => (
            <li key={r}>
              <code className="nf-code-inline">{r}</code>
            </li>
          ))}
        </ul>
      ) : (
        <p className="nf-muted">None.</p>
      )}
    </>
  );
}
