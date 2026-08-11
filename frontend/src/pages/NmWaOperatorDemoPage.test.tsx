import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NmWaOperatorDemoPage } from "./NmWaOperatorDemoPage";
import { loadNmWaOperatorDemoPayload } from "../demo/loadNmWaOperatorDemo";

describe("NmWaOperatorDemoPage", () => {
  it("renders NM/WA summaries and advisory flags", () => {
    render(<NmWaOperatorDemoPage />);
    expect(screen.getByTestId("nm-wa-operator-demo-page")).toBeInTheDocument();
    expect(screen.getByTestId("nm-wa-demo-title")).toHaveTextContent(
      "NM/WA Operator Surfacing Demo",
    );
    expect(screen.getByTestId("nm-wa-demo-nm-summary")).toHaveTextContent(
      "fixtures=22",
    );
    expect(screen.getByTestId("nm-wa-demo-wa-summary")).toHaveTextContent(
      "fixtures=29",
    );
    expect(screen.getByTestId("nm-wa-demo-combined-summary")).toHaveTextContent(
      "combined=51",
    );
    expect(screen.getByTestId("nm-wa-demo-flags")).toHaveTextContent(
      "final_eligibility_claim_allowed=false",
    );
    expect(screen.getByTestId("nm-wa-demo-missing-data")).toHaveTextContent(
      "hidden_missing_data=false",
    );
    expect(screen.getByTestId("nm-wa-demo-next-check")).toHaveTextContent(
      "human_review_required_count=51",
    );
  });

  it("keeps payload invariants for injected data", () => {
    const payload = loadNmWaOperatorDemoPayload();
    expect(payload.final_eligibility_claim_allowed).toBe(false);
    expect(payload.auth_required).toBe(false);
    expect(payload.ui_flags.show_activation_controls).toBe(false);
    expect(payload.rows.every((r) => r.human_review_required)).toBe(true);
    expect(payload.rows.every((r) => r.operator_next_check.length > 0)).toBe(
      true,
    );
  });
});
