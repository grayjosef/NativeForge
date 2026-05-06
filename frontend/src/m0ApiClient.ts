/**
 * Typed HTTP helpers for M0 product UI + operator runner.
 * Uses buildM0Path from m0Flow — same URLs as tests/test_m0_full_chain_demo.py.
 */

import { buildM0Path, type Plane } from "./m0Flow";

export function apiFetchBase(): string {
  if (import.meta.env.DEV) {
    return "";
  }
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  return fromEnv?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
}

export function curlDisplayBase(): string {
  const b = apiFetchBase();
  return b || "http://127.0.0.1:8000";
}

export async function readHttpError(res: Response): Promise<string> {
  const t = await res.text();
  try {
    const j = JSON.parse(t) as { detail?: unknown };
    if (j.detail !== undefined) {
      return typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    }
  } catch {
    /* ignore */
  }
  return t.slice(0, 500) || `HTTP ${res.status}`;
}

function jsonHeaders(orgId: string): Record<string, string> {
  return {
    "X-NF-Org-Id": orgId.trim(),
    "Content-Type": "application/json",
  };
}

function orgHeaderOnly(orgId: string): Record<string, string> {
  return { "X-NF-Org-Id": orgId.trim() };
}

async function parseJson<T>(res: Response): Promise<T> {
  return (await res.json()) as T;
}

/** Synthetic profile labels only — not customer data. */
export function demoTribalProfileBody(): Record<string, unknown> {
  return {
    legal_name: "M0 buyer shell demo profile",
    entity_type: "tribal_government",
    uei: "UEIM0SHELL00000",
    ein: "00-0000000",
    physical_address: {
      line1: "1 Demo Lane",
      city: "Tahlequah",
      state: "OK",
      zip: "74464",
    },
    grants_manager: {
      name: "M0 shell operator",
      email: "m0-shell.operator@example.invalid",
    },
  };
}

export function demoGrantSparkBody(
  sourceId: string,
  applicationDeadlineIso: string,
): Record<string, unknown> {
  return {
    source: "manual",
    source_id: sourceId,
    agency: "HUD",
    opportunity_title: "M0 shell demo opportunity",
    award_type: "grant",
    cfda_assistance_listing: "14.134",
    opportunity_number: "M0-SHELL-001",
    raw_nofo_text:
      "SECTION I. Eligibility: federally recognized tribes. " +
      "SECTION II. Forms: SF-424 required.",
    tribal_eligible: true,
    application_deadline: applicationDeadlineIso,
  };
}

export async function getHealth(
  baseUrl: string,
): Promise<{ ok: boolean; body: unknown }> {
  const r = await fetch(`${baseUrl}/health`);
  const body = await r.json().catch(() => ({}));
  return { ok: r.ok, body };
}

