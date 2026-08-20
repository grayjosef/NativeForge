import { describe, expect, it } from "vitest";

import { readSurface } from "./viewSurface";

describe("readSurface sc_customer_demo", () => {
  it("reads sc_customer_demo from query param", () => {
    const prev = window.location.href;
    window.history.replaceState({}, "", "/?view=sc_customer_demo");
    expect(readSurface()).toBe("sc_customer_demo");
    window.history.replaceState({}, "", prev);
  });
});
