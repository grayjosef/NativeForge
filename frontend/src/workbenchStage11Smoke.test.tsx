import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkbenchStateBadges } from "./components/workbench/WorkbenchStateBadges";
import { DiscoveryIntakeReviewScreen } from "./components/workbench/stage11/DiscoveryIntakeReviewScreen";
import { MatchingReadinessScreen } from "./components/workbench/stage11/MatchingReadinessScreen";
import { NativeRelevanceReviewScreen } from "./components/workbench/stage11/NativeRelevanceReviewScreen";
import { OrgApplicantProfileScreen } from "./components/workbench/stage11/OrgApplicantProfileScreen";
import { SourceReviewQueueScreen } from "./components/workbench/stage11/SourceReviewQueueScreen";
import { WorkbenchStage11 } from "./pages/WorkbenchStage11";

const emptyList = { loading: false, error: null, data: [] as Record<string, unknown>[] };
const emptyRecord = { loading: false, error: null, data: null };

const mockBundle = {
  loading: false,
  error: null,
  data: {
    intake_preview: {
      previews: [{ fixture_key: "foi_demo_complete" }],
    },
    native_relevance_preview: {
      previews: [
        {
          fixture_key: "nrc_demo_native_specific",
          classification: {
            classification_label: "native_specific",
            confidence: "confirmed",
            human_review_required: false,
            overclaim_guard: { overclaim_blocked: false },
          },
          explanation: { operator_next_check: "Verify source." },
        },
      ],
    },
    org_applicant_profile_preview: {
      previews: [
        {
          fixture_key: "oap_demo_incomplete",
          human_review_required: true,
          review_status: "incomplete",
          application_readiness: "incomplete",
          profile_record: { profile_fields: { legal_name: "UNKNOWN" } },
          evaluation: { unknown_field_count: 3 },
        },
      ],
    },
    matching_readiness_preview: {
      records: [
        {
          fixture_key: "mr_demo_strong_unconfirmed",
          match_label: "needs_operator_review",
          readiness_label: "ready_with_review",
          match_evaluation: {
            applicant_recommendation_guard: { recommendation_blocked: true },
            match_dimensions: {
              blockers: { blocker_codes: [] },
              missing_data: { missing_data_flags: [] },
            },
          },
          readiness_evaluation: {
            eligibility_guard: { eligibility_blocked: true },
          },
          next_actions: [{ topic: "needs_operator_review" }],
        },
      ],
    },
  },
};

describe("WorkbenchStateBadges", () => {
  it("shows needs operator review badge", () => {
    render(<WorkbenchStateBadges humanReviewRequired matchLabel="needs_operator_review" />);
    expect(screen.getByText(/needs operator review/i)).toBeInTheDocument();
  });
});

describe("Stage 11 screens smoke", () => {
  const runId = `smoke-${Date.now()}`;
  const results: { screen: string; pass: boolean }[] = [];

  it(`run ${runId} — source review queue`, () => {
    render(
      <SourceReviewQueueScreen
        baseUrl="http://localhost:8000"
        plane="demo"
        orgId="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        reviewItems={emptyList}
        advisoryBundle={mockBundle}
      />,
    );
    const pass = !!screen.getByRole("heading", { name: /source review queue/i });
    results.push({ screen: "source-review-queue", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — discovery intake`, () => {
    render(<DiscoveryIntakeReviewScreen advisoryBundle={mockBundle} />);
    const pass = !!screen.getByRole("heading", { name: /discovery \/ intake review/i });
    results.push({ screen: "discovery-intake-review", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — native relevance`, () => {
    render(<NativeRelevanceReviewScreen advisoryBundle={mockBundle} />);
    const pass = !!screen.getByRole("heading", { name: /native relevance review/i });
    results.push({ screen: "native-relevance-review", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — org profile`, () => {
    render(<OrgApplicantProfileScreen advisoryBundle={mockBundle} />);
    const pass = !!screen.getByRole("heading", { name: /org \/ applicant profile/i });
    results.push({ screen: "org-applicant-profile", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — matching readiness`, () => {
    render(<MatchingReadinessScreen advisoryBundle={mockBundle} />);
    const pass = !!screen.getByRole("heading", { name: /matching \+ readiness/i });
    results.push({ screen: "matching-readiness", pass });
    expect(pass).toBe(true);
  });

  it(`run ${runId} — stage11 tabs shell`, () => {
    render(
      <WorkbenchStage11
        plane="demo"
        orgId="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        orgOk
        baseUrl="http://localhost:8000"
        advisoryBundle={mockBundle}
        reviewItems={emptyList}
        pack={emptyRecord}
        ledgerSummary={emptyRecord}
        ledgerOpen={emptyRecord}
      />,
    );
    const pass = !!screen.getByRole("navigation", { name: /operator workbench sections/i });
    results.push({ screen: "workbench-stage11-shell", pass });
    expect(pass).toBe(true);
    // eslint-disable-next-line no-console
    console.info(`NF-5 workbench smoke run_id=${runId}`, results);
  });
});
