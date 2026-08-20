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

    const table = page.getByTestId("sc-demo-review-table");
    await expect(table).toBeVisible();
    await expect(table).toContainText("south_carolina");
    await expect(table).toContainText("federal");
    await expect(table).toContainText("true"); // human review
    await expect(table).toContainText("false"); // final claim
  });
});
