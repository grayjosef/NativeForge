/** Sprint 230: HTTP client for operator workbench advisory endpoints. */

import { readHttpError } from "./m0ApiClient";
import { buildM0Path, type Plane } from "./m0Flow";
import { workbenchQueryParam } from "./workbenchFeatureFlag";

function orgHeaders(orgId: string): Record<string, string> {
  return { "X-NF-Org-Id": orgId.trim() };
}

async function advisoryFetch(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pathSuffix: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, pathSuffix);
  const u = new URL(`${baseUrl}${path}`, "http://local.example");
  u.searchParams.set("nf_workbench", workbenchQueryParam());
  const r = await fetch(u.pathname + u.search, { headers: orgHeaders(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return (await r.json()) as Record<string, unknown>;
}

export async function getWorkbenchAdvisoryBundle(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  return advisoryFetch(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-workbench-advisory/bundle",
  );
}

export async function getNativeRelevanceAdvisory(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  return advisoryFetch(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-workbench-advisory/native-relevance",
  );
}

export async function getMatchingReadinessAdvisory(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  return advisoryFetch(
    baseUrl,
    plane,
    orgId,
    "/discovery/operator-workbench-advisory/matching-readiness",
  );
}
