"""Customer auth activation demo fixtures (Gate 115G).

Eight labelled cases walking the activation gate from nothing configured to
everything satisfied. No user is created, no session is opened, no provider is
contacted, and no secret appears anywhere.

## The eight cases

```text
all_gates_missing                the environment as it actually is
provider_configured_no_secret    config arrived, the secret did not
secret_present_jwks_unvalidated  everything set, nothing checked
callback_route_no_session        a route exists, enforcing nothing
org_claim_no_membership          resolved to an organization nobody belongs to
membership_no_role_mapping       a real member the provider says nothing about
all_gates_pass                   theoretical activation
dev_header_still_enabled         everything passes except the one posture gate
```

Seven refusals and one theoretical pass, and the pass is the important one:
without it every refusal is unfalsifiable, because a gate that only ever says no
is indistinguishable from a constant.

## The last two cases are the pair worth reading together

`all_gates_pass` and `dev_header_still_enabled` differ in exactly one input. In
the first, customer auth activates. In the second, `login_live` is still true -
a login flow could run - and `customer_auth_live` is false, because an
unauthenticated header can still set `app.current_org_id`.

That is the distinction Gate 112 recorded and Gate 115E measures: a login page
existing is not the same as authentication being the only way in.

## Theoretical is not actual

`all_gates_pass` forges its inputs. It shows what the gate *would* decide, and
it is labelled `demo_fixture` throughout. The fixture set reports
`customer_auth_live_in_actual_environment: false` alongside it, measured
separately from the real environment, and an invariant fails the set if that
value is ever true while the fixtures are being used as evidence.

## Secrets

No case carries a secret value. `secret_present` is a boolean in every fixture,
the forged preflight dictionaries contain booleans only, and the fixture set
scans its own serialised output for any configured environment value before
returning.
"""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.customer_auth_activation_gate_service import (
    OIDC_ENV_KEYS,
    REQUIRED_AUTH_GATES,
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_route_readiness_service import (
    build_route_readiness,
)

SCHEMA_VERSION = "nf_customer_auth_activation_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# A route table describing an application that has auth routes and declares a
# security scheme. Invented; NativeForge has no such routes today.
DEMO_SECURED_OPENAPI: dict[str, Any] = {
    "paths": {
        "/v1/auth/login": {"get": {}},
        "/v1/auth/logout": {"post": {}},
        "/v1/auth/callback": {"get": {}},
        "/v1/auth/session": {"get": {"security": [{"nf_session": []}]}},
        "/v1/auth/me": {"get": {"security": [{"nf_session": []}]}},
    },
    "components": {"securitySchemes": {"nf_session": {"type": "apiKey"}}},
}

# The same application without any security scheme: routes that exist and
# enforce nothing.
DEMO_UNSECURED_OPENAPI: dict[str, Any] = {
    "paths": {
        "/v1/auth/login": {"get": {}},
        "/v1/auth/logout": {"post": {}},
        "/v1/auth/callback": {"get": {}},
        "/v1/auth/session": {"get": {}},
        "/v1/auth/me": {"get": {}},
    },
    "components": {},
}

# Preflight shapes. Booleans only - never a value, never a length, never a hint.
PREFLIGHT_NOTHING: dict[str, Any] = {
    "validation_possible": False,
    "client_secret_present": False,
    "issuer_url_present": False,
    "audience_present": False,
    "jwks_reachable": None,
}
PREFLIGHT_NO_SECRET: dict[str, Any] = {
    "validation_possible": False,
    "client_secret_present": False,
    "issuer_url_present": True,
    "audience_present": True,
    "jwks_reachable": None,
}
PREFLIGHT_CONFIGURED: dict[str, Any] = {
    "validation_possible": True,
    "client_secret_present": True,
    "issuer_url_present": True,
    "audience_present": True,
    "jwks_reachable": True,
}
PREFLIGHT_CONFIGURED_UNCHECKED: dict[str, Any] = {
    **PREFLIGHT_CONFIGURED,
    "jwks_reachable": None,
}

VALIDATION_NOTHING: dict[str, Any] = {
    "provider_validated": False,
    "callback_session_validated": False,
    "invite_binding_passed": False,
    "org_binding_passed": False,
    "role_mapping_passed": False,
}
VALIDATION_ALL: dict[str, Any] = {
    "provider_validated": True,
    "callback_session_validated": True,
    "invite_binding_passed": True,
    "org_binding_passed": True,
    "role_mapping_passed": True,
}

REQUIRED_ACTIVATION_CASES: frozenset[str] = frozenset(
    {
        "all_gates_missing",
        "provider_configured_no_secret",
        "secret_present_jwks_unvalidated",
        "callback_route_no_session",
        "org_claim_no_membership",
        "membership_no_role_mapping",
        "all_gates_pass",
        "dev_header_still_enabled",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_activation_cases() -> list[dict[str, Any]]:
    """Eight labelled cases. Seven refusals and one theoretical activation."""
    secured = build_route_readiness(
        openapi=DEMO_SECURED_OPENAPI, cloudflare_access_in_front=False
    )
    unsecured = build_route_readiness(
        openapi=DEMO_UNSECURED_OPENAPI, cloudflare_access_in_front=False
    )
    no_routes = build_route_readiness(
        openapi={"paths": {}, "components": {}}, cloudflare_access_in_front=False
    )

    return [
        {
            "case": "all_gates_missing",
            "fixture_label": FIXTURE_LABEL,
            "why": "the environment as it actually is: nothing configured",
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_NOTHING,
                "validation": VALIDATION_NOTHING,
                "route_readiness": no_routes,
                "dev_header_disabled_for_production": False,
                "owner_approval": False,
            },
        },
        {
            "case": "provider_configured_no_secret",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "issuer and audience arrived and the client secret did not - "
                "presence is a boolean, and it is false"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_NO_SECRET,
                "validation": VALIDATION_NOTHING,
                "route_readiness": no_routes,
                "dev_header_disabled_for_production": False,
                "owner_approval": False,
            },
        },
        {
            "case": "secret_present_jwks_unvalidated",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "everything configured and nothing checked. Unvalidated is not "
                "the same fact as validated-and-failed, and the gate says which"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED_UNCHECKED,
                "validation": VALIDATION_NOTHING,
                "route_readiness": no_routes,
                "dev_header_disabled_for_production": False,
                "owner_approval": False,
            },
        },
        {
            "case": "callback_route_no_session",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "five auth routes exist and declare no security scheme. Route "
                "existence is not enforcement, and this is the case that says so"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED,
                "validation": VALIDATION_NOTHING,
                "route_readiness": unsecured,
                "dev_header_disabled_for_production": False,
                "owner_approval": False,
            },
        },
        {
            "case": "org_claim_no_membership",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a claim resolved to an organization_id and no membership "
                "record backs it. Gate 112's rule, at the activation layer"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED,
                "validation": {
                    **VALIDATION_ALL,
                    "org_binding_passed": False,
                    "invite_binding_passed": False,
                },
                "route_readiness": secured,
                "dev_header_disabled_for_production": True,
                "owner_approval": True,
            },
        },
        {
            "case": "membership_no_role_mapping",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a verified member whose provider roles map to nothing. Unknown "
                "grants nothing, so activation waits"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": False,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED,
                "validation": {**VALIDATION_ALL, "role_mapping_passed": False},
                "route_readiness": secured,
                "dev_header_disabled_for_production": True,
                "owner_approval": True,
            },
        },
        {
            "case": "all_gates_pass",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "theoretical activation. Every refusal above is unfalsifiable "
                "without it - a gate that only says no is a constant"
            ),
            "expect_customer_auth_live": True,
            "expect_login_live": True,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED,
                "validation": VALIDATION_ALL,
                "route_readiness": secured,
                "dev_header_disabled_for_production": True,
                "owner_approval": True,
            },
        },
        {
            "case": "dev_header_still_enabled",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "identical to all_gates_pass but for one input. A login flow "
                "could run; customer auth is not live while an unauthenticated "
                "header can still set app.current_org_id"
            ),
            "expect_customer_auth_live": False,
            "expect_login_live": True,
            "request": {
                "preflight": PREFLIGHT_CONFIGURED,
                "validation": VALIDATION_ALL,
                "route_readiness": secured,
                "dev_header_disabled_for_production": False,
                "owner_approval": True,
            },
        },
    ]


