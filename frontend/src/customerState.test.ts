import { describe, expect, it } from "vitest";

import { interpretError, friendlyError } from "./customerState";

/**
 * The rule these tests defend: nothing reaches a customer unless it was
 * written for them. The previous mapper echoed any unmatched message under
 * 180 characters, which is how a raw backend payload ended up in a red box
 * on the workspace.
 */
describe("interpretError", () => {
  it("never echoes a raw JSON payload", () => {
    const raw =
      '{"error":"no_verified_organization_context","blocked_reasons":["dev_header_consulted","no_session_cookie_was_sent"]}';
    const state = interpretError(new Error(raw));

    expect(state.title).toBe("Organization setup required");
    expect(state.body).not.toContain("{");
    expect(state.body).not.toContain("blocked_reasons");
    expect(state.body).not.toContain("no_verified_organization_context");
    // The original is preserved for diagnostics, just not for display.
    expect(state.technical).toBe(raw);
  });

  it("treats a tenant refusal as blocked, not as a fault", () => {
    const state = interpretError(new Error("no_verified_organization_context"));
    expect(state.tone).toBe("blocked");
    expect(state.actionLabel).toBe("Complete organization setup");
  });

  it("finds a known code inside blocked_reasons", () => {
    const state = interpretError(
      new Error('{"error":"unmapped_outer","blocked_reasons":["no_session_cookie_was_sent"]}'),
    );
    expect(state.title).toBe("Sign in to continue");
  });

  it("reports a server fault as a consequence, not a status code", () => {
    const state = interpretError(new Error("HTTP 500"));
    expect(state.tone).toBe("error");
    expect(state.body).not.toContain("500");
    expect(state.technical).toBe("HTTP 500");
  });

  it("does not leak an unrecognised short message", () => {
    const raw = "psycopg.errors.UndefinedColumn: column x does not exist";
    const state = interpretError(new Error(raw));
    expect(state.body).not.toContain("psycopg");
    expect(state.body).not.toContain("UndefinedColumn");
    expect(state.technical).toBe(raw);
  });

  it("keeps the domain knowledge the previous mapper had", () => {
    expect(interpretError(new Error("Grant spark not found")).tone).toBe("empty");
    expect(interpretError(new Error("Failed to fetch")).title).toBe("Can't reach NativeForge");
    expect(interpretError(new Error("form package already exists")).tone).toBe("success");
  });

  it("always offers a title and a body", () => {
    for (const input of ["", "   ", "???", null, undefined, 42]) {
      const state = interpretError(input);
      expect(state.title.length).toBeGreaterThan(0);
      expect(state.body.length).toBeGreaterThan(0);
    }
  });

  it("exposes no internal vocabulary in any mapped state", () => {
    const forbidden = [
      "dev_header",
      "blocked_reasons",
      "session_cookie",
      "traceback",
      "psycopg",
      "null",
      "undefined",
    ];
    const inputs = [
      '{"error":"no_verified_organization_context"}',
      "no_session_cookie_was_sent",
      "HTTP 500",
      "HTTP 401",
      "tribal profile required",
      "totally unknown failure",
    ];
    for (const input of inputs) {
      const state = interpretError(new Error(input));
      const shown = `${state.title} ${state.body} ${state.actionLabel ?? ""}`.toLowerCase();
      for (const word of forbidden) {
        expect(shown).not.toContain(word);
      }
    }
  });
});

describe("friendlyError compatibility shim", () => {
  it("returns designed copy, so an unconverted call site cannot leak", () => {
    const raw = '{"error":"no_verified_organization_context"}';
    expect(friendlyError(new Error(raw))).not.toContain("{");
    expect(friendlyError(new Error(raw))).toBe(
      "NativeForge needs a verified organization profile before it can evaluate funding opportunities for you.",
    );
  });
});
