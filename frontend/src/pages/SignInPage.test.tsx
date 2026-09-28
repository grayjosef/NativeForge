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

function mockProviders(entries: Array<{ key: string; label: string; configured: boolean }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(
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
      ),
    ),
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

  it("draws the full kit lockup on ivory, with the tagline in the artwork", async () => {
    render(<SignInPage />);
    await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i });
    const lockup = document.querySelector(".nf-login-lockup");
    expect(lockup).toHaveAttribute("data-brand-mode", "full");
    expect(lockup?.querySelector("img")?.getAttribute("src")).toBe("/brand/nf-lockup.png");
    expect(screen.getAllByText("Find. Pursue. Govern.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Funding intelligence for a stronger tomorrow.")).toBeInTheDocument();
    expect(screen.getByText("Find")).toBeInTheDocument();
    expect(screen.getByText("Pursue")).toBeInTheDocument();
    expect(screen.getByText("Govern")).toBeInTheDocument();
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

  it("survives a provider list that cannot be fetched", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("nope", { status: 500 })));
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
