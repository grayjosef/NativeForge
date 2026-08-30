"""Authorization URL construction (Gate 119D).

The first code in NativeForge that can build an OIDC authorization URL. Gate
119A searched for it and found nothing: zero hits on `authorization_endpoint`,
`response_type`, `urlencode`, `quote_plus` and `/authorize` across every
service. The `urlparse` and `urljoin` hits were all HTML listing adapters
resolving relative hrefs on grant pages.

## Building a URL is not visiting one

This module performs string construction and nothing else. There is no HTTP
client here, no import that could make a request, and no code path that resolves
a hostname. `provider_called` is a constant `False` and an invariant refuses any
result claiming otherwise.

That distinction is the reason an authorization URL can exist while
`network_call_allowed` stays false: the browser is what visits the URL, and no
browser is involved in a test.

## The client secret is never in the URL

An authorization request carries the client *id*, which is public by design —
it appears in every redirect a user's browser makes. It never carries the client
*secret*, which is presented once at token exchange over a back channel.

A secret in a query string is a secret in browser history, in the provider's
access logs, in any proxy between them, and in the `Referer` header of whatever
the callback page loads next. `secret_exposed` is derived by scanning the
constructed URL for the configured secret value, and an invariant fails if it is
ever true.

## Why state and PKCE are required rather than optional

```text
no state    the callback cannot tell a genuine return from a forged one
no PKCE     an intercepted authorization code can be exchanged by whoever
            intercepted it
```

Both are omissible in the OAuth specification and neither is omissible here. A
URL missing either is not built, and the reason is named.

## Provider config blocks the URL; it does not block the state

`/login` can generate a state and a PKCE pair with no provider configured at all
— the generator is local (Gate 117D) and depends on nothing. What provider
config gates is whether those values can be *placed in a URL*.

Keeping those two facts separate is what lets `/login` report
`state_issued: True` and `authorization_url_available: False` in the same
response, which is exactly the state NativeForge is in.

## Nothing here returns a URL containing a real state

`authorization_url` is returned only when every input is present. Artifacts
publish `authorization_url_redacted`, in which the state and challenge are
replaced by placeholders — a real state in a committed file is a state somebody
can present at a callback.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

from nativeforge.services.customer_auth_state_pkce_service import (
    CODE_CHALLENGE_METHOD,
)

SCHEMA_VERSION = "nf_customer_auth_authorization_url_v1"

# OIDC's authorization code flow. `token` and `id_token` response types are the
# implicit flow, which hands credentials to the browser in a URL fragment.
RESPONSE_TYPE = "code"

# Bridged from Gate 60's config schema rather than restated.
DEFAULT_SCOPES: tuple[str, ...] = ("openid", "profile", "email")

# Where provider configuration is read from. Presence only; no value from any of
# these reaches a result, and the secret is never read into the URL at all.
ISSUER_ENV = "OIDC_ISSUER"
CLIENT_ID_ENV = "OIDC_CLIENT_ID"
CLIENT_SECRET_ENV = "OIDC_CLIENT_SECRET"
AUDIENCE_ENV = "OIDC_AUDIENCE"

# The conventional OIDC path. Discovery would fetch this from the issuer's
# well-known document, which is a network call this gate does not make.
AUTHORIZE_PATH = "/authorize"

# What a published artifact may carry in place of the real values.
REDACTED_STATE = "REDACTED_STATE"
REDACTED_CHALLENGE = "REDACTED_CODE_CHALLENGE"

FORBIDDEN_VALUE_FIELDS = frozenset(
    {
        "client_secret",
        "secret",
        "code_verifier",
        "pkce_verifier",
        "verifier",
        "signing_key",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "provider_configured",
    "issuer",
    "authorization_endpoint_configured",
    "client_id_configured",
    "redirect_uri_configured",
    "scope",
    "state_bound",
    "pkce_bound",
    "authorization_url_available",
    "authorization_url_returned",
    "authorization_url",
    "authorization_url_redacted",
    "provider_called",
    "secret_exposed",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _authorization_endpoint(issuer: str) -> str:
    """The conventional path under the issuer. No discovery document is fetched."""
    return f"{issuer.rstrip('/')}{AUTHORIZE_PATH}"


def build_authorization_url(
    *,
    issuer: str | None = None,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    audience: str | None = None,
    scopes: tuple[str, ...] | list[str] | None = None,
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str = CODE_CHALLENGE_METHOD,
) -> dict[str, Any]:
    """Construct an authorization URL, or name why one cannot be constructed.

    Every provider input is a parameter with an environment fallback, so a test
    can reach the permitted branch without configuring a process-wide provider.
    Gates 117 and 118 each shipped a conjunct whose permitted branch was
    unreachable; every conjunct here is both derived and injectable.

    No parameter accepts a client secret, because no part of an authorization
    URL takes one.
    """
    resolved_issuer = str(issuer if issuer is not None else _env(ISSUER_ENV)).strip()
    resolved_client_id = str(
        client_id if client_id is not None else _env(CLIENT_ID_ENV)
    ).strip()
    resolved_redirect = str(redirect_uri or "").strip()
    resolved_audience = str(
        audience if audience is not None else _env(AUDIENCE_ENV)
    ).strip()

    scope_list = list(scopes) if scopes else list(DEFAULT_SCOPES)
    scope = " ".join(s for s in (str(x).strip() for x in scope_list) if s)

    blocked_reasons: list[str] = []

    issuer_configured = bool(resolved_issuer)
    client_id_configured = bool(resolved_client_id)
    redirect_uri_configured = bool(resolved_redirect)

    if not issuer_configured:
        blocked_reasons.append(f"no_issuer_configured_set_{ISSUER_ENV}")
    if not client_id_configured:
        blocked_reasons.append(f"no_client_id_configured_set_{CLIENT_ID_ENV}")
    if not redirect_uri_configured:
        blocked_reasons.append("no_redirect_uri_supplied")
    if not scope:
        blocked_reasons.append("no_scope_requested")

    state_bound = bool(str(state or "").strip())
    pkce_bound = bool(str(code_challenge or "").strip())
    method = str(code_challenge_method or "").strip()

    if not state_bound:
        blocked_reasons.append("no_state_bound_to_the_authorization_request")
    if not pkce_bound:
        blocked_reasons.append("no_pkce_challenge_bound_to_the_authorization_request")
    if method != CODE_CHALLENGE_METHOD:
        blocked_reasons.append("code_challenge_method_must_be_s256")

    # Provider config alone. Deliberately separate from state and PKCE: /login
    # issues those with no provider configured, and conflating the two would
    # make an unconfigured provider look like a generator failure.
    provider_configured = bool(
        issuer_configured and client_id_configured and redirect_uri_configured
    )

    endpoint_configured = issuer_configured
    endpoint = _authorization_endpoint(resolved_issuer) if issuer_configured else ""

    available = bool(provider_configured and state_bound and pkce_bound)
    url = ""
    redacted = ""

    if available and not blocked_reasons:
        params = {
            "response_type": RESPONSE_TYPE,
            "client_id": resolved_client_id,
            "redirect_uri": resolved_redirect,
            "scope": scope,
            "state": str(state),
            "code_challenge": str(code_challenge),
            "code_challenge_method": method,
        }
        if resolved_audience:
            params["audience"] = resolved_audience
        url = f"{endpoint}?{urlencode(params)}"

        redacted_params = dict(params)
        redacted_params["state"] = REDACTED_STATE
        redacted_params["code_challenge"] = REDACTED_CHALLENGE
        redacted = f"{endpoint}?{urlencode(redacted_params)}"

    result = {
        "schema_version": SCHEMA_VERSION,
        "provider_configured": provider_configured,
        # The issuer is configuration, not a credential: it is the public
        # hostname every user's browser is sent to.
        "issuer": resolved_issuer,
        "authorization_endpoint_configured": endpoint_configured,
        "client_id_configured": client_id_configured,
        "redirect_uri_configured": redirect_uri_configured,
        "scope": scope,
        "state_bound": state_bound,
        "pkce_bound": pkce_bound,
        "authorization_url_available": available,
        "authorization_url_returned": bool(url),
        "authorization_url": url,
        "authorization_url_redacted": redacted,
        # Constant. This module constructs a string; it has no client to call
        # with and no import that could acquire one.
        "provider_called": False,
        "secret_exposed": False,
        "blocked_reasons": sorted(set(blocked_reasons)),
    }
    result["secret_exposed"] = _secret_in_url(url)
    return _json_safe(result)


def _secret_in_url(url: str) -> bool:
    """Did the configured client secret reach the constructed URL?

    A self-check rather than a guard: no code path here reads the secret, so
    this should be unfalsifiable. It is checked anyway, because "should be" is
    what an invariant exists to stop being an assumption.
    """
    if not url:
        return False
    secret = _env(CLIENT_SECRET_ENV)
    if len(secret) < 8:
        return False
    return secret in url


def build_fixture_authorization_url() -> dict[str, Any]:
    """A complete URL built from obviously-fake inputs, for artifacts and docs.

    Every value is a fixture. The issuer resolves nowhere, the client id belongs
    to nobody, and the state signs nothing — which is what makes it safe to
    commit alongside a redacted real one.
    """
    return build_authorization_url(
        issuer="https://nf-demo-fixture-issuer.invalid",
        client_id="nf-demo-fixture-client-id",
        redirect_uri="https://nf-demo-fixture-app.invalid/auth/callback",
        state="nf-demo-fixture-state",
        code_challenge="nf-demo-fixture-code-challenge",
    )


def authorization_url_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this service must never be able to produce."""
    failures: list[str] = []

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            failures.append(f"result_carries_{field}")

    if result.get("provider_called"):
        failures.append("authorization_url_construction_called_a_provider")

    if result.get("secret_exposed"):
        failures.append("client_secret_reached_the_authorization_url")

    url = str(result.get("authorization_url") or "")
    if url and "client_secret" in url:
        failures.append("authorization_url_carries_a_client_secret_parameter")

    if result.get("authorization_url_returned") and not result.get(
        "authorization_url_available"
    ):
        failures.append("url_returned_while_unavailable")

    if result.get("authorization_url_available") and not result.get(
        "provider_configured"
    ):
        failures.append("url_available_without_provider_configuration")

    if result.get("authorization_url_available") and not result.get("state_bound"):
        failures.append("url_available_without_a_bound_state")

    if result.get("authorization_url_available") and not result.get("pkce_bound"):
        failures.append("url_available_without_a_bound_pkce_challenge")

    if result.get("authorization_url_returned") and result.get("blocked_reasons"):
        failures.append("url_returned_with_blocked_reasons_present")

    if (
        result.get("authorization_url_available")
        and not result.get("blocked_reasons")
        and not result.get("authorization_url_returned")
    ):
        # Availability is provider config plus state plus PKCE. Something else
        # can still refuse - an unusable challenge method, say - and when it
        # does it must have said so. A silent gap here is the shape of a URL
        # that was withheld for a reason nobody recorded.
        failures.append("url_available_and_unblocked_but_not_returned")

    if not result.get("authorization_url_returned") and not result.get(
        "blocked_reasons"
    ):
        failures.append("no_url_and_no_reason_given")

    if url and REDACTED_STATE in str(result.get("authorization_url_redacted") or ""):
        # The redacted twin must not be the live one. Cheap to check, and the
        # failure mode - publishing the wrong string - is expensive.
        if url == result.get("authorization_url_redacted"):
            failures.append("redacted_url_is_identical_to_the_live_url")

    if result.get("provider_configured") and not result.get(
        "authorization_endpoint_configured"
    ):
        failures.append("provider_configured_without_an_authorization_endpoint")

    return sorted(set(failures))
