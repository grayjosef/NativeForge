import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivationReadinessPreviewStep } from "./components/stage12/ActivationReadinessPreviewStep";
import { EvidenceAuditTrailStep } from "./components/stage12/EvidenceAuditTrailStep";
import { NativeRelevanceStep } from "./components/stage12/NativeRelevanceStep";
import { OperatorDecisionStep } from "./components/stage12/OperatorDecisionStep";
import { OpportunityIntakeStep } from "./components/stage12/OpportunityIntakeStep";
import { ProfileMatchReadinessStep } from "./components/stage12/ProfileMatchReadinessStep";
import { SourceDiscoveryStep } from "./components/stage12/SourceDiscoveryStep";
import { SourceQualityReviewStep } from "./components/stage12/SourceQualityReviewStep";
import { Stage12GuidedDemo } from "./components/stage12/Stage12GuidedDemo";

const mockPath = {
  loading: false,
  error: null,
  data: {
    steps: [
      {
        step_id: "source-discovery",
        payload: {
          sources: [
            {
              fixture_key: "nf_stage12_src_red_cedar_portal",
              source_name: "Red Cedar Portal (Fictional)",
              source_type: "federal",
              quality_posture: "adequate",
            },
          ],
        },
      },
      {
        step_id: "source-quality-review",
        payload: {
          quality_summary: { nf_stage12_src_red_cedar_portal: "adequate" },
        },
      },
      {
        step_id: "activation-readiness-preview",
        payload: {
          source_previews: [
            {
              source_fixture_key: "nf_stage12_src_red_cedar_portal",
              source_name: "Red Cedar Portal (Fictional)",
              activation_readiness_preview: "ready_for_future_activation_review_packet",
              may_activate_now: false,
            },
          ],
        },
      },
      {
        step_id: "opportunity-intake",
        payload: {
          intake_previews: [
            {
              opportunity_record: {
                fixture_key: "nf_stage12_opp_red_cedar_language",
                opportunity_title: "Red Cedar Language (Fictional)",
              },
            },
          ],
          stale_opportunities_shown: ["nf_stage12_opp_expired_capacity"],
        },
      },
      {
        step_id: "native-relevance-review",
        payload: {
          relevance_previews: [
            {
              fixture_key: "nf_stage12_opp_red_cedar_language",
              classification: {
                classification_label: "native_specific",
                confidence: "confirmed",
                human_review_required: false,
                overclaim_guard: { overclaim_blocked: false },
              },
            },
          ],
        },
      },
      {
        step_id: "profile-match-readiness",
        payload: {
          profile_preview: {
            fixture_key: "nf_stage12_profile_red_cedar_nation",
            human_review_required: true,
            readiness_label: "ready_with_review",
            evaluation: { unknown_field_count: 1 },
          },
          match_records: [
            {
              fixture_key: "nf_stage12_pair_nf_stage12_opp_red_cedar_language",
              match_label: "needs_operator_review",
              readiness_label: "ready_with_review",
            },
          ],
        },
      },
      {
        step_id: "operator-decision",
        payload: {
          primary_opportunity_fixture_key: "nf_stage12_opp_red_cedar_language",
          match_label: "needs_operator_review",
          readiness_label: "ready_with_review",
          needs_operator_review: true,
          verified_or_approved: false,
        },
      },
      {
        step_id: "evidence-audit-trail",
        payload: {
          audit_events: [
            {
              event_type: "stage12_guided_step_viewed",
              step_id: "source-discovery",
              synthetic: true,
            },
          ],
        },
      },
    ],
  },
};

describe("Stage 12 guided flow smoke", () => {
  const runId = `stage12-smoke-${Date.now()}`;
  const results: { step: string; pass: boolean }[] = [];

  it(`run ${runId} — source-discovery`, () => {
    render(
      <SourceDiscoveryStep
        payload={
          (mockPath.data.steps[0].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /source discovery/i });
    results.push({ step: "source-discovery", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — source-quality-review`, () => {
    render(
      <SourceQualityReviewStep
        payload={
          (mockPath.data.steps[1].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /source quality review/i });
    results.push({ step: "source-quality-review", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — activation-readiness-preview`, () => {
    render(
      <ActivationReadinessPreviewStep
        payload={
          (mockPath.data.steps[2].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /activation readiness/i });
    results.push({ step: "activation-readiness-preview", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — opportunity-intake`, () => {
    render(
      <OpportunityIntakeStep
        payload={
          (mockPath.data.steps[3].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /opportunity intake/i });
    results.push({ step: "opportunity-intake", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — native-relevance-review`, () => {
    render(
      <NativeRelevanceStep
        payload={
          (mockPath.data.steps[4].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /native relevance review/i });
    results.push({ step: "native-relevance-review", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — profile-match-readiness`, () => {
    render(
      <ProfileMatchReadinessStep
        payload={
          (mockPath.data.steps[5].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /profile match \+ readiness/i });
    results.push({ step: "profile-match-readiness", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — operator-decision`, () => {
    render(
      <OperatorDecisionStep
        payload={
          (mockPath.data.steps[6].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /operator decision/i });
    results.push({ step: "operator-decision", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — evidence-audit-trail`, () => {
    render(
      <EvidenceAuditTrailStep
        payload={
          (mockPath.data.steps[7].payload as Record<string, unknown>) ?? {}
        }
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /evidence \/ audit trail/i });
    results.push({ step: "evidence-audit-trail", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — guided demo shell`, () => {
    render(<Stage12GuidedDemo guidedPath={mockPath} />);
    const pass = !!screen.getByRole("heading", { name: /future-state demo path/i });
    results.push({ step: "guided-demo-shell", pass });
    expect(pass).toBe(true);
    // eslint-disable-next-line no-console
    console.info(`NF-6 Stage 12 smoke run_id=${runId}`, results);
  });
});
