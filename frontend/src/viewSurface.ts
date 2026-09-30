/**
 * Which page the application is showing, and how that survives a reload.
 *
 * The surface lives in `?view=`, so a customer can bookmark a page, send a
 * colleague a link to it, and get the same page back after a refresh. That
 * matters more than the URL being pretty: a workspace that always reopens on
 * its front page is a workspace people stop deep-linking into.
 *
 * `workspace` is the default and is written as an absent parameter rather
 * than `?view=workspace`, so the product's front door has a clean URL.
 */

export type AppSurface =
  // Customer destinations, one per primary navigation item.
  | "workspace"
  | "discover"
  | "opportunities"
  | "add_opportunity"
  | "pursuits"
  | "documents"
  | "organization"
  | "trust"
  | "settings"
  // Entry and setup.
  | "sign_in"
  | "demo_workspace"
  | "commercial_activation"
  | "onboarding"
  // Operator and demo surfaces. Not in primary navigation for customers.
  | "workbench"
  | "activation"
  | "nm_wa_operator_demo"
  | "sc_customer_demo"
  | "beta_onboarding_cockpit";

/**
 * Every surface that may appear in `?view=`.
 *
 * A set rather than a chain of comparisons: the chain had to be extended in
 * two places for each new page - here and in the writer - and the two drifted
 * the moment anyone added a page to only one of them.
 */
const SURFACES: ReadonlySet<string> = new Set<AppSurface>([
  "workspace",
  "discover",
  "opportunities",
  "add_opportunity",
  "pursuits",
  "documents",
  "organization",
  "trust",
  "settings",
  "sign_in",
  "demo_workspace",
  "commercial_activation",
  "onboarding",
  "workbench",
  "activation",
  "nm_wa_operator_demo",
  "sc_customer_demo",
  "beta_onboarding_cockpit",
]);

/** Whether a string names a surface this application can show. */
export function isSurface(value: string): value is AppSurface {
  return SURFACES.has(value);
}

export function readSurface(): AppSurface {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    if (q && SURFACES.has(q)) return q as AppSurface;
    return "workspace";
  } catch {
    return "workspace";
  }
}

/** Write a surface into the current URL without adding a history entry. */
export function writeSurface(surface: AppSurface): void {
  try {
    const url = new URL(window.location.href);
    if (surface === "workspace") {
      url.searchParams.delete("view");
    } else {
      url.searchParams.set("view", surface);
    }
    window.history.replaceState({}, "", url.toString());
  } catch {
    /* a URL that cannot be rewritten still leaves the app on the right page */
  }
}
