import { afterEach, describe, expect, it, vi } from "vitest";

import { getAuthSession } from "./authApiClient";

describe("getAuthSession", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads organization_id from the session envelope, not a nested verifier blob", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            status: "authenticated",
            authenticated: true,
            organization_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            roles: ["org_owner"],
          }),
          { status: 200 },
        ),
      ),
    );

    const session = await getAuthSession("");
    expect(session.authenticated).toBe(true);
    expect(session.organization_id).toBe("bbbbbbbb-cccc-dddd-eeee-ffffffffffff");
    expect(session.roles).toEqual(["org_owner"]);
    expect(session.display_name).toBeNull();
    expect(session.picture_url).toBeNull();
    expect(session.identity_provider).toBeNull();
  });

  it("reads display_name and picture_url from the session envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            status: "authenticated",
            authenticated: true,
            organization_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            roles: ["org_owner"],
            display_name: "Josef Gray",
            picture_url: "https://lh3.googleusercontent.com/a/photo",
            identity_provider: "google",
          }),
          { status: 200 },
        ),
      ),
    );

    const session = await getAuthSession("");
    expect(session.display_name).toBe("Josef Gray");
    expect(session.picture_url).toBe("https://lh3.googleusercontent.com/a/photo");
    expect(session.identity_provider).toBe("google");
  });
});
