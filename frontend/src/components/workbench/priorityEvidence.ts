import type { EvidenceKind } from "./evidenceUrls";
import { looksLikeUuid } from "./evidenceUrls";
import { str } from "./workbenchFormat";

export interface RefEvidenceLink {
  key: string;
  kind: EvidenceKind;
  id: string;
  short: string;
}

export function walkRefsForRow(refs: unknown): RefEvidenceLink[] {
  if (!refs || typeof refs !== "object") {
    return [];
  }
  const r = refs as Record<string, unknown>;
  const out: RefEvidenceLink[] = [];
  const sid = r.source_registry_id;
  if (looksLikeUuid(sid)) {
    const id = str(sid);
    out.push({
      key: `sources:${id}`,
      kind: "sources",
      id,
      short: "source",
    });
  }
  const rid = r.review_item_id ?? r.discovery_review_item_id;
  if (looksLikeUuid(rid)) {
    const id = str(rid);
    out.push({
      key: `review-items:${id}`,
      kind: "review-items",
      id,
      short: "review item",
    });
  }
  const spark = r.grant_spark_id;
  if (looksLikeUuid(spark)) {
    const id = str(spark);
    out.push({
      key: `grant-sparks:${id}`,
      kind: "grant-sparks",
      id,
      short: "spark",
    });
  }
  const cand = r.intake_candidate_id;
  if (looksLikeUuid(cand)) {
    const id = str(cand);
    out.push({
      key: `intake-candidates:${id}`,
      kind: "intake-candidates",
      id,
      short: "candidate",
    });
  }
  return out;
}

/** Include top-level UUID fields common on review rows (not only nested refs). */
export function walkRowEvidenceLinks(row: Record<string, unknown>): RefEvidenceLink[] {
  const merged = new Map<string, RefEvidenceLink>();
  for (const x of walkRefsForRow(row.refs)) {
    merged.set(x.key, x);
  }
  const top: [string, EvidenceKind, string][] = [
    ["source_registry_id", "sources", "source"],
    ["grant_spark_id", "grant-sparks", "spark"],
    ["intake_candidate_id", "intake-candidates", "candidate"],
    ["review_item_id", "review-items", "review item"],
  ];
  for (const [field, kind, short] of top) {
    const v = row[field];
    if (looksLikeUuid(v)) {
      const id = str(v);
      const key = `${kind}:${id}`;
      if (!merged.has(key)) {
        merged.set(key, { key, kind, id, short });
      }
    }
  }
  return [...merged.values()];
}
