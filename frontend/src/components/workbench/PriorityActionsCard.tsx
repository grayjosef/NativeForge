import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import { looksLikeUuid } from "./evidenceUrls";
import { walkRefsForRow } from "./priorityEvidence";
import { str } from "./workbenchFormat";

export interface AsyncPack {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
}

interface PriorityActionsCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  block: AsyncPack;
}

/** Merge compact priority_next_actions rows with decision_items for rationale + refs. */
function mergePriority(
  pack: Record<string, unknown>,
): { pri: Record<string, unknown>; detail: Record<string, unknown> | null }[] {
  const priRaw = pack.priority_next_actions;
  const itemsRaw = pack.decision_items;
  const byDid = new Map<string, Record<string, unknown>>();
  if (Array.isArray(itemsRaw)) {
    for (const raw of itemsRaw) {
      if (raw && typeof raw === "object") {
        const it = raw as Record<string, unknown>;
        const did = str(it.decision_id);
        if (did) {
          byDid.set(did, it);
        }
      }
    }
  }
  if (!Array.isArray(priRaw)) {
    return [];
  }
  return priRaw.map((p) => {
    const pri = p as Record<string, unknown>;
    const did = str(pri.decision_id);
    return { pri, detail: byDid.get(did) ?? null };
  });
}

export function PriorityActionsCard({
  baseUrl,
  plane,
  orgId,
  block,
}: PriorityActionsCardProps) {
  const { loading, error, data } = block;

  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-priority-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-priority-heading" className="nf-card-title">
          Priority actions
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Top-ranked operator decisions from the discovery engine decision pack.
      </p>
      {loading ? (
        <p className="nf-muted">Loading priority actions…</p>
      ) : error ? (
        <div className="nf-alert nf-alert--error" role="alert">
          {error}
        </div>
      ) : !data ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">No priority actions returned.</p>
        </div>
      ) : (
        <PriorityActionsBody
          baseUrl={baseUrl}
          plane={plane}
          orgId={orgId}
          pack={data}
        />
      )}
    </section>
  );
}

function PriorityActionsBody({
  baseUrl,
  plane,
  orgId,
  pack,
}: {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  pack: Record<string, unknown>;
}) {
  const rows = mergePriority(pack);
  if (rows.length === 0) {
    return (
      <div className="nf-empty nf-empty--calm">
        <p className="nf-empty-title">No priority actions in this pack.</p>
        <p className="nf-empty-hint">
          The engine returned an empty ranked list for this organization.
        </p>
      </div>
    );
  }

  return (
    <ul className="nf-wb-action-list">
      {rows.map(({ pri, detail }) => {
        const rank = pri.rank;
        const severity = str(pri.severity);
        const title = str(pri.title);
        const opAction = str(
          pri.recommended_action ?? pri.operator_action ?? pri.action,
        );
        const rationale = str(detail?.rationale);
        const oaLedgerId = str(detail?.operator_action_id);
        const refs = detail?.refs;
        return (
          <li key={str(pri.decision_id) || title} className="nf-wb-action-item">
            <div className="nf-wb-action-head">
              <span className="nf-chip">{severity || "—"}</span>
              <span className="nf-wb-rank">
                {rank != null ? `#${str(rank)}` : ""}
              </span>
            </div>
            <p className="nf-wb-action-title">{title || "—"}</p>
            {opAction ? (
              <p className="nf-wb-meta">
                <span className="nf-muted">Operator action · </span>
                {opAction}
              </p>
            ) : null}
            {rationale ? (
              <p className="nf-wb-rationale">{rationale}</p>
            ) : (
              <p className="nf-muted nf-wb-rationale">No rationale text.</p>
            )}
            <div className="nf-wb-evidence-row">
              {looksLikeUuid(oaLedgerId) ? (
                <EvidenceJsonLink
                  baseUrl={baseUrl}
                  plane={plane}
                  orgId={orgId}
                  kind="operator-actions"
                  id={oaLedgerId}
                >
                  Evidence · operator action
                </EvidenceJsonLink>
              ) : null}
              {walkRefsForRow(refs).map((l) => (
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
          </li>
        );
      })}
    </ul>
  );
}
