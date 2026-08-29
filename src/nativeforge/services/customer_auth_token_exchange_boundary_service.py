"""Customer auth token exchange boundary (Gate 117E).

The one place in NativeForge that would ever send a client secret over the
network, and the reason it does not.

## Why a boundary rather than an implementation

Token exchange is the single most dangerous operation in an OIDC flow. It posts
the client secret and an authorization code to the provider and receives an
identity in return. Everything about it is irreversible: a leaked secret is
leaked, a code redeemed by the wrong party is redeemed.

So this service decides *whether* an exchange may happen and never performs one.
`token_exchange_performed` is a constant `False` with an invariant behind it,
and the network call is behind an explicit `network_call_allowed` flag that
defaults to `False` and is never raised by anything in this repository.

## Six conditions, all required

```text
provider_configured    an issuer, client id and audience are present
secret_present         a client secret is present (a boolean, never a value)
callback_code_present  the provider actually returned a code
state_validated        the browser that started the flow finished it
pkce_validated         the client that started the flow is redeeming the code
network_call_allowed   somebody deliberately turned the network on
```

The first five decide whether an exchange *should* happen. The sixth decides
whether it *may*, and it is separate on purpose: a flow that satisfies every
security condition still must not reach the internet by accident during a test
run or an artifact regeneration.

## Nothing here handles a secret value

`secret_present` is a boolean from `auth0_preflight_service`, which reads
`os.environ` for presence only. This service never reads the value, never
receives one as a parameter, and never returns one. There is no code path here
that could print a secret, because there is no code path here that has one.

The same applies to tokens: `id_token_received` is a boolean. No token value is
accepted, stored or returned, and an invariant fails any result carrying a field
that looks like one.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_token_exchange_boundary_v1"

# Every condition that must hold before an exchange is permitted. Named
# individually so a refusal can say which one is missing.
REQUIRED_EXCHANGE_CONDITIONS: tuple[str, ...] = (
    "provider_configured",
    "secret_present",
    "callback_code_present",
    "state_validated",
    "pkce_validated",
    "network_call_allowed",
)

RESULT_FIELDS: tuple[str, ...] = REQUIRED_EXCHANGE_CONDITIONS + (
    "token_exchange_allowed",
    "token_exchange_performed",
    "id_token_received",
    "claims_verified",
    "blocked_reasons",
)

# Field names that would mean a token or secret value had entered the result.
# Checked by the invariants rather than trusted not to appear.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "id_token",
        "access_token",
        "refresh_token",
        "client_secret",
        "code",
        "authorization_code",
        "token",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_token_exchange_boundary(
    *,
    provider_configured: bool | None = None,
    secret_present: bool | None = None,
    callback_code_present: bool = False,
    state_validated: bool = False,
    pkce_validated: bool = False,
    network_call_allowed: bool = False,
) -> dict[str, Any]:
    """May a token exchange happen? Deny by default, and never perform one.

    `network_call_allowed` defaults to False and nothing in this repository
    raises it. It is a parameter so a future gate can turn it on deliberately,
    under review, rather than discovering it was on all along.
    """
    from nativeforge.services.auth0_preflight_service import run_auth0_preflight

    if provider_configured is None or secret_present is None:
        preflight = run_auth0_preflight()
        if provider_configured is None:
            provider_configured = bool(preflight.get("validation_possible"))
        if secret_present is None:
            # A boolean. The value is never read into this service.
            secret_present = bool(preflight.get("client_secret_present"))

    conditions = {
        "provider_configured": bool(provider_configured),
        "secret_present": bool(secret_present),
        "callback_code_present": bool(callback_code_present),
        "state_validated": bool(state_validated),
        "pkce_validated": bool(pkce_validated),
        "network_call_allowed": bool(network_call_allowed),
    }

    blocked_reasons: list[str] = []
    for name in REQUIRED_EXCHANGE_CONDITIONS:
        if not conditions[name]:
            blocked_reasons.append(f"token_exchange_blocked:{name}")

    # Derived affirmatively. Every condition must hold.
    token_exchange_allowed = all(
        conditions[name] for name in REQUIRED_EXCHANGE_CONDITIONS
    )

    # Allowed is not performed, and this service performs nothing. A later gate
    # that implements the exchange must set this from an actual result, and the
    # invariants below already refuse a claim without one.
    token_exchange_performed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **conditions,
            "token_exchange_allowed": token_exchange_allowed,
            "token_exchange_performed": token_exchange_performed,
            "id_token_received": False,
            "claims_verified": False,
            "missing_conditions": [
                name for name in REQUIRED_EXCHANGE_CONDITIONS if not conditions[name]
            ],
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_action": _next_action(conditions),
            # Constants. This service decides and does not act.
            "secret_value_read": False,
            "secret_value_emitted": False,
            "token_value_emitted": False,
            "provider_contacted": False,
            "network_calls": False,
            "real_sessions_created": False,
            "real_users_created": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def _next_action(conditions: dict[str, bool]) -> str:
    """What would lift the first unmet condition, in dependency order."""
    if not conditions["provider_configured"]:
        return (
            "owner sets the OIDC_* environment variables out-of-band; this "
            "service never receives or stores them"
        )
    if not conditions["secret_present"]:
        return (
            "owner supplies OIDC_CLIENT_SECRET out-of-band; presence is "
            "detected as a boolean and the value is never read here"
        )
    if not conditions["callback_code_present"]:
        return "the provider must return an authorization code to the callback"
    if not conditions["state_validated"]:
        return "validate the callback state against the one issued at /login"
    if not conditions["pkce_validated"]:
        return "validate the code verifier against the challenge sent at /login"
    if not conditions["network_call_allowed"]:
        return (
            "a later gate must turn network_call_allowed on deliberately, under "
            "review. Nothing in this repository raises it today"
        )
    return "every condition is met; an exchange implementation does not exist yet"


def token_exchange_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"token_exchange_missing_field:{field}")

    for constant in (
        "secret_value_read",
        "secret_value_emitted",
        "token_value_emitted",
        "provider_contacted",
        "network_calls",
        "real_sessions_created",
        "real_users_created",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"token_exchange_claimed:{constant}")

    # No token or secret value may ever appear in a result, by field name.
    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            fails.append(f"token_exchange_result_carries_a_value_field:{field}")

    # The rule this service exists to enforce.
    if result.get("token_exchange_allowed"):
        for name in REQUIRED_EXCHANGE_CONDITIONS:
            if not result.get(name):
                fails.append(f"token_exchange_allowed_without:{name}")
        if result.get("blocked_reasons"):
            fails.append("token_exchange_allowed_despite_blocked_reasons")

    # Allowed is not performed, and nothing here performs.
    if result.get("token_exchange_performed"):
        if not result.get("token_exchange_allowed"):
            fails.append("token_exchange_performed_without_being_allowed")
        if not result.get("network_call_allowed"):
            fails.append("token_exchange_performed_with_the_network_disallowed")
        fails.append("token_exchange_performed_by_a_boundary_service")

    # A token cannot arrive from an exchange that did not happen.
    if result.get("id_token_received") and not result.get(
        "token_exchange_performed"
    ):
        fails.append("id_token_received_without_an_exchange")

    # Claims cannot be verified from a token that never arrived.
    if result.get("claims_verified") and not result.get("id_token_received"):
        fails.append("claims_verified_without_an_id_token")

    # The missing list must agree with the conditions it summarises.
    expected = [
        name for name in REQUIRED_EXCHANGE_CONDITIONS if not result.get(name)
    ]
    if list(result.get("missing_conditions") or []) != expected:
        fails.append("missing_conditions_disagrees_with_the_conditions")

    # A refusal must name itself.
    if not result.get("token_exchange_allowed") and not result.get(
        "blocked_reasons"
    ):
        fails.append("token_exchange_refused_without_a_reason")

    return fails
