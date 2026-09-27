/**
 * Turn whatever the API failed with into something a customer can act on.
 *
 * ## The hole this closes
 *
 * `friendlyError` mapped a list of known phrases and then ended with
 * `return t || GENERIC_SHORT` - it echoed the raw message whenever nothing
 * matched and it was under 180 characters. Most backend failures are exactly
 * that: short. So a customer evaluating a $34,999 platform was shown
 *
 *     {"error":"no_verified_organization_context","blocked_reasons":[...]}
 *
 * in a red box on the workspace, because `readHttpError` JSON-stringifies an
 * object `detail` and that string became the Error message.
 *
 * The rule here is inverted. Nothing reaches the customer unless it was
 * deliberately written for them. Unrecognised text is never echoed; it is
 * carried in `technical`, which only renders where diagnostics are
 * appropriate, and the customer sees designed copy instead.
 *
 * ## Why a state rather than a string
 *
 * A message alone cannot say what to do next, and "Organization setup
 * required" with no button is the same dead end as the JSON was. Every state
 * carries a tone, a title, a short explanation and, where one genuinely
 * exists, the single next action.
 *
 * ## Blocked is not an error
 *
 * A tenant boundary refusing an unverified organization is the product
 * working. Presenting it in red alongside genuine faults teaches customers
 * that NativeForge is broken when it is being careful, so refusals carry the
 * `blocked` tone and explain the requirement.
 */

export type StateTone =
  | "loading"
  | "empty"
  | "blocked"
  | "partial"
  | "error"
  | "success";

export interface CustomerState {
  tone: StateTone;
  title: string;
  /** One or two plain sentences. Never a payload, never an enum. */
  body: string;
  /** The single next action, when one genuinely exists. */
  actionLabel?: string;
  /**
   * The original text, for diagnostics surfaces only. Never rendered in
   * ordinary customer UI.
   */
  technical?: string;
}

/** Stable backend codes we have written customer copy for. */
const CODE_STATES: Record<string, Omit<CustomerState, "technical">> = {
  no_verified_organization_context: {
    tone: "blocked",
    title: "Organization setup required",
    body: "NativeForge needs a verified organization profile before it can evaluate funding opportunities for you.",
    actionLabel: "Complete organization setup",
  },
  no_session_cookie_was_sent: {
    tone: "blocked",
    title: "Sign in to continue",
    body: "Your session has ended. Sign in again to return to your workspace.",
    actionLabel: "Sign in",
  },
  organization_not_found: {
    tone: "blocked",
    title: "Organization not found",
    body: "We could not find that organization. Check you are in the right workspace.",
  },
  tribal_profile_required: {
    tone: "blocked",
    title: "Organization profile required",
    body: "Scoring and application previews need your organization profile on file first.",
    actionLabel: "Complete organization profile",
  },
};

/** Phrase rules, kept from the previous mapper because the domain knowledge
 *  in them was correct. Order matters: the first match wins. */
