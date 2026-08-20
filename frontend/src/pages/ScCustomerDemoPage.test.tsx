import { describe, expect, it } from "vitest";

import { loadScCustomerDemoPayload } from "../demo/loadScCustomerDemo";
import { ScCustomerDemoPage } from "./ScCustomerDemoPage";
import { renderToStaticMarkup } from "react-dom/server";

describe("ScCustomerDemoPage", () => {
  it("renders buyer story and honest flags from static payload", () => {
    const payload = loadScCustomerDemoPayload();
    const html = renderToStaticMarkup(<ScCustomerDemoPage payload={payload} />);
    expect(html).toContain("sc-customer-demo-page");
    expect(html).toContain("live_ingestion=false");
    expect(html).toContain("final_eligibility_claim_allowed=false");
    expect(html).toContain("live_ingest_claimed=false");
    expect(html).toContain("What NativeForge found");
    expect(html).toContain("south_carolina=");
    expect(html).toContain("federal=");
    expect(html).toContain("nofo_pdf_extraction=NOT_IN_THIS_BLOCK");
    expect(payload.opportunities.south_carolina_count).toBeGreaterThanOrEqual(1);
    expect(payload.opportunities.federal_count).toBeGreaterThanOrEqual(1);
  });

  it("renders loading empty and error states", () => {
    expect(renderToStaticMarkup(<ScCustomerDemoPage loading />)).toContain(
      "sc-demo-loading",
    );
    expect(
      renderToStaticMarkup(<ScCustomerDemoPage error="boom" payload={null} />),
    ).toContain("sc-demo-error");
    expect(renderToStaticMarkup(<ScCustomerDemoPage payload={null} />)).toContain(
      "sc-demo-empty",
    );
  });
});
