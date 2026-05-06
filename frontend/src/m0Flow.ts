/** M0 spine — aligns with docs/m0-demo-runbook.md */

export type Plane = "demo" | "real";

export type HttpMethod = "GET" | "POST";

export interface M0Step {
  n: number;
  phase: string;
  title: string;
  summary: string;
  method: HttpMethod;
  /** Path after `/v1/nf/{plane}/orgs/{ORG}` */
  pathSuffix: string;
}

export const M0_STEPS: M0Step[] = [
  {
    n: 1,
    phase: "Profile",
    title: "Tribal profile",
    summary:
      "Organization identity and contacts used later for SF-424 preview and exports.",
    method: "POST",
    pathSuffix: "/tribal-profile",
  },
  {
    n: 2,
    phase: "Opportunity",
    title: "Grant Spark",
    summary: "Create or ingest an opportunity row tied to the tenant.",
    method: "POST",
    pathSuffix: "/grant-sparks",
  },
  {
    n: 3,
    phase: "NOFO",
    title: "NOFO extract (stub)",
    summary:
      "Deterministic stub extraction producing structured requirements and a review-gated artifact — not live Grants.gov or LLM extraction.",
    method: "POST",
    pathSuffix: "/grant-sparks/{SPARK}/nofo/extract-stub",
  },
  {
    n: 4,
    phase: "NOFO",
    title: "Structured requirements",
    summary: "Checklist rows exposed as requirements after extraction.",
    method: "GET",
    pathSuffix: "/grant-sparks/{SPARK}/nofo/requirements",
  },
  {
    n: 5,
    phase: "Score",
    title: "Deterministic score",
    summary:
      "Rule-based pursuit-readiness score persisted for the spark — same inputs yield the same outputs.",
    method: "POST",
    pathSuffix: "/grant-sparks/{SPARK}/score",
  },
  {
    n: 6,
    phase: "Pursuit",
    title: "Open pursuit",
    summary:
      "Creates the pursuit pipeline row; downstream tasks and calendar events attach here.",
    method: "POST",
    pathSuffix: "/grant-sparks/{SPARK}/pursuit",
  },
  {
    n: 7,
    phase: "Pursuit",
    title: "Tasks and calendar",
    summary: "Pursuit detail includes seeded tasks and calendar events for the workflow.",
    method: "GET",
    pathSuffix: "/pursuits/{PURSUIT}",
  },
  {
    n: 8,
    phase: "Forms",
    title: "Form package / SF-424 preview",
    summary:
      "Review-gated form package with SF-424 JSON preview — not an agency submission or final PDF.",
    method: "POST",
    pathSuffix: "/pursuits/{PURSUIT}/form-package",
  },
  {
    n: 9,
    phase: "Trust",
    title: "Trust manifest",
    summary: "Policy and capability narrative, including M0 scope limits (e.g. no auto-submit).",
    method: "GET",
    pathSuffix: "/trust/manifest",
  },
  {
    n: 10,
    phase: "Trust",
    title: "Audit events",
    summary: "Tenant-scoped audit stream for operator and buyer review.",
    method: "GET",
    pathSuffix: "/trust/audit-events",
  },
  {
    n: 11,
    phase: "Trust",
    title: "Review summary",
    summary: "Consolidated view of review-gated artifacts and status.",
    method: "GET",
    pathSuffix: "/trust/review-summary",
  },
  {
    n: 12,
    phase: "Trust",
    title: "Org data export",
    summary:
      "Org-wide JSON snapshot (and recorded audit) — data ownership and portability.",
    method: "GET",
    pathSuffix: "/export/org-data-snapshot",
  },
];

export function expandPathSuffix(
  pathSuffix: string,
  spark: string,
  pursuit: string,
): string {
  return pathSuffix
    .replace("{SPARK}", spark || "{SPARK}")
    .replace("{PURSUIT}", pursuit || "{PURSUIT}");
}

export function buildM0Path(plane: Plane, org: string, pathSuffix: string): string {
  const o = org.trim() || "{ORG}";
  return `/v1/nf/${plane}/orgs/${o}${pathSuffix}`;
}
