"""Customer auth redirect flow (Gate 117C).

The OIDC authorization-code flow, expressed as a contract that refuses at every
step it cannot complete honestly.

## The flow, and where it stops today

```text
1. /login builds an authorization URL          needs provider config
2. state and PKCE are generated locally        works today, no provider needed
3. the browser goes to the provider            never happens; no URL is built
4. the provider redirects to /callback         never happens
5. state and PKCE are validated                works today, given inputs
6. the code is exchanged for tokens            blocked at the boundary
7. claims resolve to an organization_id        Gate 112's contract, unexercised
8. a membership is verified                    Gate 112's contract, unexercised
9. a session is created                        never
```

Steps 2 and 5 are real code that runs. Everything else is a contract that says
what would have to be true.

## Building a URL is not calling a provider

`authorization_url_available` requires provider configuration and nothing else.
Constructing a URL string is local work — no socket is opened, and the browser
would be the thing that visits it, not NativeForge.

This service does not return the URL either. It reports whether one *could* be
built, because a URL containing a client id and a redirect URI in a committed
artifact is a configuration disclosure nobody asked for.

## session_creation_allowed has five conjuncts

```python
session_creation_allowed = (
    token_exchange_allowed
    and callback_validation_passed
    and organization_id_resolved
    and membership_verified
    and role_mapping_available
)
```

The middle three are Gate 112's rule restated at the flow layer: a token proves
who somebody is; it does not prove which organization they act for, and a claim
about an organization is not a membership in one.

`session_created` is a separate constant `False`. Allowed is not done, and
nothing in this repository creates a session.

## No provider call, by construction

The token exchange lives behind `customer_auth_token_exchange_boundary_service`,
whose `network_call_allowed` defaults to `False` and is raised by nothing here.
`provider_contacted` and `network_calls` are constants with invariants behind
them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_redirect_flow_v1"

# What must hold before a session may be created at the end of a flow.
SESSION_CREATION_CONDITIONS: tuple[str, ...] = (
    "token_exchange_allowed",
    "callback_validation_passed",
    "organization_id_resolved",
    "membership_verified",
    "role_mapping_available",
)

RESULT_FIELDS: tuple[str, ...] = (
    "provider_configured",
    "authorization_url_available",
    "state_generated",
    "state_validated",
    "pkce_generated",
    "pkce_validated",
    "token_exchange_allowed",
    "token_exchange_performed",
    "callback_validation_passed",
    "session_creation_allowed",
    "session_created",
    "customer_auth_live",
    "login_live",
    "blocked_reasons",
    "next_required_actions",
)

# What lifts each step, in the order the flow would need them.
FLOW_REMEDIES: tuple[tuple[str, str], ...] = (
    (
        "provider_configured",
        "owner sets the OIDC_* environment variables out-of-band; no value is "
        "read into this service",
    ),
    (
        "authorization_url_available",
        "follows provider configuration; building a URL is local work and "
        "contacts nobody",
    ),
    (
        "state_validated",
        "the callback must return the state issued at /login",
    ),
    (
        "pkce_validated",
        "the callback must present a verifier matching the challenge sent at "
        "/login",
    ),
    (
        "token_exchange_allowed",
        "every condition in the token exchange boundary, including "
        "network_call_allowed, which nothing raises today",
    ),
    (
        "callback_validation_passed",
        "validate a real callback against the eight failure modes the OIDC "
        "harness already models",
    ),
    (
        "organization_id_resolved",
        "Gate 112's resolution must turn a verified claim into an "
        "organization_id; a token does not carry one",
    ),
    (
        "membership_verified",
        "a membership record must back the organization the claim names",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def build_redirect_flow_contract(
    *,
    provider_configured: bool | None = None,
    secret_present: bool | None = None,
    callback_code_present: bool = False,
    callback_validation_passed: bool | None = None,
    organization_id_resolved: bool = False,
    membership_verified: bool = False,
    network_call_allowed: bool = False,
    state_pkce: dict[str, Any] | None = None,
    state_validation: dict[str, Any] | None = None,
    generator: Callable[[int], str] | None = None,
) -> dict[str, Any]:
    """The whole flow, refusing at every step it cannot complete. Deny by default."""
    from nativeforge.services.auth0_live_validation_runner_service import (
        run_auth0_live_validation,
    )
    from nativeforge.services.auth0_preflight_service import run_auth0_preflight
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_state_pkce_service import (
        generate_state_and_pkce,
    )
    from nativeforge.services.customer_auth_token_exchange_boundary_service import (
        evaluate_token_exchange_boundary,
    )

    if provider_configured is None:
        provider_configured = bool(
            run_auth0_preflight().get("validation_possible")
        )
    if callback_validation_passed is None:
        callback_validation_passed = bool(
            run_auth0_live_validation().get("callback_session_validated")
        )

    # Generated locally. No provider is involved in either.
    generated = (
        state_pkce
        if state_pkce is not None
        else generate_state_and_pkce(generator=generator)
    )
    state_generated = bool(generated.get("state_generated"))
    pkce_generated = bool(generated.get("code_challenge_generated"))

    # Validation happens at the callback, against a state and verifier this
    # service was handed. Absent one, nothing is validated - which is different
    # from validated-and-failed, and reported as such.
    validation = state_validation or {}
    state_validated = bool(validation.get("state_valid"))
    pkce_validated = bool(validation.get("pkce_valid"))

    blocked_reasons: list[str] = []

    # Building a URL needs configuration and nothing else. NativeForge does not
    # visit it; a browser would.
    authorization_url_available = bool(provider_configured)
    if not provider_configured:
        blocked_reasons.append("no_provider_configured_so_no_authorization_url")

    if not state_generated:
        blocked_reasons.append("no_state_generated")
    if not pkce_generated:
        blocked_reasons.append("no_pkce_challenge_generated")
    if not state_validated:
        blocked_reasons.append("callback_state_not_validated")
    if not pkce_validated:
        blocked_reasons.append("callback_pkce_not_validated")

    # `secret_present` is threaded through rather than left to the boundary to
    # detect. Without it the permitted branch of this contract would be
    # unreachable in a test, and every refusal above would be unfalsifiable.
    exchange = evaluate_token_exchange_boundary(
        provider_configured=provider_configured,
        secret_present=secret_present,
        callback_code_present=callback_code_present,
        state_validated=state_validated,
        pkce_validated=pkce_validated,
        network_call_allowed=network_call_allowed,
    )
    token_exchange_allowed = bool(exchange["token_exchange_allowed"])
    token_exchange_performed = bool(exchange["token_exchange_performed"])
    blocked_reasons.extend(exchange["blocked_reasons"])

    if not callback_validation_passed:
        blocked_reasons.append("callback_validation_has_not_passed")
    if not organization_id_resolved:
        blocked_reasons.append("no_organization_id_resolved_from_the_claims")
    if not membership_verified:
        blocked_reasons.append("no_verified_membership_for_this_organization")

    role_mapping_available = _module_importable(
        "nativeforge.services.customer_auth_role_mapping_service"
    )
    if not role_mapping_available:
        blocked_reasons.append("no_role_mapping_contract_available")

    conditions = {
        "token_exchange_allowed": token_exchange_allowed,
        "callback_validation_passed": bool(callback_validation_passed),
        "organization_id_resolved": bool(organization_id_resolved),
        "membership_verified": bool(membership_verified),
        "role_mapping_available": role_mapping_available,
    }

    # Derived affirmatively. Every conjunct must hold.
    session_creation_allowed = all(
        conditions[name] for name in SESSION_CREATION_CONDITIONS
    )

    # Allowed is not done. Nothing in this repository creates a session.
    session_created = False

    gate = build_customer_auth_activation_gate()

    next_required_actions = [
        {"step": step, "action": action}
        for step, action in FLOW_REMEDIES
        if not _step_satisfied(
            step,
            provider_configured=provider_configured,
            authorization_url_available=authorization_url_available,
            state_validated=state_validated,
            pkce_validated=pkce_validated,
            token_exchange_allowed=token_exchange_allowed,
            callback_validation_passed=bool(callback_validation_passed),
            organization_id_resolved=bool(organization_id_resolved),
            membership_verified=bool(membership_verified),
        )
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "redirect_flow_contract_available": True,
            "provider_configured": bool(provider_configured),
            "authorization_url_available": authorization_url_available,
            # Deliberately not returned. A URL carrying a client id and a
            # redirect URI in a committed artifact is a disclosure nobody asked
            # for.
            "authorization_url_returned": False,
            "state_generated": state_generated,
            "state_validated": state_validated,
            "pkce_generated": pkce_generated,
            "pkce_validated": pkce_validated,
            "code_challenge_method": generated.get("code_challenge_method"),
            "token_exchange_allowed": token_exchange_allowed,
            "token_exchange_performed": token_exchange_performed,
            "callback_code_present": bool(callback_code_present),
            "callback_validation_passed": bool(callback_validation_passed),
            "organization_id_resolved": bool(organization_id_resolved),
            "membership_verified": bool(membership_verified),
            "role_mapping_available": role_mapping_available,
            "session_creation_allowed": session_creation_allowed,
            "session_created": session_created,
            "missing_session_conditions": [
                name for name in SESSION_CREATION_CONDITIONS if not conditions[name]
            ],
            "customer_auth_live": bool(gate["customer_auth_live"]),
            "login_live": bool(gate["login_live"]),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": next_required_actions,
            # Constants: a contract describes a flow it does not run.
            "provider_contacted": False,
            "network_calls": False,
            "real_sessions_created": False,
            "real_users_created": False,
            "secret_value_emitted": False,
            "token_value_emitted": False,
            "current_org_id_set": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def _step_satisfied(step: str, **facts: bool) -> bool:
    return bool(facts.get(step, False))


def redirect_flow_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"redirect_flow_missing_field:{field}")

    for constant in (
        "provider_contacted",
        "network_calls",
        "real_sessions_created",
        "real_users_created",
        "secret_value_emitted",
        "token_value_emitted",
        "current_org_id_set",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"redirect_flow_claimed:{constant}")

    # A URL needs configuration, and building one is not visiting one.
    if result.get("authorization_url_available") and not result.get(
        "provider_configured"
    ):
        fails.append("authorization_url_available_without_a_configured_provider")
    if result.get("authorization_url_returned"):
        fails.append("redirect_flow_returned_an_authorization_url")

    # Token exchange requires validated state and PKCE, always.
    if result.get("token_exchange_allowed"):
        for required in ("state_validated", "pkce_validated", "provider_configured"):
            if not result.get(required):
                fails.append(f"token_exchange_allowed_without:{required}")

    # And a boundary service never performs one.
    if result.get("token_exchange_performed"):
        fails.append("redirect_flow_reported_a_performed_token_exchange")

    # The five conjuncts, each named.
    if result.get("session_creation_allowed"):
        for name in SESSION_CREATION_CONDITIONS:
            if not result.get(name):
                fails.append(f"session_creation_allowed_without:{name}")

    # Allowed is not done.
    if result.get("session_created"):
        if not result.get("session_creation_allowed"):
            fails.append("session_created_without_being_allowed")
        fails.append("redirect_flow_created_a_session")

    # Gate 112's rule, at the flow layer.
    if result.get("session_creation_allowed"):
        if not result.get("organization_id_resolved"):
            fails.append("session_allowed_without_an_organization_id")
        if not result.get("membership_verified"):
            fails.append("session_allowed_without_a_verified_membership")

    # PKCE is S256 or it is not PKCE.
    method = result.get("code_challenge_method")
    if result.get("pkce_validated") and method not in {"S256", None}:
        fails.append(f"pkce_validated_with_a_disallowed_method:{method}")

    # The missing list must agree with the conditions it summarises.
    expected = [
        name for name in SESSION_CREATION_CONDITIONS if not result.get(name)
    ]
    if list(result.get("missing_session_conditions") or []) != expected:
        fails.append("missing_session_conditions_disagrees_with_the_conditions")

    # A refusal must name itself.
    if not result.get("session_creation_allowed") and not result.get(
        "blocked_reasons"
    ):
        fails.append("session_creation_refused_without_a_reason")

    return fails
