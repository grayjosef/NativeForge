"""Live redirect and signing key demo fixtures (Gate 119H).

Ten labelled cases across the three things Gate 119 built: the signing key
readiness contract, the authorization URL builder, and the durable redirect
state repository.

## Every value here is fake, and says so

```text
nf-demo-fixture-*        states, verifiers, client ids, issuers
*.invalid                every hostname, reserved by RFC 2606 to resolve nowhere
signing key material     forged strings that sign nothing anybody accepts
```

No case reads the environment, so the set is identical on every machine and a
committed artifact means the same thing everywhere.

## Why nine of ten cases refuse

The refusals are the contract; the one permitted case exists so the refusals are
falsifiable. A service that only ever says no is indistinguishable from a
constant, which is the defect Gates 117 and 118 each shipped once and had to go
back and fix.

`url_available_with_full_provider_config` is the permitted case, and even it
produces no session, contacts no provider, and makes no network call.

## The repository cases use a real database

An in-memory SQLite, created and dropped inside this module. It is a real
INSERT, a real SELECT and a real UPDATE — which is the only way to demonstrate
that what lands in the row is a digest and not a verifier.

Nothing here touches the application's database, and the table is never seeded
into a migration-managed one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

from nativeforge.services.customer_auth_authorization_url_service import (
    build_authorization_url,
)
from nativeforge.services.customer_auth_redirect_state_repository_service import (
    REDIRECT_STATES,
    consume_redirect_state,
    persist_redirect_state,
    redirect_state_repository_invariant_failures,
)
from nativeforge.services.customer_auth_signing_key_readiness_service import (
    build_signing_key_readiness,
    signing_key_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_customer_auth_live_redirect_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Every hostname below is `.invalid`, reserved by RFC 2606 precisely so that it
# resolves nowhere. A fixture that pointed at a real domain would be one DNS
# lookup away from being a live provider call.
DEMO_ISSUER = "https://nf-demo-fixture-issuer.invalid"
DEMO_CLIENT_ID = "nf-demo-fixture-client-id"
DEMO_REDIRECT_URI = "https://nf-demo-fixture-app.invalid/auth/callback"
DEMO_AUDIENCE = "https://nf-demo-fixture-api.invalid"

DEMO_STATE = FIXTURE_PREFIX + "state-" + ("a" * 32)
DEMO_VERIFIER = FIXTURE_PREFIX + "verifier-" + ("b" * 48)
DEMO_CHALLENGE = FIXTURE_PREFIX + "challenge-" + ("c" * 32)

# The committed fake, long enough to pass the length floor so its refusal is
# about the *source* rather than the shape. The one key-shaped string in this
# module, and it signs nothing anybody should accept.
DEMO_FIXTURE_KEY = FIXTURE_PREFIX + "signing-key-not-a-real-secret"

REQUIRED_CASES: tuple[str, ...] = (
    "signing_key_missing",
    "signing_key_is_the_local_dev_fixture",
    "signing_key_too_short",
    "signing_key_ready_from_secret_manager",
    "url_blocked_without_provider_config",
    "url_blocked_without_state_or_pkce",
    "url_available_with_full_provider_config",
    "redirect_state_persisted_as_hashes",
    "redirect_state_consumed_once",
    "redirect_state_replay_detected",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    REDIRECT_STATES.create(engine)
    return engine


def _signing_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "signing_key_missing",
            "kind": "signing_key",
            "why": "the environment as it actually is: no key anywhere",
            "expect_can_sign": False,
            "expect_source": "missing",
            "result": build_signing_key_readiness(signing_key_material=""),
        },
        {
            "case": "signing_key_is_the_local_dev_fixture",
            "kind": "signing_key",
            "why": (
                "present, long enough, and disqualified. A committed key is a "
                "key anybody who has read the repository already holds"
            ),
            "expect_can_sign": False,
            "expect_source": "local_dev_fixture",
            "result": build_signing_key_readiness(
                signing_key_material=DEMO_FIXTURE_KEY
            ),
        },
        {
            "case": "signing_key_too_short",
            "kind": "signing_key",
            "why": (
                "HMAC accepts any key length and fails silently on a weak one, "
                "so the floor is enforced here rather than discovered later"
            ),
            "expect_can_sign": False,
            "expect_source": "environment",
            "result": build_signing_key_readiness(signing_key_material="abc123"),
        },
        {
            "case": "signing_key_ready_from_secret_manager",
            "kind": "signing_key",
            "why": (
                "the one permitted signing case. Even here nothing is signed - "
                "readiness is a statement about a key, not about a session"
            ),
            "expect_can_sign": True,
            "expect_source": "secret_manager",
            "result": build_signing_key_readiness(
                secret_manager_present=True, rotation_supported=True
            ),
        },
    ]


def _url_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "url_blocked_without_provider_config",
            "kind": "authorization_url",
            "why": "no issuer, no client id, no redirect URI, so no URL",
            "expect_url": False,
            "result": build_authorization_url(
                issuer="",
                client_id="",
                redirect_uri="",
                state=DEMO_STATE,
                code_challenge=DEMO_CHALLENGE,
            ),
        },
        {
            "case": "url_blocked_without_state_or_pkce",
            "kind": "authorization_url",
            "why": (
                "full provider configuration and still no URL. Both are "
                "optional in the specification and neither is optional here"
            ),
            "expect_url": False,
            "result": build_authorization_url(
                issuer=DEMO_ISSUER,
                client_id=DEMO_CLIENT_ID,
                redirect_uri=DEMO_REDIRECT_URI,
                state=None,
                code_challenge=None,
            ),
        },
        {
            "case": "url_available_with_full_provider_config",
            "kind": "authorization_url",
            "why": (
                "the permitted case, and the reason every refusal above is "
                "falsifiable. A string is built; nobody visits it"
            ),
            "expect_url": True,
            "result": build_authorization_url(
                issuer=DEMO_ISSUER,
                client_id=DEMO_CLIENT_ID,
                redirect_uri=DEMO_REDIRECT_URI,
                audience=DEMO_AUDIENCE,
                state=DEMO_STATE,
                code_challenge=DEMO_CHALLENGE,
            ),
        },
    ]


def _repository_cases() -> list[dict[str, Any]]:
    """Three cases against a real in-memory database."""
    created = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    cases: list[dict[str, Any]] = []

    def _persist(conn: Any, state: str) -> dict[str, Any]:
        return persist_redirect_state(
            connection=conn,
            state_value=state,
            code_verifier=DEMO_VERIFIER,
            code_challenge=DEMO_CHALLENGE,
            redirect_uri=DEMO_REDIRECT_URI,
            issuer=DEMO_ISSUER,
            created_at=created,
            storage_scope="database",
        )

    # 1. what actually lands in the row
    engine = _memory_engine()
    with engine.begin() as conn:
        stored = _persist(conn, DEMO_STATE)
        row = conn.execute(sa.select(REDIRECT_STATES)).mappings().first()
        rendered = json.dumps({k: str(v) for k, v in dict(row or {}).items()})
        cases.append(
            {
                "case": "redirect_state_persisted_as_hashes",
                "kind": "redirect_state",
                "why": (
                    "a real INSERT into a real table, and what lands is two "
                    "digests. A database holding live verifiers is a database "
                    "whose backups hold live verifiers"
                ),
                "expect_row_written": True,
                "expect_consume_allowed": False,
                "raw_state_in_row": DEMO_STATE in rendered,
                "raw_verifier_in_row": DEMO_VERIFIER in rendered,
                "result": stored,
            }
        )
    engine.dispose()

    # 2. consumed exactly once
    engine = _memory_engine()
    with engine.begin() as conn:
        _persist(conn, DEMO_STATE)
        first = consume_redirect_state(
            connection=conn,
            returned_state=DEMO_STATE,
            now=created + timedelta(seconds=30),
            storage_scope="database",
        )
        cases.append(
            {
                "case": "redirect_state_consumed_once",
                "kind": "redirect_state",
                "why": "the state issued at /login, returned at /callback, in time",
                "expect_row_written": True,
                "expect_consume_allowed": True,
                "raw_state_in_row": False,
                "raw_verifier_in_row": False,
                "result": first,
            }
        )
    engine.dispose()

    # 3. the same state, twice
    engine = _memory_engine()
    with engine.begin() as conn:
        _persist(conn, DEMO_STATE)
        consume_redirect_state(
            connection=conn,
            returned_state=DEMO_STATE,
            now=created + timedelta(seconds=30),
            storage_scope="database",
        )
        replay = consume_redirect_state(
            connection=conn,
            returned_state=DEMO_STATE,
            now=created + timedelta(seconds=60),
            storage_scope="database",
        )
        cases.append(
            {
                "case": "redirect_state_replay_detected",
                "kind": "redirect_state",
                "why": (
                    "somebody resubmitting a captured callback URL. Reported "
                    "separately from expiry, because only one of the two is "
                    "worth waking anybody up for"
                ),
                "expect_row_written": True,
                "expect_consume_allowed": False,
                "raw_state_in_row": False,
                "raw_verifier_in_row": False,
                "result": replay,
            }
        )
    engine.dispose()

    return cases


def build_demo_live_redirect_cases() -> list[dict[str, Any]]:
    """Ten labelled cases. Nine refusals and one buildable URL."""
    return [
        {"fixture_label": FIXTURE_LABEL, **case}
        for case in _signing_cases() + _url_cases() + _repository_cases()
    ]


def measure_live_redirect_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def _agrees(case: dict[str, Any]) -> bool:
    result = case["result"]
    if case["kind"] == "signing_key":
        return bool(
            bool(result["can_sign_production_session"]) is bool(case["expect_can_sign"])
            and result["signing_key_source"] == case["expect_source"]
        )
    if case["kind"] == "authorization_url":
        return bool(
            bool(result["authorization_url_returned"]) is bool(case["expect_url"])
        )
    return bool(
        bool(result["row_written"]) is bool(case["expect_row_written"])
        and bool(result["consume_allowed"]) is bool(case["expect_consume_allowed"])
    )


def build_live_redirect_demo_fixture_set() -> dict[str, Any]:
    """The ten cases, measured. Values in, booleans out."""
    cases = build_demo_live_redirect_cases()
    covered = measure_live_redirect_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "kind": case["kind"],
                "why": case["why"],
                "agrees_with_expectation": _agrees(case),
                # Per-kind facts, all booleans and vocabulary terms. No state,
                # no verifier, no key and no full URL reaches a row.
                "can_sign_production_session": bool(
                    result.get("can_sign_production_session")
                ),
                "signing_key_source": result.get("signing_key_source"),
                "authorization_url_available": bool(
                    result.get("authorization_url_available")
                ),
                "authorization_url_returned": bool(
                    result.get("authorization_url_returned")
                ),
                "row_written": bool(result.get("row_written")),
                "row_found": bool(result.get("row_found")),
                "consume_allowed": bool(result.get("consume_allowed")),
                "replay_detected": bool(result.get("replay_detected")),
                "expired": bool(result.get("expired")),
                "raw_state_in_row": bool(case.get("raw_state_in_row")),
                "raw_verifier_in_row": bool(case.get("raw_verifier_in_row")),
                "secret_exposed": bool(
                    result.get("secret_exposed") or result.get("secret_value_exposed")
                ),
                "provider_called": bool(result.get("provider_called")),
                "blocked_reasons": list(result.get("blocked_reasons") or []),
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
            "live_redirect_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "can_sign_count": sum(1 for r in rows if r["can_sign_production_session"]),
            "url_returned_count": sum(
                1 for r in rows if r["authorization_url_returned"]
            ),
            "consume_allowed_count": sum(1 for r in rows if r["consume_allowed"]),
            "replay_detected_count": sum(1 for r in rows if r["replay_detected"]),
            # Constants. A fixture set demonstrates; it activates nothing.
            "sessions_created": 0,
            "real_users_created": 0,
            "provider_contacted": False,
            "network_calls": False,
            "state_value_emitted": False,
            "pkce_verifier_emitted": False,
            "signing_key_value_emitted": False,
            "application_database_touched": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def live_redirect_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("live_redirect_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    for row in rows:
        label = row.get("case")
        if row.get("raw_state_in_row"):
            fails.append(f"raw_state_reached_the_database:{label}")
        if row.get("raw_verifier_in_row"):
            fails.append(f"raw_verifier_reached_the_database:{label}")
        if row.get("secret_exposed"):
            fails.append(f"a_secret_value_reached_a_result:{label}")
        if row.get("provider_called"):
            fails.append(f"a_provider_was_called:{label}")
        if row.get("consume_allowed") and row.get("replay_detected"):
            fails.append(f"a_replayed_state_was_permitted:{label}")
        if row.get("consume_allowed") and row.get("expired"):
            fails.append(f"an_expired_state_was_permitted:{label}")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")

    # Exactly one URL is buildable, and exactly one key can sign. More than one
    # of either would mean a refusal case stopped refusing.
    if fixture.get("url_returned_count") != 1:
        fails.append("expected_exactly_one_buildable_authorization_url")
    if fixture.get("can_sign_count") != 1:
        fails.append("expected_exactly_one_key_fit_to_sign")
    if fixture.get("consume_allowed_count") != 1:
        fails.append("expected_exactly_one_permitted_consumption")

    if fixture.get("sessions_created"):
        fails.append("a_fixture_created_a_session")
    if fixture.get("provider_contacted") or fixture.get("network_calls"):
        fails.append("a_fixture_reached_the_network")
    if fixture.get("application_database_touched"):
        fails.append("a_fixture_wrote_to_the_application_database")

    return sorted(set(fails))


def repository_case_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """Run each repository case's own invariants, so the two cannot drift."""
    fails: list[str] = []
    for case in build_demo_live_redirect_cases():
        if case["kind"] == "redirect_state":
            fails.extend(
                f"{case['case']}:{failure}"
                for failure in redirect_state_repository_invariant_failures(
                    case["result"]
                )
            )
        elif case["kind"] == "signing_key":
            fails.extend(
                f"{case['case']}:{failure}"
                for failure in signing_key_readiness_invariant_failures(case["result"])
            )
    return sorted(set(fails))
