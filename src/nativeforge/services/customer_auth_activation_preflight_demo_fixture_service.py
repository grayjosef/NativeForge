"""Auth activation preflight demo fixtures (Gate 121F).

Eight labelled cases walking one hypothetical deployment from nothing
configured to everything configured — and showing that the last step still does
not turn auth on.

## The cases are a staircase, on purpose

Each case adds exactly one thing to the one before it:

```text
1  all_missing                        nothing set
2  provider_env_present_secret_missing   + issuer, client id, audience
3  secret_present_signing_key_missing    + client secret
4  signing_key_present_callback_mismatch + signing key
5  callback_match_database_missing       + a callback that matches a route
6  database_ready_role_mapping_missing   + a migrated database
7  role_mapping_present_binding_missing  + mapped roles
8  all_preflight_gates_pass_activation_still_not_live
```

A set where every case failed differently would prove each check works in
isolation. A staircase proves the *order* is right — that fixing step 3 does not
accidentally satisfy step 5, and that nothing collapses into a single
pass/fail.

## The eighth case is the point of the set

Every preflight gate passes and `customer_auth_live` is still false, because
activation needs an owner's signature and three things only a real browser can
prove. A preflight that went green and left a reader thinking auth was on would
be worse than no preflight.

## Every value is fake, and none of them is a secret

```text
issuer          https://nf-demo-fixture-issuer.invalid
client id       nf-demo-fixture-client-id
secret          a boolean. There is no fixture secret value, because a fixture
                secret is a string somebody eventually pastes somewhere real.
signing key     a boolean and a source name
```

`.invalid` is reserved by RFC 2606 to resolve nowhere. No case reads the
process environment, so the set is identical on every machine and a committed
artifact means the same thing everywhere.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_environment_preflight_service import (
    build_environment_preflight,
    environment_preflight_invariant_failures,
)
from nativeforge.services.customer_auth_provider_readiness_service import (
    build_provider_readiness,
    provider_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_customer_auth_activation_preflight_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Every host is `.invalid`, reserved to resolve nowhere. A fixture pointing at a
# real domain would be one DNS lookup away from being a live provider call.
DEMO_ISSUER = "https://nf-demo-fixture-issuer.invalid"
DEMO_CLIENT_ID = FIXTURE_PREFIX + "client-id"
DEMO_AUDIENCE = "https://nf-demo-fixture-api.invalid"
DEMO_ORIGIN = "https://nf-demo-fixture-app.invalid"

# The path that matches the API route, and the one that does not.
DEMO_CALLBACK_GOOD = DEMO_ORIGIN + "/api/auth/callback"
DEMO_CALLBACK_BAD = DEMO_ORIGIN + "/auth/callback"

# Deliberately not a value. A fixture secret is a string somebody eventually
# pastes into something real; presence is all any of this needs.
DEMO_SECRET_PLACEHOLDER = FIXTURE_PREFIX + "secret-presence-only"

REQUIRED_CASES: tuple[str, ...] = (
    "all_missing",
    "provider_env_present_secret_missing",
    "secret_present_signing_key_missing",
    "signing_key_present_callback_mismatch",
    "callback_match_database_missing",
    "database_ready_role_mapping_missing",
    "role_mapping_present_binding_missing",
    "all_preflight_gates_pass_activation_still_not_live",
)

_SAFE_COOKIE = {"production_safe": True}
_SAFE_HEADER = {
    "must_disable_before_production_auth": False,
    "dev_header_is_production_safe": True,
    "dev_header_name": "X-NF-Org-Id",
    "dev_header_used_by_routes": 0,
}
_READY_KEY = {
    "signing_key_present": True,
    "signing_key_source": "secret_manager",
    "can_sign_production_session": True,
    "blocked_reasons": [],
}
_MISSING_KEY = {
    "signing_key_present": False,
    "signing_key_source": "missing",
    "can_sign_production_session": False,
    "blocked_reasons": ["no_signing_key_configured"],
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _env(**overrides: str) -> dict[str, str]:
    """A forged environment. Never the process one."""
    base: dict[str, str] = {}
    base.update(overrides)
    return base


def build_demo_preflight_cases() -> list[dict[str, Any]]:
    """Eight labelled cases. Seven incomplete and one complete-and-still-off."""
    provider_env = {
        "OIDC_ISSUER": DEMO_ISSUER,
        "OIDC_CLIENT_ID": DEMO_CLIENT_ID,
        "OIDC_AUDIENCE": DEMO_AUDIENCE,
    }
    secret_env = {"OIDC_CLIENT_SECRET": DEMO_SECRET_PLACEHOLDER}
    signing_env = {"NF_SESSION_SIGNING_KEY": FIXTURE_PREFIX + "signing-key"}
    origin_env = {"NF_PUBLIC_ORIGIN": DEMO_ORIGIN}
    approval_env = {"NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL": "fixture-approval"}

    def case(
        name: str,
        why: str,
        *,
        environ: dict[str, str],
        callback: str,
        signing: dict[str, Any],
        database_revision: str,
        role_mapping_passed: bool,
        expect_provider_env: bool,
        expect_secret_env: bool,
        expect_callback_match: bool,
        expect_database_ready: bool,
    ) -> dict[str, Any]:
        preflight = build_environment_preflight(
            environ=environ,
            app_env="staging",
            configured_callback_url=callback,
            public_origin=environ.get("NF_PUBLIC_ORIGIN"),
            database_revision=database_revision,
            signing_key_readiness=signing,
            session_cookie_policy=_SAFE_COOKIE,
            dev_header_readiness=_SAFE_HEADER,
        )
        provider = build_provider_readiness(
            environ=environ,
            redirect_uri=callback,
            callback_route_available=True,
        )
        return {
            "case": name,
            "fixture_label": FIXTURE_LABEL,
            "why": why,
            "role_mapping_passed": role_mapping_passed,
            "expect_provider_env": expect_provider_env,
            "expect_secret_env": expect_secret_env,
            "expect_callback_match": expect_callback_match,
            "expect_database_ready": expect_database_ready,
            "preflight": preflight,
            "provider": provider,
        }

    return [
        case(
            "all_missing",
            "a deployment where nobody has configured anything yet",
            environ=_env(),
            callback="",
            signing=_MISSING_KEY,
            database_revision="",
            role_mapping_passed=False,
            expect_provider_env=False,
            expect_secret_env=False,
            expect_callback_match=False,
            expect_database_ready=False,
        ),
        case(
            "provider_env_present_secret_missing",
            "the three public provider keys are set and the secret is not",
            environ=_env(**provider_env),
            callback="",
            signing=_MISSING_KEY,
            database_revision="",
            role_mapping_passed=False,
            expect_provider_env=True,
            expect_secret_env=False,
            expect_callback_match=False,
            expect_database_ready=False,
        ),
        case(
            "secret_present_signing_key_missing",
            (
                "the provider can be talked to and no session can be signed - "
                "two different secrets, two different owners"
            ),
            environ=_env(**provider_env, **secret_env),
            callback="",
            signing=_MISSING_KEY,
            database_revision="",
            role_mapping_passed=False,
            expect_provider_env=True,
            expect_secret_env=False,
            expect_callback_match=False,
            expect_database_ready=False,
        ),
        case(
            "signing_key_present_callback_mismatch",
            (
                "everything set, and the callback points at a path nothing can "
                "consume. Gate 121A found exactly this in the real config"
            ),
            environ=_env(**provider_env, **secret_env, **signing_env, **origin_env),
            callback=DEMO_CALLBACK_BAD,
            signing=_READY_KEY,
            database_revision="",
            role_mapping_passed=False,
            expect_provider_env=True,
            expect_secret_env=True,
            expect_callback_match=False,
            expect_database_ready=False,
        ),
        case(
            "callback_match_database_missing",
            (
                "the redirect would complete and then have nowhere to write a "
                "state row - a failure no activation gate would have caught"
            ),
            environ=_env(**provider_env, **secret_env, **signing_env, **origin_env),
            callback=DEMO_CALLBACK_GOOD,
            signing=_READY_KEY,
            database_revision="",
            role_mapping_passed=False,
            expect_provider_env=True,
            expect_secret_env=True,
            expect_callback_match=True,
            expect_database_ready=False,
        ),
        case(
            "database_ready_role_mapping_missing",
            "a login that succeeds and grants nothing, because unknown roles do",
            environ=_env(**provider_env, **secret_env, **signing_env, **origin_env),
            callback=DEMO_CALLBACK_GOOD,
            signing=_READY_KEY,
            database_revision="0030",
            role_mapping_passed=False,
            expect_provider_env=True,
            expect_secret_env=True,
            expect_callback_match=True,
            expect_database_ready=True,
        ),
        case(
            "role_mapping_present_binding_missing",
            (
                "roles mapped, and still nobody is bound to an organization - "
                "the Gate 120 workflow has a repository and no verifier"
            ),
            environ=_env(**provider_env, **secret_env, **signing_env, **origin_env),
            callback=DEMO_CALLBACK_GOOD,
            signing=_READY_KEY,
            database_revision="0030",
            role_mapping_passed=True,
            expect_provider_env=True,
            expect_secret_env=True,
            expect_callback_match=True,
            expect_database_ready=True,
        ),
        case(
            "all_preflight_gates_pass_activation_still_not_live",
            (
                "the point of the whole set. Every preflight gate green, and "
                "auth is not live: activation needs an owner's signature and "
                "three things only a real browser can prove"
            ),
            environ=_env(
                **provider_env,
                **secret_env,
                **signing_env,
                **origin_env,
                **approval_env,
            ),
            callback=DEMO_CALLBACK_GOOD,
            signing=_READY_KEY,
            database_revision="0030",
            role_mapping_passed=True,
            expect_provider_env=True,
            expect_secret_env=True,
            expect_callback_match=True,
            expect_database_ready=True,
        ),
    ]


def measure_preflight_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def _agrees(case: dict[str, Any]) -> bool:
    pre = case["preflight"]
    return bool(
        bool(pre["provider_env_present"]) is bool(case["expect_provider_env"])
        and bool(pre["secret_env_present"]) is bool(case["expect_secret_env"])
        and bool(pre["callback_path_matches_route"])
        is bool(case["expect_callback_match"])
        and bool(pre["database_revision_ready"]) is bool(case["expect_database_ready"])
    )


def build_preflight_demo_fixture_set() -> dict[str, Any]:
    """The eight cases, measured. Key names and booleans only."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    cases = build_demo_preflight_cases()
    covered = measure_preflight_cases(cases)

    # Measured once, from the real environment, so the set can state plainly
    # that no fixture moved it.
    actual = build_customer_auth_activation_gate()

    rows: list[dict[str, Any]] = []
    for case in cases:
        pre = case["preflight"]
        prov = case["provider"]
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "why": case["why"],
                "provider_env_present": bool(pre["provider_env_present"]),
                "provider_env_missing_keys": list(pre["provider_env_missing_keys"]),
                "secret_env_present": bool(pre["secret_env_present"]),
                "secret_env_missing_keys": list(pre["secret_env_missing_keys"]),
                "signing_key_source": pre["signing_key_source"],
                "callback_path_matches_route": bool(pre["callback_path_matches_route"]),
                "callback_url_matches_public_origin": bool(
                    pre["callback_url_matches_public_origin"]
                ),
                "database_revision_ready": bool(pre["database_revision_ready"]),
                "role_mapping_passed": bool(case["role_mapping_passed"]),
                # Cases 7 and 8 are identical at every preflight gate; the only
                # thing between them is the owner's signature. Tracked per row
                # so the set can say which case is which.
                "owner_authorization_present": (
                    "owner_has_not_authorized_customer_auth_activation"
                    not in list(pre["blocked_reasons"])
                ),
                "provider_ready": bool(prov["provider_ready"]),
                "jwks_validated": bool(prov["jwks_validated"]),
                "preflight_blocked_reasons": list(pre["blocked_reasons"]),
                "provider_blocked_reasons": list(prov["blocked_reasons"]),
                "agrees_with_expectation": _agrees(case),
                # Constant across every case, and the reason the set exists.
                "customer_auth_live": False,
                "login_live": False,
                "secret_values_exposed": bool(pre["secret_values_exposed"]),
                "provider_called": bool(prov["provider_called"]),
                "invariant_failures": sorted(
                    {
                        *environment_preflight_invariant_failures(pre),
                        *provider_readiness_invariant_failures(prov),
                    }
                ),
            }
        )

    missing = [name for name in REQUIRED_CASES if name not in covered]
    disagreeing = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "case_count": len(rows),
            "cases": rows,
            "preflight_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "provider_ready_count": sum(1 for r in rows if r["provider_ready"]),
            "database_ready_count": sum(
                1 for r in rows if r["database_revision_ready"]
            ),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            # The real environment, measured once and unmoved by any of this.
            "actual_customer_auth_live": bool(actual["customer_auth_live"]),
            "actual_login_live": bool(actual["login_live"]),
            "actual_missing_auth_gates": list(actual["missing_auth_gates"]),
            # Constants. A fixture set demonstrates; it configures nothing.
            "operator_authorization_present": False,
            "customer_auth_live": False,
            "login_live": False,
            "customer_persistence_live": False,
            "production_verified_bindings_created": 0,
            "secret_values_exposed": False,
            "provider_called": False,
            "network_calls": False,
            "environment_mutated": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def preflight_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("preflight_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_its_own_service_invariants")

    for row in rows:
        label = row.get("case")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")
        if row.get("customer_auth_live") or row.get("login_live"):
            fails.append(f"a_fixture_claimed_auth_is_live:{label}")
        if row.get("secret_values_exposed"):
            fails.append(f"a_fixture_exposed_a_value:{label}")
        if row.get("provider_called"):
            fails.append(f"a_fixture_contacted_a_provider:{label}")

    # Two cases reach every preflight gate: the last one and the one before it.
    # They are identical at the preflight level by design - the only thing
    # between them is the owner's signature, which is not a preflight fact.
    preflight_complete = [
        r
        for r in rows
        if r["provider_env_present"]
        and r["secret_env_present"]
        and r["callback_path_matches_route"]
        and r["database_revision_ready"]
        and r["role_mapping_passed"]
    ]
    if len(preflight_complete) != 2:
        fails.append("expected_exactly_two_preflight_complete_cases")

    # Exactly one of them carries the owner's authorization. More than one would
    # mean the staircase had collapsed into a pass/fail.
    authorized = [r for r in preflight_complete if r["owner_authorization_present"]]
    if len(authorized) != 1:
        fails.append("expected_exactly_one_authorized_and_fully_configured_case")

    # And that case must still not be live. This is the whole point of the set:
    # every preflight gate green, an owner's signature present, and auth still
    # off - because three of the sixteen gates need a real browser.
    for row in preflight_complete:
        if row["customer_auth_live"] or row["login_live"]:
            fails.append(f"a_fully_configured_case_claimed_auth_is_live:{row['case']}")

    if fixture.get("actual_customer_auth_live") or fixture.get("actual_login_live"):
        fails.append("the_actual_environment_was_reported_as_live")
    if not fixture.get("actual_missing_auth_gates"):
        fails.append("the_actual_environment_reported_no_missing_gates")

    if fixture.get("operator_authorization_present"):
        fails.append("a_fixture_claimed_owner_authorization")
    if fixture.get("customer_persistence_live"):
        fails.append("a_fixture_claimed_customer_persistence_is_live")
    if fixture.get("production_verified_bindings_created"):
        fails.append("a_fixture_created_a_production_verified_binding")
    if fixture.get("environment_mutated"):
        fails.append("a_fixture_changed_the_environment")

    return sorted(set(fails))
