import { describe, expect, it } from "vitest";

import { readWorkbenchFlag, setWorkbenchFlag } from "./workbenchFeatureFlag";

describe("workbenchFeatureFlag", () => {
  it("defaults false without query or storage", () => {
    expect(readWorkbenchFlag()).toBe(false);
  });

  it("setWorkbenchFlag persists", () => {
    setWorkbenchFlag(true);
    expect(readWorkbenchFlag()).toBe(true);
    setWorkbenchFlag(false);
    expect(readWorkbenchFlag()).toBe(false);
  });
});
