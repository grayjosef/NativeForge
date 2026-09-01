"""Gate 133B: the issuer/JWKS validation that happens, written down.

The callback verifies Google's ID token against Google's JWKS on every login.
It has done so since Gate 131. `issuer_jwks_validated` has been false
throughout, because the result was a local and locals do not survive a request.

```python
verification = verify_oidc_token(token=..., jwks=..., ...)   # and then gone
```

A gate cannot read a local. This module turns one verification attempt into a
sanitized row in `nf_auth_validation_events` and reads those rows back.

## What crosses the boundary, and what cannot

```text
in     the verification RESULT dict, plus two booleans about the fetch
out    booleans, an issuer URL, a state name, an algorithm, a kid fingerprint
never  the token, the JWKS, key material, the audience value, the subject,
       the email, or any claim
```

`record_validation_evidence` takes the whole verification result rather than
individual booleans, for the reason Gate 118 established for session decisions:
a caller passing booleans can assert a verification that did not happen. The
result is `verify_oidc_token`'s own output or it is nothing.

The subject and the email are present in that result when it verified. They are
read to decide nothing and are never written. The table has no column they could
go in, which is a stronger guarantee than a rule about what to put in one.

## The kid, and why a fingerprint

A `kid` is public - it is published in the JWKS document alongside the key it
names. Storing it would be defensible. A truncated SHA-256 is stored instead
because it gives the only thing the fingerprint is for, correlating events
across logins and key rotations, without anybody having to re-derive that
argument later.

## Evidence is a query, not a flag

`build_jwks_validation_evidence(connection=...)` asks the table. Without a
connection every field is false and the reason is `no_connection_supplied` -
the same contract Gate 132's binding evidence uses, and for the same reason:
`build_customer_auth_activation_gate` feeds committed artifacts, and an artifact
whose contents depend on the rows in one developer's database is one nobody else
can regenerate.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_customer_auth_jwks_validation_evidence_v1"

TABLE_NAME = "nf_auth_validation_events"

#: Migration 0037's CHECK. A test parses the migration and compares.
EVIDENCE_SOURCES: frozenset[str] = frozenset({"oauth_callback"})

VERIFICATION_STATES: frozenset[str] = frozenset(
    {
        "verified",
        "missing_token",
        "malformed_token",
        "unsupported_algorithm",
        "missing_kid",
        "unknown_kid",
        "jwks_unavailable",
        "signature_invalid",
        "issuer_invalid",
        "audience_invalid",
        "expired",
        "not_yet_valid",
        "subject_missing",
        "verification_error",
        "unknown",
    }
)

#: Fields a recorded event carries. Nothing outside this list is written, and a
#: test asserts the table's columns and this tuple agree.
EVENT_FIELDS: tuple[str, ...] = (
    "evidence_source",
    "issuer",
    "verification_state",
    "algorithm",
    "key_id_fingerprint",
    "provider_called",
    "issuer_validated",
    "jwks_validated",
    "id_token_signature_validated",
    "audience_validated",
    "blocked_reasons",
)

#: Keys of a verification result that must never reach a row. Named so the
#: refusal is testable rather than implied by the absence of a column.
FORBIDDEN_EVENT_KEYS: tuple[str, ...] = (
    "token",
    "id_token",
    "access_token",
    "refresh_token",
    "subject",
    "email",
    "claims",
    "jwks",
    "keys",
    "audience",
)

_METADATA = sa.MetaData()

VALIDATION_EVENTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("evidence_source", sa.String(length=32), nullable=False),
    sa.Column("issuer", sa.Text(), nullable=True),
    sa.Column("verification_state", sa.String(length=32), nullable=False),
    sa.Column("algorithm", sa.String(length=16), nullable=True),
    sa.Column("key_id_fingerprint", sa.String(length=32), nullable=True),
    sa.Column("provider_called", sa.Boolean(), nullable=False),
    sa.Column("issuer_validated", sa.Boolean(), nullable=False),
    sa.Column("jwks_validated", sa.Boolean(), nullable=False),
    sa.Column("id_token_signature_validated", sa.Boolean(), nullable=False),
    sa.Column("audience_validated", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.CheckConstraint(
        "id_token_signature_validated = false OR jwks_validated = true",
        name="ck_nf_auth_validation_events_signature_needs_jwks",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _fingerprint(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def build_validation_event(
    *,
    verification: dict[str, Any] | None = None,
    jwks_fetch: dict[str, Any] | None = None,
    provider_called: bool = False,
    evidence_source: str = "oauth_callback",
) -> dict[str, Any]:
    """One verification attempt, reduced to what may be stored. No database.

    Separate from the write so the reduction can be inspected without a
    connection - and so a test can assert what it drops.
    """
    result = verification or {}
    fetch = jwks_fetch or {}
    blocked_reasons: list[str] = []

    source = str(evidence_source or "").strip().lower()
    if source not in EVIDENCE_SOURCES:
        blocked_reasons.append(f"evidence_source_not_recognised:{source}")

    state = str(result.get("state") or "unknown").strip().lower()
    if state not in VERIFICATION_STATES:
        blocked_reasons.append(f"verification_state_not_recognised:{state}")
        state = "unknown"

    verified = bool(result.get("verified"))

    # A JWKS document with at least one key was actually available. `fetch` is
    # the fetcher's own report; `jwks_unavailable` is the verifier's word for
    # the same failure, and either one falsifies this.
    jwks_available = bool((fetch.get("jwks") or {}).get("keys"))
    jwks_validated = bool(jwks_available and state != "jwks_unavailable")

    # All three come from the verifier's own outcome rather than from a caller's
    # opinion of it. `verify_oidc_token` checks the signature, the issuer and
    # the audience on the way to `verified`, and refuses by name when any of
    # them fails - `signature_invalid`, `issuer_invalid`, `audience_invalid`.
    # So `verified` is exactly the conjunction, and deriving each separately
    # from the state name would be re-implementing the verifier's logic beside
    # it, where the two could disagree.
    signature_validated = bool(verified)
    issuer_validated = bool(verified)
    audience_validated = bool(verified)

    if verified and not jwks_validated:
        # The database CHECK refuses this too. Caught here so the caller gets a
        # named reason instead of an IntegrityError.
        blocked_reasons.append("verified_without_a_jwks_document")

    if not str(result.get("issuer") or "").strip():
        blocked_reasons.append("no_issuer_recorded")

    event = {
        "evidence_source": source,
        "issuer": str(result.get("issuer") or "").strip() or None,
        "verification_state": state,
        "algorithm": str(result.get("algorithm") or "").strip() or None,
        "key_id_fingerprint": _fingerprint(result.get("kid")),
        "provider_called": bool(provider_called),
        "issuer_validated": issuer_validated,
        "jwks_validated": jwks_validated,
        "id_token_signature_validated": signature_validated,
        "audience_validated": audience_validated,
        "blocked_reasons": sorted(set(blocked_reasons)),
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "event": event,
            "storage_allowed": not blocked_reasons,
            "write_performed": False,
            "rows_written": 0,
            # Constants: this reduction carries none of them, and says so where
            # a reader is looking.
            "token_recorded": False,
            "jwks_recorded": False,
            "subject_recorded": False,
            "email_recorded": False,
            "audience_value_recorded": False,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def record_validation_evidence(
    *,
    connection: Any = None,
    verification: dict[str, Any] | None = None,
    jwks_fetch: dict[str, Any] | None = None,
    provider_called: bool = False,
    evidence_source: str = "oauth_callback",
    event_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write one sanitized validation event, if the reduction permits it."""
    decision = build_validation_event(
        verification=verification,
        jwks_fetch=jwks_fetch,
        provider_called=provider_called,
        evidence_source=evidence_source,
    )
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if decision["storage_allowed"] and connection is not None:
        connection.execute(
            sa.insert(VALIDATION_EVENTS).values(
                id=event_id or uuid.uuid4(),
                occurred_at=now or datetime.now(UTC),
                **decision["event"],
            )
        )
        written = 1

    return _json_safe(
        {
            **decision,
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def build_jwks_validation_evidence(*, connection: Any = None) -> dict[str, Any]:
    """Has issuer/JWKS validation actually happened? Ask the table."""
    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "connection_supplied": False,
                "event_rows": 0,
                "verified_event_rows": 0,
                "issuers_validated": [],
                "issuer_jwks_validated": False,
                "provider_called": False,
                "last_verified_at": None,
                "blocked_reasons": ["no_connection_supplied"],
            }
        )

    blocked_reasons: list[str] = []
    total = 0
    verified_rows = 0
    issuers: list[str] = []
    provider_called = False
    last_verified: str | None = None

    try:
        total = int(
            connection.execute(
                sa.select(sa.func.count()).select_from(VALIDATION_EVENTS)
            ).scalar_one()
        )
        rows = (
            connection.execute(
                sa.select(
                    VALIDATION_EVENTS.c.issuer,
                    VALIDATION_EVENTS.c.occurred_at,
                    VALIDATION_EVENTS.c.provider_called,
                ).where(
                    VALIDATION_EVENTS.c.verification_state == "verified",
                    VALIDATION_EVENTS.c.issuer_validated.is_(True),
                    VALIDATION_EVENTS.c.jwks_validated.is_(True),
                    VALIDATION_EVENTS.c.id_token_signature_validated.is_(True),
                    VALIDATION_EVENTS.c.audience_validated.is_(True),
                )
            )
            .mappings()
            .all()
        )
    except Exception:
        blocked_reasons.append("validation_event_table_unreadable")
        rows = []

    for row in rows:
        verified_rows += 1
        issuer = str(row["issuer"] or "").strip()
        if issuer and issuer not in issuers:
            issuers.append(issuer)
        provider_called = provider_called or bool(row["provider_called"])
        moment = row["occurred_at"]
        stamp = moment.isoformat() if hasattr(moment, "isoformat") else str(moment)
        if last_verified is None or stamp > last_verified:
            last_verified = stamp

    # Derived affirmatively: a verified event, from a named issuer, that
    # actually reached the provider.
    validated = bool(
        verified_rows and issuers and provider_called and not blocked_reasons
    )
    if not verified_rows:
        blocked_reasons.append("no_verified_validation_event_recorded")
    elif not provider_called:
        # An event that verified without the provider being called is an offline
        # replay, not a live validation.
        blocked_reasons.append("no_validation_event_reached_the_provider")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "connection_supplied": True,
            "event_rows": total,
            "verified_event_rows": verified_rows,
            "issuers_validated": sorted(issuers),
            "issuer_jwks_validated": validated,
            "provider_called": provider_called,
            "last_verified_at": last_verified,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def validation_evidence_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("issuer_jwks_validated") and not result.get("connection_supplied"):
        fails.append("issuer_jwks_validated_without_reading_anything")
    if result.get("issuer_jwks_validated") and not result.get("verified_event_rows"):
        fails.append("issuer_jwks_validated_without_a_verified_event")
    if result.get("issuer_jwks_validated") and not result.get("provider_called"):
        fails.append("issuer_jwks_validated_without_the_provider_being_called")
    if result.get("issuer_jwks_validated") and not result.get("issuers_validated"):
        fails.append("issuer_jwks_validated_without_a_named_issuer")
    if result.get("verified_event_rows", 0) > result.get("event_rows", 0):
        fails.append("more_verified_events_than_events")

    return fails


