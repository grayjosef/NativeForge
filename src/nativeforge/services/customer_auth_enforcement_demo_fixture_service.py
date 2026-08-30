"""Customer auth enforcement demo fixtures (Gate 117H).

Ten labelled cases across the dependency, the redirect flow and the token
exchange boundary. No user, no session, no token, no secret, no provider call.

## The ten cases

```text
required_dependency_no_session      the 401 NativeForge now returns
optional_dependency_no_session      the 200 that says "you are nobody"
invalid_session_cookie              something was sent, and it did not check out
verified_principal_no_auth_live     a forged principal, and auth still not live
login_provider_missing              /login refuses, nothing to redirect to
login_provider_configured           an authorization URL becomes buildable
callback_missing_state              a callback with nothing to compare against
callback_invalid_pkce               a verifier that does not match its challenge
token_exchange_network_blocked      every condition met except the network
current_user_unauthenticated_401    the enforced route, refusing
```

## The pair that carries the gate

`verified_principal_no_auth_live` forges a principal all the way through: a
valid cookie, a resolved principal, an organization, a verified membership. The
dependency authorises it and returns 200 — and `customer_auth_live` is still
false, because it is measured from the real environment rather than from the
forged inputs.

That is enforcement and liveness pulling apart in a single row. A route can
admit somebody in a world where somebody exists, and nobody exists.

## `token_exchange_network_blocked` is the one that matters most

Provider configured, secret present, code returned, state validated, PKCE
validated — and `token_exchange_allowed` is false, because
`network_call_allowed` is false and nothing in this repository raises it.

Five security conditions satisfied and the exchange still does not happen. That
separation is deliberate: a flow that satisfied every security condition must
still not reach the internet by accident during a test run.

## Nothing is created

Every case is a dictionary handed to a contract function. No route is called,
no cookie is written, no token is requested, and the state and PKCE values in
the fixture set are the labelled `nf-demo-fixture-` ones that fail their own
entropy checks on purpose.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_dependency_contract_service import (
    evaluate_auth_dependency,
)
from nativeforge.services.customer_auth_redirect_flow_service import (
    build_redirect_flow_contract,
)
from nativeforge.services.customer_auth_state_pkce_service import (
    build_fixture_state_pkce,
    derive_code_challenge,
    validate_state_and_pkce,
)
from nativeforge.services.customer_auth_token_exchange_boundary_service import (
    evaluate_token_exchange_boundary,
)

SCHEMA_VERSION = "nf_customer_auth_enforcement_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# A state and verifier long enough to pass the entropy checks, so the "valid"
# cases are genuinely valid. Invented, labelled, and never a real credential -
# they are compared against each other and sent nowhere.
DEMO_STATE = "nf-demo-state-" + ("a" * 40)
DEMO_VERIFIER = "nf-demo-verifier-" + ("b" * 40)

# Gate 119D. An authorization URL needs an issuer, a client id and a redirect
# URI; `provider_configured: True` on its own no longer conjures one, which is
# exactly the defect Gate 119 went back and fixed. All three resolve nowhere.
DEMO_PROVIDER: dict[str, Any] = {
    "issuer": "https://nf-demo-fixture-issuer.invalid",
    "client_id": "nf-demo-fixture-client-id",
    "redirect_uri": "https://nf-demo-fixture-app.invalid/auth/callback",
}

REQUIRED_ENFORCEMENT_CASES: frozenset[str] = frozenset(
    {
        "required_dependency_no_session",
        "optional_dependency_no_session",
        "invalid_session_cookie",
        "verified_principal_no_auth_live",
        "login_provider_missing",
        "login_provider_configured",
        "callback_missing_state",
        "callback_invalid_pkce",
        "token_exchange_network_blocked",
        "current_user_unauthenticated_401",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_enforcement_cases() -> list[dict[str, Any]]:
    """Ten labelled cases. None creates a session and none calls a provider."""
    return [
        {
            "case": "required_dependency_no_session",
            "fixture_label": FIXTURE_LABEL,
            "kind": "dependency",
            "why": "the 401 NativeForge now returns, and never did before",
            "expect_http_status": 401,
            "expect_authorized": False,
            "request": {"dependency_mode": "required"},
        },
        {
            "case": "optional_dependency_no_session",
            "fixture_label": FIXTURE_LABEL,
            "kind": "dependency",
            "why": (
                "the 200 that says you are nobody. A caller asking whether they "
                "have a session is told no rather than refused for not having one"
            ),
            "expect_http_status": 200,
            "expect_authorized": True,
            "request": {"dependency_mode": "optional"},
        },
        {
            "case": "invalid_session_cookie",
            "fixture_label": FIXTURE_LABEL,
            "kind": "dependency",
            "why": (
                "something was sent and it did not check out, which is worse "
                "than nothing being sent and is named separately"
            ),
            "expect_http_status": 401,
            "expect_authorized": False,
            "request": {
                "dependency_mode": "required",
                "session_cookie_present": True,
                "session_cookie_valid": False,
            },
        },
        {
            "case": "verified_principal_no_auth_live",
            "fixture_label": FIXTURE_LABEL,
            "kind": "dependency",
            "why": (
                "a principal forged all the way through: valid cookie, resolved "
                "principal, organization, verified membership. The dependency "
                "admits it - and customer_auth_live is still false, because that "
                "is measured from the real environment"
            ),
            "expect_http_status": 200,
            "expect_authorized": True,
            "request": {
                "dependency_mode": "required",
                "session_cookie_present": True,
                "session_cookie_valid": True,
                "principal_resolved": True,
                "organization_id_resolved": True,
                "membership_verified": True,
            },
        },
        {
            "case": "current_user_unauthenticated_401",
            "fixture_label": FIXTURE_LABEL,
            "kind": "dependency",
            "why": (
                "the enforced route, refusing. Same shape as the first case and "
                "kept separate because it is the one attached to the security "
                "scheme"
            ),
            "expect_http_status": 401,
            "expect_authorized": False,
            "request": {
                "dependency_mode": "required",
                "session_cookie_present": True,
                "session_cookie_valid": False,
            },
        },
        {
            "case": "login_provider_missing",
            "fixture_label": FIXTURE_LABEL,
            "kind": "flow",
            "why": "no provider, so no authorization URL and nothing to redirect to",
            "expect_authorization_url": False,
            "expect_session_allowed": False,
            "request": {"provider_configured": False},
        },
        {
            "case": "login_provider_configured",
            "fixture_label": FIXTURE_LABEL,
            "kind": "flow",
            "why": (
                "an authorization URL becomes buildable. Building one is local "
                "work; the browser would visit it, not NativeForge"
            ),
            "expect_authorization_url": True,
            "expect_session_allowed": False,
            "request": {"provider_configured": True, **DEMO_PROVIDER},
        },
        {
            "case": "callback_missing_state",
            "fixture_label": FIXTURE_LABEL,
            "kind": "flow",
            "why": "a callback with nothing to compare its state against",
            "expect_authorization_url": True,
            "expect_session_allowed": False,
            "request": {
                **DEMO_PROVIDER,
                "provider_configured": True,
                "secret_present": True,
                "callback_code_present": True,
                "state_validation": validate_state_and_pkce(
                    expected_state=None,
                    returned_state=DEMO_STATE,
                    code_verifier=DEMO_VERIFIER,
                    expected_code_challenge=derive_code_challenge(DEMO_VERIFIER),
                ),
            },
        },
        {
            "case": "callback_invalid_pkce",
            "fixture_label": FIXTURE_LABEL,
            "kind": "flow",
            "why": "a verifier that does not derive the challenge that was sent",
            "expect_authorization_url": True,
            "expect_session_allowed": False,
            "request": {
                **DEMO_PROVIDER,
                "provider_configured": True,
                "secret_present": True,
                "callback_code_present": True,
                "state_validation": validate_state_and_pkce(
                    expected_state=DEMO_STATE,
                    returned_state=DEMO_STATE,
                    code_verifier=DEMO_VERIFIER,
                    expected_code_challenge=derive_code_challenge(
                        DEMO_VERIFIER + "-different"
                    ),
                ),
            },
        },
        {
            "case": "token_exchange_network_blocked",
            "fixture_label": FIXTURE_LABEL,
            "kind": "flow",
            "why": (
                "every security condition satisfied and the exchange still does "
                "not happen, because network_call_allowed is false and nothing "
                "in this repository raises it"
            ),
            "expect_authorization_url": True,
            "expect_session_allowed": False,
            "request": {
                **DEMO_PROVIDER,
                "provider_configured": True,
                "secret_present": True,
                "callback_code_present": True,
                "callback_validation_passed": True,
                "organization_id_resolved": True,
                "membership_verified": True,
                "state_validation": validate_state_and_pkce(
                    expected_state=DEMO_STATE,
                    returned_state=DEMO_STATE,
                    code_verifier=DEMO_VERIFIER,
                    expected_code_challenge=derive_code_challenge(DEMO_VERIFIER),
                ),
            },
        },
    ]


def measure_enforcement_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_enforcement_demo_fixture_set() -> dict[str, Any]:
    """The ten cases, each run through the contract that owns it."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    cases = build_demo_enforcement_cases()
    covered = measure_enforcement_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        if case["kind"] == "dependency":
            result = evaluate_auth_dependency(**case["request"])
            rows.append(
                {
                    "case": case["case"],
                    "fixture_label": FIXTURE_LABEL,
                    "kind": "dependency",
                    "dependency_mode": result["dependency_mode"],
                    "http_status": result["http_status"],
                    "authorized": result["authorized"],
                    "authenticated": result["authenticated"],
                    "sets_rls_context": result["sets_rls_context"],
                    "customer_auth_live": result["customer_auth_live"],
                    "session_created": False,
                    "provider_contacted": False,
                    "blocked_reasons": result["blocked_reasons"],
                    "agrees_with_expectation": (
                        result["http_status"] == case["expect_http_status"]
                        and bool(result["authorized"])
                        is bool(case["expect_authorized"])
                    ),
                }
            )
        else:
            result = build_redirect_flow_contract(**case["request"])
            rows.append(
                {
                    "case": case["case"],
                    "fixture_label": FIXTURE_LABEL,
                    "kind": "flow",
                    "authorization_url_available": result[
                        "authorization_url_available"
                    ],
                    "state_validated": result["state_validated"],
                    "pkce_validated": result["pkce_validated"],
                    "token_exchange_allowed": result["token_exchange_allowed"],
                    "token_exchange_performed": result["token_exchange_performed"],
                    "session_creation_allowed": result["session_creation_allowed"],
                    "session_created": result["session_created"],
                    "customer_auth_live": result["customer_auth_live"],
                    "provider_contacted": result["provider_contacted"],
                    "blocked_reasons": result["blocked_reasons"],
                    "agrees_with_expectation": (
                        bool(result["authorization_url_available"])
                        is bool(case["expect_authorization_url"])
                        and bool(result["session_creation_allowed"])
                        is bool(case["expect_session_allowed"])
                    ),
                }
            )

    # The boundary on its own, so the network condition is visible as its own row.
    boundary = evaluate_token_exchange_boundary(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        state_validated=True,
        pkce_validated=True,
    )

    actual = build_customer_auth_activation_gate()
    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "cases": cases,
            "case_count": len(cases),
            "rows": rows,
            "enforcement_cases_covered": sorted(covered),
            "enforcement_cases_missing": sorted(REQUIRED_ENFORCEMENT_CASES - covered),
            "cases_disagreeing_with_expectation": disagreements,
            "refused_401_count": sum(1 for r in rows if r.get("http_status") == 401),
            "session_created_count": sum(1 for r in rows if r["session_created"]),
            "rls_context_count": sum(1 for r in rows if r.get("sets_rls_context")),
            "token_exchange_allowed_count": sum(
                1 for r in rows if r.get("token_exchange_allowed")
            ),
            # The boundary, isolated: five conditions met, network off.
            "boundary_with_network_off": {
                "token_exchange_allowed": boundary["token_exchange_allowed"],
                "token_exchange_performed": boundary["token_exchange_performed"],
                "missing_conditions": boundary["missing_conditions"],
            },
            # The state and PKCE values that reach the artifact: labelled,
            # deliberately too short to pass their own entropy checks.
            "fixture_state_pkce": build_fixture_state_pkce(),
            # Measured from the real environment, never forged.
            "customer_auth_live_in_actual_environment": actual["customer_auth_live"],
            "login_live_in_actual_environment": actual["login_live"],
            # Constants.
            "real_users_created": False,
            "real_sessions_created": False,
            "provider_contacted": False,
            "network_calls": False,
            "secrets_stored": False,
            "secret_value_emitted": False,
            "token_value_emitted": False,
            "current_org_id_set": False,
            "cookies_set": False,
            "fabricated": False,
        }
    )


