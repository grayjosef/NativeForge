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
