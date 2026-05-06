import { describe, expect, it } from "vitest";

import { readSurface } from "./viewSurface";

describe("readSurface", () => {
  it("reads workbench from query param", () => {
    const prev = window.location.href;
    window.history.replaceState({}, "", "/?view=workbench");
    expect(readSurface()).toBe("workbench");
    window.history.replaceState({}, "", prev);
  });
});
