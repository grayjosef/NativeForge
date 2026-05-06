import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof Request
              ? input.url
              : String(input);
        if (url.includes("/health")) {
          return new Response(JSON.stringify({ ok: true }), { status: 200 });
        }
        if (url.includes("/trust/manifest")) {
          return new Response(JSON.stringify({ manifest_schema_version: "test" }), {
            status: 200,
          });
        }
        return new Response(JSON.stringify(null), { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders NativeForge workspace shell", async () => {
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: /nativeforge/i }),
    ).toBeInTheDocument();
  });
});
