"""Durable redirect state repository (Gate 119C).

The database-backed half of Gate 118D's store. Same contract, same vocabulary,
different lifetime: a row here survives a process restart, which is the whole
reason a redirect can complete on a different worker than started it.

## What is written, and what is not

```text
written        state_hash            sha256 of the state
               pkce_verifier_hash    sha256 of the verifier
               code_challenge        the public half - it went to the provider
               redirect_uri issuer audience
               created_at expires_at consumed_at replay_detected

never written  the state
               the verifier
               a token
               a session
               anything belonging to a customer
```

A database holding live PKCE verifiers is a database whose backups, replicas and
query logs hold live PKCE verifiers. The callback never needs the value — it
needs to know whether what it was handed matches what was issued, and a digest
answers that exactly.

## Comparison is constant-time

`hmac.compare_digest` on the digests, not `==`. The digests are of
high-entropy values so a timing oracle here is close to worthless, and using the
constant-time comparison anyway costs nothing and removes the question.

## Single-use, and the difference between expired and replayed

```text
expired     the state stopped being usable
replayed    the state was already used, and this is a second attempt
```

A store that called both "invalid" would lose the one worth alerting on. A
consumed state presented again is the signature of somebody resubmitting a
captured callback URL, so `replay_detected` is reported separately and is
recorded on the row.

Consumption is one-way. There is no code path that clears `consumed_at`, and an
invariant refuses any result permitting the consumption of a consumed state.

## No ORM model

`nf_auth_redirect_states` is reached through SQLAlchemy Core, matching
`nf_identities`, `nf_raw_source_payloads` and `nf_tenant_customer_org_bindings`
— none of the three has an ORM model either. A model would be a mapped class
nothing constructs.

## Nothing writes here in production yet

`/login` still refuses while no provider is configured, and this gate does not
configure one. The `database` scope works, is exercised against a real database
in tests, and is reached by nothing in the running application.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

from nativeforge.services.customer_auth_redirect_state_store_service import (
    DEFAULT_SCOPE,
    DEFAULT_STATE_TTL_SECONDS,
    FIXTURE_PREFIX,
    MAX_STATE_TTL_SECONDS,
    PRODUCTION_SCOPES,
    STORAGE_SCOPES,
)
from nativeforge.services.customer_auth_state_pkce_service import (
    CODE_CHALLENGE_METHOD,
)

SCHEMA_VERSION = "nf_customer_auth_redirect_state_repository_v1"

TABLE_NAME = "nf_auth_redirect_states"

REPOSITORY_OPERATIONS = frozenset({"persist", "consume"})

# No result from this module may carry any of these. The raw values are hashed
# on the way in and discarded; the hashes stay in the database.
FORBIDDEN_VALUE_FIELDS = frozenset(
    {
        "state_value",
        "state",
        "code_verifier",
        "pkce_verifier",
        "verifier",
        "state_hash",
        "pkce_verifier_hash",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "storage_scope",
    "production_store",
    "durable",
    "row_written",
    "row_found",
    "state_hash_recorded",
    "pkce_verifier_hash_recorded",
    "raw_state_stored",
    "raw_verifier_stored",
    "state_matches",
    "expired",
    "consumed",
    "consume_allowed",
    "replay_detected",
    "demo_fixture",
    "expires_at",
    "blocked_reasons",
)

_METADATA = sa.MetaData()

# Core rather than ORM, matching the three tables nearest this one. Column set
# mirrors migration 0030 exactly; a test asserts the two agree.
REDIRECT_STATES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("state_hash", sa.Text(), nullable=False),
    sa.Column("pkce_verifier_hash", sa.Text(), nullable=False),
    sa.Column("code_challenge", sa.Text(), nullable=False),
    sa.Column("code_challenge_method", sa.Text(), nullable=False),
    sa.Column("redirect_uri", sa.Text(), nullable=False),
    sa.Column("issuer", sa.Text(), nullable=True),
    sa.Column("audience", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("consumed_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("replay_detected", sa.Boolean(), nullable=False),
    sa.Column("storage_scope", sa.Text(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    # Migration 0030's constraints, restated so the Core table and the migrated
    # one enforce the same rules. Without these a test that creates the table
    # from this definition would exercise a *weaker* table than production has,
    # and would pass on writes the real database refuses.
    sa.UniqueConstraint("state_hash", name="uq_nf_auth_redirect_state_hash"),
    sa.CheckConstraint(
        "expires_at > created_at",
        name="ck_nf_auth_redirect_expiry_after_creation",
    ),
    sa.CheckConstraint(
        "consumed_by_identity_id IS NULL OR consumed_at IS NOT NULL",
        name="ck_nf_auth_redirect_consumer_needs_consumption",
    ),
    sa.CheckConstraint(
        "code_challenge_method IN ('S256')",
        name="ck_nf_auth_redirect_challenge_method",
    ),
    sa.CheckConstraint(
        "storage_scope IN ('contract_only', 'in_memory_test', 'database', 'unknown')",
        name="ck_nf_auth_redirect_storage_scope",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def hash_secret_value(value: Any) -> str:
    """SHA-256 hex digest. The only thing that ever reaches the database."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _digests_match(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def _aware(moment: datetime) -> datetime:
    """SQLite hands back naive datetimes. Compare like with like."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _result(**fields: Any) -> dict[str, Any]:
    scope = str(fields.get("storage_scope") or DEFAULT_SCOPE)
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "production_store": scope in PRODUCTION_SCOPES,
        "durable": scope in PRODUCTION_SCOPES,
        # Constants, restated on every result so a caller reading one in
        # isolation still sees them. Both are false by construction: the raw
        # values are hashed on the way in and never held.
        "raw_state_stored": False,
        "raw_verifier_stored": False,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    return _json_safe(out)


def persist_redirect_state(
    *,
    connection: Any = None,
    state_value: Any = None,
    code_verifier: Any = None,
    code_challenge: Any = None,
    code_challenge_method: str = CODE_CHALLENGE_METHOD,
    redirect_uri: Any = None,
    issuer: Any = None,
    audience: Any = None,
    created_at: datetime | None = None,
    ttl_seconds: int = DEFAULT_STATE_TTL_SECONDS,
    storage_scope: str = DEFAULT_SCOPE,
    state_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Record that a state and verifier were issued. Values are hashed, then dropped.

    ``connection`` is a SQLAlchemy connection. Without one the scope cannot be
    ``database`` and nothing is written — which is the default, so importing
    this module writes nothing anywhere.
    """
    scope = str(storage_scope or "").strip().lower()
    if scope not in STORAGE_SCOPES:
        scope = "unknown"

    blocked_reasons: list[str] = []

    raw_state = str(state_value or "").strip()
    raw_verifier = str(code_verifier or "").strip()
    challenge = str(code_challenge or "").strip()
    uri = str(redirect_uri or "").strip()

    if not raw_state:
        blocked_reasons.append("no_state_value_supplied")
    if not raw_verifier:
        blocked_reasons.append("no_pkce_verifier_supplied")
    if not challenge:
        blocked_reasons.append("no_pkce_challenge_supplied")
    if not uri:
        blocked_reasons.append("no_redirect_uri_supplied")

    method = str(code_challenge_method or "").strip()
    if method != CODE_CHALLENGE_METHOD:
        # `plain` defeats PKCE. The database refuses it too.
        blocked_reasons.append("code_challenge_method_must_be_s256")

    ttl = int(ttl_seconds)
    if ttl <= 0:
        blocked_reasons.append("state_ttl_must_be_positive")
    elif ttl > MAX_STATE_TTL_SECONDS:
        blocked_reasons.append(
            f"state_ttl_exceeds_{MAX_STATE_TTL_SECONDS}_second_ceiling"
        )

    if scope == "unknown":
        blocked_reasons.append("storage_scope_not_recognised")
    if scope == "contract_only":
        blocked_reasons.append("contract_only_scope_stores_nothing")
    if scope in PRODUCTION_SCOPES and connection is None:
        blocked_reasons.append("database_scope_requested_without_a_connection")

    demo_fixture = raw_state.startswith(FIXTURE_PREFIX) or raw_verifier.startswith(
        FIXTURE_PREFIX
    )

    issued = created_at or datetime.now(UTC)
    expires = issued + timedelta(seconds=max(ttl, 1))

    row_written = False
    if scope in PRODUCTION_SCOPES and connection is not None and not blocked_reasons:
        connection.execute(
            sa.insert(REDIRECT_STATES).values(
                id=state_id or uuid.uuid4(),
                state_hash=hash_secret_value(raw_state),
                pkce_verifier_hash=hash_secret_value(raw_verifier),
                code_challenge=challenge,
                code_challenge_method=method,
                redirect_uri=uri,
                issuer=str(issuer) if issuer else None,
                audience=str(audience) if audience else None,
                created_at=issued,
                expires_at=expires,
                consumed_at=None,
                consumed_by_identity_id=None,
                replay_detected=False,
                storage_scope=scope,
                blocked_reasons=[],
            )
        )
        row_written = True

    return _result(
        operation="persist",
        storage_scope=scope,
        row_written=row_written,
        row_found=False,
        state_hash_recorded=row_written,
        pkce_verifier_hash_recorded=row_written,
        state_matches=False,
        expired=False,
        consumed=False,
        # A persist never authorises a consumption. Gate 118's defect: judging a
        # successful store by whether consumption was allowed.
        consume_allowed=False,
        replay_detected=False,
        demo_fixture=demo_fixture,
        expires_at=expires.isoformat(),
        blocked_reasons=blocked_reasons,
    )


