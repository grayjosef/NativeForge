"""Customer auth provider readiness (Gate 121C).

Whether the OIDC provider side is configured enough for a redirect to complete.

## Configured, reachable, and validated are three different facts

```text
configured   a value is set here
reachable    a browser could get to it - asserted by an operator, never tested
validated    we fetched the issuer's JWKS and it checked out
```

Only the first is measurable offline, and it is the only one this service
measures on its own. `redirect_uri_publicly_reachable_claimed` carries
`_claimed` in its name because nothing here can verify it: reachability is a
question about DNS, TLS and a tunnel, and a service that answered it from a
config file would be guessing.

## An unvalidated JWKS is not a failed one

```text
jwks_network_check_allowed     false by default; nothing here raises it
jwks_network_check_attempted   false unless allowed AND a result was supplied
jwks_validated                 false unless attempted AND it passed
```

Three booleans rather than one, because "we never looked" and "we looked and it
was wrong" call for completely different operator actions. Gate 115 made the
same distinction for the activation gate and this preserves it.

## The redirect URI has to match a route

Gate 121A found the configured callback URL points at a path that exists in
neither the API nor the frontend — `http://localhost:5173/auth/callback` against
an API route of `/api/auth/callback`.

A "configured" boolean cannot catch that: the value *is* configured. So
`callback_route_matches_redirect_uri` compares the path, and it is false today.
Registering the configured value provider-side and completing a login would land
a real browser on a 404 holding a live authorization code.

## provider_ready needs every non-network gate

Derived affirmatively, and deliberately independent of the network check: a
deployment that has configured everything correctly is *provider ready* whether
or not anybody has run a JWKS fetch. The fetch is a separate, later assurance,
and folding it in would make `provider_ready` unreachable without a network
call this gate refuses to make.

## No secret, no value, no call

`client_secret_present` is a boolean. The endpoints and the issuer are public
identifiers — every browser sees them — and are still redacted to scheme, host
and path before they reach a result, so an artifact can carry them safely.

`provider_called` is a constant `False` and an invariant refuses any result
claiming otherwise.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_authorization_url_service import (
    AUDIENCE_ENV,
    CLIENT_ID_ENV,
    CLIENT_SECRET_ENV,
    ISSUER_ENV,
)
from nativeforge.services.customer_auth_environment_preflight_service import (
    CALLBACK_ROUTE_PATH,
    redact_url,
    url_path,
)

SCHEMA_VERSION = "nf_customer_auth_provider_readiness_v1"

# The conventional OIDC paths under an issuer. Discovery would fetch these from
# the well-known document, which is the network call this gate does not make.
TOKEN_PATH = "/oauth/token"
JWKS_PATH = "/.well-known/jwks.json"

# What must hold before a redirect could complete. Every one is measurable
# offline; the JWKS check is deliberately not among them.
REQUIRED_PROVIDER_GATES: tuple[str, ...] = (
    "issuer_configured",
    "client_id_configured",
    "client_secret_present",
    "authorization_endpoint_configured",
    "token_endpoint_configured",
    "jwks_uri_configured",
    "audience_configured",
    "redirect_uri_configured",
    "callback_route_available",
    "callback_route_matches_redirect_uri",
)

FORBIDDEN_VALUE_FIELDS = frozenset(
    {
        "client_secret",
        "client_secret_value",
        "secret",
        "secret_value",
        "signing_key",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    *REQUIRED_PROVIDER_GATES,
    "redirect_uri_publicly_reachable_claimed",
    "jwks_network_check_allowed",
    "jwks_network_check_attempted",
    "jwks_validated",
    "provider_ready",
    "blocked_reasons",
    "next_required_actions",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _present(value: Any) -> bool:
    return bool(str(value or "").strip())


def _endpoint(issuer: str, path: str) -> str:
    return f"{issuer.rstrip('/')}{path}" if issuer else ""


def build_provider_readiness(
    *,
    environ: dict[str, str] | None = None,
    issuer: str | None = None,
    client_id: str | None = None,
    client_secret_present: bool | None = None,
    audience: str | None = None,
    redirect_uri: str | None = None,
    callback_route_path: str = CALLBACK_ROUTE_PATH,
    callback_route_available: bool | None = None,
    redirect_uri_publicly_reachable_claimed: bool = False,
    jwks_network_check_allowed: bool = False,
    jwks_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Is the provider side complete? Deny by default; contact nobody.

    Every input is injectable so each branch is reachable without a configured
    provider. Injecting one does not configure anything: with nothing supplied
    the environment is read and reports what it actually holds.
    """
    # Gate 129C: same resolution order as the preflight. Two answers to
    # "is the issuer configured" is the defect this campaign keeps finding.
    from nativeforge.lib.settings import auth_environment_overlay

    env = auth_environment_overlay(environ)

    resolved_issuer = str(
        issuer if issuer is not None else env.get(ISSUER_ENV, "")
    ).strip()
    resolved_client_id = str(
        client_id if client_id is not None else env.get(CLIENT_ID_ENV, "")
    ).strip()
    resolved_audience = str(
        audience if audience is not None else env.get(AUDIENCE_ENV, "")
    ).strip()

    # Presence only. The value is never read into a variable that reaches a
    # result, and there is no field for one.
    secret_present = (
        bool(client_secret_present)
        if client_secret_present is not None
        else _present(env.get(CLIENT_SECRET_ENV))
    )

    if redirect_uri is not None:
        resolved_redirect = str(redirect_uri).strip()
    else:
        from nativeforge.services.oidc_config_schema_service import (
            build_oidc_config_schema,
        )

        resolved_redirect = str(
            build_oidc_config_schema().get("callback_url") or ""
        ).strip()

    if callback_route_available is None:
        from nativeforge.services.customer_auth_route_readiness_service import (
            build_route_readiness,
        )

        callback_route_available = bool(
            build_route_readiness().get("callback_route_available")
        )

    blocked_reasons: list[str] = []
    next_required_actions: list[str] = []

    gates: dict[str, bool] = {
        "issuer_configured": _present(resolved_issuer),
        "client_id_configured": _present(resolved_client_id),
        "client_secret_present": bool(secret_present),
        "audience_configured": _present(resolved_audience),
        # Derived from the issuer rather than configured separately. A
        # deployment that had to set four endpoint URLs by hand would get one of
        # them wrong, and the wrong one would be discovered at token exchange.
        "authorization_endpoint_configured": _present(resolved_issuer),
        "token_endpoint_configured": _present(resolved_issuer),
        "jwks_uri_configured": _present(resolved_issuer),
        "redirect_uri_configured": _present(resolved_redirect),
        "callback_route_available": bool(callback_route_available),
        "callback_route_matches_redirect_uri": False,
    }

    # Gate 121A's finding, checked rather than assumed. The path has to be one
    # something can consume.
    if gates["redirect_uri_configured"]:
        gates["callback_route_matches_redirect_uri"] = bool(
            url_path(resolved_redirect) == str(callback_route_path).strip()
        )

    for name in REQUIRED_PROVIDER_GATES:
        if not gates[name]:
            blocked_reasons.append(f"provider_gate_not_satisfied:{name}")

    if not gates["issuer_configured"]:
        next_required_actions.append(f"set {ISSUER_ENV} out-of-band")
    if not gates["client_id_configured"]:
        next_required_actions.append(f"set {CLIENT_ID_ENV} out-of-band")
    if not gates["client_secret_present"]:
        next_required_actions.append(
            f"supply {CLIENT_SECRET_ENV} from a secret manager; presence is "
            "detected and the value is never read"
        )
    if not gates["audience_configured"]:
        next_required_actions.append(f"set {AUDIENCE_ENV} out-of-band")
    if (
        gates["redirect_uri_configured"]
        and not gates["callback_route_matches_redirect_uri"]
    ):
        next_required_actions.append(
            "point the redirect URI at a path that can consume a callback - the "
            f"API route is {callback_route_path} - and register the same value "
            "in the provider console"
        )
    if not redirect_uri_publicly_reachable_claimed:
        # Not a gate. Nothing here can test reachability, so refusing on it
        # would be refusing on a measurement that never happened.
        next_required_actions.append(
            "confirm the redirect URI is reachable from a browser on the public "
            "internet - this service cannot test that and does not claim to"
        )

    # -- the network check, which stays off ----------------------------------
    allowed = bool(jwks_network_check_allowed)
    check = jwks_check or {}
    attempted = bool(allowed and check.get("attempted"))
    validated = bool(attempted and check.get("passed"))
    if not allowed:
        blocked_reasons.append("jwks_network_check_not_allowed_so_unvalidated")
        next_required_actions.append(
            "run the JWKS check deliberately, under review, once the issuer is "
            "configured - it is the only step here that touches the network"
        )
    elif not attempted:
        blocked_reasons.append("jwks_network_check_allowed_but_not_attempted")

    # Derived affirmatively, and independent of the network check on purpose:
    # a correctly configured deployment is provider-ready whether or not anybody
    # has run a JWKS fetch yet.
    provider_ready = all(gates[name] for name in REQUIRED_PROVIDER_GATES)

    from nativeforge.services.oidc_provider_discovery_service import (
        build_provider_endpoints,
    )

    _resolved_endpoints = build_provider_endpoints(resolved_issuer)

    result = {
        "schema_version": SCHEMA_VERSION,
        **gates,
        # Public identifiers, redacted anyway so an artifact can carry them.
        "issuer_redacted": redact_url(resolved_issuer),
        # Gate 130: derived from the issuer's discovery document when one is
        # available, and from the conventional shape otherwise. Concatenating
        # `/authorize` under the issuer publishes a falsehood for any provider
        # that does not follow Auth0's convention - Google's authorization
        # endpoint is /o/oauth2/v2/auth and its token and JWKS endpoints are on
        # different hosts entirely.
        "authorization_endpoint_redacted": redact_url(
            _resolved_endpoints.get("authorization_endpoint", "")
        ),
        "token_endpoint_redacted": redact_url(
            _resolved_endpoints.get("token_endpoint", "")
        ),
        "jwks_uri_redacted": redact_url(_resolved_endpoints.get("jwks_uri", "")),
        "endpoints_discovered": bool(_resolved_endpoints.get("endpoints_discovered")),
        "endpoints_are_conventional": bool(
            _resolved_endpoints.get("endpoints_are_conventional")
        ),
        "redirect_uri_redacted": redact_url(resolved_redirect),
        "callback_route_path": str(callback_route_path),
        # Named `_claimed` because nothing here can verify it.
        "redirect_uri_publicly_reachable_claimed": bool(
            redirect_uri_publicly_reachable_claimed
        ),
        "jwks_network_check_allowed": allowed,
        "jwks_network_check_attempted": attempted,
        "jwks_validated": validated,
        "provider_ready": provider_ready,
        "missing_provider_gates": [
            name for name in REQUIRED_PROVIDER_GATES if not gates[name]
        ],
        "blocked_reasons": sorted(set(blocked_reasons)),
        "next_required_actions": sorted(set(next_required_actions)),
        # Constants. This service reads configuration and calls nobody.
        "provider_called": False,
        "network_calls": False,
        "client_secret_value_emitted": False,
        "customer_auth_live": False,
        "login_live": False,
    }
    return _json_safe(result)