const PHRASE_RULES: Array<{
  test: (lower: string) => boolean;
  state: Omit<CustomerState, "technical">;
}> = [
  {
    test: (l) => l.includes("failed to fetch") || l.includes("networkerror"),
    state: {
      tone: "error",
      title: "Can't reach NativeForge",
      body: "The workspace service did not respond. Check your connection and try again.",
      actionLabel: "Try again",
    },
  },
  {
    test: (l) => l.includes("spark") && l.includes("not found"),
    state: {
      tone: "empty",
      title: "Opportunity unavailable",
      body: "This opportunity is no longer available. Choose another from your list.",
    },
  },
  {
    test: (l) => l.includes("pursuit") && l.includes("not found"),
    state: {
      tone: "empty",
      title: "Pursuit unavailable",
      body: "We could not open this pursuit. Return to the opportunity and open it again.",
    },
  },
  {
    test: (l) => l.includes("no score") || (l.includes("score") && l.includes("404")),
    state: {
      tone: "empty",
      title: "Not scored yet",
      body: "Readiness scoring runs once requirements have been extracted from the notice.",
    },
  },
  {
    test: (l) =>
      l.includes("form package") && (l.includes("already exists") || l.includes("409")),
    state: {
      tone: "success",
      title: "Preview already prepared",
      body: "An application preview already exists for this pursuit.",
      actionLabel: "Refresh",
    },
  },
  {
    test: (l) =>
      (l.includes("nofo") || l.includes("extraction") || l.includes("requirements")) &&
      (l.includes("not found") || l.includes("no extraction")),
    state: {
      tone: "empty",
      title: "Requirements not extracted yet",
      body: "Extract the notice requirements to build the checklist for this opportunity.",
      actionLabel: "Extract requirements",
    },
  },
  {
    test: (l) => l.includes("tribal profile") || l.includes("organization profile"),
    state: {
      tone: "blocked",
      title: "Organization profile required",
      body: "Scoring and application previews need your organization profile on file first.",
      actionLabel: "Complete organization profile",
    },
  },
];

const SERVER_FAULT: Omit<CustomerState, "technical"> = {
  tone: "error",
  title: "NativeForge is having trouble",
  body: "The workspace service could not complete that request. Try again in a moment.",
  actionLabel: "Try again",
};

const UNAVAILABLE: Omit<CustomerState, "technical"> = {
  tone: "error",
  title: "Something went wrong",
  body: "We could not complete that request. Try again, or refresh the page.",
  actionLabel: "Try again",
};

/** Pull a stable code out of a JSON body or a bare string. */
function extractCode(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed) as Record<string, unknown>;
      for (const key of ["error", "code", "reason", "detail"]) {
        const value = parsed[key];
        if (typeof value === "string" && value in CODE_STATES) return value;
      }
      const reasons = parsed["blocked_reasons"];
      if (Array.isArray(reasons)) {
        const hit = reasons.find((r) => typeof r === "string" && r in CODE_STATES);
        if (typeof hit === "string") return hit;
      }
    } catch {
      /* not JSON after all */
    }
    return null;
  }
  return trimmed in CODE_STATES ? trimmed : null;
}

/**
 * Interpret any thrown value as a customer-facing state.
 *
 * Unrecognised input never reaches `title` or `body`. That is the whole
 * point: an escape hatch that echoes the raw text is how the JSON reached
 * the screen last time.
 */
export function interpretError(err: unknown): CustomerState {
  const raw = err instanceof Error ? err.message : String(err ?? "");
  const trimmed = raw.trim();
  const lower = trimmed.toLowerCase();

  const code = extractCode(trimmed);
  if (code) return { ...CODE_STATES[code], technical: trimmed };

  for (const rule of PHRASE_RULES) {
    if (rule.test(lower)) return { ...rule.state, technical: trimmed };
  }

  // A bare status line, e.g. "HTTP 500". Customers get the consequence, not
  // the number.
  const status = /\b(5\d{2})\b/.exec(trimmed);
  if (status || lower.startsWith("http 5")) {
    return { ...SERVER_FAULT, technical: trimmed };
  }
  if (/\b(401|403)\b/.test(trimmed)) {
    return { ...CODE_STATES.no_session_cookie_was_sent, technical: trimmed };
  }

  return { ...UNAVAILABLE, technical: trimmed };
}

/**
 * Compatibility shim for call sites that still want a single string.
 *
 * It returns the designed body, never the raw message, so an unconverted
 * call site cannot reintroduce the leak while the migration finishes.
 */
export function friendlyError(err: unknown): string {
  return interpretError(err).body;
}

/** Whether technical detail may be shown. Diagnostics are a development and
 *  operator concern; customers get the designed state. */
export function diagnosticsVisible(): boolean {
  try {
    return Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV);
  } catch {
    return false;
  }
}
