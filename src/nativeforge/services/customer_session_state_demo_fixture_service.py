"""Customer session and state demo fixtures (Gate 118G).

Eleven labelled cases across the session verifier and the redirect state store.
No production session, no user, no real secret, and no verifier value in any
artifact.

## The eleven cases

```text
session
  missing_cookie                   nothing was sent
  malformed_cookie                 something was, and it is not a session
  expired_session                  genuine, signed, and past its expiry
  invalid_signature                well-formed, signed with a different key
  profile_shaped_organization_id   genuinely signed, wrong identity space
  valid_session_without_membership  everything checks out and nobody vouches
  valid_session_with_membership     the one that authorizes

state
  missing_state                    nothing stored under that id
  expired_state                    stored, and the redirect window closed
  consumed_state_replay            used once, presented again
  valid_state_and_pkce             the one that consumes
```

## The two rows that carry the gate

`profile_shaped_organization_id` is a session whose **signature is genuine** and
which is refused anyway. That is Gates 110-113 restated at the session layer: a
profile id is a real value from a real column in the wrong identity space, and
signing it does not make it an RLS authority.

`valid_session_with_membership` reaches `rls_context_allowed: True` — and
`customer_auth_live` is still false, measured from the real environment rather
than from the fixture. A session can be entirely valid under a fixture key while
nobody in the world can authenticate.

## Fixture sessions are not production sessions

Every session here is signed with `FIXTURE_SIGNING_KEY`, an obviously-fake
committed constant. `production_session` is false for all of them and an
invariant refuses any that claims otherwise.

Timestamps are pinned so an artifact does not churn, and `now` is pinned inside
each session's window so "valid" cases are valid rather than expired the moment
the wall clock passes them.

## Nothing is created

No cookie is set, no row is written, no provider is contacted. The state store
runs in `in_memory_test` scope, which is a dict that dies with the process —
`production_store` is false for it and an invariant enforces that.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_redirect_state_store_service import (
    InMemoryRedirectStateStore,
    consume_state,
    store_state,
)
from nativeforge.services.customer_session_format_service import (
    FIXTURE_SIGNING_KEY,
    build_fixture_session,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)

SCHEMA_VERSION = "nf_customer_session_state_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# Pinned so artifacts do not churn. `now` sits inside the session window.
FIXTURE_ISSUED_AT = 1_700_000_000
FIXTURE_NOW = FIXTURE_ISSUED_AT + 60
FIXTURE_LIFETIME = 8 * 60 * 60

FIXTURE_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000118"
FIXTURE_PROFILE_ID = "nf-demo-org-profile-118"

# State fixture values. Long enough to be compared meaningfully, prefixed so
# they are recognisable, and never returned by any result.
FIXTURE_STATE_ID = "nf-demo-fixture-state-118"
FIXTURE_STATE_VALUE = "nf-demo-fixture-state-value-" + ("a" * 40)
FIXTURE_VERIFIER = "nf-demo-fixture-verifier-" + ("b" * 40)
FIXTURE_CHALLENGE = "nf-demo-fixture-challenge-" + ("c" * 40)

REQUIRED_SESSION_STATE_CASES: frozenset[str] = frozenset(
    {
        "missing_cookie",
        "malformed_cookie",
        "expired_session",
        "invalid_signature",
        "profile_shaped_organization_id",
        "valid_session_without_membership",
        "valid_session_with_membership",
        "missing_state",
        "expired_state",
        "consumed_state_replay",
        "valid_state_and_pkce",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _fixture_cookie(**overrides: Any) -> str:
    kwargs: dict[str, Any] = {
        "organization_id": FIXTURE_ORGANIZATION_ID,
        "issued_at": FIXTURE_ISSUED_AT,
        "lifetime_seconds": FIXTURE_LIFETIME,
        "now": FIXTURE_NOW,
    }
    kwargs.update(overrides)
    return build_fixture_session(**kwargs)["session_cookie_value"]


def build_demo_session_cases() -> list[dict[str, Any]]:
    """Seven session cases. Two authorize; five are refused, each for a reason."""
    good = _fixture_cookie()
    profile = _fixture_cookie(organization_id=FIXTURE_PROFILE_ID)

    return [
        {
            "case": "missing_cookie",
            "fixture_label": FIXTURE_LABEL,
            "why": "nothing was sent",
            "expect_valid": False,
            "expect_rls": False,
            "request": {"cookie_value": None},
        },
        {
            "case": "malformed_cookie",
            "fixture_label": FIXTURE_LABEL,
            "why": "something was sent and it is not a session",
            "expect_valid": False,
            "expect_rls": False,
            "request": {"cookie_value": "not-a-session-at-all"},
        },
        {
            "case": "expired_session",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "genuine and signed, and past the expiry it carries inside "
                "itself. A cookie Max-Age is a request to the browser; this is "
                "the check the server makes"
            ),
            "expect_valid": False,
            "expect_rls": False,
            "request": {
                "cookie_value": good,
                "now": FIXTURE_ISSUED_AT + FIXTURE_LIFETIME + 60,
            },
        },
        {
            "case": "invalid_signature",
            "fixture_label": FIXTURE_LABEL,
            "why": "well-formed, signed with a key we do not hold",
            "expect_valid": False,
            "expect_rls": False,
            "request": {
                "cookie_value": good,
                "signing_key": "a-different-fixture-key-entirely",
            },
        },
        {
            "case": "profile_shaped_organization_id",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the signature is genuine and the session is refused anyway. "
                "Gates 110-113 at the session layer: a profile id is a real "
                "value in the wrong identity space, and signing it does not "
                "make it an RLS authority"
            ),
            "expect_valid": False,
            "expect_rls": False,
            "request": {"cookie_value": profile, "membership_verified": True},
        },
        {
            "case": "valid_session_without_membership",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "everything checks out and nobody vouches for the organization. "
                "A valid session is not a membership - memberships get revoked "
                "and a session outlives the revocation until it expires"
            ),
            "expect_valid": True,
            "expect_rls": False,
            "request": {"cookie_value": good, "membership_verified": False},
        },
        {
            "case": "valid_session_with_membership",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the one that authorizes - and customer_auth_live is still "
                "false, measured from the real environment rather than from "
                "this fixture"
            ),
            "expect_valid": True,
            "expect_rls": True,
            "request": {"cookie_value": good, "membership_verified": True},
        },
    ]


def build_demo_state_cases() -> list[dict[str, Any]]:
    """Four state cases. One consumes; three are refused."""
    return [
        {
            "case": "missing_state",
            "fixture_label": FIXTURE_LABEL,
            "why": "nothing was stored under that id",
            "expect_consume_allowed": False,
            "expect_replay": False,
        },
        {
            "case": "expired_state",
            "fixture_label": FIXTURE_LABEL,
            "why": "stored, and the redirect window closed before the callback",
            "expect_consume_allowed": False,
            "expect_replay": False,
        },
        {
            "case": "consumed_state_replay",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "used once and presented again - the signature of somebody "
                "resubmitting a captured callback URL, reported separately from "
                "expiry because only one of them is worth alerting on"
            ),
            "expect_consume_allowed": False,
            "expect_replay": True,
        },
        {
            "case": "valid_state_and_pkce",
            "fixture_label": FIXTURE_LABEL,
            "why": "the one that consumes, exactly once",
            "expect_consume_allowed": True,
            "expect_replay": False,
        },
    ]


def _run_state_case(case: str) -> dict[str, Any]:
    """Each case gets its own store, so one cannot leak into the next."""
    store = InMemoryRedirectStateStore()
    scope = "in_memory_test"

    def _seed(ttl: int = 600) -> dict[str, Any]:
        return store_state(
            state_id=FIXTURE_STATE_ID,
            state_value=FIXTURE_STATE_VALUE,
            code_verifier=FIXTURE_VERIFIER,
            code_challenge=FIXTURE_CHALLENGE,
            issued_at=FIXTURE_ISSUED_AT,
            ttl_seconds=ttl,
            storage_scope=scope,
            store=store,
            is_demo_fixture=True,
        )

    if case == "missing_state":
        return consume_state(
            state_id="nf-demo-fixture-state-that-was-never-stored",
            returned_state=FIXTURE_STATE_VALUE,
            now=FIXTURE_NOW,
            storage_scope=scope,
            store=store,
        )

    if case == "expired_state":
        _seed()
        return consume_state(
            state_id=FIXTURE_STATE_ID,
            returned_state=FIXTURE_STATE_VALUE,
            now=FIXTURE_ISSUED_AT + 3600,
            storage_scope=scope,
            store=store,
        )

    if case == "consumed_state_replay":
        _seed()
        consume_state(
            state_id=FIXTURE_STATE_ID,
            returned_state=FIXTURE_STATE_VALUE,
            now=FIXTURE_NOW,
            storage_scope=scope,
            store=store,
        )
        return consume_state(
            state_id=FIXTURE_STATE_ID,
            returned_state=FIXTURE_STATE_VALUE,
            now=FIXTURE_NOW + 30,
            storage_scope=scope,
            store=store,
        )

    _seed()
    return consume_state(
        state_id=FIXTURE_STATE_ID,
        returned_state=FIXTURE_STATE_VALUE,
        now=FIXTURE_NOW,
        storage_scope=scope,
        store=store,
    )


def measure_session_state_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's lists, so a test can hand
    it a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_session_state_demo_fixture_set() -> dict[str, Any]:
    """The eleven cases, each run through the contract that owns it."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    session_cases = build_demo_session_cases()
    state_cases = build_demo_state_cases()
    cases = session_cases + state_cases
    covered = measure_session_state_cases(cases)

    # The artifact carries what each case *is*, never what it was built from.
    #
    # A session case's `request` holds a cookie value and a signing key. Both
    # are committed fixture constants that sign nothing anybody would accept -
    # and the artifact writer refuses them anyway, by field name. That refusal
    # is correct: a rule that depended on remembering which values were fake
    # would eventually meet one that was not.
    published_cases = [
        {k: v for k, v in case.items() if k != "request"} for case in cases
    ]

    rows: list[dict[str, Any]] = []

    for case in session_cases:
        request = dict(case["request"])
        request.setdefault("signing_key", FIXTURE_SIGNING_KEY)
        request.setdefault("now", FIXTURE_NOW)
        result = verify_session_cookie(**request)
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "kind": "session",
                "expect_valid": case["expect_valid"],
                "expect_rls": case["expect_rls"],
                "cookie_present": result["cookie_present"],
                "cookie_parseable": result["cookie_parseable"],
                "signature_valid": result["signature_valid"],
                "session_expired": result["session_expired"],
                "organization_id_valid": result["organization_id_valid"],
                "principal_resolved": result["principal_resolved"],
                "membership_verified": result["membership_verified"],
                "session_cookie_valid": result["session_cookie_valid"],
                "rls_context_allowed": result["rls_context_allowed"],
                "customer_auth_live": result["customer_auth_live"],
                "signing_key_present": result["signing_key_present"],
                "blocked_reasons": result["blocked_reasons"],
                "agrees_with_expectation": (
                    bool(result["session_cookie_valid"]) is bool(case["expect_valid"])
                    and bool(result["rls_context_allowed"])
                    is bool(case["expect_rls"])
                ),
            }
        )

    for case in state_cases:
        result = _run_state_case(case["case"])
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "kind": "state",
                "expect_consume_allowed": case["expect_consume_allowed"],
                "expect_replay": case["expect_replay"],
                "operation": result["operation"],
                "state_value_present": result["state_value_present"],
                "state_value_valid": result["state_value_valid"],
                "pkce_verifier_present": result["pkce_verifier_present"],
                "expired": result["expired"],
                "consumed": result["consumed"],
                "consume_allowed": result["consume_allowed"],
                "replay_detected": result["replay_detected"],
                "storage_scope": result["storage_scope"],
                "production_store": result["production_store"],
                "blocked_reasons": result["blocked_reasons"],
                "agrees_with_expectation": (
                    bool(result["consume_allowed"])
                    is bool(case["expect_consume_allowed"])
                    and bool(result["replay_detected"]) is bool(case["expect_replay"])
                ),
            }
        )

    actual = build_customer_auth_activation_gate()
    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "cases": published_cases,
            "case_count": len(cases),
            "rows": rows,
            "session_state_cases_covered": sorted(covered),
            "session_state_cases_missing": sorted(
                REQUIRED_SESSION_STATE_CASES - covered
            ),
            "cases_disagreeing_with_expectation": disagreements,
            "valid_session_count": sum(
                1 for r in rows if r.get("session_cookie_valid")
            ),
            "rls_allowed_count": sum(1 for r in rows if r.get("rls_context_allowed")),
            "consume_allowed_count": sum(
                1 for r in rows if r.get("consume_allowed")
            ),
            "replay_detected_count": sum(
                1 for r in rows if r.get("replay_detected")
            ),
            "production_store_count": sum(
                1 for r in rows if r.get("production_store")
            ),
            # Measured from the real environment, never forged.
            "customer_auth_live_in_actual_environment": actual["customer_auth_live"],
            "login_live_in_actual_environment": actual["login_live"],
            "session_signing_key_present_in_actual_environment": bool(
                rows[0].get("signing_key_present")
            ),
            # Constants.
            "production_sessions_created": False,
            "real_users_created": False,
            "real_secrets_exposed": False,
            "session_cookie_value_emitted": False,
            "state_value_emitted": False,
            "pkce_verifier_emitted": False,
            "provider_contacted": False,
            "cookies_set": False,
            "persisted_to_database": False,
            "fabricated": False,
        }
    )