def measure_activation_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_activation_demo_fixture_set() -> dict[str, Any]:
    """The eight cases, each run through the activation gate."""
    cases = build_demo_activation_cases()
    covered = measure_activation_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        gate = build_customer_auth_activation_gate(**case["request"])
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "expect_customer_auth_live": case["expect_customer_auth_live"],
                "expect_login_live": case["expect_login_live"],
                "customer_auth_live": gate["customer_auth_live"],
                "login_live": gate["login_live"],
                "activation_allowed": gate["activation_allowed"],
                "provider_configured": gate["provider_configured"],
                "secret_present": gate["secret_present"],
                "issuer_jwks_validated": gate["issuer_jwks_validated"],
                "callback_route_available": gate["callback_route_available"],
                "callback_session_validated": gate["callback_session_validated"],
                "org_binding_passed": gate["org_binding_passed"],
                "role_mapping_passed": gate["role_mapping_passed"],
                "dev_header_disabled_for_production": gate[
                    "dev_header_disabled_for_production"
                ],
                "owner_approval_present": gate["owner_approval_present"],
                "secret_value_emitted": gate["secret_value_emitted"],
                "missing_gate_count": len(gate["missing_auth_gates"]),
                "blocked_reasons": gate["blocked_reasons"],
                "agrees_with_expectation": (
                    bool(gate["customer_auth_live"])
                    is bool(case["expect_customer_auth_live"])
                    and bool(gate["login_live"]) is bool(case["expect_login_live"])
                ),
            }
        )

    # Measured separately from the real environment, and reported beside the
    # theoretical pass so nobody quotes one as the other.
    actual = build_customer_auth_activation_gate()
    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "cases": cases,
            "case_count": len(cases),
            "rows": rows,
            "activation_cases_covered": sorted(covered),
            "activation_cases_missing": sorted(REQUIRED_ACTIVATION_CASES - covered),
            "cases_disagreeing_with_expectation": disagreements,
            "theoretical_activation_count": sum(
                1 for r in rows if r["customer_auth_live"]
            ),
            "refused_count": sum(1 for r in rows if not r["customer_auth_live"]),
            # The actual environment, measured, never forged.
            "customer_auth_live_in_actual_environment": actual["customer_auth_live"],
            "login_live_in_actual_environment": actual["login_live"],
            "actual_missing_gate_count": len(actual["missing_auth_gates"]),
            "required_auth_gate_count": len(REQUIRED_AUTH_GATES),
            # Constants: invented config, no user, no session, no provider.
            "real_users_created": False,
            "real_sessions_created": False,
            "identity_provider_contacted": False,
            "secrets_stored": False,
            "secret_value_emitted": False,
            "network_calls": False,
            "current_org_id_set": False,
            "fabricated": False,
        }
    )

    # A fixture set is a committed artifact. Scan it for any configured
    # environment value before it goes anywhere.
    blob = json.dumps(result)
    for key in OIDC_ENV_KEYS:
        raw = os.environ.get(key) or ""
        if raw and len(raw) >= 8 and raw in blob:
            result["secret_value_emitted"] = True
            break

    return result


