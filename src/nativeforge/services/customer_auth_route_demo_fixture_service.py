"""Customer auth route demo fixtures (Gate 116G).

Seven labelled cases walking the route spine from nothing registered to
everything built and still blocked. No user, no session, no provider call, no
secret.

## The seven cases

```text
routes_absent                    the application before this gate
routes_exist_no_provider         the application after it - this is today
provider_configured_no_callback  config arrived, nothing validated
callback_validated_no_org        validated, and nobody knows whose session it is
session_route_unauthenticated    the honest answer /session gives everyone
logout_clears_without_session    the one action permitted while auth is dead
all_routes_and_policy_blocked    everything built, activation still refused
```

The second and the last are the pair worth reading together. `routes_exist_no
_provider` is the state Gate 116 leaves the system in. `all_routes_and_policy
_blocked` adds a security scheme, enforcement and a cookie policy — and
activation is *still* refused, because provider configuration and secrets are
not things a route can supply.

That is the point of the set: it shows how much can be built without moving
`customer_auth_live` at all.

## No case activates

Unlike Gate 115's fixture set, none of these seven reaches a permitted state,
and that is correct rather than a gap — these fixtures vary *route* facts, and
no arrangement of routes makes auth live. Reachability of the permitted branch
is proved by Gate 115's own fixture set, which varies the provider facts that
actually gate activation.

An invariant here asserts zero activations, so a case that started activating
would be caught rather than celebrated.

## Nothing is created

Every case is a dictionary handed to a contract function. No route is called, no
`TestClient` is constructed, no cookie is written and no environment variable is
read for its value.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_route_contract_service import (
    build_auth_route_contract_set,
)
from nativeforge.services.customer_auth_route_readiness_service import (
    build_route_readiness,
)

SCHEMA_VERSION = "nf_customer_auth_route_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# Route tables describing applications other than this one. Invented.
NO_ROUTES: dict[str, Any] = {"paths": {}, "components": {}}

AUTH_ROUTES_UNSECURED: dict[str, Any] = {
    "paths": {
        "/api/auth/login": {"get": {}},
        "/api/auth/logout": {"post": {}},
        "/api/auth/callback": {"get": {}},
        "/api/auth/session": {"get": {}},
        "/api/auth/current-user": {"get": {}},
    },
    "components": {"securitySchemes": {"nf_session_cookie": {"type": "apiKey"}}},
}

AUTH_ROUTES_SECURED: dict[str, Any] = {
    "paths": {
        "/api/auth/login": {"get": {}},
        "/api/auth/logout": {"post": {}},
        "/api/auth/callback": {"get": {}},
        "/api/auth/session": {"get": {"security": [{"nf_session_cookie": []}]}},
        "/api/auth/current-user": {
            "get": {"security": [{"nf_session_cookie": []}]}
        },
    },
    "components": {"securitySchemes": {"nf_session_cookie": {"type": "apiKey"}}},
}

REQUIRED_ROUTE_CASES: frozenset[str] = frozenset(
    {
        "routes_absent",
        "routes_exist_no_provider",
        "provider_configured_no_callback",
        "callback_validated_no_org",
        "session_route_unauthenticated",
        "logout_clears_without_session",
        "all_routes_and_policy_blocked",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_route_cases() -> list[dict[str, Any]]:
    """Seven labelled cases. None of them activates anything."""
    absent = build_route_readiness(
        openapi=NO_ROUTES, cloudflare_access_in_front=False
    )
    unsecured = build_route_readiness(
        openapi=AUTH_ROUTES_UNSECURED, cloudflare_access_in_front=False
    )
    secured = build_route_readiness(
        openapi=AUTH_ROUTES_SECURED, cloudflare_access_in_front=False
    )

    return [
        {
            "case": "routes_absent",
            "fixture_label": FIXTURE_LABEL,
            "why": "the application before Gate 116: nowhere to log in",
            "expect_routes_available": 0,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": absent,
                "provider_configured": False,
                "callback_validation_passed": False,
                "session_cookie_policy_available": False,
            },
        },
        {
            "case": "routes_exist_no_provider",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the application after Gate 116, which is today: five routes "
                "that answer honestly and authenticate nobody"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": unsecured,
                "provider_configured": False,
                "callback_validation_passed": False,
                "session_cookie_policy_available": True,
            },
        },
        {
            "case": "provider_configured_no_callback",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "configuration arrived and nothing has been validated. The "
                "login route may now reach a provider; the callback still "
                "refuses to mint anything"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": unsecured,
                "provider_configured": True,
                "callback_validation_passed": False,
                "session_cookie_policy_available": True,
            },
        },
        {
            "case": "callback_validated_no_org",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a callback validated and nobody knows whose session it would "
                "be. Gate 112's resolution and a verified membership are both "
                "still required"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": unsecured,
                "provider_configured": True,
                "callback_validation_passed": True,
                "organization_id_resolved": False,
                "membership_verified": False,
                "session_cookie_policy_available": True,
            },
        },
        {
            "case": "session_route_unauthenticated",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the honest answer /session gives every caller, including one "
                "arriving through Cloudflare Access with a valid dev header"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": secured,
                "provider_configured": False,
                "callback_validation_passed": False,
                "session_cookie_policy_available": True,
            },
        },
        {
            "case": "logout_clears_without_session",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the one action permitted while auth is dead. Clearing a cookie "
                "is safe whether or not one exists"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": unsecured,
                "provider_configured": False,
                "callback_validation_passed": False,
                "session_cookie_policy_available": True,
            },
        },
        {
            "case": "all_routes_and_policy_blocked",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "everything a route gate can build - five routes, a security "
                "scheme, enforcement, a cookie policy - and activation is still "
                "refused. Provider configuration is not something a route "
                "supplies"
            ),
            "expect_routes_available": 5,
            "expect_any_session_created": False,
            "request": {
                "route_readiness": secured,
                "provider_configured": False,
                "callback_validation_passed": False,
                "session_cookie_policy_available": True,
            },
        },
    ]


def measure_route_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_route_demo_fixture_set() -> dict[str, Any]:
    """The seven cases, each run through the route contract."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    cases = build_demo_route_cases()
    covered = measure_route_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        contract = build_auth_route_contract_set(**case["request"])
        session_rows = [
            r["route"] for r in contract["rows"] if r["creates_real_session"]
        ]
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "expect_routes_available": case["expect_routes_available"],
                "expect_any_session_created": case["expect_any_session_created"],
                "routes_available_count": contract["routes_available_count"],
                "provider_call_allowed_count": contract[
                    "provider_call_allowed_count"
                ],
                "session_creating_routes": session_rows,
                "any_session_created": bool(session_rows),
                "provider_configured": contract["provider_configured"],
                "callback_validation_passed": contract["callback_validation_passed"],
                "session_cookie_policy_available": contract[
                    "session_cookie_policy_available"
                ],
                "blocked_reasons": sorted(
                    {
                        reason
                        for row in contract["rows"]
                        for reason in row["blocked_reasons"]
                    }
                ),
                "agrees_with_expectation": (
                    contract["routes_available_count"]
                    == case["expect_routes_available"]
                    and bool(session_rows)
                    is bool(case["expect_any_session_created"])
                ),
            }
        )

    # Measured separately from the real application, never forged.
    actual = build_customer_auth_activation_gate()
    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "cases": cases,
            "case_count": len(cases),
            "rows": rows,
            "route_cases_covered": sorted(covered),
            "route_cases_missing": sorted(REQUIRED_ROUTE_CASES - covered),
            "cases_disagreeing_with_expectation": disagreements,
            "session_creating_case_count": sum(
                1 for r in rows if r["any_session_created"]
            ),
            "customer_auth_live_in_actual_environment": actual["customer_auth_live"],
            "login_live_in_actual_environment": actual["login_live"],
            # Constants: invented route tables, no user, no session, no provider.
            "real_users_created": False,
            "real_sessions_created": False,
            "provider_contacted": False,
            "secrets_stored": False,
            "secret_value_emitted": False,
            "network_calls": False,
            "current_org_id_set": False,
            "cookies_set": False,
            "fabricated": False,
        }
    )