def consume_redirect_state(
    *,
    connection: Any = None,
    returned_state: Any = None,
    now: datetime | None = None,
    storage_scope: str = DEFAULT_SCOPE,
    consumed_by_identity_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Match a returned state against a stored one, exactly once.

    Looks the row up by digest, so the raw value is used for comparison and
    never for storage. A row that is found, unexpired and unconsumed is marked
    consumed in the same call — there is no window in which a caller holds a
    valid unconsumed match.
    """
    scope = str(storage_scope or "").strip().lower()
    if scope not in STORAGE_SCOPES:
        scope = "unknown"

    blocked_reasons: list[str] = []

    raw_state = str(returned_state or "").strip()
    if not raw_state:
        blocked_reasons.append("no_returned_state_supplied")

    # Derived from the value presented, not from the row: every row this
    # repository writes carries the `database` scope, so reading the scope back
    # would report every fixture state as a real one.
    demo_fixture = raw_state.startswith(FIXTURE_PREFIX)

    if scope == "unknown":
        blocked_reasons.append("storage_scope_not_recognised")
    if scope == "contract_only":
        blocked_reasons.append("contract_only_scope_stores_nothing")
    if scope in PRODUCTION_SCOPES and connection is None:
        blocked_reasons.append("database_scope_requested_without_a_connection")

    moment = now or datetime.now(UTC)

    row = None
    if scope in PRODUCTION_SCOPES and connection is not None and raw_state:
        digest = hash_secret_value(raw_state)
        candidate = (
            connection.execute(
                sa.select(REDIRECT_STATES).where(REDIRECT_STATES.c.state_hash == digest)
            )
            .mappings()
            .first()
        )
        # Constant-time even though the lookup already matched: the comparison
        # is what the contract says decides, so the contract is what runs.
        if candidate is not None and _digests_match(
            str(candidate["state_hash"]), digest
        ):
            row = candidate

    found = row is not None
    if not found and not blocked_reasons:
        blocked_reasons.append("no_stored_state_matched_the_returned_value")

    expired = False
    consumed = False
    replay = False

    if row is not None:
        expired = _aware(row["expires_at"]) <= _aware(moment)
        consumed = row["consumed_at"] is not None
        if expired:
            blocked_reasons.append("stored_state_expired")
        if consumed:
            # The one worth alerting on, reported separately from expiry.
            replay = True
            blocked_reasons.append("stored_state_already_consumed_replay_suspected")

    consume_allowed = bool(found and not expired and not consumed)

    if consume_allowed and connection is not None:
        connection.execute(
            sa.update(REDIRECT_STATES)
            .where(REDIRECT_STATES.c.id == row["id"])
            .values(
                consumed_at=moment,
                consumed_by_identity_id=consumed_by_identity_id,
            )
        )
        consumed = True
    elif replay and connection is not None and row is not None:
        connection.execute(
            sa.update(REDIRECT_STATES)
            .where(REDIRECT_STATES.c.id == row["id"])
            .values(replay_detected=True)
        )

    return _result(
        operation="consume",
        storage_scope=scope,
        row_written=bool(consume_allowed or replay),
        row_found=found,
        state_hash_recorded=found,
        pkce_verifier_hash_recorded=found,
        state_matches=found,
        expired=expired,
        consumed=consumed,
        consume_allowed=consume_allowed,
        replay_detected=replay,
        demo_fixture=demo_fixture,
        expires_at=(_aware(row["expires_at"]).isoformat() if row is not None else ""),
        blocked_reasons=blocked_reasons,
    )


def redirect_state_repository_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    """Contradictions this repository must never be able to produce."""
    failures: list[str] = []

    operation = str(result.get("operation") or "")
    if operation not in REPOSITORY_OPERATIONS:
        failures.append("operation_outside_vocabulary")

    scope = str(result.get("storage_scope") or "")
    if scope not in STORAGE_SCOPES:
        failures.append("storage_scope_outside_vocabulary")

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            failures.append(f"result_carries_{field}")

    if result.get("raw_state_stored") or result.get("raw_verifier_stored"):
        failures.append("raw_credential_material_reached_the_database")

    if (scope in PRODUCTION_SCOPES) != bool(result.get("production_store")):
        failures.append("production_store_disagrees_with_scope")

    if bool(result.get("durable")) != bool(result.get("production_store")):
        failures.append("durability_disagrees_with_production_store")

    if result.get("row_written") and scope not in PRODUCTION_SCOPES:
        failures.append("row_claimed_written_outside_a_database_scope")

    if operation == "persist" and result.get("consume_allowed"):
        failures.append("persist_claimed_a_consumption")

    if result.get("consume_allowed") and result.get("expired"):
        failures.append("expired_state_permitted_for_consumption")

    if result.get("consume_allowed") and result.get("replay_detected"):
        failures.append("replayed_state_permitted_for_consumption")

    if result.get("consume_allowed") and not result.get("row_found"):
        failures.append("consumption_permitted_without_a_stored_state")

    if result.get("consume_allowed") and result.get("blocked_reasons"):
        failures.append("consumption_permitted_with_blocked_reasons_present")

    if (
        operation == "consume"
        and not result.get("consume_allowed")
        and not result.get("blocked_reasons")
    ):
        failures.append("consumption_refused_without_a_reason")

    return sorted(set(failures))
