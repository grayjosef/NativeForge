/**
 * Live M0 API sequence for the buyer shell — matches tests/test_m0_full_chain_demo.py.
 * Deterministic stub / rule-based M0 only; no live AI or Grants.gov.
 */

import { buildM0Path, type Plane } from "./m0Flow";

export type RunnerStepStatus = "pending" | "running" | "success" | "error";

export interface RunnerLogStep {
  key: string;
  name: string;
  method: string;
  pathLine: string;
  status: RunnerStepStatus;
  summary?: string;
  error?: string;
}

export interface RunM0LiveDemoResult {
  ok: boolean;
  sparkId?: string;
  pursuitId?: string;
  failedStepKey?: string;
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

async function readHttpError(res: Response): Promise<string> {
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

/** Synthetic profile labels only — not customer data. */
function demoTribalProfileBody() {
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

function demoGrantSparkBody(sourceId: string, applicationDeadlineIso: string) {
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

const STEP_TEMPLATE: Omit<RunnerLogStep, "status" | "summary" | "error">[] = [
  { key: "tribal_profile", name: "Tribal profile", method: "POST|PUT", pathLine: "" },
  { key: "grant_spark", name: "Grant Spark", method: "POST", pathLine: "" },
  { key: "nofo_extract", name: "NOFO extract (stub)", method: "POST", pathLine: "" },
  { key: "requirements", name: "Structured requirements", method: "GET", pathLine: "" },
  { key: "score", name: "Deterministic score", method: "POST", pathLine: "" },
  { key: "pursuit", name: "Open pursuit", method: "POST", pathLine: "" },
  { key: "pursuit_detail", name: "Pursuit detail (tasks / calendar)", method: "GET", pathLine: "" },
  { key: "form_package", name: "Form package / SF-424 preview", method: "POST", pathLine: "" },
  { key: "trust_manifest", name: "Trust manifest", method: "GET", pathLine: "" },
  { key: "audit_events", name: "Audit events", method: "GET", pathLine: "" },
  { key: "review_summary", name: "Review summary", method: "GET", pathLine: "" },
  { key: "org_export", name: "Org data export", method: "GET", pathLine: "" },
];

function initSteps(plane: Plane, orgId: string): RunnerLogStep[] {
  const o = orgId.trim();
  return STEP_TEMPLATE.map((t) => {
    let pathLine = t.pathLine;
    if (t.key === "tribal_profile") {
      pathLine = `${t.method} ${buildM0Path(plane, o, "/tribal-profile")}`;
    } else if (t.key === "grant_spark") {
      pathLine = `${t.method} ${buildM0Path(plane, o, "/grant-sparks")}`;
    }
    return {
      ...t,
      pathLine,
      status: "pending" as const,
    };
  });
}

export async function runM0LiveDemoSequence(
  baseUrl: string,
  plane: Plane,
  orgId: string,
  onStepsChange: (steps: RunnerLogStep[]) => void,
): Promise<RunM0LiveDemoResult> {
  const o = orgId.trim();
  const h = jsonHeaders(o);
  const actorId = crypto.randomUUID();
  const sourceId = `m0-shell-${crypto.randomUUID()}`;
  const applicationDeadline = new Date(Date.now() + 50 * 86_400_000).toISOString();

  const steps = initSteps(plane, o);
  const sync = () => onStepsChange(steps.map((s) => ({ ...s })));
  sync();

  const setStatus = (key: string, patch: Partial<RunnerLogStep>) => {
    const i = steps.findIndex((s) => s.key === key);
    if (i >= 0) {
      steps[i] = { ...steps[i], ...patch };
    }
    sync();
  };

  const abort = (key: string): RunM0LiveDemoResult => ({
    ok: false,
    failedStepKey: key,
  });

  const requireOk = async (res: Response, key: string): Promise<boolean> => {
    if (res.ok) {
      return true;
    }
    setStatus(key, { status: "error", error: await readHttpError(res) });
    return false;
  };

  // 1) Tribal profile — POST, or PUT on 409
  {
    const k = "tribal_profile";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/tribal-profile");
    const body = demoTribalProfileBody();
    let res = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: h,
      body: JSON.stringify(body),
    });
    let summary: string;
    if (res.status === 409) {
      res = await fetch(`${baseUrl}${path}`, {
        method: "PUT",
        headers: h,
        body: JSON.stringify(body),
      });
      if (!(await requireOk(res, k))) {
        return abort(k);
      }
      summary = "updated (PUT) — existing profile for org";
    } else {
      if (!(await requireOk(res, k))) {
        return abort(k);
      }
      summary = "created (POST)";
    }
    setStatus(k, { status: "success", summary, pathLine: `POST|PUT ${path}` });
  }

  // 2) Grant Spark
  let sparkId: string;
  {
    const k = "grant_spark";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/grant-sparks");
    const res = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: h,
      body: JSON.stringify(demoGrantSparkBody(sourceId, applicationDeadline)),
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { id?: string };
    if (!j.id) {
      setStatus(k, { status: "error", error: "response missing id" });
      return abort(k);
    }
    sparkId = j.id;
    setStatus(k, {
      status: "success",
      summary: `spark id ${sparkId.slice(0, 8)}…`,
    });
  }

  // 3) NOFO extract-stub
  {
    const k = "nofo_extract";
    setStatus(k, { status: "running" });
    const path = buildM0Path(
      plane,
      o,
      `/grant-sparks/${sparkId}/nofo/extract-stub`,
    );
    setStatus(k, { pathLine: `POST ${path}` });
    const res = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: orgHeaderOnly(o),
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { checklist_row_count?: number };
    setStatus(k, {
      status: "success",
      summary: `checklist rows: ${j.checklist_row_count ?? "?"}`,
    });
  }

  // 4) Requirements
  {
    const k = "requirements";
    setStatus(k, { status: "running" });
    const path = buildM0Path(
      plane,
      o,
      `/grant-sparks/${sparkId}/nofo/requirements`,
    );
    setStatus(k, { pathLine: `GET ${path}` });
    const res = await fetch(`${baseUrl}${path}`, { headers: { "X-NF-Org-Id": o } });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { requirements?: unknown[] };
    const n = Array.isArray(j.requirements) ? j.requirements.length : 0;
    setStatus(k, { status: "success", summary: `${n} requirement(s)` });
  }

  // 5) Score
  {
    const k = "score";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, `/grant-sparks/${sparkId}/score`);
    setStatus(k, { pathLine: `POST ${path}` });
    const res = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: orgHeaderOnly(o),
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    setStatus(k, { status: "success", summary: "score persisted" });
  }

  // 6) Pursuit
  let pursuitId: string;
  {
    const k = "pursuit";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, `/grant-sparks/${sparkId}/pursuit`);
    const url = new URL(path, "http://local.example");
    url.searchParams.set("actor_id", actorId);
    const withQuery = `${url.pathname}${url.search}`;
    setStatus(k, { pathLine: `POST ${withQuery}` });
    const res = await fetch(`${baseUrl}${withQuery}`, {
      method: "POST",
      headers: h,
      body: JSON.stringify({ notes: "M0 shell demo pursuit." }),
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { id?: string };
    if (!j.id) {
      setStatus(k, { status: "error", error: "response missing id" });
      return abort(k);
    }
    pursuitId = j.id;
    setStatus(k, {
      status: "success",
      summary: `pursuit id ${pursuitId.slice(0, 8)}…`,
    });
  }

  // 7) Pursuit detail
  {
    const k = "pursuit_detail";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, `/pursuits/${pursuitId}`);
    setStatus(k, { pathLine: `GET ${path}` });
    const res = await fetch(`${baseUrl}${path}`, { headers: { "X-NF-Org-Id": o } });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as {
      tasks?: unknown[];
      calendar_events?: { kind?: string }[];
    };
    const t = j.tasks?.length ?? 0;
    const c = j.calendar_events?.length ?? 0;
    setStatus(k, { status: "success", summary: `${t} task(s), ${c} calendar event(s)` });
  }

  // 8) Form package
  {
    const k = "form_package";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, `/pursuits/${pursuitId}/form-package`);
    const url = new URL(path, "http://local.example");
    url.searchParams.set("actor_id", actorId);
    const withQuery = `${url.pathname}${url.search}`;
    setStatus(k, { pathLine: `POST ${withQuery}` });
    const res = await fetch(`${baseUrl}${withQuery}`, {
      method: "POST",
      headers: orgHeaderOnly(o),
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { package_engine?: string };
    setStatus(k, {
      status: "success",
      summary: j.package_engine ?? "form package created",
    });
  }

  // 9) Trust manifest
  {
    const k = "trust_manifest";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/trust/manifest");
    setStatus(k, { pathLine: `GET ${path}` });
    const res = await fetch(`${baseUrl}${path}`, { headers: { "X-NF-Org-Id": o } });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { manifest_schema_version?: string };
    setStatus(k, {
      status: "success",
      summary: j.manifest_schema_version ?? "ok",
    });
  }

  // 10) Audit events
  {
    const k = "audit_events";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/trust/audit-events");
    const url = new URL(path, "http://local.example");
    url.searchParams.set("limit", "100");
    const withQuery = `${url.pathname}${url.search}`;
    setStatus(k, { pathLine: `GET ${withQuery}` });
    const res = await fetch(`${baseUrl}${withQuery}`, {
      headers: { "X-NF-Org-Id": o },
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { events?: unknown[] };
    const n = Array.isArray(j.events) ? j.events.length : 0;
    setStatus(k, { status: "success", summary: `${n} event(s)` });
  }

  // 11) Review summary
  {
    const k = "review_summary";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/trust/review-summary");
    setStatus(k, { pathLine: `GET ${path}` });
    const res = await fetch(`${baseUrl}${path}`, { headers: { "X-NF-Org-Id": o } });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { review_artifact_count?: number };
    setStatus(k, {
      status: "success",
      summary: `artifacts: ${j.review_artifact_count ?? "?"}`,
    });
  }

  // 12) Org export
  {
    const k = "org_export";
    setStatus(k, { status: "running" });
    const path = buildM0Path(plane, o, "/export/org-data-snapshot");
    const url = new URL(path, "http://local.example");
    url.searchParams.set("audit_sample_limit", "50");
    url.searchParams.set("actor_id", actorId);
    url.searchParams.set("include_sf424_previews", "false");
    const withQuery = `${url.pathname}${url.search}`;
    setStatus(k, { pathLine: `GET ${withQuery}` });
    const res = await fetch(`${baseUrl}${withQuery}`, {
      headers: { "X-NF-Org-Id": o },
    });
    if (!(await requireOk(res, k))) {
      return abort(k);
    }
    const j = (await res.json()) as { snapshot_schema_version?: string };
    setStatus(k, {
      status: "success",
      summary: j.snapshot_schema_version ?? "exported",
    });
  }

  return { ok: true, sparkId, pursuitId };
}
