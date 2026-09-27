import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { BrandLockup } from "../BrandLockup";
import { NavIcon } from "./NavIcon";
import { activeNavId, navGroups, type NavItem } from "./navigation";
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
 * stays usable by keyboard and by screen reader when it is 76px wide. The
 * choice persists, because a navigation that forgets how you left it is a
 * navigation you have to re-adjust on every visit.
 *
 * Below 1100px the rail collapses on its own and stops being resizable. That
 * is a layout constraint rather than a preference, so it does not overwrite
 * the stored choice: widen the window and the rail returns the way the user
 * left it.
 *
 * ## Below 900px it stops being a rail at all
 *
 * A 76px column against a 380px viewport is a fifth of the screen spent on
 * chrome. Under `DRAWER_AT` the rail leaves the layout and returns as an
 * overlay behind a menu button - focus-trapped, dismissed by Escape, by the
 * scrim, and by navigating, because a drawer that survives navigation covers
 * the page the customer just asked for.
 */

const STORAGE_KEY = "nf.shell.rail";
const AUTO_COLLAPSE_AT = 1100;
const DRAWER_AT = 900;

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
  /** Signed-in person, when there is one. */
  account?: { name: string; email?: string } | null;
  onSignIn?: () => void;
  onSignOut?: () => void;
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
  account = null,
  onSignIn,
  onSignOut,
  topBarExtra,
  children,
}: AppShellProps) {
  const [userCollapsed, setUserCollapsed] = useState(readStoredRail);
  const [forcedCollapsed, setForcedCollapsed] = useState(false);
  const [drawerMode, setDrawerMode] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const drawerRef = useRef<HTMLElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const check = () => {
      const w = window.innerWidth;
      setForcedCollapsed(w < AUTO_COLLAPSE_AT);
      setDrawerMode(w < DRAWER_AT);
      // Widening past the breakpoint leaves an overlay floating over a layout
      // that now has room for the rail.
      if (w >= DRAWER_AT) setDrawerOpen(false);
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Escape closes whichever transient surface is open, innermost first.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (menuOpen) setMenuOpen(false);
      else if (drawerOpen) setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen, drawerOpen]);

  // A click outside the account menu dismisses it. Pointerdown rather than
  // click, so the menu is gone before the thing underneath reacts.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    window.addEventListener("pointerdown", onDown);
    return () => window.removeEventListener("pointerdown", onDown);
  }, [menuOpen]);

  // Focus moves into the drawer when it opens; without this the next Tab goes
  // to whatever followed the menu button in the document, which is the page
  // the drawer is covering.
  useEffect(() => {
    if (!drawerOpen) return;
    const first = drawerRef.current?.querySelector<HTMLElement>("button, a[href]");
    first?.focus();
  }, [drawerOpen]);

  const trapTab = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !drawerRef.current) return;
    const focusable = Array.from(
      drawerRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href]"),
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  const collapsed = !drawerMode && (userCollapsed || forcedCollapsed);

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

  const go = useCallback(
    (item: NavItem) => {
      if (!item.ready || !onSurfaceChange) return;
      onSurfaceChange(item.surface);
      setDrawerOpen(false);
    },
    [onSurfaceChange],
  );

  const renderNav = (showLabels: boolean) => (
    <div className="nf-rail-nav">
      {navGroups().map(({ group, items }) => (
        <div key={group} className="nf-rail-group">
          {showLabels ? <p className="nf-rail-group-label">{group}</p> : null}
          <ul className="nf-rail-list">
            {items.map((item) => {
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
                    // The label disappears when collapsed, so it has to
                    // survive somewhere the pointer and the screen reader can
                    // still find.
                    title={showLabels ? item.hint : `${item.label}. ${item.hint}`}
                    aria-label={
                      needsAttention
                        ? `${item.label}, needs attention`
                        : item.ready
                          ? item.label
                          : `${item.label} (coming soon)`
                    }
                    onClick={() => go(item)}
                  >
                    <span className="nf-rail-glyph">
                      <NavIcon id={item.id} />
                      {needsAttention ? <i className="nf-rail-attention" /> : null}
                    </span>
                    {showLabels ? (
                      <span className="nf-rail-label">
                        {item.label}
                        {item.ready ? null : <span className="nf-rail-soon">Soon</span>}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );

  return (
    <div className="nf-shell" data-collapsed={collapsed} data-drawer={drawerMode}>
      <a className="nf-skip" href="#nf-main">
        Skip to content
      </a>

      {/* The rail in the layout. In drawer mode it is not rendered at all
          rather than hidden with CSS, so its controls are not reachable by
          keyboard from behind the page. */}
      {drawerMode ? null : (
        <nav className="nf-rail" aria-label="Primary">
          {/* An h1, not a div. Removing the old header strip took the page's
              only top-level heading with it, which a test caught: the document
              had no h1 and no heading named NativeForge for a screen reader to
              land on. The emblem's visually hidden name carries it when the
              rail is collapsed and the wordmark is not drawn. */}
          {/* A brand block, not a logo squeezed into a corner.
              The emblem sat at 34px beside the wordmark on one line. Its
              geometry was never distorted - the artwork's 1.169 ratio was
              preserved exactly - but an anvil, a woven pattern and bevelled
              edges rendered into 34 pixels of height read as mush, which is
              what "skewed" looked like on screen.
              It is given its own line and room to be legible, with the
              canonical tagline beneath the wordmark: restrained, letter-
              spaced, and clearly secondary to it. */}
          <h1 className="nf-rail-brand">
            <BrandLockup
              size={collapsed ? 34 : 44}
              mode="emblem"
              decorative={!collapsed}
            />
            {collapsed ? null : (
              <span className="nf-rail-brand-text">
                <span className="nf-rail-wordmark">NativeForge</span>
                {/* Not part of the accessible name: a screen reader
                    announcing "NativeForge Find. Pursue. Govern." every time
                    it lands on the page heading is a slogan read aloud, not a
                    heading. It stays visible and is hidden from the name. */}
                <span className="nf-rail-tagline" aria-hidden="true">
                  Find. Pursue. Govern.
                </span>
              </span>
            )}
          </h1>

          {renderNav(!collapsed)}

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
      )}

      {/* The same navigation as an overlay, for narrow viewports. */}
      {drawerMode && drawerOpen ? (
        <>
          <div
            className="nf-scrim"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <nav
            className="nf-rail nf-rail--drawer"
            aria-label="Primary"
            ref={drawerRef}
            onKeyDown={trapTab}
          >
            <div className="nf-drawer-head">
              <BrandLockup size={30} mode="emblem" />
              <button
                type="button"
                className="nf-btn nf-btn-ghost nf-btn-sm"
                onClick={() => setDrawerOpen(false)}
              >
                Close
              </button>
            </div>
            {renderNav(true)}
          </nav>
        </>
      ) : null}

      <div className="nf-shell-body">
        <header className="nf-topbar">
          <div className="nf-topbar-context">
            {drawerMode ? (
              <>
                <button
                  type="button"
                  className="nf-menu-btn"
                  onClick={() => setDrawerOpen(true)}
                  aria-expanded={drawerOpen}
                  aria-label="Open navigation"
                >
                  <span aria-hidden="true">☰</span>
                </button>
                {/* The h1 lives in the rail, which is not rendered here, so
                    the drawer layout would otherwise have no top-level
                    heading at all. */}
                <h1 className="nf-topbar-brand">
                  <BrandLockup size={26} mode="emblem" decorative />
                  <span className="nf-visually-hidden">NativeForge</span>
                </h1>
              </>
            ) : null}
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

            {account ? (
              <div className="nf-account" ref={menuRef}>
                <button
                  type="button"
                  className="nf-account-btn"
                  onClick={() => setMenuOpen((v) => !v)}
                  aria-expanded={menuOpen}
                  aria-haspopup="menu"
                >
                  <span className="nf-avatar" aria-hidden="true">
                    {account.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="nf-account-name">{account.name}</span>
                </button>
                {menuOpen ? (
                  <div className="nf-menu" role="menu">
                    <p className="nf-menu-head">
                      <span className="nf-menu-name">{account.name}</span>
                      {account.email ? (
                        <span className="nf-menu-email">{account.email}</span>
                      ) : null}
                    </p>
                    <button
                      type="button"
                      role="menuitem"
                      className="nf-menu-item"
                      onClick={() => {
                        setMenuOpen(false);
                        onSurfaceChange?.("settings");
                      }}
                    >
                      Settings
                    </button>
                    {onSignOut ? (
                      <button
                        type="button"
                        role="menuitem"
                        className="nf-menu-item"
                        onClick={() => {
                          setMenuOpen(false);
                          onSignOut();
                        }}
                      >
                        Sign out
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : onSignIn ? (
              <button type="button" className="nf-btn nf-btn-primary nf-btn-sm" onClick={onSignIn}>
                Sign in
              </button>
            ) : null}
          </div>
        </header>

        <main id="nf-main" className="nf-main">
          {children}
        </main>
      </div>
    </div>
  );
}
