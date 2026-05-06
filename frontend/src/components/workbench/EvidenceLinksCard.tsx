import type { Plane } from "../../m0Flow";
import { EvidenceJsonLink } from "./EvidenceJsonLink";
import type { EvidenceLinkRow } from "./evidenceUrls";

interface EvidenceLinksCardProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  rows: EvidenceLinkRow[];
}

export function EvidenceLinksCard({
  baseUrl,
  plane,
  orgId,
  rows,
}: EvidenceLinksCardProps) {
  return (
    <section
      className="nf-card nf-card-pad"
      aria-labelledby="nf-wb-evidence-heading"
    >
      <div className="nf-card-head-row">
        <h2 id="nf-wb-evidence-heading" className="nf-card-title">
          Evidence links
        </h2>
      </div>
      <p className="nf-card-one-liner">
        Open raw JSON evidence packs in a new browser tab (no in-app viewer).
      </p>
      {rows.length === 0 ? (
        <div className="nf-empty nf-empty--calm">
          <p className="nf-empty-title">
            No evidence identifiers in current responses.
          </p>
          <p className="nf-empty-hint">
            When the engine returns UUIDs for sources, review items, ledger
            actions, sparks, or candidates, quick links appear here and on rows
            above.
          </p>
        </div>
      ) : (
        <ul className="nf-wb-evidence-index">
          {rows.map((r) => (
            <li key={r.key}>
              <EvidenceJsonLink
                baseUrl={baseUrl}
                plane={plane}
                orgId={orgId}
                kind={r.kind}
                id={r.id}
              >
                {r.label}
              </EvidenceJsonLink>
              <code className="nf-code-inline nf-wb-evidence-id">{r.id}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
