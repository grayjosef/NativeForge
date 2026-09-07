/**
 * Gate 144: the cockpit shows the truth, including the parts that are false.
 *
 * The test that matters most is the last one: a cockpit that rendered only the
 * green lanes would be the most dangerous thing this campaign could ship, so
 * the false lanes are asserted present with their blockers.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  BetaOnboardingCockpitPage,
  type CockpitNextActions,
  type CockpitReadiness,
} from "./BetaOnboardingCockpitPage";

const READINESS: CockpitReadiness = {
  organization_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
  cockpit_scope: "controlled_dev_demo",
  lanes: [
    {
      lane: "login",
      status: "operational",
      value: true,
      scope: "controlled_dev_demo",
      summary: "a person can sign in with Google and reach their organization",
      evidence: "self_evidencing",
      blockers: [],
      owner: null,
      usable_today: true,
    },
    {
      lane: "customer_auth",
      status: "requires_human_approval",
      value: false,
      scope: null,
      summary: "a second real person has to accept a real invite",
      evidence: "self_evidencing",
      blockers: ["invite_binding_passed"],
      owner: "a second person, and the owner who invites them",
      usable_today: false,
    },
    {
      lane: "email_delivery",
      status: "not_configured",
      value: false,
      scope: null,
      summary: "no provider is configured and nobody has activated sending",
      evidence: "self_evidencing",
      blockers: ["no_email_provider_configured", "send_activation_absent"],
      owner: "whoever chooses a provider and decides to send",
      usable_today: false,
    },
    {
      lane: "production_rollout",
      status: "production_false",
      value: false,
      scope: null,
      summary: "not approved, and no lane above is a production claim",
      evidence: "self_evidencing",
      blockers: ["production_not_approved"],
      owner: "the owner",
      usable_today: false,
    },
  ],
  operational_lanes: ["login"],
  blocked_lanes: [],
  requires_human_approval_lanes: ["customer_auth"],
  not_configured_lanes: ["email_delivery"],
  usable_today_count: 1,
  invariant_failures: [],
  production_rollout: false,
  controlled_customer_pilot: false,
};

const NEXT_ACTIONS: CockpitNextActions = {
  next_safe_action: "finish_the_controlled_beta_readiness_matrix",
  why: "every controlled_dev_demo lane that can be proved is proved",
  safe_because: "it activates nothing and changes no lane's value",
  not_this_yet: ["activating a controlled customer pilot"],
};

function renderCockpit(
  overrides: Partial<React.ComponentProps<typeof BetaOnboardingCockpitPage>> = {},
) {
  return render(
    <BetaOnboardingCockpitPage
      orgId="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
      readiness={READINESS}
      nextActions={NEXT_ACTIONS}
      loading={false}
      error={null}
      {...overrides}
    />,
  );
}

// This repo's vitest setup registers no automatic cleanup, so a file that
// renders more than once leaves every previous tree in the document.
afterEach(cleanup);

describe("BetaOnboardingCockpitPage", () => {
  it("renders the scope and says production is false", () => {
    renderCockpit();
    expect(screen.getByTestId("beta-cockpit-scope").textContent).toContain(
      "controlled_dev_demo",
    );
    const production = screen.getByTestId("beta-cockpit-production").textContent;
    expect(production).toContain("Production rollout:");
    expect(production).toContain("false");
  });

  it("shows every lane it was given", () => {
    renderCockpit();
    for (const lane of READINESS.lanes) {
      expect(screen.getByTestId(`beta-cockpit-lane-${lane.lane}`)).toBeTruthy();
    }
  });

  it("shows the false lanes and names their blockers", () => {
    renderCockpit();
    const auth = screen.getByTestId("beta-cockpit-lane-customer_auth");
    expect(auth.getAttribute("data-lane-value")).toBe("false");
    expect(
      screen.getByTestId("beta-cockpit-blockers-customer_auth").textContent,
    ).toContain("invite_binding_passed");
    expect(
      screen.getByTestId("beta-cockpit-blockers-email_delivery").textContent,
    ).toContain("no_email_provider_configured");
  });

  it("does not claim a production capability anywhere on the page", () => {
    const { container } = renderCockpit();
    const text = container.textContent ?? "";
    expect(text).not.toContain("production ready");
    expect(text).not.toContain("Production ready");
    expect(text).not.toContain("live monitoring");
    // The word "Working" is only used for lanes that are operational.
    const working = Array.from(
      container.querySelectorAll('[data-lane-status="operational"]'),
    );
    expect(working.length).toBe(READINESS.operational_lanes.length);
  });

  it("names no customer, Tribe, grant, eligibility or deadline", () => {
    const { container } = renderCockpit();
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["tribe", "eligib", "deadline", "award amount"]) {
      expect(text).not.toContain(forbidden);
    }
  });

  it("shows the next safe action and what is deliberately not yet", () => {
    renderCockpit();
    expect(screen.getByTestId("beta-cockpit-next-action").textContent).toContain(
      "finish_the_controlled_beta_readiness_matrix",
    );
    expect(screen.getByTestId("beta-cockpit-not-yet").textContent).toContain(
      "controlled customer pilot",
    );
  });

  it("tells a signed-out operator to sign in rather than showing nothing", () => {
    renderCockpit({
      readiness: null,
      error: "Sign in to your demo organization to see readiness.",
    });
    expect(screen.getByTestId("beta-cockpit-error").textContent).toContain(
      "Sign in",
    );
  });
});