def route_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "real_users_created",
        "real_sessions_created",
        "provider_contacted",
        "secrets_stored",
        "secret_value_emitted",
        "network_calls",
        "current_org_id_set",
        "cookies_set",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"route_demo_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("route_cases_missing") or []:
        fails.append(f"route_case_not_covered:{case}")

    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"contract_disagreed_with_the_fixture:{case}")

    # No arrangement of routes may mint a session. Provider configuration,
    # callback validation, organization resolution and membership verification
    # are all required, and none of them is a route fact.
    if fixture.get("session_creating_case_count") != 0:
        fails.append("route_demo_created_a_session")

    # The actual environment is measured and must not be live.
    if fixture.get("customer_auth_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_auth_live")
    if fixture.get("login_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_login_live")

    for row in fixture.get("rows") or []:
        case = row.get("case")

        if row.get("any_session_created"):
            fails.append(f"demo_row_created_a_session:{case}")

        # A provider call is only ever permitted from the redirect flow, and
        # only where a provider is configured.
        if row.get("provider_call_allowed_count") and not row.get(
            "provider_configured"
        ):
            fails.append(f"demo_row_permitted_a_provider_call_unconfigured:{case}")
        if (row.get("provider_call_allowed_count") or 0) > 2:
            fails.append(f"demo_row_permitted_too_many_provider_calls:{case}")

        # A case with no routes must say why.
        if not row.get("routes_available_count") and not row.get("blocked_reasons"):
            fails.append(f"demo_row_without_routes_or_a_reason:{case}")

    return fails
