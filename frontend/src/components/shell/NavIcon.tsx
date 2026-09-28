/**
 * Navigation glyphs.
 *
 * ## Why these are drawn rather than lettered
 *
 * The collapsed rail used the first letter of each label. With the real
 * navigation in place that gives D for Discover and D for Documents, and O
 * for Opportunities and O for Organization - so the collapsed rail, which
 * exists precisely so people can navigate at a glance, offered two pairs of
 * identical targets. A letter is a label with the information removed.
 *
 * ## Why not an icon library
 *
 * Eight glyphs is not worth a dependency, a bundle and a licence review.
 * These are stroked paths on a 24-unit grid using `currentColor`, so they
 * inherit the rail's active and disabled states without a second set of
 * rules, and they stay sharp at the 20px the collapsed rail draws them at.
 *
 * Every icon is `aria-hidden`. The accessible name lives on the button, which
 * keeps it correct when the rail collapses and the visible label disappears.
 */

const PATHS: Record<string, string> = {
  // Overview: a simple dashboard division.
  workspace: "M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z",
  // Find funding: a magnifier.
  discover: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM16.5 16.5 21 21",
  // Tracked opportunities: a bookmarked list.
  opportunities: "M5 4h14v16l-7-4-7 4z",
  // Pursue: a flag on a staff.
  pursuits: "M6 21V4M6 4h11l-2.5 3.5L17 11H6",
  // Documents: a page with a folded corner.
  documents: "M6 3h7l5 5v13H6zM13 3v5h5M9 13h6M9 17h6",
  // Govern: a building with columns.
  organization: "M3 10 12 4l9 6M5 10v10M19 10v10M9 20v-6M15 20v-6M3 20h18",
  // Trust: a shield.
  trust: "M12 3l7 3v6c0 4.2-2.8 7.6-7 9-4.2-1.4-7-4.8-7-9V6z",
  // Settings: a slider bank. A cog at 20px turns to porridge.
  settings: "M4 7h10M18 7h2M4 17h4M12 17h8M16 4v6M8 14v6",
  // Sign-in trust items. Same stroke as the rail, not a second icon language.
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v10H6z",
  people: "M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4zM4 21v-1a5 5 0 0 1 5-5h6a5 5 0 0 1 5 5v1",
};

export function NavIcon({ id }: { id: string }) {
  const d = PATHS[id];
  if (!d) return null;
  return (
    <svg
      className="nf-nav-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={d} />
    </svg>
  );
}
