"""Customer auth route contract (Gate 116C).

What each auth route is permitted to do before a provider exists.

## The point of a contract that mostly says no

Five routes are added by this gate and none of them authenticates anybody. That
sounds like a reason not to write a contract, and it is the opposite: a route
that exists and does nothing is the easiest thing in a codebase to quietly widen
later. This service states, per route and before the code, exactly which of five
dangerous things each one may do:

```text
provider_call_allowed        may it reach an identity provider?
creates_real_session         may it mint a session a browser will carry?
requires_state               must a state parameter be validated?
requires_pkce                must a code verifier be presented?
requires_organization_id_resolution   must Gate 112's resolution run?
requires_membership_verification      must a membership record back it?
```

Today every `provider_call_allowed` and every `creates_real_session` is false,
and each is false with a named reason rather than by omission.

## safe_without_provider is the field this gate turns on

A route is safe without a provider when it can answer honestly with no
configuration at all. All five are: `/login` says not-configured, `/callback`
refuses, `/session` and `/current-user` say unauthenticated, `/logout` clears a
cookie that was never set.

A route that were *not* safe without a provider would be one that hangs, crashes
or half-completes when asked — and adding one of those to a running application
is how a contract gate becomes an outage.

## Why /logout is different

It is the only route permitted to act while auth is not live: clearing a cookie
is safe whether or not one exists, and refusing to clear on the grounds that
there is no session would leave a stale cookie behind on exactly the path
somebody uses to get rid of one.

It still creates no session and calls no provider.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_route_contract_v1"

# The prefix the auth router mounts under. Stated once so the contract, the
# router and the readiness detector cannot disagree about the paths.
AUTH_ROUTE_PREFIX = "/api/auth"

ROUTE_FIELDS: tuple[str, ...] = (
    "route_path",
    "method",
    "route_available",
    "security_required",
    "provider_call_allowed",
    "creates_real_session",
    "requires_state",
    "requires_pkce",
    "requires_session_cookie_policy",
    "requires_organization_id_resolution",
    "requires_membership_verification",
    "safe_without_provider",
    "blocked_reasons",
)

# Per-route requirements, declared before the code that implements them.
#
# `security_required` means "a caller must already hold a session to use this",
# and it is true for exactly one route.
#
# /login and /callback are false by necessity: a caller with a session does not
# need to log in. /logout is false because clearing a cookie is safe either way.
# /session is false because a caller asking whether they have one should be told
# no rather than refused for not having one - Gate 116 had it true, which read
# correctly before there was a dependency to make the distinction.
# /current-user is the one that refuses.
ROUTE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "login",
        "route_path": f"{AUTH_ROUTE_PREFIX}/login",
        "method": "GET",
        "security_required": False,
        "requires_state": True,
        "requires_pkce": True,
        "requires_session_cookie_policy": True,
        "requires_organization_id_resolution": False,
        "requires_membership_verification": False,
        "why": (
            "starts the flow. It needs state and PKCE because it is where both "
            "are generated, and it needs no organization yet because nobody has "
            "authenticated"
        ),
    },
    {
        "name": "callback",
        "route_path": f"{AUTH_ROUTE_PREFIX}/callback",
        "method": "GET",
        "security_required": False,
        "requires_state": True,
        "requires_pkce": True,
        "requires_session_cookie_policy": True,
        "requires_organization_id_resolution": True,
        "requires_membership_verification": True,
        "why": (
            "the only route that could ever mint a session, so it carries every "
            "requirement: state and PKCE validated, an organization_id resolved "
            "per Gate 112, and a membership record verified"
        ),
    },
    {
        "name": "logout",
        "route_path": f"{AUTH_ROUTE_PREFIX}/logout",
        "method": "POST",
        "security_required": False,
        "requires_state": False,
        "requires_pkce": False,
        "requires_session_cookie_policy": True,
        "requires_organization_id_resolution": False,
        "requires_membership_verification": False,
        "why": (
            "clearing a cookie is safe whether or not one exists, and refusing "
            "on the grounds that there is no session would leave a stale cookie "
            "on the path somebody uses to get rid of one. POST so a link or an "
            "image tag cannot log a user out"
        ),
    },
    {
        "name": "session",
        "route_path": f"{AUTH_ROUTE_PREFIX}/session",
        "method": "GET",
        # Gate 117 made this optional. Gate 116 declared it required, which read
        # correctly then and would now be wrong: a caller asking whether they
        # have a session should be told no, not refused for not having one.
        "security_required": False,
        "requires_state": False,
        "requires_pkce": False,
        "requires_session_cookie_policy": True,
        "requires_organization_id_resolution": False,
        "requires_membership_verification": False,
        "why": (
            "reports on whatever session the caller holds, including none. It "
            "resolves no organization because it establishes nothing - it "
            "describes"
        ),
    },
    {
        "name": "current_user",
        "route_path": f"{AUTH_ROUTE_PREFIX}/current-user",
        "method": "GET",
        "security_required": True,
        "requires_state": False,
        "requires_pkce": False,
        "requires_session_cookie_policy": True,
        "requires_organization_id_resolution": True,
        "requires_membership_verification": True,
        "why": (
            "returning who somebody is includes which organization they act "
            "for, and that answer is only trustworthy through Gate 112's "
            "resolution plus a verified membership"
        ),
    },
)

# The only route that could ever mint a session, and only then.
SESSION_MINTING_ROUTE = "callback"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_route_contract(
    spec: dict[str, Any],
    *,
    route_available: bool = False,
    provider_configured: bool = False,
    callback_validation_passed: bool = False,
    organization_id_resolved: bool = False,
    membership_verified: bool = False,
    session_cookie_policy_available: bool = False,
) -> dict[str, Any]:
    """What this route may do, given what is true. Deny by default."""
    name = str(spec["name"])
    blocked_reasons: list[str] = []

    if not route_available:
        blocked_reasons.append(f"route_not_registered:{spec['route_path']}")
    if spec["requires_session_cookie_policy"] and not session_cookie_policy_available:
        blocked_reasons.append("no_session_cookie_policy_available")

    # A provider call is permitted only where a provider is configured, and only
    # from the two routes that are part of the redirect flow. Nothing else in
    # NativeForge has a reason to contact an identity provider.
    provider_flow_route = name in {"login", "callback"}
    provider_call_allowed = bool(provider_configured and provider_flow_route)
    if provider_flow_route and not provider_configured:
        blocked_reasons.append("no_provider_configured_so_no_provider_call")

    # Only the callback may mint a session, and only once everything that
    # decides who the session belongs to has actually run.
    if name == SESSION_MINTING_ROUTE:
        creates_real_session = bool(
            provider_configured
            and callback_validation_passed
            and organization_id_resolved
            and membership_verified
        )
        if not callback_validation_passed:
            blocked_reasons.append("callback_validation_has_not_passed")
        if not organization_id_resolved:
            blocked_reasons.append("organization_id_not_resolved_from_the_claims")
        if not membership_verified:
            blocked_reasons.append("membership_not_verified_for_this_organization")
    else:
        creates_real_session = False

    # Safe without a provider: can this route answer honestly with nothing
    # configured? All five can, which is what makes registering them safe.
    safe_without_provider = True

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "route": name,
            "route_path": spec["route_path"],
            "method": spec["method"],
            "why": spec["why"],
            "route_available": bool(route_available),
            "security_required": bool(spec["security_required"]),
            "provider_call_allowed": provider_call_allowed,
            "creates_real_session": creates_real_session,
            "requires_state": bool(spec["requires_state"]),
            "requires_pkce": bool(spec["requires_pkce"]),
            "requires_session_cookie_policy": bool(
                spec["requires_session_cookie_policy"]
            ),
            "requires_organization_id_resolution": bool(
                spec["requires_organization_id_resolution"]
            ),
            "requires_membership_verification": bool(
                spec["requires_membership_verification"]
            ),
            "safe_without_provider": safe_without_provider,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a contract describes. It registers nothing and calls
            # nothing.
            "real_users_created": False,
            "real_sessions_created": False,
            "provider_contacted": False,
            "current_org_id_set": False,
            "secret_value_emitted": False,
            "fabricated": False,
        }
    )


def build_auth_route_contract_set(
    *,
    route_readiness: dict[str, Any] | None = None,
    provider_configured: bool | None = None,
    callback_validation_passed: bool | None = None,
    organization_id_resolved: bool = False,
    membership_verified: bool = False,
    session_cookie_policy_available: bool | None = None,
) -> dict[str, Any]:
    """Every route's contract, against what is actually true today."""
    from nativeforge.services.auth0_live_validation_runner_service import (
        run_auth0_live_validation,
    )
    from nativeforge.services.auth0_preflight_service import run_auth0_preflight
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy,
        policy_invariant_failures,
    )

    readiness = (
        route_readiness if route_readiness is not None else build_route_readiness()
    )
    if provider_configured is None:
        provider_configured = bool(run_auth0_preflight().get("validation_possible"))
    if callback_validation_passed is None:
        callback_validation_passed = bool(
            run_auth0_live_validation().get("callback_session_validated")
        )
    if session_cookie_policy_available is None:
        policy = build_session_cookie_policy()
        # Available means it exists *and* holds together. A policy failing its
        # own invariants is not a policy anything should rely on.
        session_cookie_policy_available = not policy_invariant_failures(policy)

    # Which routes the application actually serves, from the readiness detector
    # rather than from this module's own list.
    availability = {
        "login": bool(readiness.get("login_route_available")),
        "callback": bool(readiness.get("callback_route_available")),
        "logout": bool(readiness.get("logout_route_available")),
        "session": bool(readiness.get("session_route_available")),
        "current_user": bool(readiness.get("current_user_route_available")),
    }

    rows = [
        build_route_contract(
            spec,
            route_available=availability[spec["name"]],
            provider_configured=provider_configured,
            callback_validation_passed=callback_validation_passed,
            organization_id_resolved=organization_id_resolved,
            membership_verified=membership_verified,
            session_cookie_policy_available=session_cookie_policy_available,
        )
        for spec in ROUTE_SPECS
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_route_prefix": AUTH_ROUTE_PREFIX,
            "auth_routes_contract_available": True,
            "rows": rows,
            "route_count": len(rows),
            "routes_available_count": sum(1 for r in rows if r["route_available"]),
            "provider_call_allowed_count": sum(
                1 for r in rows if r["provider_call_allowed"]
            ),
            "session_minting_route": SESSION_MINTING_ROUTE,
            "session_cookie_policy_available": bool(session_cookie_policy_available),
            "provider_configured": bool(provider_configured),
            "callback_validation_passed": bool(callback_validation_passed),
            # Constants.
            "real_users_created": False,
            "real_sessions_created": False,
            "provider_contacted": False,
            "current_org_id_set": False,
            "secret_value_emitted": False,
            "fabricated": False,
        }
    )


