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
 */

export interface NavItem {
  id: string;
  label: string;
  /** Surface this routes to, when one exists today. */
  surface?: AppSurface;
  /** Short description, used as the tooltip when the rail is collapsed. */
  hint: string;
  /**
   * Destinations the product promises but has not built yet. They render
   * disabled and say so, rather than being hidden: a navigation that
   * silently omits half the product is harder to trust than one that admits
   * what is coming.
   */
  ready: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: "workspace",
    label: "Workspace",
    surface: "workspace",
    hint: "What needs your attention today",
    ready: true,
  },
  {
    id: "discover",
    label: "Discover",
    hint: "Funding opportunities matched to your organization",
    ready: false,
  },
  {
    id: "opportunities",
    label: "Opportunities",
    hint: "Opportunities you are tracking",
    ready: false,
  },
  {
    id: "pursuits",
    label: "Pursuits",
    hint: "Applications in progress",
    ready: false,
  },
  {
    id: "documents",
    label: "Documents",
    hint: "Notices, appendices and amendments NativeForge has read",
    ready: false,
  },
  {
    id: "organization",
    label: "Organization",
    hint: "Your profile, recognition and authority",
    ready: false,
  },
  {
    id: "trust",
    label: "Trust",
    hint: "Data ownership, review and provenance",
    ready: false,
  },
  {
    id: "workbench",
    label: "Workbench",
    surface: "workbench",
    hint: "Operator tools",
    ready: true,
  },
  {
    id: "settings",
    label: "Settings",
    hint: "Workspace preferences",
    ready: false,
  },
];

/** Which nav item a surface belongs under. */
export function activeNavId(surface: AppSurface): string {
  const match = NAV_ITEMS.find((item) => item.surface === surface);
  if (match) return match.id;
  // Demo surfaces are shown from the workspace, so the rail keeps workspace lit
  // rather than losing its active state entirely.
  return "workspace";
}
