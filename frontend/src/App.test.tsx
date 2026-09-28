import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

/**
 * Two facts about the front door.
 *
 * Both are about routing rather than rendering, because the failure they
 * guard against is silent: an unauthenticated visitor used to land on the
 * workspace, where every organization-scoped request is refused, and see one
 * missing session cookie reported as three separate product failures.
 */

function mockApi(options: { authenticated: boolean }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof Request
            ? input.url
            : String(input);

      if (url.includes("/api/auth/session")) {
        return new Response(
          JSON.stringify({
            status: options.authenticated ? "authenticated" : "unauthenticated",
            authenticated: options.authenticated,
            organization_id: options.authenticated
              ? "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
              : null,
            roles: options.authenticated ? ["org_owner"] : [],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/auth/providers")) {
        return new Response(
          JSON.stringify({
            providers: [
              {
                key: "google",
                label: "Google",
                configured: true,
                start_path: "/api/auth/login?provider=google",
                redirect_uri: "",
                scopes: "openid profile email",
              },
            ],
            any_configured: true,
            login_live: false,
            customer_auth_live: false,
          }),
          { status: 200 },
        );
      }
      if (url.includes("/health")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.includes("/trust/manifest")) {
        return new Response(JSON.stringify({ manifest_schema_version: "test" }), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(null), { status: 404 });
    }),
  );
}

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the workspace for a signed-in visitor", async () => {
    mockApi({ authenticated: true });
    render(<App />);

    // The rail's brand is the document's top-level heading. Losing it is how
    // a previous refactor left the page with no h1 at all.
    expect(
      await screen.findByRole("heading", { level: 1, name: /nativeforge/i }),
    ).toBeInTheDocument();
    expect(window.location.search).not.toContain("sign_in");

    // Identity is a session fact. Hardcoding it false on Workspace made a
    // signed-in customer look unverified on the one page that is supposed
    // to say what NativeForge already knows about them.
    const identity = await screen.findByText("Identity");
    expect(identity.closest(".nf-tier")).toHaveAttribute("data-state", "verified");
  });

  it("sends an unauthenticated visitor to sign in", async () => {
    mockApi({ authenticated: false });
    render(<App />);

    // The sign-in page's own h1. It greets rather than apologising, which is
    // the point of the rebuild: the front door should not open on the
    // product's configuration state.
    expect(
      await screen.findByRole("heading", { level: 1, name: /welcome to nativeforge/i }),
    ).toBeInTheDocument();

    // The URL follows, so a refresh does not bounce the visitor around.
    await waitFor(() => expect(window.location.search).toContain("view=sign_in"));
  });
});
