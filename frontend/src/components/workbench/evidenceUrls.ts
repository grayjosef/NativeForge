import { buildM0Path, type Plane } from "../../m0Flow";

export const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function looksLikeUuid(s: unknown): boolean {
  return typeof s === "string" && UUID_RE.test(s.trim());
}

export type EvidenceKind =
  | "sources"
  | "review-items"
  | "operator-actions"
  | "grant-sparks"
  | "intake-candidates"
  | "source-check-runs"
  | "intake-runs";

export function buildEvidencePackPath(
  plane: Plane,
  orgId: string,
  kind: EvidenceKind,
  id: string,
): string {
  const slug = id.trim();
  return buildM0Path(
    plane,
    orgId,
    `/discovery/evidence-pack/${kind}/${slug}`,
  );
}

/** Opens JSON from the API (same-origin in dev via Vite proxy). */
export function openEvidenceJsonTab(baseUrl: string, absoluteOrRelativePath: string): void {
  const path = absoluteOrRelativePath.startsWith("/")
    ? absoluteOrRelativePath
    : `/${absoluteOrRelativePath}`;
  const root =
    baseUrl && baseUrl.length > 0
      ? baseUrl.replace(/\/$/, "")
      : typeof window !== "undefined"
        ? window.location.origin
        : "";
  const url = `${root}${path}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

export interface EvidenceLinkRow {
  key: string;
  label: string;
  kind: EvidenceKind;
  id: string;
}

function add(
  out: Map<string, EvidenceLinkRow>,
  kind: EvidenceKind,
  id: unknown,
  label: string,
): void {
  if (!looksLikeUuid(id)) {
    return;
  }
  const sid = String(id).trim();
  const key = `${kind}:${sid}`;
  if (!out.has(key)) {
    out.set(key, { key, kind, id: sid, label });
  }
}

function walkRefs(
  out: Map<string, EvidenceLinkRow>,
  refs: unknown,
  prefix: string,
): void {
  if (!refs || typeof refs !== "object") {
    return;
  }
  const r = refs as Record<string, unknown>;
  add(out, "sources", r.source_registry_id, `${prefix} · source`);
  add(out, "review-items", r.review_item_id, `${prefix} · review item`);
  add(
    out,
    "review-items",
    r.discovery_review_item_id,
    `${prefix} · review item`,
  );
  add(out, "grant-sparks", r.grant_spark_id, `${prefix} · grant spark`);
  add(out, "intake-candidates", r.intake_candidate_id, `${prefix} · candidate`);
}

/** Aggregate recognizable IDs from engine payloads for the Evidence Links card. */
export function collectEvidenceLinkRows(input: {
  decisionPack: Record<string, unknown> | null;
  ledgerList: Record<string, unknown> | null;
  reviewItems: Record<string, unknown>[] | null;
  overdueSources: Record<string, unknown>[] | null;
  coverageIntel: Record<string, unknown> | null;
  sourceRecs: Record<string, unknown> | null;
}): EvidenceLinkRow[] {
  const out = new Map<string, EvidenceLinkRow>();

  const pack = input.decisionPack;
  if (pack) {
    const items = pack.decision_items;
    if (Array.isArray(items)) {
      for (const raw of items) {
        if (!raw || typeof raw !== "object") {
          continue;
        }
        const it = raw as Record<string, unknown>;
        const title = String(it.title ?? "Decision item").slice(0, 80);
        add(
          out,
          "operator-actions",
          it.operator_action_id,
          `${title} · ledger action`,
        );
        walkRefs(out, it.refs, title);
      }
    }
  }

  const ledger = input.ledgerList;
  const actions = ledger?.operator_actions;
  if (Array.isArray(actions)) {
    for (const raw of actions) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const row = raw as Record<string, unknown>;
      const title = String(row.action_title ?? row.title ?? "Operator action").slice(
        0,
        80,
      );
      add(out, "operator-actions", row.id, `${title} · open ledger row`);
      walkRefs(out, row.refs, title);
    }
  }

  if (input.reviewItems) {
    for (const raw of input.reviewItems) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const ri = raw as Record<string, unknown>;
      const ty = String(ri.review_item_type ?? "review").slice(0, 40);
      add(out, "review-items", ri.id, `${ty} · queue item`);
      walkRefs(out, ri, `${ty} · queue`);
    }
  }

  if (input.overdueSources) {
    for (const raw of input.overdueSources) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const s = raw as Record<string, unknown>;
      const name = String(s.source_name ?? "Source").slice(0, 60);
      add(out, "sources", s.id, `${name} · overdue`);
    }
  }

  const intel = input.coverageIntel;
  const gaps = intel?.coverage_gaps;
  if (Array.isArray(gaps)) {
    for (const raw of gaps) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const g = raw as Record<string, unknown>;
      const t = String(g.title ?? g.gap_type ?? "Gap").slice(0, 60);
      walkRefs(out, g.refs, t);
      add(out, "sources", g.source_registry_id, `${t} · gap`);
    }
  }

  const recBlock = input.sourceRecs;
  const recs = recBlock?.source_recommendations;
  if (Array.isArray(recs)) {
    for (const raw of recs) {
      if (!raw || typeof raw !== "object") {
        continue;
      }
      const rec = raw as Record<string, unknown>;
      const t = String(rec.title ?? "Recommendation").slice(0, 60);
      walkRefs(out, rec.refs, t);
      add(out, "sources", rec.source_registry_id, `${t} · recommendation`);
    }
  }

  return [...out.values()].sort((a, b) => a.label.localeCompare(b.label));
}
