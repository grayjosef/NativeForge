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
    expect(html).toContain("What NativeForge did");
    expect(html).toContain("south_carolina=");
    expect(html).toContain("federal=");
    expect(payload.opportunities.south_carolina_count).toBeGreaterThanOrEqual(1);
    expect(payload.opportunities.federal_count).toBeGreaterThanOrEqual(1);
  });
});
