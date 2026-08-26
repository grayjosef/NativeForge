import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TrustCenterCard } from "./TrustCenterCard";

// This project does not configure auto-cleanup, so a previous render stays in
// document.body and the "renders nothing" cases would pass on stale DOM.
afterEach(cleanup);

// Gate 93C. The Grants.gov API terms require this notice to be displayed
// prominently within the application. It has to reach the screen — a Python
// constant and a markdown file are what Gate 92 had, and no customer could see
// either of them.
const GRANTS_GOV_NOTICE =
  "This product uses the Grants.gov API but is not endorsed or certified by " +
  "the U.S. Department of Health and Human Services.";

const baseProps = {
  auditCount: 3,
  reviewSummary: { review_artifact_count: 2 },
  exportHint: null,
  busy: false,
  error: null,
  statusChip: "Ready",
  onRefresh: () => {},
  onExportDownload: () => {},
};

describe("TrustCenterCard Grants.gov attribution", () => {
  it("renders the notice verbatim when the manifest carries it", () => {
    render(
      <TrustCenterCard
        {...baseProps}
        manifest={{
          manifest_schema_version: "m0_trust_v1",
          source_attribution: {
            grants_gov_notice: GRANTS_GOV_NOTICE,
            grants_gov_collector_active: false,
          },
        }}
      />,
    );

    const el = screen.getByTestId("nf-grants-gov-attribution");
    expect(el.textContent).toBe(GRANTS_GOV_NOTICE);
  });

  it("renders nothing rather than a paraphrase when the manifest omits it", () => {
    render(
      <TrustCenterCard
        {...baseProps}
        manifest={{ manifest_schema_version: "m0_trust_v1" }}
      />,
    );

    expect(screen.queryByTestId("nf-grants-gov-attribution")).toBeNull();
    expect(document.body.textContent).not.toContain("endorsed or certified");
  });

  it("does not invent the notice when there is no manifest at all", () => {
    render(<TrustCenterCard {...baseProps} manifest={null} />);

    expect(screen.queryByTestId("nf-grants-gov-attribution")).toBeNull();
  });

  it("renders whatever the manifest says, so drift is visible not silent", () => {
    // The component must not "correct" a wrong string into the right one —
    // that would hide a drifted manifest behind a healthy-looking UI. The
    // Python contract is what rejects a non-verbatim notice.
    render(
      <TrustCenterCard
        {...baseProps}
        manifest={{
          source_attribution: { grants_gov_notice: "Powered by Grants.gov." },
        }}
      />,
    );

    expect(screen.getByTestId("nf-grants-gov-attribution").textContent).toBe(
      "Powered by Grants.gov.",
    );
  });
});
