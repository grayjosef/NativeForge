import { expect, test, type Page } from "@playwright/test";

/**
 * SC Monday customer demo Playwright smoke — curated state+federal lane.
 * Offline static bridge; no live ingest / activation / auth mutation.
 */

const DEMO_PATH = "/?view=sc_customer_demo";

async function openDemo(page: Page) {
  await page.goto(DEMO_PATH);
  await expect(page.getByTestId("sc-customer-demo-page")).toBeVisible();
}

test.describe("SC customer demo Playwright smoke", () => {
  test("renders required Monday customer surfaces", async ({ page }) => {
    await openDemo(page);

    await expect(page.getByTestId("sc-demo-opening-line")).toBeVisible();
    await expect(page.getByTestId("sc-demo-closing-line")).toBeVisible();
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "curated-current",
    );
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "not automated live ingest",
    );
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "human review required",
    );
    await expect(page.getByTestId("sc-demo-allowed-claims")).toBeVisible();
    await expect(page.getByTestId("sc-demo-forbidden-claims")).toContainText(
      "Automated live ingestion",
    );
    await expect(page.getByTestId("sc-demo-opportunity-engine")).toBeVisible();
    await expect(page.getByTestId("sc-demo-engine-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-engine-flags")).toContainText(
      "org_geo_filters_federal=false",
    );
    await expect(page.getByTestId("sc-demo-engine-counts")).toContainText("sc_state");
    await expect(page.getByTestId("sc-demo-engine-counts")).toContainText("federal");
    await expect(page.getByTestId("sc-demo-eligibility-evidence")).toBeVisible();
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "federal_pairs_visible=true",
    );
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "scoring_math_changed=false",
    );
    await expect(page.getByTestId("sc-demo-eligibility-samples")).toContainText(
      "recognition_tier=",
    );
    await expect(page.getByTestId("sc-demo-eligibility-tier-why")).toContainText(
      "Federal recognition",
    );
    await expect(page.getByTestId("sc-demo-pursuit-workspace")).toBeVisible();
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "final_submission_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-summary")).toContainText(
      "pursuit workspace",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-pursuit-card-"]').first(),
    ).toContainText("not_submission_ready=");
    await expect(
      page.locator('[data-testid^="sc-demo-pursuit-card-"]').first(),
    ).toContainText("What NativeForge pre-built");
    await expect(page.getByTestId("sc-demo-application-checklist")).toBeVisible();
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "submission_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "application_complete_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-summary")).toContainText(
      "package we need to assemble",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-checklist-card-"]').first(),
    ).toContainText("why_submission_not_allowed=");
    await expect(
      page.locator('[data-testid^="sc-demo-checklist-card-"]').first(),
    ).toContainText("Missing information questions");
    await expect(page.getByTestId("sc-demo-intake-approvals")).toBeVisible();
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "upload_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "approval_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "package_readiness_unlocked=false",
    );
    await expect(page.getByTestId("sc-demo-intake-summary")).toContainText(
      "files, confirmations, and approvals",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-intake-card-"]').first(),
    ).toContainText("why_package_not_ready=");
    await expect(
      page.locator('[data-testid^="sc-demo-intake-card-"]').first(),
    ).toContainText("Required intake items");
    await expect(page.getByTestId("sc-demo-narrative-budget")).toBeVisible();
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "generated_prose_produced=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "drafting_supported=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "budget_claimed_complete=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "match_claimed_complete=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-summary")).toContainText(
      "narrative and budget areas",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-narrative-card-"]').first(),
    ).toContainText("why_drafting_not_supported=");
    await expect(
      page.locator('[data-testid^="sc-demo-narrative-card-"]').first(),
    ).toContainText("Budget / match evidence");
    await expect(page.getByTestId("sc-demo-readiness-queue")).toBeVisible();
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "not_submission_ready=true",
    );
    await expect(page.getByTestId("sc-demo-readiness-summary")).toContainText(
      "package readiness",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-readiness-card-"]').first(),
    ).toContainText("next_safest_action=");
    await expect(
      page.locator('[data-testid^="sc-demo-readiness-card-"]').first(),
    ).toContainText("Operator review queue");
    await expect(page.getByTestId("sc-demo-org-evidence-memory")).toBeVisible();
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "customer_data_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "binary_upload_persistence_supported=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-summary")).toContainText(
      "organization",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-org-memory-card-"]').first(),
    ).toContainText("Must not claim");
    await expect(
      page.locator('[data-testid^="sc-demo-org-memory-card-"]').first(),
    ).toContainText("None auto-approved without review.");
    await expect(page.getByTestId("sc-demo-nofo-extraction-pilot")).toBeVisible();
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "full_pdf_extraction_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "broad_pdf_support_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "pdf_bytes_parsed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-summary")).toContainText(
      "Controlled NOFO",
    );
    await expect(page.getByTestId("sc-demo-source-freshness")).toBeVisible();
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "continuous_monitoring_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "external_live_check_not_run=true",
    );
    await expect(page.getByTestId("sc-demo-draft-workspace")).toBeVisible();
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "ai_drafting_enabled=false",
    );
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "generated_prose_present=false",
    );
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "customer_prose_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-controlled-drafting")).toBeVisible();
    await expect(page.getByTestId("sc-demo-controlled-draft-flags")).toContainText(
      "complete_proposal_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-controlled-draft-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-proposal-honesty")).toContainText(
      "NOT_SUPPORTED",
    );

    await expect(page.getByTestId("sc-demo-banner")).toBeVisible();
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "live_ingestion=false",
    );
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "final_eligibility_claim_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "source_activation=false",
    );

    await expect(page.getByTestId("sc-demo-what-nf-did")).toContainText(
      "What NativeForge found",
    );
    await expect(page.getByTestId("sc-demo-attention")).toContainText(
      "What is uncertain / needs your attention",
    );
    await expect(page.getByTestId("sc-demo-next-actions")).toContainText(
      "What to do next",
    );

    const profiles = page.getByTestId("sc-demo-profiles");
    await expect(profiles).toContainText("profiles=10");

    const opps = page.getByTestId("sc-demo-opportunities");
    await expect(opps).toContainText("south_carolina=");
    await expect(opps).toContainText("federal=");

    await expect(page.getByTestId("sc-demo-combined-summary")).toContainText(
      "human_review=",
    );
    await expect(page.getByTestId("sc-demo-missing-data")).toContainText(
      "hidden_missing_data=false",
    );
    await expect(page.getByTestId("sc-demo-provenance")).toContainText(
      "notes_visible=true",
    );
    await expect(page.getByTestId("sc-demo-provenance")).toContainText(
      "demo_real_isolation=visible",
    );

    const table = page.getByTestId("sc-demo-review-table");
    await expect(table).toBeVisible();
    await expect(table).toContainText("south_carolina");
    await expect(table).toContainText("federal");
    await expect(table).toContainText("true"); // human review
    await expect(table).toContainText("false"); // final claim

    const nofo = page.getByTestId("sc-demo-nofo-showcase");
    await expect(nofo).toBeVisible();
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "nofo_pdf_extraction_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-buyer-sections")).toContainText(
      "What NativeForge found",
    );
    await expect(page.getByTestId("sc-demo-nofo-buyer-sections")).toContainText(
      "What needs human review",
    );

    // At least one SC and one federal intelligence card
    await expect(
      page.locator('[data-testid^="sc-demo-nofo-card-"][data-source-layer="sc_state"]'),
    ).toHaveCount(1, { timeout: 5000 });
    await expect(
      page.locator('[data-testid^="sc-demo-nofo-card-"][data-source-layer="federal"]'),
    ).not.toHaveCount(0);

    const firstCard = page.locator('[data-testid^="sc-demo-nofo-card-"]').first();
    await expect(firstCard).toContainText("What NativeForge found");
    await expect(firstCard).toContainText("What is missing");
    await expect(firstCard).toContainText("Application plan skeleton");
    await expect(firstCard).toContainText("Evidence / provenance");
    await expect(firstCard).toContainText("not_supported");
  });
});