def route_contract_invariant_failures(row: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if row.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in ROUTE_FIELDS:
        if field not in row:
            fails.append(f"route_contract_missing_field:{field}")

    for constant in (
        "real_users_created",
        "real_sessions_created",
        "provider_contacted",
        "current_org_id_set",
        "secret_value_emitted",
        "fabricated",
    ):
        if row.get(constant) is not False:
            fails.append(f"route_contract_claimed:{constant}")

    name = row.get("route")

    # Only the callback may mint a session. This is the rule the whole service
    # exists to hold.
    if row.get("creates_real_session") and name != SESSION_MINTING_ROUTE:
        fails.append(f"non_callback_route_creates_a_session:{name}")

    # And only when everything that decides whose session it is has run.
    if row.get("creates_real_session"):
        for required in (
            "requires_organization_id_resolution",
            "requires_membership_verification",
        ):
            if not row.get(required):
                fails.append(f"session_created_without:{required}")
        if row.get("blocked_reasons"):
            fails.append("session_created_despite_blocked_reasons")

    # A provider call may only come from the redirect flow.
    if row.get("provider_call_allowed") and name not in {"login", "callback"}:
        fails.append(f"provider_call_permitted_from:{name}")

    # The callback carries every requirement, unconditionally.
    if name == SESSION_MINTING_ROUTE:
        for required in (
            "requires_state",
            "requires_pkce",
            "requires_organization_id_resolution",
            "requires_membership_verification",
            "requires_session_cookie_policy",
        ):
            if not row.get(required):
                fails.append(f"callback_route_missing_requirement:{required}")

    # A route in the redirect flow validates state and a verifier.
    if name in {"login", "callback"}:
        if not row.get("requires_state"):
            fails.append(f"redirect_flow_route_without_state:{name}")
        if not row.get("requires_pkce"):
            fails.append(f"redirect_flow_route_without_pkce:{name}")

    # Every route must be answerable with nothing configured.
    if not row.get("safe_without_provider"):
        fails.append(f"route_not_safe_without_a_provider:{name}")

    # A refusal must name itself.
    if not row.get("route_available") and not row.get("blocked_reasons"):
        fails.append(f"route_unavailable_without_a_reason:{name}")

    return fails


def contract_set_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = contract.get("rows") or []
    if len(rows) != len(ROUTE_SPECS):
        fails.append("contract_set_does_not_cover_every_route")

    covered = {row.get("route") for row in rows}
    for spec in ROUTE_SPECS:
        if spec["name"] not in covered:
            fails.append(f"route_not_covered:{spec['name']}")

    for row in rows:
        fails.extend(
            f"{row.get('route')}:{f}" for f in route_contract_invariant_failures(row)
        )

    # At most one route may ever mint a session.
    minting = [r.get("route") for r in rows if r.get("creates_real_session")]
    if len(minting) > 1:
        fails.append("more_than_one_route_mints_a_session")

    # The counts must agree with the rows they summarise.
    if contract.get("routes_available_count") != sum(
        1 for r in rows if r.get("route_available")
    ):
        fails.append("routes_available_count_disagrees_with_the_rows")

    for constant in (
        "real_users_created",
        "real_sessions_created",
        "provider_contacted",
        "current_org_id_set",
        "secret_value_emitted",
        "fabricated",
    ):
        if contract.get(constant) is not False:
            fails.append(f"contract_set_claimed:{constant}")

    return fails