def activation_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "real_users_created",
        "real_sessions_created",
        "identity_provider_contacted",
        "secrets_stored",
        "secret_value_emitted",
        "network_calls",
        "current_org_id_set",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"activation_demo_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("activation_cases_missing") or []:
        fails.append(f"activation_case_not_covered:{case}")

    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"gate_disagreed_with_the_fixture:{case}")

    # The actual environment is measured and must not be live. A fixture set
    # showing a theoretical pass beside a live actual environment would be
    # presenting forged inputs as evidence about the real one.
    if fixture.get("customer_auth_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_auth_live")
    if fixture.get("login_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_login_live")

    # Exactly one case may activate. Zero makes every refusal unfalsifiable;
    # more than one means a refusal stopped refusing.
    if fixture.get("theoretical_activation_count") != 1:
        fails.append("activation_demo_theoretical_pass_count_is_not_one")

    for row in fixture.get("rows") or []:
        case = row.get("case")

        # A refusal must name itself.
        if not row.get("customer_auth_live") and not row.get("blocked_reasons"):
            fails.append(f"demo_row_refused_without_a_reason:{case}")

        # No fixture may leak a secret value.
        if row.get("secret_value_emitted"):
            fails.append(f"demo_row_emitted_a_secret_value:{case}")

        # Activation requires the dev header gone, in every case.
        if row.get("customer_auth_live") and not row.get(
            "dev_header_disabled_for_production"
        ):
            fails.append(f"demo_row_activated_with_the_dev_header_enabled:{case}")

        # And owner approval, in every case.
        if row.get("customer_auth_live") and not row.get("owner_approval_present"):
            fails.append(f"demo_row_activated_without_owner_approval:{case}")

        # An activated row has no missing gates.
        if row.get("customer_auth_live") and row.get("missing_gate_count"):
            fails.append(f"demo_row_activated_with_missing_gates:{case}")

    return fails
