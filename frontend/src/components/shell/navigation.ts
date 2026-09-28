import type { AppSurface } from "../../viewSurface";

/**
 * Primary navigation, and the line between a destination and a mode.
 *
 * The old header put Workspace, Workbench, Activation, two demos, Demo/Real
 * and Online/Trust in one strip of look-alike buttons. Three different things
 * wore the same clothes: places you go, an environment you are in, and a
 * status you are being told. Switching from real data to demo data looked
 * exactly like opening another page.
 *
 * So destinations live here, the environment lives in the top bar, and
 * status is reported where the thing it describes is shown.
 *
 * ## Grouped, because nine flat items is a list rather than a structure
 *
 * Finding money, pursuing it, and governing the organization that does both
 * are three different jobs, often done by three different people. The groups
 * are named after the jobs rather than after the data: a grants manager looks
 * for "Pursue", not for "Entities".
 */

export interface NavItem {
  id: string;
  label: string;
  /** Surface this routes to. Every item has one; none are decorative. */
  surface: AppSurface;
  /** Short description, used as the tooltip when the rail is collapsed. */
  hint: string;
  /** Section heading this item sits under when the rail is expanded. */
  group: string;
  /**
   * Retained for destinations that are still being built. Nothing sets it
   * false today; it stays because hiding an unbuilt page is worse than
   * labelling one, and the labelling has to be possible.
   */
  ready: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: "workspace",
    label: "Home",
    surface: "workspace",
    hint: "What needs your attention today",
    group: "Overview",
    ready: true,
  },
  {
    id: "discover",
    label: "Discovery",
    surface: "discover",
    hint: "Funding matched to your organization",
    group: "Find funding",
    ready: true,
  },
  {
    id: "opportunities",
    label: "Opportunities",
    surface: "opportunities",
    hint: "Opportunities you are tracking",
    group: "Find funding",
    ready: true,
  },
  {
    id: "pursuits",
    label: "My Pursuits",
    surface: "pursuits",
    hint: "Applications in progress",
    group: "Pursue",
    ready: true,
  },
  {
    id: "documents",
    label: "Documents",
    surface: "documents",
    hint: "Notices and amendments NativeForge has read",
    group: "Pursue",
    ready: true,
  },
  {
    id: "organization",
    label: "Organization",
    surface: "organization",
    hint: "Your profile, recognition and authority",
    group: "Govern",
    ready: true,
  },
  {
    id: "trust",
    label: "Trust",
    surface: "trust",
    hint: "Data ownership, review and provenance",
    group: "Govern",
    ready: true,
  },
  {
    id: "settings",
    label: "Settings",
    surface: "settings",
    hint: "Workspace preferences and operator tools",
    group: "Govern",
    ready: true,
  },
];

/** Navigation in the order it is drawn, with group headings resolved once. */
export function navGroups(): Array<{ group: string; items: NavItem[] }> {
  const out: Array<{ group: string; items: NavItem[] }> = [];
  for (const item of NAV_ITEMS) {
    const last = out[out.length - 1];
    if (last && last.group === item.group) {
      last.items.push(item);
    } else {
      out.push({ group: item.group, items: [item] });
    }
  }
  return out;
}

/**
 * Which nav item a surface belongs under.
 *
 * Operator and demo surfaces have no item of their own - they are reached
 * from Settings and from links - so they light Settings rather than leaving
 * the rail with nothing active, which reads as "you are nowhere".
 */
export function activeNavId(surface: AppSurface): string {
  const match = NAV_ITEMS.find((item) => item.surface === surface);
  if (match) return match.id;
  if (surface === "sign_in" || surface === "onboarding") return "";
  // Adding an opportunity belongs to Opportunities; the rail stays lit
  // there rather than losing its active state mid-task.
  if (surface === "add_opportunity") return "opportunities";
  return "settings";
}

/** The surface a nav id routes to, for callers that only know the id. */
export function surfaceForNav(navId: string): AppSurface | null {
  return NAV_ITEMS.find((item) => item.id === navId)?.surface ?? null;
}