def provider_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this service must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            failures.append(f"result_carries_{field}")

    if result.get("provider_called") or result.get("network_calls"):
        failures.append("provider_readiness_contacted_a_provider")

    if result.get("client_secret_value_emitted"):
        failures.append("a_client_secret_value_was_emitted")

    if result.get("jwks_network_check_attempted") and not result.get(
        "jwks_network_check_allowed"
    ):
        failures.append("jwks_check_attempted_without_permission")

    if result.get("jwks_validated") and not result.get("jwks_network_check_attempted"):
        failures.append("jwks_validated_without_being_checked")

    if result.get("provider_ready"):
        for name in REQUIRED_PROVIDER_GATES:
            if not result.get(name):
                failures.append(f"provider_ready_without:{name}")
        if result.get("missing_provider_gates"):
            failures.append("provider_ready_with_missing_gates")

    if result.get("customer_auth_live") or result.get("login_live"):
        failures.append("provider_readiness_claimed_auth_is_live")

    # A redacted URL carrying a query string means the redaction did not run.
    for field in (
        "issuer_redacted",
        "authorization_endpoint_redacted",
        "token_endpoint_redacted",
        "jwks_uri_redacted",
        "redirect_uri_redacted",
    ):
        value = str(result.get(field) or "")
        if "?" in value or "#" in value:
            failures.append(f"{field}_was_not_redacted")

    if not result.get("provider_ready") and not result.get("blocked_reasons"):
        failures.append("provider_refused_without_a_reason")

    return sorted(set(failures))
