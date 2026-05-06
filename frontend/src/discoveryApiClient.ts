/**
 * Discovery / operator engine HTTP helpers — mirrors m0ApiClient conventions.
 */

import { readHttpError } from "./m0ApiClient";
import { buildM0Path, type Plane } from "./m0Flow";

function orgHeaders(orgId: string): Record<string, string> {
  return { "X-NF-Org-Id": orgId.trim() };
}

function appendQuery(
  path: string,
  query?: Record<string, string | boolean | number | undefined | null>,
): string {
  if (!query) {
    return path;
  }
  const u = new URL(path, "http://local.example");
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) {
      continue;
    }
    if (typeof v === "boolean") {
      u.searchParams.set(k, v ? "true" : "false");
    } else {
      u.searchParams.set(k, String(v));
    }
  }
  return `${u.pathname}${u.search}`;
}

async function discoveryFetchJson(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pathSuffix: string,
  query?: Record<string, string | boolean | number | undefined | null>,
): Promise<unknown> {
  const path = appendQuery(buildM0Path(plane, orgId, pathSuffix), query);
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaders(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return r.json();
}

export async function getOperatorDecisionPack(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: { limit?: number } = {},
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-decision-pack",
    { limit: opts.limit ?? 50 },
  );
  return raw as Record<string, unknown>;
}

export async function getOperatorLedgerSummary(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-actions-ledger/summary",
  );
  return raw as Record<string, unknown>;
}

export async function listOperatorLedgerActions(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: { open_only?: boolean; limit?: number } = {},
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-actions-ledger",
    {
      open_only: opts.open_only ?? false,
      limit: opts.limit ?? 50,
    },
  );
  return raw as Record<string, unknown>;
}

export async function listDiscoveryReviewItems(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: { open_queue_only?: boolean; limit?: number } = {},
): Promise<Record<string, unknown>[]> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/review-items",
    {
      open_queue_only: opts.open_queue_only ?? false,
      limit: opts.limit ?? 200,
    },
  );
  return Array.isArray(raw) ? (raw as Record<string, unknown>[]) : [];
}

export async function listSourcesOverdue(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>[]> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/sources/overdue",
  );
  return Array.isArray(raw) ? (raw as Record<string, unknown>[]) : [];
}

export async function getSourcesFreshnessSummary(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/sources/freshness-summary",
  );
  return raw as Record<string, unknown>;
}

export async function getCoverageGapIntelligence(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: { limit?: number } = {},
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/coverage-gap-intelligence",
    { limit: opts.limit ?? 50 },
  );
  return raw as Record<string, unknown>;
}

export async function getSourceRecommendations(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: { limit?: number } = {},
): Promise<Record<string, unknown>> {
  const raw = await discoveryFetchJson(
    baseUrl,
    plane,
    orgId,
    "/discovery/source-recommendations",
    { limit: opts.limit ?? 50 },
  );
  return raw as Record<string, unknown>;
}