def session_state_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "production_sessions_created",
        "real_users_created",
        "real_secrets_exposed",
        "session_cookie_value_emitted",
        "state_value_emitted",
        "pkce_verifier_emitted",
        "provider_contacted",
        "cookies_set",
        "persisted_to_database",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"session_state_demo_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("session_state_cases_missing") or []:
        fails.append(f"session_state_case_not_covered:{case}")

    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"contract_disagreed_with_the_fixture:{case}")

    # The actual environment is measured and must not be live.
    if fixture.get("customer_auth_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_auth_live")
    if fixture.get("login_live_in_actual_environment"):
        fails.append("fixture_set_reports_the_actual_environment_as_login_live")
    if fixture.get("session_signing_key_present_in_actual_environment"):
        fails.append("fixture_set_reports_a_configured_signing_key")

    # A valid session must be reachable, or every refusal is unfalsifiable.
    if not fixture.get("valid_session_count"):
        fails.append("no_valid_session_demonstrated")
    if not fixture.get("rls_allowed_count"):
        fails.append("no_rls_context_demonstrated")
    if not fixture.get("consume_allowed_count"):
        fails.append("no_state_consumption_demonstrated")
    if not fixture.get("replay_detected_count"):
        fails.append("no_replay_demonstrated")

    # No fixture may run in a production store.
    if fixture.get("production_store_count"):
        fails.append("session_state_demo_used_a_production_store")

    for row in fixture.get("rows") or []:
        case = row.get("case")

        # A refusal must name itself.
        if row.get("kind") == "session" and not row.get("session_cookie_valid"):
            if not row.get("blocked_reasons"):
                fails.append(f"demo_row_refused_without_a_reason:{case}")

        # RLS needs a valid session, a UUID organization and a membership.
        if row.get("rls_context_allowed"):
            for required in (
                "session_cookie_valid",
                "organization_id_valid",
                "membership_verified",
            ):
                if not row.get(required):
                    fails.append(f"demo_row_rls_without:{required}:{case}")

        # No row may report customer auth as live.
        if row.get("customer_auth_live"):
            fails.append(f"demo_row_reported_customer_auth_live:{case}")

        # A consumed replay may never be permitted.
        if row.get("replay_detected") and row.get("consume_allowed"):
            fails.append(f"demo_row_permitted_a_replay:{case}")

    return fails