export async function getTribalProfile(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown> | null> {
  const path = buildM0Path(plane, orgId, "/tribal-profile");
  const r = await fetch(`${baseUrl}${path}`, {
    headers: orgHeaderOnly(orgId),
  });
  if (r.status === 404) {
    return null;
  }
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

/** POST then PUT on 409 — same behavior as the live runner. */
export async function createOrUpdateTribalProfile(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  body: Record<string, unknown>,
): Promise<{ mode: "created" | "updated"; profile: Record<string, unknown> }> {
  const path = buildM0Path(plane, orgId, "/tribal-profile");
  const h = jsonHeaders(orgId);
  let res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: h,
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    res = await fetch(`${baseUrl}${path}`, {
      method: "PUT",
      headers: h,
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(await readHttpError(res));
    }
    return { mode: "updated", profile: await parseJson(res) };
  }
  if (!res.ok) {
    throw new Error(await readHttpError(res));
  }
  return { mode: "created", profile: await parseJson(res) };
}

export async function listGrantSparks(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>[]> {
  const path = buildM0Path(plane, orgId, "/grant-sparks");
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getGrantSpark(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/grant-sparks/${sparkId}`);
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function createGrantSpark(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, "/grant-sparks");
  const r = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: jsonHeaders(orgId),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function postNofoExtractStub(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(
    plane,
    orgId,
    `/grant-sparks/${sparkId}/nofo/extract-stub`,
  );
  const r = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: orgHeaderOnly(orgId),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getNofoRequirements(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
): Promise<{ requirements: Record<string, unknown>[] }> {
  const path = buildM0Path(
    plane,
    orgId,
    `/grant-sparks/${sparkId}/nofo/requirements`,
  );
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function postScoreSpark(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
  actorId?: string | null,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/grant-sparks/${sparkId}/score`);
  const url = new URL(path, "http://local.example");
  if (actorId) {
    url.searchParams.set("actor_id", actorId);
  }
  const r = await fetch(`${baseUrl}${url.pathname}${url.search}`, {
    method: "POST",
    headers: orgHeaderOnly(orgId),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getScoreLatest(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(
    plane,
    orgId,
    `/grant-sparks/${sparkId}/score/latest`,
  );
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function openPursuit(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  sparkId: string,
  actorId: string,
  notes?: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/grant-sparks/${sparkId}/pursuit`);
  const url = new URL(path, "http://local.example");
  url.searchParams.set("actor_id", actorId);
  const r = await fetch(`${baseUrl}${url.pathname}${url.search}`, {
    method: "POST",
    headers: jsonHeaders(orgId),
    body: JSON.stringify({ notes: notes ?? "M0 workspace pursuit." }),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getPursuitDetail(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pursuitId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/pursuits/${pursuitId}`);
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function patchPursuitTask(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pursuitId: string,
  taskId: string,
  patch: { status?: string },
): Promise<Record<string, unknown>> {
  const path = buildM0Path(
    plane,
    orgId,
    `/pursuits/${pursuitId}/tasks/${taskId}`,
  );
  const r = await fetch(`${baseUrl}${path}`, {
    method: "PATCH",
    headers: jsonHeaders(orgId),
    body: JSON.stringify(patch),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function postFormPackage(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pursuitId: string,
  actorId?: string | null,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/pursuits/${pursuitId}/form-package`);
  const url = new URL(path, "http://local.example");
  if (actorId) {
    url.searchParams.set("actor_id", actorId);
  }
  const r = await fetch(`${baseUrl}${url.pathname}${url.search}`, {
    method: "POST",
    headers: orgHeaderOnly(orgId),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getFormPackage(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  pursuitId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, `/pursuits/${pursuitId}/form-package`);
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getTrustManifest(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, "/trust/manifest");
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getAuditEvents(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  limit = 100,
): Promise<{ events?: unknown[]; limit?: number }> {
  const path = buildM0Path(plane, orgId, "/trust/audit-events");
  const url = new URL(path, "http://local.example");
  url.searchParams.set("limit", String(limit));
  const r = await fetch(`${baseUrl}${url.pathname}${url.search}`, {
    headers: orgHeaderOnly(orgId),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getReviewSummary(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, "/trust/review-summary");
  const r = await fetch(`${baseUrl}${path}`, { headers: orgHeaderOnly(orgId) });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}

export async function getOrgDataSnapshot(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  opts: {
    actorId?: string | null;
    auditSampleLimit?: number;
    includeSf424Previews?: boolean;
  } = {},
): Promise<Record<string, unknown>> {
  const path = buildM0Path(plane, orgId, "/export/org-data-snapshot");
  const url = new URL(path, "http://local.example");
  url.searchParams.set(
    "audit_sample_limit",
    String(opts.auditSampleLimit ?? 50),
  );
  if (opts.actorId) {
    url.searchParams.set("actor_id", opts.actorId);
  }
  url.searchParams.set(
    "include_sf424_previews",
    opts.includeSf424Previews ? "true" : "false",
  );
  const r = await fetch(`${baseUrl}${url.pathname}${url.search}`, {
    headers: orgHeaderOnly(orgId),
  });
  if (!r.ok) {
    throw new Error(await readHttpError(r));
  }
  return parseJson(r);
}
