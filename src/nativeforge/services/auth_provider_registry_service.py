"""Which identity providers this deployment can actually sign a customer in with.

NativeForge's auth stack was built for exactly one provider: seven ``OIDC_*``
environment variables, one issuer, one client. That is enough to authenticate
somebody, and it is not enough for the product being sold - a Tribal
government on Microsoft 365 and a Native nonprofit on Google Workspace are
both customers, and telling one of them to create a second account somewhere
else is telling them no.

This module adds the provider dimension **without** touching the flow. Each
provider gets its own copy of the same seven keys under a prefix, the base
keys stay as the default, and everything downstream - state, PKCE, exchange,
verification, session minting - is the code that already exists.

## The provider is the callback path, not a stored column

The callback has to know which provider's client secret to present at the
token endpoint, and it learns that before it has verified anything, so it
cannot read it out of an ID token. The two usual answers are a column on the
redirect-state row or the provider encoded in ``state``; both put a value the
callback trusts into storage the callback then has to defend.

The path is simpler and is already authenticated by the provider itself:
``/api/auth/callback/google`` is reachable only because *Google* was told to
redirect there. Providers require an exact redirect URI, so a per-provider
path is a registration each provider independently confirms, and no migration
is needed to carry it.

## Availability is measured, never assumed

:func:`available_providers` reports what is configured, as booleans. It never
returns a client id, a secret, an issuer or a URL: a login page needs to know
which buttons to draw, and nothing about a provider's configuration is a
login page's business.

A provider with an issuer but no secret is **not** available. Half a
configuration produces a redirect to a provider that refuses on arrival,
which a customer reads as NativeForge being broken.
"""

from __future__ import annotations

from typing import Any

from nativeforge.lib.settings import AUTH_ENV_KEYS, auth_environment_overlay

#: Prefix for a provider's own copy of the seven auth keys, e.g.
#: ``NF_OIDC_MICROSOFT_CLIENT_ID``. The base ``OIDC_*`` keys remain the
#: default provider's configuration, so a single-provider deployment that
#: predates this module keeps working with no change.
ENV_PREFIX = "NF_OIDC_"

#: The keys a provider may override. ``NF_PUBLIC_ORIGIN`` is deliberately
#: absent: the public origin is a property of the deployment, not of an
#: identity provider, and letting a provider override it would let a
#: misconfigured provider entry redirect a customer to another host.
#:
#: `NF_SESSION_SIGNING_KEY` is excluded for a stronger reason than tidiness.
#: It signs NativeForge's own session cookie, which has nothing to do with
#: which provider proved the identity. A per-provider signing key would mean
#: sessions minted through Google could not be verified against sessions
#: minted through Microsoft, so a customer would be signed out by choosing a
#: different button - and rotating one provider's key would silently
#: invalidate only half the sessions.
PROVIDER_KEYS: tuple[str, ...] = tuple(
    k for k in AUTH_ENV_KEYS if k.startswith("OIDC_")
)


class Provider:
    """One identity provider, as the login page needs to talk about it."""

    __slots__ = ("key", "label", "issuer_hint", "scopes")

    def __init__(self, key: str, label: str, issuer_hint: str, scopes: str) -> None:
        self.key = key
        self.label = label
        self.issuer_hint = issuer_hint
        self.scopes = scopes


#: The providers NativeForge knows how to talk to.
#:
#: ``issuer_hint`` is used only to recognise a base ``OIDC_ISSUER`` that
#: already points at one of them, so a deployment configured before this
#: module lights the right button instead of an anonymous one. It is never
#: used to *construct* an issuer: guessing an issuer is how a login flow ends
#: up at a URL nobody registered.
PROVIDERS: tuple[Provider, ...] = (
    Provider(
        key="microsoft",
        label="Microsoft",
        issuer_hint="login.microsoftonline.com",
        scopes="openid profile email",
    ),
    Provider(
        key="google",
        label="Google",
        issuer_hint="accounts.google.com",
        scopes="openid profile email",
    ),
)

PROVIDER_KEYS_KNOWN: frozenset[str] = frozenset(p.key for p in PROVIDERS)


def _env_name(provider_key: str, key: str) -> str:
    """``google`` + ``OIDC_CLIENT_ID`` -> ``NF_OIDC_GOOGLE_CLIENT_ID``."""
    stem = key[5:] if key.startswith("OIDC_") else key
    return f"{ENV_PREFIX}{provider_key.upper()}_{stem}"


