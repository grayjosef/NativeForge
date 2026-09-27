import { useEffect, useState } from "react";

import { BrandLockup } from "../components/BrandLockup";
import { StateView } from "../components/StateView";
import { ProviderMark } from "../components/ProviderMark";
import { getAuthProviders, type AuthProvider } from "../authApiClient";
import { interpretError, type CustomerState } from "../customerState";

/**
 * Sign in.
 *
 * ## The buttons are drawn from what the server says it can do
 *
 * A hard-coded pair of provider buttons is a promise the deployment may not
 * be able to keep: pressing one when its credentials are absent sends the
 * customer to an error page at Google or Microsoft, which reads as
 * NativeForge being broken rather than as NativeForge not being finished.
 *
 * `/api/auth/providers` reports which are configured, in booleans. A provider
 * that is not configured still appears - hiding it would leave a customer
 * whose organization uses Microsoft wondering whether the product supports
 * them at all - but it is disabled and says why.
 *
 * ## Nothing on this page knows a secret
 *
 * No client id, no issuer, no authorization URL. Pressing a provider button
 * is a plain navigation to a route on this same origin, and the server builds
 * the provider URL with the state and PKCE challenge it just issued. A
 * sign-in page that constructs its own authorization URL is a sign-in page
 * that has the client id in the bundle.
 */

const AUTH_MESSAGES: Record<string, CustomerState> = {
  sign_in_incomplete: {
    tone: "blocked",
    title: "Sign-in did not complete",
    body: "Your identity provider did not return everything NativeForge needs to start a session. Signing in again usually resolves it.",
    actionLabel: "Try again",
  },
  signed_out: {
    tone: "success",
    title: "You are signed out",
    body: "Your session has ended on this device.",
  },
};

export interface SignInPageProps {
  /** A code from `?auth=`, set by the callback when it sends a browser back. */
  notice?: string | null;
  /** Lets a viewer reach the demo without credentials. */
  onContinueToDemo?: () => void;
}

export function SignInPage({ notice, onContinueToDemo }: SignInPageProps) {
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

  const configured = (providers ?? []).filter((p) => p.configured);
  const unconfigured = (providers ?? []).filter((p) => !p.configured);
  const noticeState = notice ? AUTH_MESSAGES[notice] : undefined;

  return (
    <div className="nf-signin">
      {/* The brand surface. Restrained: the lockup is the expressive thing on
          the page and it does not need help from a gradient. */}
      <aside className="nf-signin-brand" aria-hidden="true">
        <div className="nf-signin-brand-inner">
          <BrandLockup size={68} decorative />
          <p className="nf-signin-tagline">Find. Pursue. Govern.</p>
          <p className="nf-signin-claim">
            Grant intelligence, pursuit and award compliance, built for Tribal governments and
            Native-serving organizations.
          </p>
        </div>
      </aside>

      <main className="nf-signin-panel">
        <div className="nf-signin-card">
          <div className="nf-signin-mobile-brand">
            <BrandLockup size={40} />
          </div>

          {/* The document h1. The brand panel beside it is aria-hidden - it is
              decoration - so without this the sign-in page would have no
              top-level heading at all. */}
          <h1 className="nf-signin-title">Sign in to NativeForge</h1>
          <p className="nf-signin-lead">
            Use the account your organization already works from. NativeForge never asks for a
            separate password.
          </p>

          {noticeState ? <StateView state={noticeState} /> : null}
          {error ? <StateView state={error} /> : null}

          {providers === null ? (
            <p className="nf-signin-loading" role="status">
              Checking available sign-in methods…
            </p>
          ) : (
            <>
              <div className="nf-signin-providers">
                {configured.map((p) => (
                  // An anchor, not a button with a click handler. The server
                  // issues state and PKCE and then redirects, so this has to
                  // be a real navigation; an fetch would follow the redirect
                  // to the provider in the background and get nowhere.
                  <a key={p.key} className="nf-provider-btn" href={p.start_path}>
                    <ProviderMark provider={p.key} />
                    <span>Continue with {p.label}</span>
                  </a>
                ))}
                {unconfigured.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    className="nf-provider-btn"
                    disabled
                    title={`${p.label} sign-in is not yet configured for this workspace`}
                  >
                    <ProviderMark provider={p.key} />
                    <span>Continue with {p.label}</span>
                    <span className="nf-provider-note">Not yet available</span>
                  </button>
                ))}
              </div>

              {configured.length === 0 ? (
                <StateView
                  state={{
                    tone: "blocked",
                    title: "Sign-in is not available yet",
                    body: "This NativeForge workspace has not finished connecting to an identity provider. Your administrator can complete that setup.",
                  }}
                />
              ) : null}
            </>
          )}

          {onContinueToDemo ? (
            <p className="nf-signin-alt">
              <button type="button" className="nf-btn nf-btn-ghost" onClick={onContinueToDemo}>
                Continue to the demo workspace
              </button>
              <span className="nf-signin-alt-note">
                Demo data only. Nothing you do there touches a live organization.
              </span>
            </p>
          ) : null}

          <p className="nf-signin-legal">
            NativeForge does not submit to Grants.gov. Application packages are prepared for
            internal review.
          </p>
        </div>
      </main>
    </div>
  );
}
