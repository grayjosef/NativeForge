import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import demoPayload from "../demo/sc_customer_demo.json";
import { DemoOperatingShell } from "./DemoOperatingShell";

// This project does not configure auto-cleanup, so a previous render stays in
// document.body and the "renders nothing" cases would pass on stale DOM.
afterEach(cleanup);

// Gate 129B. These six must reach the screen. A demo that shows a Tribal
// government a product story without saying which parts are not live is the
// one failure mode this whole campaign exists to prevent.
const REQUIRED_LABELS = [
  "CONTROLLED DEMO DATA",
  "AUTH NOT LIVE",
  "LIVE SOURCE MONITORING NOT ACTIVE",
  "EMAIL DELIVERY NOT ACTIVE",
  "OBJECT STORE NOT CONFIGURED",
  "PROVIDER CONFIG REQUIRED FOR LOGIN",
];

const REQUIRED_SECTIONS = [
  "tenant_profile",
  "source_watchlist",
  "weekly_digest",
  "pursuit_pipeline",
  "awarded_grants",
  "award_requirements",
  "proof_audit",
  "document_metadata",
  "readiness_blockers",
  "next_actions",
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const shell = (demoPayload as any).demo_operating_shell;

describe("DemoOperatingShell", () => {
  it("the committed payload carries an operating shell", () => {
    expect(shell).toBeTruthy();
    expect(shell.section_count).toBe(REQUIRED_SECTIONS.length);
  });

  it("renders all ten sections in order", () => {
    render(<DemoOperatingShell shell={shell} />);
    for (const id of REQUIRED_SECTIONS) {
      expect(screen.getByTestId(`demo-shell-section-${id}`)).toBeInTheDocument();
    }
    expect(shell.section_ids).toEqual(REQUIRED_SECTIONS);
  });

  it("displays every active truth label", () => {
    render(<DemoOperatingShell shell={shell} />);
    const labels = screen.getByTestId("demo-truth-labels");
    for (const label of REQUIRED_LABELS) {
      expect(labels).toHaveTextContent(label);
    }
  });

  it("does not claim auth, monitoring, email or object store are live", () => {
    render(<DemoOperatingShell shell={shell} />);
    expect(shell.customer_auth_live).toBe(false);
    expect(shell.login_live).toBe(false);
    expect(shell.live_source_monitoring_active).toBe(false);
    expect(shell.email_delivery_active).toBe(false);
    expect(shell.object_store_configured).toBe(false);
    expect(shell.provider_ready).toBe(false);
    expect(shell.operational_section_count).toBe(0);
    expect(shell.rows_written).toBe(0);
  });

  it("every section reports zero rows written", () => {
    render(<DemoOperatingShell shell={shell} />);
    for (const section of shell.sections) {
      expect(section.rows_written).toBe(0);
      expect(section.data_source).toBe("controlled_demo");
      expect(section.operational).toBe(false);
    }
  });

  it("a label that is not active is not rendered", () => {
    // The point of `active` being computed: when auth goes live the label has
    // to disappear on its own. If it rendered regardless, the six labels would
    // be six hardcoded strings and would still be there after the fix.
    const live = {
      ...shell,
      truth_labels: shell.truth_labels.map(
        (l: { label: string; active: boolean }) =>
          l.label === "AUTH NOT LIVE" ? { ...l, active: false } : l,
      ),
    };
    render(<DemoOperatingShell shell={live} />);
    const labels = screen.getByTestId("demo-truth-labels");
    expect(labels).not.toHaveTextContent("AUTH NOT LIVE");
    expect(labels).toHaveTextContent("CONTROLLED DEMO DATA");
  });

  it("renders nothing when there is no shell", () => {
    const { container } = render(<DemoOperatingShell shell={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the blocking reason rather than an empty status", () => {
    render(<DemoOperatingShell shell={shell} />);
    const blockers = screen.getByTestId("demo-shell-blockers-awarded_grants");
    expect(blockers).toHaveTextContent("no_customer_auth_so_nobody_owns_the_row");
  });
});
