import { readHttpError } from "./m0ApiClient";
import { buildM0Path, type Plane } from "./m0Flow";

export interface StageMetrics {
  count?: number;
  known_count?: number;
  unknown_count?: number;
  known_value_coverage_pct?: number;
  totals_by_currency?: Record<string, string>;
  known_value_total_usd?: string | null;
  supported?: boolean;
}

export interface ExpiringWindowMetrics {
  expiring_opportunity_count?: number;
  expiring_known_count?: number;
  expiring_known_value_by_currency?: Record<string, string>;
}

export interface OrgFunnelResponse {
  funnel_methodology_version: string;
  value_methodology_version: string;
  calculated_at: string;
  stages_are_additive: boolean;
  stages: {
    active?: StageMetrics;
    native_relevant?: StageMetrics;
    eligibility?: {
      eligible?: StageMetrics;
      conditionally_eligible?: StageMetrics;
      ineligible?: StageMetrics;
      unknown_eligibility?: StageMetrics;
    };
    pursuing?: StageMetrics;
  };
  funding_landscape_v3?: {
    expiring_value?: {
      windows?: Record<string, ExpiringWindowMetrics>;
    };
  };
}

export async function fetchOrgOpportunityValueFunnel(
  baseUrl: string,
  plane: Plane,
  orgId: string,
): Promise<OrgFunnelResponse> {
  const path = buildM0Path(plane, orgId, "/intelligence/opportunity-value-funnel");
  const res = await fetch(`${baseUrl}${path}`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(await readHttpError(res));
  }
  return (await res.json()) as OrgFunnelResponse;
}

export function formatUsdCompact(total: string | null | undefined): string | null {
  if (total == null || total.trim() === "") return null;
  const n = Number.parseFloat(total);
  if (!Number.isFinite(n)) return null;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
