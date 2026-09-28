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
  });
});
