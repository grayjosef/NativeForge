"""Redirect state and PKCE store (Gate 118D).

Where a state and a code verifier live between `/login` issuing them and
`/callback` redeeming them.

## Why a store is needed at all

Gate 117 can generate a state and a verifier, and can validate a pair handed to
it. What it cannot do is *remember* one across the redirect — and the redirect
is the whole point. The browser leaves, visits the provider, and comes back with
a state that has to be compared against one the server issued minutes earlier.

## Single-use, and why that is the interesting rule

An expired state is a state that stopped being usable. A **consumed** state is
one that was already used, and reusing it is the signature of a replay: somebody
captured a callback URL and is submitting it a second time.

So consumption is a one-way transition, `replay_detected` is reported
separately from `expired`, and a consumed state cannot be un-consumed. The two
refusals look similar and mean different things, and a store that reported both
as "invalid" would lose the one worth alerting on.

## Storage scopes

```text
contract_only   this gate. Nothing is stored anywhere; the contract describes
                what a store must do.
in_memory_test  a dict, for tests. Dies with the process, which is correct for
                a test and disqualifying for anything else.
database        a table. Does not exist - Gate 118A found no session or state
                table and this gate deliberately adds none.
unknown         refuses.
```

`production_store` is true only for `database`, and an invariant enforces it.
A contract-only store does not make login live, and neither does an in-memory
one — a state that vanishes when the process restarts cannot survive a redirect
in any deployment with more than one worker.

## The verifier never reaches an artifact

`pkce_verifier_present` is a boolean. `store_state` accepts a verifier and
records only that it had one; nothing returns it. An invariant refuses any
result carrying a field that could hold one, and the artifact writer scans for
the same names.

That is stricter than it needs to be for a fixture value, and deliberately so:
the rule should not depend on remembering which values were fake.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_redirect_state_store_v1"

STORAGE_SCOPES: frozenset[str] = frozenset(
    {"contract_only", "in_memory_test", "database", "unknown"}
)

# The scope this gate operates in. A store that keeps nothing is honest about
# keeping nothing.
DEFAULT_SCOPE = "contract_only"

# Only one scope survives a process restart or a second worker.
PRODUCTION_SCOPES: frozenset[str] = frozenset({"database"})

# A state that outlives the redirect it was issued for is a state somebody can
# come back to later. Ten minutes is longer than any provider round trip.
DEFAULT_STATE_TTL_SECONDS = 600
MAX_STATE_TTL_SECONDS = 900

FIXTURE_PREFIX = "nf-demo-fixture-"

STORE_OPERATIONS: frozenset[str] = frozenset({"store", "consume"})

RESULT_FIELDS: tuple[str, ...] = (
    "operation",
    "state_store_available",
    "state_id",
    "state_value_present",
    "state_value_valid",
    "pkce_verifier_present",
    "pkce_challenge_present",
    "expires_at",
    "expired",
    "consumed",
    "consume_allowed",
    "replay_detected",
    "storage_scope",
    "production_store",
    "demo_fixture",
    "blocked_reasons",
)

# Field names that would mean a state or verifier value had entered a result.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "state_value",
        "state",
        "code_verifier",
        "pkce_verifier",
        "verifier",
        "code_challenge",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


class InMemoryRedirectStateStore:
    """A dict, for tests.

    Named so it cannot be mistaken for a store: it dies with the process, which
    is correct for a test and disqualifying for a deployment with more than one
    worker. `storage_scope` reports `in_memory_test` and `production_store` is
    false for it.
    """

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def put(self, state_id: str, record: dict[str, Any]) -> None:
        self._records[str(state_id)] = dict(record)

    def get(self, state_id: str) -> dict[str, Any] | None:
        record = self._records.get(str(state_id))
        return dict(record) if record else None

    def mark_consumed(self, state_id: str) -> None:
        record = self._records.get(str(state_id))
        if record is not None:
            record["consumed"] = True

    def __len__(self) -> int:
        return len(self._records)


def store_state(
    *,
    state_id: Any = None,
    state_value: Any = None,
    code_verifier: Any = None,
    code_challenge: Any = None,
    issued_at: int = 0,
    ttl_seconds: int = DEFAULT_STATE_TTL_SECONDS,
    storage_scope: str = DEFAULT_SCOPE,
    store: InMemoryRedirectStateStore | None = None,
    is_demo_fixture: bool = False,
) -> dict[str, Any]:
    """Record that a state and verifier were issued. Values are never returned."""
    scope = str(storage_scope or "").strip().lower()
    if scope not in STORAGE_SCOPES:
        scope = "unknown"

    blocked_reasons: list[str] = []

    identifier = str(state_id or "")
    if not identifier:
        blocked_reasons.append("state_stored_without_an_id")

    state_present = bool(str(state_value or "").strip())
    verifier_present = bool(str(code_verifier or "").strip())
    challenge_present = bool(str(code_challenge or "").strip())

    if not state_present:
        blocked_reasons.append("no_state_value_supplied")
    if not verifier_present:
        blocked_reasons.append("no_pkce_verifier_supplied")
    if not challenge_present:
        blocked_reasons.append("no_pkce_challenge_supplied")

    ttl = int(ttl_seconds)
    if ttl <= 0:
        blocked_reasons.append("state_ttl_must_be_positive")
    elif ttl > MAX_STATE_TTL_SECONDS:
        # A state that outlives the redirect is one somebody can come back to.
        blocked_reasons.append(
            f"state_ttl_exceeds_{MAX_STATE_TTL_SECONDS}_second_ceiling"
        )

    expires_at = int(issued_at) + ttl if issued_at else 0
    if not issued_at:
        blocked_reasons.append("state_stored_without_an_issued_at")

    if scope == "unknown":
        blocked_reasons.append("storage_scope_not_recognised")
    if scope == "contract_only":
        # Named rather than silent: nothing was actually kept.
        blocked_reasons.append("contract_only_scope_stores_nothing")

    demo_fixture = bool(
        is_demo_fixture
        or identifier.startswith(FIXTURE_PREFIX)
        or str(state_value or "").startswith(FIXTURE_PREFIX)
    )

    stored = False
    if scope == "in_memory_test" and store is not None and identifier:
        store.put(
            identifier,
            {
                # Only what a callback needs to compare against, and the
                # comparison happens in the state/PKCE service, not here.
                "state_value": str(state_value or ""),
                "code_verifier": str(code_verifier or ""),
                "code_challenge": str(code_challenge or ""),
                "expires_at": expires_at,
                "consumed": False,
                "demo_fixture": demo_fixture,
            },
        )
        stored = True
    elif scope == "in_memory_test" and store is None:
        blocked_reasons.append("in_memory_scope_requested_without_a_store")

    return _json_safe(
        _result(
            operation="store",
            state_id=identifier,
            state_value_present=state_present,
            state_value_valid=False,
            pkce_verifier_present=verifier_present,
            pkce_challenge_present=challenge_present,
            expires_at=expires_at,
            expired=False,
            consumed=False,
            consume_allowed=False,
            replay_detected=False,
            scope=scope,
            demo_fixture=demo_fixture,
            blocked_reasons=blocked_reasons,
            stored=stored,
        )
    )


def consume_state(
    *,
    state_id: Any = None,
    returned_state: Any = None,
    now: int = 0,
    storage_scope: str = DEFAULT_SCOPE,
    store: InMemoryRedirectStateStore | None = None,
) -> dict[str, Any]:
    """Redeem a stored state exactly once. Deny by default."""
    import hmac

    scope = str(storage_scope or "").strip().lower()
    if scope not in STORAGE_SCOPES:
        scope = "unknown"

    blocked_reasons: list[str] = []
    identifier = str(state_id or "")

    if not identifier:
        blocked_reasons.append("no_state_id_supplied")
    if scope == "unknown":
        blocked_reasons.append("storage_scope_not_recognised")

    record: dict[str, Any] | None = None
    if scope == "in_memory_test":
        if store is None:
            blocked_reasons.append("in_memory_scope_requested_without_a_store")
        else:
            record = store.get(identifier)
            if record is None:
                blocked_reasons.append("no_state_found_for_this_id")
    elif scope == "contract_only":
        blocked_reasons.append("contract_only_scope_has_nothing_to_consume")

    state_value_present = bool(record and record.get("state_value"))
    verifier_present = bool(record and record.get("code_verifier"))
    challenge_present = bool(record and record.get("code_challenge"))
    expires_at = int((record or {}).get("expires_at") or 0)
    already_consumed = bool((record or {}).get("consumed"))
    demo_fixture = bool((record or {}).get("demo_fixture"))

    expired = bool(record and expires_at and int(now) >= expires_at)
    if expired:
        blocked_reasons.append("state_expired")

    # A consumed state being presented again is the signature of a replay:
    # somebody captured a callback URL and is submitting it a second time. It is
    # reported separately from expiry, because the two mean different things and
    # only one of them is worth alerting on.
    replay_detected = bool(record and already_consumed)
    if replay_detected:
        blocked_reasons.append("state_already_consumed_replay_detected")

    # Constant-time, as everywhere else a state is compared.
    state_value_valid = False
    if record and returned_state is not None:
        state_value_valid = hmac.compare_digest(
            str(record.get("state_value") or ""), str(returned_state)
        )
        if not state_value_valid:
            blocked_reasons.append("returned_state_does_not_match_the_stored_state")
    elif record and returned_state is None:
        blocked_reasons.append("no_returned_state_to_compare")

    consume_allowed = bool(
        record is not None
        and state_value_valid
        and not expired
        and not already_consumed
        and not blocked_reasons
    )

    consumed = already_consumed
    if consume_allowed and store is not None:
        store.mark_consumed(identifier)
        consumed = True

    return _json_safe(
        _result(
            operation="consume",
            state_id=identifier,
            state_value_present=state_value_present,
            state_value_valid=state_value_valid,
            pkce_verifier_present=verifier_present,
            pkce_challenge_present=challenge_present,
            expires_at=expires_at,
            expired=expired,
            consumed=consumed,
            consume_allowed=consume_allowed,
            replay_detected=replay_detected,
            scope=scope,
            demo_fixture=demo_fixture,
            blocked_reasons=blocked_reasons,
            stored=record is not None,
        )
    )


def _result(
    *,
    operation: str,
    state_id: str,
    state_value_present: bool,
    state_value_valid: bool,
    pkce_verifier_present: bool,
    pkce_challenge_present: bool,
    expires_at: int,
    expired: bool,
    consumed: bool,
    consume_allowed: bool,
    replay_detected: bool,
    scope: str,
    demo_fixture: bool,
    blocked_reasons: list[str],
    stored: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        # Gate 118D: storing and consuming return the same shape and mean
        # different things. Without this field the invariants judged a
        # successful store by whether consumption was allowed - which is false
        # for every store, correctly, and was being reported as an unexplained
        # refusal.
        "operation": operation,
        "state_store_available": True,
        "state_id": state_id or None,
        "state_value_present": state_value_present,
        "state_value_valid": state_value_valid,
        "pkce_verifier_present": pkce_verifier_present,
        "pkce_challenge_present": pkce_challenge_present,
        "expires_at": expires_at or None,
        "expired": expired,
        "consumed": consumed,
        "consume_allowed": consume_allowed,
        "replay_detected": replay_detected,
        "storage_scope": scope,
        # Only a database-backed store survives a restart or a second worker.
        "production_store": scope in PRODUCTION_SCOPES,
        "record_stored": stored,
        "demo_fixture": demo_fixture,
        "blocked_reasons": sorted(set(blocked_reasons)),
        # Constants: values in, booleans out.
        "state_value_emitted": False,
        "pkce_verifier_emitted": False,
        "persisted_to_database": False,
        "provider_contacted": False,
        "fabricated": False,
    }


def state_store_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"state_store_missing_field:{field}")

    for constant in (
        "state_value_emitted",
        "pkce_verifier_emitted",
        "persisted_to_database",
        "provider_contacted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"state_store_claimed:{constant}")

    # No state or verifier value may appear, by field name.
    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            fails.append(f"state_store_result_carries_a_value_field:{field}")

    scope = result.get("storage_scope")
    if scope not in STORAGE_SCOPES:
        fails.append("storage_scope_out_of_vocabulary")

    # Only a database-backed store is a production store.
    if result.get("production_store") and scope not in PRODUCTION_SCOPES:
        fails.append(f"production_store_claimed_for_scope:{scope}")
    if scope in PRODUCTION_SCOPES and not result.get("production_store"):
        fails.append("database_scope_not_reported_as_a_production_store")

    # And this gate adds no database, so nothing may claim to have persisted.
    if result.get("persisted_to_database"):
        fails.append("state_store_claimed_a_database_write")

    # Consumption requires a matching, unexpired, unconsumed state.
    if result.get("consume_allowed"):
        if not result.get("state_value_valid"):
            fails.append("consume_allowed_without_a_matching_state")
        if result.get("expired"):
            fails.append("consume_allowed_for_an_expired_state")
        if result.get("replay_detected"):
            fails.append("consume_allowed_for_an_already_consumed_state")
        if result.get("blocked_reasons"):
            fails.append("consume_allowed_despite_blocked_reasons")

    # A replay is a consumed state presented again, and must never be allowed.
    if result.get("replay_detected") and result.get("consume_allowed"):
        fails.append("replay_permitted_to_consume")

    # Expiry is required. A state with no expiry never stops being usable.
    if result.get("state_value_present") and not result.get("expires_at"):
        if not result.get("blocked_reasons"):
            fails.append("state_stored_without_an_expiry")

    if result.get("operation") not in STORE_OPERATIONS:
        fails.append("state_store_operation_out_of_vocabulary")

    # A store never consumes anything, and saying so is not a refusal.
    if result.get("operation") == "store" and result.get("consume_allowed"):
        fails.append("a_store_operation_reported_a_consumption")

    # A refusal must name itself - but only where a refusal is what happened.
    # A successful store legitimately reports consume_allowed false with no
    # reasons, because storing is not consuming.
    if (
        result.get("operation") == "consume"
        and not result.get("consume_allowed")
        and not result.get("blocked_reasons")
    ):
        fails.append("state_refused_without_a_reason")

    return fails