def enforcement_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "real_users_created",
        "real_sessions_created",
        "provider_contacted",
        "network_calls",
        "secrets_stored",
        "secret_value_emitted",
        "token_value_emitted",
        "current_org_id_set",
        "cookies_set",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"enforcement_demo_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("enforcement_cases_missing") or []:
        fails.append(f"enforcement_case_not_covered:{case}")

    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"contract_disagreed_with_the_fixture:{case}")

    # Nothing creates a session, in any arrangement.
    if fixture.get("session_created_count") != 0:
        fails.append("enforcement_demo_created_a_session")

    # No arrangement of fixture inputs may reach a real token exchange.
    if fixture.get("token_exchange_allowed_count"):
        fails.append("enforcement_demo_allowed_a_token_exchange")

    # At least one case must refuse with 401, or the enforcement this gate
    # added is undemonstrated.
    if not fixture.get("refused_401_count"):
        fails.append("enforcement_demo_demonstrates_no_refusal")

    # The actual environment is measured and must not be live.
    if fixture.get("customer_auth_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_auth_live")
    if fixture.get("login_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_login_live")

    # The state and PKCE values in the artifact are fixtures, and must be
    # incapable of passing for real ones.
    state_pkce = fixture.get("fixture_state_pkce") or {}
    if not state_pkce.get("is_fixture"):
        fails.append("artifact_state_pkce_is_not_labelled_a_fixture")
    if state_pkce.get("production_safe"):
        fails.append("artifact_state_pkce_reported_as_production_safe")

    # The boundary row must show the network condition doing the blocking.
    boundary = fixture.get("boundary_with_network_off") or {}
    if boundary.get("token_exchange_allowed"):
        fails.append("boundary_allowed_an_exchange_with_the_network_off")
    if boundary.get("token_exchange_performed"):
        fails.append("boundary_performed_an_exchange")
    if "network_call_allowed" not in (boundary.get("missing_conditions") or []):
        fails.append("boundary_did_not_name_the_network_condition")

    for row in fixture.get("rows") or []:
        case = row.get("case")

        if row.get("session_created"):
            fails.append(f"demo_row_created_a_session:{case}")
        if row.get("provider_contacted"):
            fails.append(f"demo_row_contacted_a_provider:{case}")

        # A 401 is a refusal, and a refusal names itself.
        if row.get("http_status") == 401 and not row.get("blocked_reasons"):
            fails.append(f"demo_row_refused_without_a_reason:{case}")

        # An authorised caller in a dependency row is not authenticated unless
        # the mode required it.
        if (
            row.get("kind") == "dependency"
            and row.get("sets_rls_context")
            and not row.get("authenticated")
        ):
            fails.append(f"demo_row_set_an_rls_context_unauthenticated:{case}")

    return fails
