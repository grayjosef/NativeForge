import { describe, expect, it, vi } from "vitest";

import { readStage12DemoFlag } from "./stage12DemoFeatureFlag";

describe("readStage12DemoFlag", () => {
  it("reads query param nf_stage12_demo=1", () => {
    vi.stubGlobal("location", { search: "?nf_stage12_demo=1" });
    expect(readStage12DemoFlag()).toBe(true);
    vi.unstubAllGlobals();
  });
});
