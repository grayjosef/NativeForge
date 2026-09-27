import { describe, expect, it } from "vitest";

import { humanDisqualification, humanEntity, joinList } from "./entityTypes";

describe("humanEntity", () => {
  it("names each classification the way a customer would", () => {
    expect(humanEntity("federally_recognized_tribe")).toBe("Federally recognized Tribe");
    expect(humanEntity("native_hawaiian_organization")).toBe("Native Hawaiian organization");
  });

  it("makes an unmapped value readable rather than hiding it", () => {
    // A new classification is information even before this table catches up.
    expect(humanEntity("some_new_type")).toBe("some new type");
  });

  it("is empty for empty input rather than the string 'undefined'", () => {
    expect(humanEntity("")).toBe("");
  });
});

describe("joinList", () => {
  it("writes an English list", () => {
    expect(joinList(["a"])).toBe("a");
    expect(joinList(["a", "b"])).toBe("a and b");
    expect(joinList(["a", "b", "c"])).toBe("a, b and c");
  });
});

describe("humanDisqualification", () => {
  const raw =
    "Entity type 'federally_recognized_tribe' is not in the extracted eligible types " +
    "['tribal_government', 'tribal_nonprofit'].";

  it("keeps the finding and drops the vocabulary", () => {
    const out = humanDisqualification(raw);
    expect(out).toBe(
      "This notice accepts Tribal government and Tribal nonprofit. " +
        "Your organization is registered as Federally recognized Tribe.",
    );
  });

  it("leaks no enum name, quote or list literal", () => {
    const out = humanDisqualification(raw);
    for (const leak of ["_", "'", "[", "]", "Entity type"]) {
      expect(out).not.toContain(leak);
    }
  });

  it("passes through a reason it has no translation for", () => {
    // Better a reason nobody rewrote than a generic refusal that tells the
    // customer nothing about what to do next.
    const other = "SAM registration expired on 2026-01-01.";
    expect(humanDisqualification(other)).toBe(other);
  });

  it("handles an empty eligible list without inventing one", () => {
    const empty = "Entity type 'tribal_college' is not in the extracted eligible types [].";
    expect(humanDisqualification(empty)).toBe(
      "This notice does not list Tribal college or university among the organization types it accepts.",
    );
  });

  it("is empty for empty input", () => {
    expect(humanDisqualification("")).toBe("");
  });
});
