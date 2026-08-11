import { describe, expect, it } from "vitest";

import { readSurface } from "./viewSurface";

describe("readSurface nm_wa_operator_demo", () => {
  it("reads nm_wa_operator_demo from query param", () => {
    const prev = window.location.href;
    window.history.replaceState({}, "", "/?view=nm_wa_operator_demo");
    expect(readSurface()).toBe("nm_wa_operator_demo");
    window.history.replaceState({}, "", prev);
  });
});
