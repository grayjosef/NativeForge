import { apiFetchBase, readHttpError } from "./m0ApiClient";

/** Public HABEAS DATA aggregate — no organization context. */
export interface ActiveOpportunityValuePublic {
  schema_version: string;
  methodology_version: string;
  active_opportunity_count: number;
  known_value_count: number;
  unknown_value_count: number;
  conflicting_value_count: number;
  known_value_coverage_pct: number;
  totals_by_currency: Record<string, string>;
  active_known_value_total_usd: string | null;
  calculated_at: string;
  source_freshness?: { latest_last_seen_at?: string | null };
  label?: string;
  habeas_data?: string;
}

export async function fetchActiveOpportunityValuePublic(
  baseUrl: string = apiFetchBase(),
): Promise<ActiveOpportunityValuePublic> {
  const res = await fetch(`${baseUrl}/api/public/opportunity-value/active`);
  if (!res.ok) {
    throw new Error(await readHttpError(res));
  }
  return (await res.json()) as ActiveOpportunityValuePublic;
}

/** Compact USD display for hero; null when no defensible total. */
export function formatKnownActiveValueUsd(total: string | null | undefined): string | null {
  if (total == null || total.trim() === "") return null;
  const n = Number.parseFloat(total);
  if (!Number.isFinite(n)) return null;
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
