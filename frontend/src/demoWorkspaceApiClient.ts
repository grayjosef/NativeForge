import { apiFetchBase, readHttpError } from "./m0ApiClient";

export interface DemoEducationCard {
  id: string;
  title: string;
  body: string;
}

export interface DemoWorkspaceSummary {
  title: string;
  tagline: string;
  introduction: string;
  environment_label: string;
  fixture_feed: boolean;
  find: { headline: string; opportunities: unknown[] };
  pursue: { headline: string; pursuit: unknown };
  govern: { headline: string; dashboard: unknown; trust_panel: unknown };
  education: DemoEducationCard[];
  upgrade: { cta_label: string; summary: string; contact_path: string };
}

export async function getDemoWorkspaceSummary(
  baseUrl: string = apiFetchBase(),
): Promise<DemoWorkspaceSummary> {
  const res = await fetch(`${baseUrl}/api/demo-workspace/summary`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readHttpError(res));
  return (await res.json()) as DemoWorkspaceSummary;
}
