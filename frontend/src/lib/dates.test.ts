import { describe, expect, it } from "vitest";

import { daysUntil, deadlineTone, formatDeadline } from "./dates";

const NOW = new Date("2026-09-27T12:00:00Z");

describe("daysUntil", () => {
  it("counts whole days forward", () => {
    expect(daysUntil("2026-09-28T12:00:00Z", NOW)).toBe(1);
    expect(daysUntil("2026-10-27T12:00:00Z", NOW)).toBe(30);
  });

  it("rounds up, so twenty hours away is tomorrow and not today", () => {
    expect(daysUntil("2026-09-28T08:00:00Z", NOW)).toBe(1);
  });

  it("goes negative for a closed deadline", () => {
    expect(daysUntil("2026-09-20T12:00:00Z", NOW)).toBeLessThan(0);
  });

  it("returns null for anything it cannot read", () => {
    // The point of the whole module. `new Date("soon")` is Invalid Date,
    // subtracting it yields NaN, and NaN fails every threshold comparison
    // silently - so an unreadable deadline would quietly become "not urgent".
    for (const bad of ["", "   ", "soon", "not a date", "TBD"]) {
      expect(daysUntil(bad, NOW)).toBeNull();
    }
  });
});

describe("formatDeadline", () => {
  it("speaks in days, not dates", () => {
    expect(formatDeadline(-1)).toBe("Closed");
    expect(formatDeadline(0)).toBe("Today");
    expect(formatDeadline(1)).toBe("Tomorrow");
    expect(formatDeadline(12)).toBe("In 12 days");
  });
});

describe("deadlineTone", () => {
  it("escalates as the deadline approaches and stands down once it passes", () => {
    expect(deadlineTone(-1)).toBe("muted");
    expect(deadlineTone(0)).toBe("bad");
    expect(deadlineTone(3)).toBe("bad");
    expect(deadlineTone(4)).toBe("warn");
    expect(deadlineTone(14)).toBe("warn");
    expect(deadlineTone(15)).toBe("neutral");
  });
});
