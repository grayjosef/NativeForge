import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  BrandLockup,
  MIN_TAGLINE_HEIGHT,
  MIN_WORDMARK_HEIGHT,
  resolveBrandMode,
} from "./BrandLockup";

describe("resolveBrandMode", () => {
  it("honours an explicit mode even below the wordmark floor", () => {
    expect(resolveBrandMode(12, "compact")).toBe("compact");
  });

  it("chooses emblem below the wordmark floor", () => {
    expect(resolveBrandMode(MIN_WORDMARK_HEIGHT - 1)).toBe("emblem");
  });

  it("chooses compact between the wordmark floor and the tagline floor", () => {
    expect(resolveBrandMode(MIN_WORDMARK_HEIGHT)).toBe("compact");
    expect(resolveBrandMode(MIN_TAGLINE_HEIGHT - 1)).toBe("compact");
  });

  it("chooses full at the tagline floor", () => {
    expect(resolveBrandMode(MIN_TAGLINE_HEIGHT)).toBe("full");
  });
});

describe("BrandLockup", () => {
  it("draws compact artwork for the expanded-rail size", () => {
    const { container } = render(<BrandLockup size={44} mode="compact" />);
    const lockup = container.querySelector("[data-brand-mode]");
    expect(lockup).toHaveAttribute("data-brand-mode", "compact");
    expect(lockup?.querySelector("img")?.getAttribute("src")).toBe(
      "/brand/nf-lockup-notag.png",
    );
  });

  it("draws the emblem when collapsed-rail size is requested", () => {
    const { container } = render(<BrandLockup size={34} mode="emblem" />);
    expect(container.querySelector("[data-brand-mode]")).toHaveAttribute(
      "data-brand-mode",
      "emblem",
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      "/brand/nf-emblem.png",
    );
  });

  it("draws the dark-field lockup when the tagline is included", () => {
    const { container } = render(<BrandLockup size={120} mode="full" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      "/brand/nf-lockup-dark.png",
    );
    expect(container.querySelector("img")?.getAttribute("width")).toBe("960");
    expect(container.querySelector("img")?.getAttribute("height")).toBe("287");
  });

  it("does not pin height when width is allowed to drive", () => {
    const { container } = render(
      <BrandLockup size={108} mode="compact" fit="width" />,
    );
    expect(container.querySelector("img")?.getAttribute("style")).toBeNull();
  });
});
