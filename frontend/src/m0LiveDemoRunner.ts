/**
 * Live M0 API sequence for operator tools — matches tests/test_m0_full_chain_demo.py.
 * Deterministic stub / rule-based M0 only; no live AI or Grants.gov.
 * Core HTTP calls live in m0ApiClient.ts for reuse by the product workspace.
 */

import { buildM0Path, type Plane } from "./m0Flow";
import {
  createGrantSpark,
  createOrUpdateTribalProfile,
  demoGrantSparkBody,
  demoTribalProfileBody,
  getAuditEvents,
  getNofoRequirements,
  getOrgDataSnapshot,
  getTrustManifest,
  getReviewSummary,
  openPursuit,
  postFormPackage,
  postNofoExtractStub,
  postScoreSpark,
  getPursuitDetail,
} from "./m0ApiClient";

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

  const runStep = async (key: string, fn: () => Promise<void>) => {
    setStatus(key, { status: "running" });
    try {
      await fn();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "request failed";
      setStatus(key, { status: "error", error: msg });
      throw e;
    }
  };

  let sparkId = "";
  let pursuitId = "";

  try {
    await runStep("tribal_profile", async () => {
      const path = buildM0Path(plane, o, "/tribal-profile");
      const { mode } = await createOrUpdateTribalProfile(
        baseUrl,
        plane,
        o,
        demoTribalProfileBody(),
      );
      const summary =
        mode === "updated"
          ? "updated (PUT) — existing profile for org"
          : "created (POST)";
      setStatus("tribal_profile", {
        status: "success",
        summary,
        pathLine: `POST|PUT ${path}`,
      });
    });

    await runStep("grant_spark", async () => {
      const row = await createGrantSpark(
        baseUrl,
        plane,
        o,
        demoGrantSparkBody(sourceId, applicationDeadline),
      );
      const id = row.id as string | undefined;
      if (!id) {
        throw new Error("response missing id");
      }
      sparkId = id;
      setStatus("grant_spark", {
        status: "success",
        summary: `spark id ${sparkId.slice(0, 8)}…`,
      });
    });

    await runStep("nofo_extract", async () => {
      const path = buildM0Path(
        plane,
        o,
        `/grant-sparks/${sparkId}/nofo/extract-stub`,
      );
      setStatus("nofo_extract", { pathLine: `POST ${path}` });
      const j = await postNofoExtractStub(baseUrl, plane, o, sparkId);
      const n = j.checklist_row_count ?? "?";
      setStatus("nofo_extract", {
        status: "success",
        summary: `checklist rows: ${n}`,
      });
    });

    await runStep("requirements", async () => {
      const path = buildM0Path(
        plane,
        o,
        `/grant-sparks/${sparkId}/nofo/requirements`,
      );
      setStatus("requirements", { pathLine: `GET ${path}` });
      const j = await getNofoRequirements(baseUrl, plane, o, sparkId);
      const n = Array.isArray(j.requirements) ? j.requirements.length : 0;
      setStatus("requirements", {
        status: "success",
        summary: `${n} requirement(s)`,
      });
    });

    await runStep("score", async () => {
      const path = buildM0Path(plane, o, `/grant-sparks/${sparkId}/score`);
      setStatus("score", { pathLine: `POST ${path}` });
      await postScoreSpark(baseUrl, plane, o, sparkId);
      setStatus("score", { status: "success", summary: "score persisted" });
    });

    await runStep("pursuit", async () => {
      const path = buildM0Path(plane, o, `/grant-sparks/${sparkId}/pursuit`);
      const url = new URL(path, "http://local.example");
      url.searchParams.set("actor_id", actorId);
      setStatus("pursuit", { pathLine: `POST ${url.pathname}${url.search}` });
      const j = await openPursuit(baseUrl, plane, o, sparkId, actorId, "M0 shell demo pursuit.");
      const id = j.id as string | undefined;
      if (!id) {
        throw new Error("response missing id");
      }
      pursuitId = id;
      setStatus("pursuit", {
        status: "success",
        summary: `pursuit id ${pursuitId.slice(0, 8)}…`,
      });
    });

    await runStep("pursuit_detail", async () => {
      const path = buildM0Path(plane, o, `/pursuits/${pursuitId}`);
      setStatus("pursuit_detail", { pathLine: `GET ${path}` });
      const j = await getPursuitDetail(baseUrl, plane, o, pursuitId);
      const tasks = j.tasks as unknown[] | undefined;
      const cal = j.calendar_events as unknown[] | undefined;
      const t = tasks?.length ?? 0;
      const c = cal?.length ?? 0;
      setStatus("pursuit_detail", {
        status: "success",
        summary: `${t} task(s), ${c} calendar event(s)`,
      });
    });

    await runStep("form_package", async () => {
      const path = buildM0Path(plane, o, `/pursuits/${pursuitId}/form-package`);
      const url = new URL(path, "http://local.example");
      url.searchParams.set("actor_id", actorId);
      setStatus("form_package", { pathLine: `POST ${url.pathname}${url.search}` });
      const j = await postFormPackage(baseUrl, plane, o, pursuitId, actorId);
      const engine = j.package_engine as string | undefined;
      setStatus("form_package", {
        status: "success",
        summary: engine ?? "form package created",
      });
    });

    await runStep("trust_manifest", async () => {
      const path = buildM0Path(plane, o, "/trust/manifest");
      setStatus("trust_manifest", { pathLine: `GET ${path}` });
      const j = await getTrustManifest(baseUrl, plane, o);
      const ver = j.manifest_schema_version as string | undefined;
      setStatus("trust_manifest", {
        status: "success",
        summary: ver ?? "ok",
      });
    });

    await runStep("audit_events", async () => {
      const path = buildM0Path(plane, o, "/trust/audit-events");
      const url = new URL(path, "http://local.example");
      url.searchParams.set("limit", "100");
      setStatus("audit_events", { pathLine: `GET ${url.pathname}${url.search}` });
      const j = await getAuditEvents(baseUrl, plane, o, 100);
      const n = Array.isArray(j.events) ? j.events.length : 0;
      setStatus("audit_events", { status: "success", summary: `${n} event(s)` });
    });

    await runStep("review_summary", async () => {
      const path = buildM0Path(plane, o, "/trust/review-summary");
      setStatus("review_summary", { pathLine: `GET ${path}` });
      const j = await getReviewSummary(baseUrl, plane, o);
      const n = j.review_artifact_count ?? "?";
      setStatus("review_summary", {
        status: "success",
        summary: `artifacts: ${n}`,
      });
    });

    await runStep("org_export", async () => {
      const path = buildM0Path(plane, o, "/export/org-data-snapshot");
      const url = new URL(path, "http://local.example");
      url.searchParams.set("audit_sample_limit", "50");
      url.searchParams.set("actor_id", actorId);
      url.searchParams.set("include_sf424_previews", "false");
      setStatus("org_export", { pathLine: `GET ${url.pathname}${url.search}` });
      const j = await getOrgDataSnapshot(baseUrl, plane, o, {
        actorId,
        auditSampleLimit: 50,
        includeSf424Previews: false,
      });
      const ver = j.snapshot_schema_version as string | undefined;
      setStatus("org_export", {
        status: "success",
        summary: ver ?? "exported",
      });
    });
  } catch {
    const failed = steps.find((s) => s.status === "error");
    return { ok: false, failedStepKey: failed?.key };
  }

  return { ok: true, sparkId, pursuitId };
}
