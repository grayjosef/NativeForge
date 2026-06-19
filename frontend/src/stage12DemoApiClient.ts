/** Sprint 250: HTTP client for Stage 12 guided demo path endpoints. */

import { readHttpError } from "./m0ApiClient";
import { buildM0Path, type Plane } from "./m0Flow";
import { stage12DemoQueryParam } from "./stage12DemoFeatureFlag";

function orgHeaders(orgId: string): Record<string, string> {
  return { "X-NF-Org-Id": orgId.trim() };
}

async function stage12Fetch(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pathSuffix: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, pathSuffix);
  const u = new URL(`${baseUrl}${path}`, "http://local.example");
  u.searchParams.set("nf_stage12_demo", stage12DemoQueryParam());
  const r = await fetch(u.pathname + u.search, { headers: orgHeaders(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return (await r.json()) as Record<string, unknown>;
}

export async function getStage12GuidedDemoPath(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  return stage12Fetch(baseUrl, plane, orgId, "/discovery/stage12-guided-demo-path");
}

export async function getStage12DemoReset(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  return stage12Fetch(baseUrl, plane, orgId, "/discovery/stage12-demo-reset");
}
