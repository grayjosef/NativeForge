import { useEffect, useState } from "react";

import { BrandLockup } from "../components/BrandLockup";
import { ProviderMark } from "../components/ProviderMark";
import { getAuthProviders, type AuthProvider } from "../authApiClient";
import { diagnosticsVisible, interpretError, type CustomerState } from "../customerState";

/**
 * The front door.
 *
 * ## What this replaced
 *
 * A 34px lockup floating in the middle of a half-screen void, a serif
 * headline borrowed from nothing else in the product, two provider buttons
 * each carrying the words "Not yet available", and an amber ACTION NEEDED
 * card announcing that sign-in did not work. The first screen a buyer sees
 * led with the product's own incompleteness, and the half of the page given
 * to the brand did the least work on it.
 *
 * ## The brand panel has a composition now
 *
 * The hero uses the FULL lockup, including the kit's navy FIND. PURSUE.
 * GOVERN. That colour is the one we keep. Black behind it is what made the
 * line disappear, so the panel is kit ivory — the ground the navy was
 * drawn for.
 *
 * ## Unconfigured is stated once, quietly
 *
 * A provider without credentials cannot sign anybody in, and dressing a dead
 * button as a live one would be a lie the customer discovers by clicking it.
 * So it is visibly inactive - but the reason is one muted line under the
 * group, not an operational error card in the hero. Provider configuration is
 * an administrator's problem, and the diagnostic detail appears only where
 * diagnostics belong.
 */

const TAGLINE = "Find. Pursue. Govern.";

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
      {/* ------------------------------------------------- brand panel */}
      <aside className="nf-login-brand">
        <div className="nf-login-brand-inner">
          {/* aria-hidden: the sign-in heading names the product, and a second
              accessible "NativeForge" here would make a screen reader read the
              name twice before reaching anything actionable. */}
          <BrandLockup
            className="nf-login-lockup"
            size={200}
            mode="full"
            fit="width"
            decorative
          />
          <p className="nf-visually-hidden">{TAGLINE}</p>
          <p className="nf-login-claim">
            Funding intelligence and pursuit operations for Tribal governments and
            Native-serving organizations.
          </p>
        </div>
      </aside>

      {/* -------------------------------------------------- auth panel */}
      <main className="nf-login-panel">
        <div className="nf-login-card">
          {/* Shown only where the brand panel is not: below the breakpoint it
              collapses away, and the page would otherwise open on a bare
              heading with no mark at all. */}
          <BrandLockup
            className="nf-login-compact-mark"
            size={56}
            mode="compact"
            fit="width"
            decorative
          />

          <h1 className="nf-login-title">Welcome to NativeForge</h1>
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
                  // An anchor, not a button: the server issues state and a
                  // PKCE challenge and then redirects, so this has to be a
                  // real navigation. A fetch would follow the redirect in the
                  // background and arrive nowhere.
                  <a key={p.key} className="nf-provider" href={p.start_path}>
                    <ProviderMark provider={p.key} />
                    <span>Continue with {p.label}</span>
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
                  </button>
                ),
              )
            )}
          </div>

          {/* One line, not a card. Whether an identity provider has been
              connected is an administrator's problem; it should not be the
              loudest thing on the first screen a customer ever sees. */}
          {ready && !anyConfigured ? (
            <p className="nf-login-status" id="nf-login-status">
              Sign-in is not yet connected for this workspace. Your administrator can
              complete the connection.
            </p>
          ) : null}

          {/* Development only. The reason a provider is unconfigured is a
              deployment fact, and it belongs where deployment facts belong. */}
          {error && diagnosticsVisible() ? (
            <details className="nf-login-diagnostic">
              <summary>Provider diagnostic (development only)</summary>
              <code>{error.technical ?? error.body}</code>
            </details>
          ) : null}
        </div>

        <footer className="nf-login-footer">
          NativeForge prepares application and pursuit materials for your review.
          Submission remains under your organization&rsquo;s control.
        </footer>
      </main>
    </div>
  );
}
