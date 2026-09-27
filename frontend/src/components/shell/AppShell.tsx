import { useCallback, useEffect, useState, type ReactNode } from "react";

import { BrandLockup } from "../BrandLockup";
import { NAV_ITEMS, activeNavId, type NavItem } from "./navigation";
import type { AppSurface } from "../../viewSurface";

/**
 * The application shell: a collapsible navigation rail, a context bar, and
 * the page.
 *
 * ## What this replaces
 *
 * A single header strip holding the product name, six look-alike buttons,
 * a Demo/Real pair, an Online chip, a Trust chip and a refresh control. It
 * mixed three unlike things - destinations, environment and status - into
 * one row, so changing from real data to demo data looked like navigating to
 * another page. Destinations now live in the rail, environment lives in the
 * bar, and status is reported beside whatever it describes.
 *
 * ## Collapsed is a real state, not a narrow one
 *
 * Collapsing keeps the emblem and the icons, drops the labels, and gives
 * every control its label back through `title` and `aria-label`, so the rail
 * stays usable by keyboard and by screen reader when it is 72px wide. The
 * choice persists, because a navigation that forgets how you left it is a
 * navigation you have to re-adjust on every visit.
 *
 * Below 1100px the rail collapses on its own and stops being resizable. That
 * is a layout constraint rather than a preference, so it does not overwrite
 * the stored choice: widen the window and the rail returns the way the user
 * left it.
 */

const STORAGE_KEY = "nf.shell.rail";
const AUTO_COLLAPSE_AT = 1100;

export interface AppShellProps {
  surface: AppSurface;
  onSurfaceChange?: (surface: AppSurface) => void;
  /** Organisation name, when one is known. */
  organization?: string | null;
  /** "Demo" or "Live". Environment, never a navigation item. */
  environment: "demo" | "live";
  onEnvironmentChange?: (environment: "demo" | "live") => void;
  /** Reachability of the workspace service. */
  online?: boolean;
  /** Why the workspace is unreachable, in customer terms. */
  offlineHint?: string;
  /**
   * Destinations that need attention. The Trust manifest failing to load is
   * a fact about Trust, so it is marked on Trust rather than announced in
   * the bar: status belongs beside the thing it describes.
   */
  attention?: Record<string, boolean>;
  topBarExtra?: ReactNode;
  children: ReactNode;
}

function readStoredRail(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function AppShell({
  surface,
  onSurfaceChange,
  organization,
  environment,
  onEnvironmentChange,
  online = true,
  offlineHint,
  attention = {},
  topBarExtra,
  children,
}: AppShellProps) {
  const [userCollapsed, setUserCollapsed] = useState(readStoredRail);
  const [forcedCollapsed, setForcedCollapsed] = useState(false);

  useEffect(() => {
    const check = () => setForcedCollapsed(window.innerWidth < AUTO_COLLAPSE_AT);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const collapsed = userCollapsed || forcedCollapsed;

  const toggle = useCallback(() => {
    setUserCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? "collapsed" : "expanded");
      } catch {
        /* a preference that cannot be stored is still a valid preference */
      }
      return next;
    });
  }, []);

  const active = activeNavId(surface);

  const go = (item: NavItem) => {
    if (!item.ready || !item.surface || !onSurfaceChange) return;
    onSurfaceChange(item.surface);
  };

  return (
    <div className="nf-shell" data-collapsed={collapsed}>
      <a className="nf-skip" href="#nf-main">
        Skip to content
      </a>

      <nav className="nf-rail" aria-label="Primary">
        {/* An h1, not a div. Removing the old header strip took the page's
            only top-level heading with it, which a test caught: the document
            had no h1 and no heading named NativeForge for a screen reader to
            land on. The emblem's visually hidden name carries it when the
            rail is collapsed and the wordmark is not drawn. */}
        <h1 className="nf-rail-brand">
          {/* Compact chrome gets the emblem. The full bevelled lockup turns
              to mush below about 48px, so it is kept for login and larger
              branded surfaces. */}
          <BrandLockup size={collapsed ? 30 : 34} markOnly decorative={!collapsed} />
          {collapsed ? null : <span className="nf-rail-wordmark">NativeForge</span>}
        </h1>

        <ul className="nf-rail-list">
          {NAV_ITEMS.map((item) => {
            const isActive = item.id === active;
            const needsAttention = Boolean(attention[item.id]);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className="nf-rail-item"
                  data-active={isActive}
                  disabled={!item.ready}
                  aria-current={isActive ? "page" : undefined}
                  // The label disappears when collapsed, so it has to survive
                  // somewhere the pointer and the screen reader can still find.
                  title={collapsed ? `${item.label}. ${item.hint}` : item.hint}
                  aria-label={
                    needsAttention
                      ? `${item.label}, needs attention`
                      : item.ready
                        ? item.label
                        : `${item.label} (coming soon)`
                  }
                  onClick={() => go(item)}
                >
                  <span className="nf-rail-glyph" aria-hidden="true">
                    {item.label.slice(0, 1)}
                    {needsAttention ? <i className="nf-rail-attention" /> : null}
                  </span>
                  {collapsed ? null : (
                    <span className="nf-rail-label">
                      {item.label}
                      {item.ready ? null : <span className="nf-rail-soon">Soon</span>}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        <button
          type="button"
          className="nf-rail-toggle"
          onClick={toggle}
          disabled={forcedCollapsed}
          aria-expanded={!collapsed}
          title={
            forcedCollapsed
              ? "The window is too narrow to expand navigation"
              : collapsed
                ? "Expand navigation"
                : "Collapse navigation"
          }
        >
          <span aria-hidden="true">{collapsed ? "»" : "«"}</span>
          {collapsed ? null : <span>Collapse</span>}
        </button>
      </nav>

      <div className="nf-shell-body">
        <header className="nf-topbar">
          <div className="nf-topbar-context">
            <span className="nf-topbar-org">{organization?.trim() || "No organization"}</span>
            {/* Environment is stated, not offered as a tab. Changing it is a
                deliberate act with a different affordance from navigating. */}
            <span className="nf-env" data-env={environment}>
              <span className="nf-env-dot" aria-hidden="true" />
              {environment === "demo" ? "Demo environment" : "Live organization"}
            </span>
            {onEnvironmentChange ? (
              <button
                type="button"
                className="nf-env-switch"
                onClick={() => onEnvironmentChange(environment === "demo" ? "live" : "demo")}
              >
                Switch to {environment === "demo" ? "live" : "demo"}
              </button>
            ) : null}
          </div>

          <div className="nf-topbar-actions">
            {online ? null : (
              <span className="nf-topbar-offline" role="status">
                {offlineHint?.trim() || "Workspace unreachable"}
              </span>
            )}
            {topBarExtra}
          </div>
        </header>

        <main id="nf-main" className="nf-main">
          {children}
        </main>
      </div>
    </div>
  );
}
