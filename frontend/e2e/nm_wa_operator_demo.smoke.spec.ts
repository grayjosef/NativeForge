import { expect, test, type Page } from "@playwright/test";

/**
 * NM/WA operator demo Playwright smoke — asserts all 14 required surfaces.
 * Offline static bridge data; no live ingest / auth mutation.
 */

const DEMO_PATH = "/?view=nm_wa_operator_demo";

async function openDemo(page: Page) {
  await page.goto(DEMO_PATH);
  await expect(page.getByTestId("nm-wa-operator-demo-page")).toBeVisible();
}

test.describe("NM/WA operator demo Playwright smoke", () => {
  test("renders all required operator surfaces", async ({ page }) => {
    await openDemo(page);

    // NM fixture + classify+match + operator report
    const nm = page.getByTestId("nm-wa-demo-nm-summary");
    await expect(nm).toBeVisible();
    await expect(nm).toContainText("fixtures=22");
    await expect(nm).toContainText("classify+match=22");
    await expect(nm).toContainText("operator report rows=22");

    // WA fixture + classify+match + operator report
    const wa = page.getByTestId("nm-wa-demo-wa-summary");
    await expect(wa).toBeVisible();
    await expect(wa).toContainText("fixtures=29");
    await expect(wa).toContainText("classify+match=29");
    await expect(wa).toContainText("operator report rows=29");

    // Combined review queue
    const combined = page.getByTestId("nm-wa-demo-combined-summary");
    await expect(combined).toBeVisible();
    await expect(combined).toContainText("combined=51");
    await expect(combined).toContainText("review needed=");

    // Missing-data display (must not hide)
    const missing = page.getByTestId("nm-wa-demo-missing-data");
    await expect(missing).toBeVisible();
    await expect(missing).toContainText("hidden_missing_data=false");

    // Human review + next-check
    const next = page.getByTestId("nm-wa-demo-next-check");
    await expect(next).toBeVisible();
    await expect(next).toContainText("human_review_required_count=51");
    await expect(next).toContainText("rows with next-checks=51");

    // Provenance/evidence
    const provenance = page.getByTestId("nm-wa-demo-provenance");
    await expect(provenance).toBeVisible();
    await expect(provenance).toContainText("notes_visible=true");

    // Confidence/readiness labels
    const confidence = page.getByTestId("nm-wa-demo-confidence");
    await expect(confidence).toBeVisible();
    await expect(confidence).toContainText("confidence=");
    await expect(page.getByTestId("nm-wa-demo-review-table")).toContainText(
      "Readiness",
    );

    // No final eligibility claim
    const flags = page.getByTestId("nm-wa-demo-flags");
    await expect(flags).toContainText("final_eligibility_claim_allowed=false");
    await expect(flags).toContainText("source_activation=false");
    await expect(flags).toContainText("auth_required=false");

    // Broad/partial relevance remains discoverable (sample rows)
    const table = page.getByTestId("nm-wa-demo-review-table");
    await expect(table).toBeVisible();
    await expect(table).toContainText("visible_in_operator_review");
    await expect(table).toContainText("true"); // human review true
  });
});