def event_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a reduction that kept something it must not keep."""
    fails: list[str] = []
    event = result.get("event") or {}

    for key in event:
        if key not in EVENT_FIELDS:
            fails.append(f"event_carries_an_unknown_field:{key}")
    for key in FORBIDDEN_EVENT_KEYS:
        if key in event:
            fails.append(f"event_carries_a_forbidden_field:{key}")

    # A value check as well as a key check. Gate 131 was bitten eight times by
    # matching a marker against a field NAME; a token is a value, never a key.
    for key, value in event.items():
        if not isinstance(value, str):
            continue
        if "@" in value:
            fails.append(f"event_carries_an_email_in:{key}")
        # A compact JWS has two dots and a base64url header that starts `ey`.
        if value.count(".") == 2 and value.startswith("ey"):
            fails.append(f"event_carries_a_token_in:{key}")

    if event.get("id_token_signature_validated") and not event.get("jwks_validated"):
        fails.append("signature_validated_without_a_jwks_document")
    if event.get("verification_state") == "verified" and not all(
        event.get(name)
        for name in (
            "issuer_validated",
            "jwks_validated",
            "id_token_signature_validated",
            "audience_validated",
        )
    ):
        fails.append("verified_state_without_every_validation")

    for name in (
        "token_recorded",
        "jwks_recorded",
        "subject_recorded",
        "email_recorded",
        "audience_value_recorded",
    ):
        if result.get(name) is True:
            fails.append(name)

    return fails
