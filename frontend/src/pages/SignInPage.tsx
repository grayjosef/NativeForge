import { useEffect, useState } from "react";

import { BrandLockup } from "../components/BrandLockup";
import { ProviderMark } from "../components/ProviderMark";
import { NavIcon } from "../components/shell/NavIcon";
import { getAuthProviders, type AuthProvider } from "../authApiClient";
import { diagnosticsVisible, interpretError, type CustomerState } from "../customerState";

/**
 * The front door.
 *
 * A dark two-zone composition. The brand zone carries the canonical lockup
 * and what the product does. The auth zone is a panel of the same surface
 * system, not a small card floating on an ivory field.
 */

const TAGLINE = "Find. Pursue. Govern.";

const PRINCIPLES = [
  {
    id: "discover",
    title: "Find",
    copy: "Discover and qualify the right opportunities.",
  },
  {
    id: "pursuits",
    title: "Pursue",
    copy: "Move every opportunity from decision to submission.",
  },
  {
    id: "trust",
    title: "Govern",
    copy: "Keep the work accountable, compliant, and under control.",
  },
] as const;

/** `?auth=` codes the callback leaves behind when it sends a browser back. */
const NOTICES: Record<string, { tone: "info" | "warn"; text: string }> = {
  sign_in_incomplete: {
    tone: "warn",
    text: "That sign-in did not finish. Trying again usually resolves it.",
  },
  signed_out: { tone: "info", text: "You are signed out on this device." },
};

export interface SignInPageProps {
  notice?: string | null;
}

export function SignInPage({ notice }: SignInPageProps) {
  const [providers, setProviders] = useState<AuthProvider[] | null>(null);
  const [error, setError] = useState<CustomerState | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await getAuthProviders();
        if (!cancelled) setProviders(res.providers);
      } catch (e) {
        if (!cancelled) {
          setProviders([]);
          setError(interpretError(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = providers !== null;
  const anyConfigured = (providers ?? []).some((p) => p.configured);
  const noticeState = notice ? NOTICES[notice] : undefined;

  return (
    <div className="nf-login">
      <div className="nf-login-frame">
      <aside className="nf-login-brand">
        {/* Sibling of the copy column so it centers on the brand zone, not the text. */}
        <BrandLockup
          className="nf-login-lockup"
          size={287}
          mode="full"
          fit="width"
          decorative
        />
        <div className="nf-login-brand-inner">
          <p className="nf-visually-hidden">{TAGLINE}</p>
          <h2 className="nf-login-headline">
            Funding intelligence.
            <span>Built for Native nations.</span>
          </h2>
          <p className="nf-login-claim">
            NativeForge helps Tribal governments and Native-serving organizations
            find, pursue, and govern funding opportunities with clarity, speed, and
            confidence.
          </p>
          <ul className="nf-login-principles">
            {PRINCIPLES.map((item) => (
              <li key={item.id} className="nf-login-principle">
                <span className="nf-login-principle-icon" aria-hidden="true">
                  <NavIcon id={item.id} />
                </span>
                <span className="nf-login-principle-copy">
                  <strong>{item.title}</strong>
                  <span>{item.copy}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="nf-login-panel">
        <div className="nf-login-card">
          <BrandLockup
            className="nf-login-compact-mark"
            size={56}
            mode="compact"
            fit="width"
            decorative
          />
          <p className="nf-login-tagline nf-login-tagline--on-card">{TAGLINE}</p>

          <h1 className="nf-login-title">
            <span className="nf-login-kicker">Welcome to</span>
            NativeForge
          </h1>
          <p className="nf-login-lead">
            Sign in with your organization account to continue.
          </p>

          {noticeState ? (
            <p className="nf-login-notice" data-tone={noticeState.tone} role="status">
              {noticeState.text}
            </p>
          ) : null}

          <div className="nf-login-providers">
            {!ready ? (
              <>
                <span className="nf-login-skeleton" aria-hidden="true" />
                <span className="nf-login-skeleton" aria-hidden="true" />
                <span className="nf-visually-hidden" role="status">
                  Checking available sign-in methods
                </span>
              </>
            ) : (
              (providers ?? []).map((p) =>
                p.configured ? (
                  <a key={p.key} className="nf-provider" href={p.start_path}>
                    <ProviderMark provider={p.key} />
                    <span>Continue with {p.label}</span>
                    <span className="nf-provider-arrow" aria-hidden="true">
                      →
                    </span>
                  </a>
                ) : (
                  <button
                    key={p.key}
                    type="button"
                    className="nf-provider"
                    disabled
                    aria-describedby="nf-login-status"
                  >
                    <ProviderMark provider={p.key} />
                    <span>Continue with {p.label}</span>
                    <span className="nf-provider-arrow" aria-hidden="true">
                      →
                    </span>
                  </button>
                ),
              )
            )}
          </div>

          {ready && !anyConfigured ? (
            <p className="nf-login-status" id="nf-login-status">
              Sign-in is not yet connected for this workspace. Your administrator can
              complete the connection.
            </p>
          ) : null}

          <ul className="nf-login-trust">
            <li>
              <span className="nf-login-trust-icon" aria-hidden="true">
                <NavIcon id="lock" />
              </span>
              <span>
                <strong>Use your existing organizational account</strong>
                NativeForge uses your organization&rsquo;s existing sign-in. You
                don&rsquo;t need a separate password.
              </span>
            </li>
            <li>
              <span className="nf-login-trust-icon" aria-hidden="true">
                <NavIcon id="people" />
              </span>
              <span>
                <strong>Review-first, always under your control</strong>
                NativeForge prepares application and pursuit materials for your
                review. Submission remains under your organization&rsquo;s control.
              </span>
            </li>
          </ul>

          {error && diagnosticsVisible() ? (
            <details className="nf-login-diagnostic">
              <summary>Provider diagnostic (development only)</summary>
              <code>{error.technical ?? error.body}</code>
            </details>
          ) : null}
        </div>
      </main>
      </div>
    </div>
  );
}
