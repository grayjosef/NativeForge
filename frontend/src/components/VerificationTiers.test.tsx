import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildTiers } from "./VerificationTiers";

describe("buildTiers", () => {
  it("treats a signed-in session as verified identity, not as a missing one", () => {
    const identity = buildTiers({ identityVerified: true, hasProfile: false }).find(
      (t) => t.id === "identity",
    );
    expect(identity?.state).toBe("verified");
  });

  it("never claims authority from a profile or a session", () => {
    const authority = buildTiers({ identityVerified: true, hasProfile: true }).find(
      (t) => t.id === "authority",
    );
    expect(authority?.state).toBe("unverified");
  });
});