def provider_env(
    provider_key: str | None,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """The effective auth environment for one provider.

    The provider's own keys win; anything it does not set falls through to the
    base ``OIDC_*`` configuration. So a deployment with one provider needs no
    prefixed variables at all, and a deployment adding a second sets only what
    differs.

    ``environ`` is passed through to :func:`auth_environment_overlay`, which
    refuses to read the ambient machine during canonical artifact generation.
    Passing a mapping in is supplying an input rather than reading a laptop.
    """
    base = auth_environment_overlay(environ)
    key = (provider_key or "").strip().lower()
    if key not in PROVIDER_KEYS_KNOWN:
        return base

    resolved = dict(base)
    for auth_key in PROVIDER_KEYS:
        value = str(base.get(_env_name(key, auth_key)) or "").strip()
        if value:
            resolved[auth_key] = value
    return resolved


#: Token verification refuses an empty audience. A Microsoft start that
#: borrowed Google's audience would 302, then fail at the callback.
_CONFIG_KEYS: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
)


def provider_missing_env(
    provider_key: str,
    environ: dict[str, str] | None = None,
) -> list[str]:
    """Prefixed variable names this provider still needs. Names only."""
    base = auth_environment_overlay(environ)
    missing: list[str] = []
    for auth_key in _CONFIG_KEYS:
        name = _env_name(provider_key, auth_key)
        if not str(base.get(name) or "").strip():
            missing.append(name)
    return missing


def _prefix_started(provider_key: str, environ: dict[str, str] | None) -> bool:
    base = auth_environment_overlay(environ)
    return any(
        str(base.get(_env_name(provider_key, auth_key)) or "").strip()
        for auth_key in _CONFIG_KEYS
    )


def provider_configured(
    provider_key: str,
    environ: dict[str, str] | None = None,
) -> bool:
    """Whether this provider could complete a sign-in today.

    Issuer, client id, secret, audience and callback: a flow missing any one
    of them fails at a different stage and every one of those stages looks,
    to a customer, like the product not working.

    Microsoft that has started ``NF_OIDC_MICROSOFT_*`` must finish all five
    keys. Borrowing Google's audience is how a Microsoft callback verifies a
    Google client id.

    Google may keep using the unprefixed ``OIDC_*`` stack even if a Google
    prefix is incomplete: that prefix overlay is how a single-provider
    deployment was configured, and refusing it signs every customer out.
    """
    hint = next((p.issuer_hint for p in PROVIDERS if p.key == provider_key), "")
    if not hint:
        return False

    if provider_key != "google" and _prefix_started(provider_key, environ):
        missing = provider_missing_env(provider_key, environ)
        if missing:
            return False
        base = auth_environment_overlay(environ)
        issuer = str(base.get(_env_name(provider_key, "OIDC_ISSUER")) or "").strip()
        return hint in issuer.lower()

    env = provider_env(provider_key, environ)
    if not all(str(env.get(k) or "").strip() for k in _CONFIG_KEYS):
        return False
    issuer = str(env.get("OIDC_ISSUER") or "").strip().lower()
    return hint in issuer


def callback_path(provider_key: str) -> str:
    """Where this provider must be told to redirect back to."""
    return f"/api/auth/callback/{provider_key}"


def available_providers(
    environ: dict[str, str] | None = None,
    *,
    public_origin: str = "",
) -> dict[str, Any]:
    """What the login page needs, and nothing more.

    Booleans and labels. No client id, no issuer, no secret, no authorization
    URL: the page draws buttons, and a page that knows the configuration is a
    page that leaks it to anyone who opens the network tab.
    """
    origin = (public_origin or "").rstrip("/")
    entries = []
    for provider in PROVIDERS:
        configured = provider_configured(provider.key, environ)
        missing = [] if configured else provider_missing_env(provider.key, environ)
        entries.append(
            {
                "key": provider.key,
                "label": provider.label,
                "configured": configured,
                "missing_env": missing,
                # A relative path. The browser resolves it against the origin
                # it is already on, so a stale absolute URL cannot send a
                # customer's authorization code to a host this deployment no
                # longer owns.
                "start_path": f"/api/auth/login?provider={provider.key}",
                # Stated so an operator setting the provider up can copy it
                # exactly rather than guessing. It discloses the deployment's
                # own public address, which the caller already knows.
                "redirect_uri": f"{origin}{callback_path(provider.key)}"
                if origin
                else "",
                "scopes": provider.scopes,
            }
        )
    return {
        "providers": entries,
        "any_configured": any(e["configured"] for e in entries),
    }
