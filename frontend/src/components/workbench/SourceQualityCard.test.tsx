import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceQualityCard } from "./SourceQualityCard";

const baseProps = {
  baseUrl: "",
  plane: "demo" as const,
  orgId: "550e8400-e29b-41d4-a716-446655440001",
};

function packData(sourceQuality: Record<string, unknown>) {
  return {
    loading: false,
    error: null,
    data: {
      source_quality: sourceQuality,
    },
  };
}

describe("SourceQualityCard", () => {
  it("renders critical posture with missing lanes and recommended actions", () => {
    render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 12,
          posture: "critical",
          source_counts: { active: 0, registry_total: 0, inactive: 0 },
          health_counts: {
            healthy: 0,
            stale: 0,
            failing: 0,
            degraded: 0,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          freshness_counts: {
            never_checked: 0,
            overdue_for_check: 0,
            missing_recent_check: 0,
            due_but_not_overdue: 0,
          },
          missing_lanes: ["tribal_government", "native_nonprofit"],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [],
          reason_codes: ["no_active_sources"],
          recommended_operator_actions: [
            {
              action_type: "expand_native_priority_coverage",
              priority: "critical",
              title: "Establish Native priority lane registry coverage",
              rationale: "No active registry sources; activate doctrine lanes.",
              focus_lanes: ["tribal_government"],
              affected_source_count: 0,
              evidence_refs: [],
              should_create_action: false,
            },
          ],
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: /source quality posture/i })).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getAllByText(/Tribal Government/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Native Nonprofit/i)).toBeInTheDocument();
    expect(screen.getByText(/Establish Native priority lane registry coverage/i)).toBeInTheDocument();
    expect(screen.getByText(/expand_native_priority_coverage/i)).toBeInTheDocument();
    expect(screen.getByText(/Recommendations only/i)).toBeInTheDocument();
  });

  it("renders strong and adequate posture without crashing", () => {
    const { rerender } = render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 88,
          posture: "strong",
          source_counts: { active: 12 },
          health_counts: {
            healthy: 10,
            stale: 1,
            failing: 0,
            degraded: 1,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          missing_lanes: [],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [],
          reason_codes: [],
          recommended_operator_actions: [],
        })}
      />,
    );

    expect(screen.getByText("Strong")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();

    rerender(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 55,
          posture: "adequate",
          source_counts: { active: 6 },
          health_counts: {
            healthy: 4,
            stale: 0,
            failing: 0,
            degraded: 2,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          missing_lanes: [],
          weak_lanes: ["federal_native_specific"],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [],
          reason_codes: [],
          recommended_operator_actions: [],
        })}
      />,
    );

    expect(screen.getByText("Adequate")).toBeInTheDocument();
    expect(screen.getByText(/Federal Native Specific/i)).toBeInTheDocument();
  });

  it("renders top attention sources with health and status", () => {
    render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 40,
          posture: "weak",
          source_counts: { active: 2 },
          health_counts: {
            healthy: 0,
            stale: 1,
            failing: 1,
            degraded: 0,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          missing_lanes: [],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [
            {
              rank: 1,
              source_registry_id: "550e8400-e29b-41d4-a716-446655440099",
              source_name: "Attention Alpha",
              attention_score: 120,
              health_bucket: "failing",
              priority_level: "critical",
              source_health_status: "failing",
              is_overdue_for_check: true,
            },
          ],
          top_coverage_gaps: [],
          reason_codes: [],
          recommended_operator_actions: [],
        })}
      />,
    );

    expect(screen.getByText("Attention Alpha")).toBeInTheDocument();
    expect(screen.getAllByText("failing").length).toBeGreaterThanOrEqual(1);
    const table = screen.getByRole("table");
    expect(within(table).getByText(/Attention score 120/i)).toBeInTheDocument();
    expect(within(table).getByText(/overdue for check/i)).toBeInTheDocument();
  });

  it("renders top coverage gaps", () => {
    render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 50,
          posture: "adequate",
          source_counts: { active: 3 },
          health_counts: {
            healthy: 3,
            stale: 0,
            failing: 0,
            degraded: 0,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          missing_lanes: [],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [
            {
              gap_id: "g1",
              gap_type: "lane",
              severity: "high",
              title: "Expand tribal sources",
            },
          ],
          reason_codes: [],
          recommended_operator_actions: [],
        })}
      />,
    );

    expect(screen.getByText("Expand tribal sources")).toBeInTheDocument();
    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });

  it("handles empty and missing arrays gracefully", () => {
    render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 70,
          posture: "strong",
          source_counts: { active: 5 },
          health_counts: {
            healthy: 5,
            stale: 0,
            failing: 0,
            degraded: 0,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          freshness_counts: {},
          missing_lanes: [],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [],
          reason_codes: [],
          recommended_operator_actions: [],
        })}
      />,
    );

    expect(screen.getAllByText(/No concentration warnings/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/No automated recommendations/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/^None\.$/).length).toBeGreaterThanOrEqual(1);
  });

  it("does not render stringified JSON blobs as primary UI", () => {
    const { container } = render(
      <SourceQualityCard
        {...baseProps}
        block={packData({
          schema_version: "nf_discovery_source_quality_v1",
          data_quality_score: 61,
          posture: "adequate",
          source_counts: { active: 4 },
          health_counts: {
            healthy: 4,
            stale: 0,
            failing: 0,
            degraded: 0,
            empty: 0,
            attention_needed: 0,
            unknown: 0,
          },
          missing_lanes: [],
          weak_lanes: [],
          overrepresented_lanes: [],
          top_attention_sources: [],
          top_coverage_gaps: [],
          reason_codes: ["low_coverage_score"],
          recommended_operator_actions: [],
        })}
      />,
    );

    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\{"schema_version"\s*:/);
    expect(text).not.toMatch(/\{"source_counts"\s*:/);
  });
});
