import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

function wideWindow() {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: 1400,
  });
}

describe("AppShell brand", () => {
  beforeEach(() => {
    window.localStorage.clear();
    wideWindow();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("uses compact kit artwork in the expanded rail, not live CSS text", async () => {
    render(
      <AppShell surface="workspace" environment="demo" account={{ name: "Ada" }}>
        page
      </AppShell>,
    );

    const heading = await screen.findByRole("heading", { level: 1, name: "NativeForge" });
    const lockup = heading.querySelector("[data-brand-mode]");
    expect(lockup).toHaveAttribute("data-brand-mode", "compact");
    expect(heading.querySelector("img")?.getAttribute("src")).toBe(
      "/brand/nf-lockup-notag.png",
    );
    expect(heading.querySelector(".nf-rail-wordmark")).toBeNull();
    expect(heading.querySelector(".nf-rail-tagline")?.textContent).toMatch(
      /find\. pursue\. govern\./i,
    );
  });

  it("drops to the emblem when the rail is collapsed", async () => {
    render(
      <AppShell surface="workspace" environment="demo" account={{ name: "Ada" }}>
        page
      </AppShell>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /collapse/i }));

    await waitFor(() => {
      const heading = screen.getByRole("heading", { level: 1, name: "NativeForge" });
      expect(heading.querySelector("[data-brand-mode]")).toHaveAttribute(
        "data-brand-mode",
        "emblem",
      );
      expect(heading.querySelector("img")?.getAttribute("src")).toBe(
        "/brand/nf-emblem.png",
      );
    });
  });
});
