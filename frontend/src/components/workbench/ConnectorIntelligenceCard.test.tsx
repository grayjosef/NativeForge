import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectorIntelligenceCard } from "./ConnectorIntelligenceCard";

describe("ConnectorIntelligenceCard", () => {
  it("summarizes rollup and per-source connector rows from the decision pack", () => {
    render(
      <ConnectorIntelligenceCard
        baseUrl=""
        plane="demo"
        orgId="550e8400-e29b-41d4-a716-446655440001"
        block={{
          loading: false,
          error: null,
          data: {
            connector_intelligence: {
              schema_version: "nf_workbench_connector_intelligence_v1",
              rollup: {
                registry_sources_degraded: 2,
                registry_sources_failing: 1,
                registry_sources_stale: 0,
                sources_with_connector_summaries: 1,
                empty_connector_runs: 1,
                duplicate_heavy_sources: 1,
                review_required_heavy_sources: 1,
                operator_escalation_rows_total: 2,
                warning_codes_ranked: [
                  { warning_code: "connector_run_empty", occurrences: 1 },
                ],
                connector_health_counts: {
                  healthy: 0,
                  degraded: 1,
                  empty: 0,
                  failed: 0,
                  stale: 0,
                  unknown: 0,
                },
              },
              operator_escalation_recommendations_flat: [
                {
                  operator_title: "Inspect mapping",
                  operator_message: "Normalization produced warnings.",
                },
              ],
              per_source_latest_connector_run: [
                {
                  source_registry_id: "550e8400-e29b-41d4-a716-446655440000",
                  source_name: "Card Source",
                  registry_health_status: "degraded",
                  connector_health_status: "degraded",
                  attention_summary: "Registry health is degraded.",
                  check_status: "succeeded",
                  run_completed_at: "2026-01-02T00:00:00+00:00",
                  pressure_category_tags: ["connector_quality"],
                },
              ],
            },
          },
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: /connector & source-check intelligence/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Card Source")).toBeInTheDocument();
    expect(screen.getByText(/Inspect mapping/)).toBeInTheDocument();
    expect(screen.getByText(/connector_run_empty/)).toBeInTheDocument();
  });
});
