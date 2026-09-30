import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SignInPage } from "./SignInPage";

/**
 * The front door's rules.
 *
 * The page it replaced greeted a customer with two buttons reading "Not yet
 * available" and an amber ACTION NEEDED card announcing that sign-in did not
 * work. Every assertion here is one of those defects, written down so it
 * cannot come back quietly.
 */

const DEFAULT_VALUE_INTEL = {
  schema_version: "nf_opportunity_value_intelligence_v1",
  methodology_version: "nativeforge.opportunity_value.v1",
  active_opportunity_count: 200,
  known_value_count: 166,
  unknown_value_count: 34,
  conflicting_value_count: 0,
  known_value_coverage_pct: 83,
  totals_by_currency: { USD: "57400000.00" },
  active_known_value_total_usd: "57400000.00",
  calculated_at: "2026-09-30T00:00:00+00:00",
  label: "known active opportunity value",
};

function mockProviders(entries: Array<{ key: string; label: string; configured: boolean }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/public/opportunity-value/active")) {
        return new Response(JSON.stringify(DEFAULT_VALUE_INTEL), { status: 200 });
      }
      return new Response(
        JSON.stringify({
          providers: entries.map((e) => ({
            ...e,
            start_path: `/api/auth/login?provider=${e.key}`,
            redirect_uri: "",
            scopes: "openid profile email",
          })),
          any_configured: entries.some((e) => e.configured),
          login_live: false,
          customer_auth_live: false,
        }),
        { status: 200 },
      );
    }),
  );
}

const NEITHER = [
  { key: "microsoft", label: "Microsoft", configured: false },
  { key: "google", label: "Google", configured: false },
];

const GOOGLE_ONLY = [
  { key: "microsoft", label: "Microsoft", configured: false },
  { key: "google", label: "Google", configured: true },
];

describe("SignInPage", () => {
  beforeEach(() => mockProviders(NEITHER));
  afterEach(() => vi.unstubAllGlobals());

  it("greets, rather than apologising", async () => {
    render(<SignInPage />);
    expect(
      await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: /funding intelligence/i }),
    ).toBeInTheDocument();
  });

  it("never puts 'not yet available' inside a provider button", async () => {
    /*
     * The specific defect. A control labelled "Continue with Google Not yet
     * available" makes the product look broken rather than unfinished in one
     * place, and it was the first thing a customer read.
     */
    render(<SignInPage />);
    const microsoft = await screen.findByRole("button", { name: /continue with microsoft/i });
    expect(microsoft.textContent).not.toMatch(/not yet available/i);
  });

  it("offers both providers even when neither is connected", async () => {
    // Hiding Microsoft leaves a Microsoft customer wondering whether the
    // product supports them at all.
    render(<SignInPage />);
    expect(await screen.findByRole("button", { name: /continue with microsoft/i })).toBeVisible();
    expect(await screen.findByRole("button", { name: /continue with google/i })).toBeVisible();
  });

  it("makes an unconfigured provider genuinely unusable", async () => {
    // Not merely styled as inactive. A dead button dressed as a live one is
    // a lie the customer discovers by clicking it.
    render(<SignInPage />);
    const google = await screen.findByRole("button", { name: /continue with google/i });
    expect(google).toBeDisabled();
  });

  it("states the unconnected case once, quietly, and not as an alert", async () => {
    render(<SignInPage />);
    await screen.findByRole("button", { name: /continue with google/i });
    expect(screen.getByText(/not yet connected for this workspace/i)).toBeInTheDocument();
    // An operational error card is what dominated the old page.
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders a configured provider as a real navigation", async () => {
    /*
     * The server issues state and a PKCE challenge and then redirects, so
     * this has to be an anchor. A button with a fetch would follow the
     * redirect in the background and arrive nowhere.
     */
    mockProviders(GOOGLE_ONLY);
    render(<SignInPage />);
    const google = await screen.findByRole("link", { name: /continue with google/i });
    expect(google).toHaveAttribute("href", "/api/auth/login?provider=google");
  });

  it("says nothing about connection when a provider works", async () => {
    mockProviders(GOOGLE_ONLY);
    render(<SignInPage />);
    await screen.findByRole("link", { name: /continue with google/i });
    expect(screen.queryByText(/not yet connected/i)).toBeNull();
  });

  it("carries the canonical tagline", async () => {
    render(<SignInPage />);
    const lines = await screen.findAllByText("Find. Pursue. Govern.");
    expect(lines.length).toBeGreaterThanOrEqual(1);
  });

  it("draws the full kit lockup, with the tagline in the artwork", async () => {
    render(<SignInPage />);
    await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i });
    const lockup = document.querySelector(".nf-login-lockup");
    expect(lockup).toHaveAttribute("data-brand-mode", "full");
    expect(lockup?.querySelector("img")?.getAttribute("src")).toBe(
      "/brand/nf-lockup-dark.png",
    );
    expect(screen.getAllByText("Find. Pursue. Govern.").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByRole("heading", { level: 2, name: /funding intelligence/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Built for Native nations.")).toBeInTheDocument();
    expect(screen.getByText("Find")).toBeInTheDocument();
    expect(screen.getByText("Pursue")).toBeInTheDocument();
    expect(screen.getByText("Govern")).toBeInTheDocument();
    expect(
      screen.getByText("Discover and qualify the right opportunities."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Move every opportunity from decision to submission."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Keep the work accountable, compliant, and under control."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/with AI/i)).toBeNull();
    expect(screen.queryByText(/grant writing/i)).toBeNull();
  });

  it("keeps the submission doctrine in the footer, worded exactly", async () => {
    render(<SignInPage />);
    expect(
      await screen.findByText(/submission remains under your organization/i),
    ).toBeInTheDocument();
  });

  it("reports a returning sign-in failure without shouting", async () => {
    render(<SignInPage notice="sign_in_incomplete" />);
    const notice = await screen.findByRole("status");
    expect(notice.textContent).toMatch(/did not finish/i);
  });

  it("shows live known active value from the public API", async () => {
    render(<SignInPage />);
    expect(await screen.findByText("$57.4M")).toBeInTheDocument();
    expect(screen.getByText(/known value across/i)).toBeInTheDocument();
    expect(screen.getByText(/83% coverage/i)).toBeInTheDocument();
  });

  it("does not invent a dollar figure when value API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/api/public/opportunity-value/active")) {
          return new Response("nope", { status: 503 });
        }
        return new Response(
          JSON.stringify({
            providers: NEITHER.map((e) => ({
              ...e,
              start_path: `/api/auth/login?provider=${e.key}`,
              redirect_uri: "",
              scopes: "openid profile email",
            })),
            any_configured: false,
            login_live: false,
            customer_auth_live: false,
          }),
          { status: 200 },
        );
      }),
    );
    render(<SignInPage />);
    await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i });
    expect(screen.queryByText(/\$\d/)).toBeNull();
    expect(
      screen.getByText(/live funding value metrics are temporarily unavailable/i),
    ).toBeInTheDocument();
  });

  it("survives a provider list that cannot be fetched", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/api/public/opportunity-value/active")) {
          return new Response(JSON.stringify(DEFAULT_VALUE_INTEL), { status: 200 });
        }
        return new Response("nope", { status: 500 });
      }),
    );
    render(<SignInPage />);
    // The page still renders its heading rather than collapsing to nothing.
    expect(
      await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/not yet connected for this workspace/i)).toBeInTheDocument(),
    );
  });
});
