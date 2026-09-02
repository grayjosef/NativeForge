"""Gate 132: the first identity and the first membership actually get written.

Two tables have existed since Gate 62 and have never held a row, because
nothing in `src/` could insert into either:

```text
nf_identities        migration 0023   0 rows   0 INSERT statements in src/
nf_org_memberships   migration 0024   0 rows   0 INSERT statements in src/
```

`postgres_membership_directory_service` reads memberships. Reading a table
nothing writes is a query that has only ever returned the empty set, so every
"no membership found" answer in this codebase has been true for the wrong
reason. This module is the write side.

## Scope: demo organizations, and the database says which

Mayhem authorized exactly one organization, and an authorization sitting in a
chat log is not an enforcement. So this module refuses any organization whose
`organizations.org_type` is not `demo`, via
:mod:`demo_org_classification_service`.

`is_demo` is **derived**, and there is no parameter for it. That is the whole
argument for this module existing rather than a caller writing the INSERT: the
column pairs with the RLS predicate

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

so a caller-supplied `is_demo` is a caller-supplied choice of which partition a
row lands in. Rows go where the organization row says they go.

## An identity is a verified subject or it is nothing

`verification_source` accepts one value, `oidc_token_signature`, and migration
0023 has the CHECK that agrees. Not a preference: the alternatives on offer are
an email domain, a header, and a caller's assertion, and Gate 112 already
settled that none of those are authority.

`(issuer, subject)` is the key, not email. An email address gets reassigned; a
provider subject does not. The upsert refreshes `last_seen_at`, `email` and
`email_verified` and never rewrites the subject, because a subject that changed
is a different person.

## Self-approval, permitted exactly once

Migration 0024 requires `approved_by` for any source but `verified_directory`.
The first membership in an organization has nobody to approve it - the approver
would have to be a member, and there are none. So a bootstrap membership names
itself as approver, and this module permits that **only when the organization
has no memberships at all**.

The second self-approved membership is refused. Otherwise "the approver must
already be a member" degrades to "anyone may join by approving themselves",
which is not a weaker rule but the absence of one.

Checking that requires a connection, so an unconnected `prepare_` call cannot
clear self-approval and says so by name.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.demo_org_classification_service import (
    classification_invariant_failures,
    classify_organization,
)
from nativeforge.services.membership_directory_service import (
    ACTING_STATES,
    MEMBERSHIP_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
    TRUSTED_ROLE_SOURCES,
)

SCHEMA_VERSION = "nf_dev_org_membership_bootstrap_v1"

IDENTITY_TABLE = "nf_identities"
MEMBERSHIP_TABLE = "nf_org_memberships"

#: Migration 0023's CHECK, restated. A test parses the migration and compares.
VERIFICATION_SOURCES: frozenset[str] = frozenset({"oidc_token_signature"})

#: Migration 0024's role CHECK, restated. Same test.
STORABLE_ROLES: frozenset[str] = frozenset(
    {
        "org_owner",
        "org_admin",
        "authorized_representative",
        "grant_lead",
        "reviewer",
        "viewer",
    }
)

#: Migration 0024's state CHECK. `unknown` is in the service vocabulary and not
#: in the database's, so it is excluded by subtraction rather than by a second
#: hand-written list.
STORABLE_STATES: frozenset[str] = MEMBERSHIP_STATES - {"unknown"}

#: The only source that migration 0024 lets skip an approver.
SOURCE_NEEDING_NO_APPROVER = "verified_directory"

ROLE_SOURCE = "membership_record"

IDENTITY_RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "issuer",
    "subject_recorded",
    "email_recorded",
    "email_verified",
    "verification_source",
    "identity_id",
    "identity_existed",
    "storage_allowed",
    "write_performed",
    "rows_written",
    "blocked_reasons",
)

MEMBERSHIP_RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "organization_id",
    "identity_id",
    "org_type_in_database",
    "is_demo",
    "state",
    "role",
    "role_source",
    "membership_source",
    "approved_by",
    "self_approved",
    "bootstrap_membership",
    "existing_membership_count",
    "storage_allowed",
    "write_performed",
    "rows_written",
    "real_customer_rows_written",
    "blocked_reasons",
)

_METADATA = sa.MetaData()

# Mirrors migration 0023 including the constraints, for the same reason the
# binding repository does: a Core table with the columns and none of the checks
# is a test schema weaker than production, which passes writes the real database
# refuses.
IDENTITIES = sa.Table(
    IDENTITY_TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("subject", sa.String(length=255), nullable=False),
    sa.Column("issuer", sa.String(length=512), nullable=False),
    sa.Column("email", sa.String(length=320), nullable=True),
    sa.Column("email_verified", sa.Boolean(), nullable=False),
    sa.Column("verification_source", sa.String(length=64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "verification_source IN ('oidc_token_signature')",
        name="ck_nf_identities_verification_source",
    ),
    sa.UniqueConstraint("issuer", "subject", name="uq_nf_identities_issuer_subject"),
)

MEMBERSHIPS = sa.Table(
    MEMBERSHIP_TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("identity_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("state", sa.String(length=32), nullable=False),
    sa.Column("membership_source", sa.String(length=64), nullable=False),
    sa.Column("role", sa.String(length=64), nullable=True),
    sa.Column("role_source", sa.String(length=64), nullable=False),
    sa.Column("invited_by", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("approved_by", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    # Migration 0039. How this membership came to exist, when it came through
    # an invite. Nullable: the memberships that already exist did not, and
    # must not claim to.
    sa.Column("invite_id", sa.String(length=64), nullable=True),
    sa.UniqueConstraint(
        "organization_id", "identity_id", name="uq_nf_org_memberships_org_identity"
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _clean(value: Any) -> str:
    return str(value or "").strip()


# ---------------------------------------------------------------------------
# identities
# ---------------------------------------------------------------------------


def prepare_identity_upsert(
    *,
    issuer: Any = None,
    subject: Any = None,
    email: Any = None,
    email_verified: bool = False,
    verification_source: Any = None,
) -> dict[str, Any]:
    """May an identity row be written for this verified subject? No database.

    The result reports ``subject_recorded`` and ``email_recorded`` as booleans.
    The subject and the email are the two values in this flow that identify a
    real person, and a decision record that carries them is a decision record
    somebody will paste into a ticket.
    """
    iss = _clean(issuer)
    sub = _clean(subject)
    mail = _clean(email)
    source = _clean(verification_source).lower() or "unknown"

    blocked_reasons: list[str] = []

    if not iss:
        blocked_reasons.append("identity_without_an_issuer")
    if not sub:
        blocked_reasons.append("identity_without_a_subject")
    if source not in VERIFICATION_SOURCES:
        blocked_reasons.append(f"verification_source_not_trusted:{source}")

    # An unverified email may be stored - it is a contact detail - but it must
    # never be the reason the row exists, and nothing downstream may read it as
    # authority. Gate 112's rule, restated where the column is written.
    if mail and not email_verified:
        blocked_reasons.append("email_recorded_unverified_and_grants_nothing")

    storage_allowed = not [
        r for r in blocked_reasons if not r.startswith("email_recorded_unverified")
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "prepare_identity_upsert",
            "table_name": IDENTITY_TABLE,
            "issuer": iss,
            "subject_recorded": bool(sub),
            "email_recorded": bool(mail),
            "email_verified": bool(email_verified),
            "verification_source": source,
            "identity_id": None,
            "identity_existed": False,
            "storage_allowed": storage_allowed,
            "write_performed": False,
            "rows_written": 0,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def upsert_identity(
    *,
    connection: Any = None,
    identity_id: uuid.UUID | None = None,
    now: datetime | None = None,
    issuer: Any = None,
    subject: Any = None,
    email: Any = None,
    email_verified: bool = False,
    verification_source: Any = None,
) -> dict[str, Any]:
    """Insert the identity, or refresh the one already keyed by issuer+subject.

    Idempotent by ``(issuer, subject)``: signing in twice is one identity seen
    twice, and the second sign-in must not create a second person.
    """
    decision = prepare_identity_upsert(
        issuer=issuer,
        subject=subject,
        email=email,
        email_verified=email_verified,
        verification_source=verification_source,
    )
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    existed = False
    resolved_id: uuid.UUID | None = None

    if decision["storage_allowed"] and connection is not None:
        moment = now or datetime.now(UTC)
        iss = _clean(issuer)
        sub = _clean(subject)
        mail = _clean(email) or None

        existing = (
            connection.execute(
                sa.select(IDENTITIES.c.id).where(
                    IDENTITIES.c.issuer == iss, IDENTITIES.c.subject == sub
                )
            )
            .mappings()
            .first()
        )

        if existing is not None:
            existed = True
            resolved_id = _as_uuid(existing["id"])
            connection.execute(
                sa.update(IDENTITIES)
                .where(IDENTITIES.c.issuer == iss, IDENTITIES.c.subject == sub)
                .values(
                    email=mail,
                    email_verified=bool(email_verified),
                    last_seen_at=moment,
                )
            )
        else:
            resolved_id = identity_id or uuid.uuid4()
            connection.execute(
                sa.insert(IDENTITIES).values(
                    id=resolved_id,
                    subject=sub,
                    issuer=iss,
                    email=mail,
                    email_verified=bool(email_verified),
                    verification_source=decision["verification_source"],
                    created_at=moment,
                    last_seen_at=moment,
                    disabled_at=None,
                )
            )
            written = 1

    return _json_safe(
        {
            **decision,
            "operation": "upsert_identity",
            "identity_id": str(resolved_id) if resolved_id else None,
            "identity_existed": existed,
            "write_performed": bool(written) or existed,
            "rows_written": written,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


# ---------------------------------------------------------------------------
# memberships
# ---------------------------------------------------------------------------


def prepare_membership_insert(
    *,
    organization_id: Any = None,
    identity_id: Any = None,
    state: Any = "active",
    role: Any = None,
    membership_source: Any = None,
    approved_by: Any = None,
    invited_by: Any = None,
    invite_id: Any = None,
    connection: Any = None,
    org_type_in_database: str | None = None,
    demo_org_ids: frozenset[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Decide whether this membership may be written, and derive ``is_demo``.

    There is no ``is_demo`` parameter. The organization row supplies it.

    ## ``invited_by`` and ``invite_id``

    Gate 136. Both were hardcoded to ``None`` in the INSERT, so a membership
    produced by a completed invite could not say so and
    `evaluate_membership_provenance`'s refusal -
    `completed_invite_provenance_without_invite_id` - was unfalsifiable from
    the database.

    A membership naming an invite must name who invited it. Enforced here on
    every dialect and as a CHECK on PostgreSQL, for the same reason the
    self-dealing rule is in two places: the dev database is SQLite, and a
    guard that only fires in production is not a guard where it runs.
    """
    org_uuid = _as_uuid(organization_id)
    ident_uuid = _as_uuid(identity_id)
    st = _clean(state).lower() or "unknown"
    src = _clean(membership_source).lower() or "unknown"
    rl = _clean(role).lower() or None
    approver = _as_uuid(approved_by)
    inviter = _as_uuid(invited_by)
    invite = _clean(invite_id) or None

    blocked_reasons: list[str] = []

    if not _clean(organization_id):
        blocked_reasons.append("membership_without_an_organization_id_anchor")
    elif org_uuid is None:
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    if not _clean(identity_id):
        blocked_reasons.append("membership_without_an_identity_id")
    elif ident_uuid is None:
        blocked_reasons.append("identity_id_is_not_uuid_shaped")

    if st not in STORABLE_STATES:
        blocked_reasons.append(f"membership_state_not_storable:{st}")
    if src not in TRUSTED_MEMBERSHIP_SOURCES:
        blocked_reasons.append(f"membership_source_not_trusted:{src}")
    if rl is not None and rl not in STORABLE_ROLES:
        blocked_reasons.append(f"membership_role_not_storable:{rl}")
    if ROLE_SOURCE not in TRUSTED_ROLE_SOURCES:  # pragma: no cover - constant guard
        blocked_reasons.append(f"role_source_not_trusted:{ROLE_SOURCE}")

    # -- demo scope, derived from the organization row -----------------------
    classification = classify_organization(
        organization_id,
        connection=connection,
        demo_org_ids=demo_org_ids,
        org_type_in_database=org_type_in_database,
    )
    blocked_reasons.extend(
        f"organization_classification:{reason}"
        for reason in classification["blocked_reasons"]
    )
    is_demo = bool(classification["is_demo"])
    if classification["classification_available"] and not is_demo:
        # The authorization was demo-only, and this is where that is enforced
        # rather than remembered.
        blocked_reasons.append(
            "bootstrap_membership_refused_for_a_non_demo_organization"
        )

    # -- the approver, and the one case that has nobody to be ----------------
    self_approved = bool(approver is not None and approver == ident_uuid)
    existing_count: int | None = None
    bootstrap = False

    if src != SOURCE_NEEDING_NO_APPROVER and approver is None:
        blocked_reasons.append("membership_source_requires_an_approver")

    if invite is not None and inviter is None:
        blocked_reasons.append("membership_names_an_invite_without_naming_the_inviter")
    if inviter is not None and inviter == ident_uuid:
        # Inviting yourself into an organization is the membership half of the
        # invite service's self-dealing gap, and it arrives here by a different
        # road.
        blocked_reasons.append("membership_invited_by_the_member_themselves")

    if self_approved:
        if connection is None or org_uuid is None:
            blocked_reasons.append(
                "self_approval_needs_a_connection_to_prove_it_is_the_first_membership"
            )
        else:
            try:
                existing_count = int(
                    connection.execute(
                        sa.select(sa.func.count())
                        .select_from(MEMBERSHIPS)
                        .where(MEMBERSHIPS.c.organization_id == org_uuid)
                    ).scalar_one()
                )
            except Exception:
                blocked_reasons.append("existing_membership_count_unavailable")
            if existing_count == 0:
                bootstrap = True
            elif existing_count is not None:
                blocked_reasons.append(
                    "self_approval_permitted_only_for_the_first_membership"
                )

    storage_allowed = not blocked_reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "prepare_membership_insert",
            "table_name": MEMBERSHIP_TABLE,
            "organization_id": str(org_uuid) if org_uuid else None,
            "identity_id": str(ident_uuid) if ident_uuid else None,
            "org_type_in_database": classification["org_type_in_database"],
            "is_demo": is_demo,
            "state": st,
            "role": rl,
            "role_source": ROLE_SOURCE,
            "membership_source": src,
            "approved_by": str(approver) if approver else None,
            "invited_by": str(inviter) if inviter else None,
            "invite_id": invite,
            "self_approved": self_approved,
            "bootstrap_membership": bootstrap,
            "existing_membership_count": existing_count,
            "storage_allowed": storage_allowed,
            "write_performed": False,
            "rows_written": 0,
            # A demo membership is not customer data. Stated as a measured
            # constant so a future real-org path cannot inherit the claim.
            "real_customer_rows_written": 0,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def insert_membership(
    *,
    connection: Any = None,
    membership_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert one membership, if ``prepare_membership_insert`` permits it."""
    decision = prepare_membership_insert(connection=connection, **fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if decision["storage_allowed"] and connection is not None:
        moment = now or datetime.now(UTC)
        connection.execute(
            sa.insert(MEMBERSHIPS).values(
                id=membership_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                identity_id=_as_uuid(decision["identity_id"]),
                # Derived. Never the caller's.
                is_demo=bool(decision["is_demo"]),
                state=decision["state"],
                membership_source=decision["membership_source"],
                role=decision["role"],
                role_source=ROLE_SOURCE,
                # Gate 136: was hardcoded None, both of them.
                invited_by=_as_uuid(decision["invited_by"]),
                invite_id=decision["invite_id"],
                approved_by=_as_uuid(decision["approved_by"]),
                created_at=moment,
                revoked_at=None,
                expires_at=None,
            )
        )
        written = 1

    return _json_safe(
        {
            **decision,
            "operation": "insert_membership",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def bootstrap_invariant_failures(
    identity_result: dict[str, Any] | None = None,
    membership_result: dict[str, Any] | None = None,
) -> list[str]:
    """Refuse results that contradict the rules this module exists to hold."""
    fails: list[str] = []

    if identity_result is not None:
        if identity_result.get("rows_written") and not identity_result.get(
            "storage_allowed"
        ):
            fails.append("identity_written_without_storage_permission")
        if identity_result.get("rows_written") and identity_result.get(
            "identity_existed"
        ):
            fails.append("identity_inserted_when_one_already_existed")
        source = identity_result.get("verification_source")
        if identity_result.get("rows_written") and source not in VERIFICATION_SOURCES:
            fails.append("identity_written_under_an_untrusted_verification_source")
        # The subject and the email are values, never keys. A result that
        # carries either is a leak regardless of which field holds it.
        for key, value in identity_result.items():
            if isinstance(value, str) and key not in {
                "schema_version",
                "operation",
                "table_name",
                "issuer",
                "verification_source",
                "identity_id",
            }:
                if "@" in value:
                    fails.append(f"identity_result_carries_an_email_in:{key}")

    if membership_result is not None:
        if membership_result.get("rows_written") and not membership_result.get(
            "storage_allowed"
        ):
            fails.append("membership_written_without_storage_permission")
        if membership_result.get("rows_written") and not membership_result.get(
            "is_demo"
        ):
            fails.append("non_demo_membership_written_by_the_bootstrap_path")
        if membership_result.get("is_demo") and membership_result.get(
            "org_type_in_database"
        ) not in {"demo"}:
            fails.append("is_demo_true_while_the_organization_row_says_otherwise")
        if membership_result.get("self_approved") and not membership_result.get(
            "bootstrap_membership"
        ):
            if membership_result.get("rows_written"):
                fails.append("self_approved_membership_written_outside_the_bootstrap")
        if membership_result.get("role_source") not in TRUSTED_ROLE_SOURCES:
            fails.append("membership_role_source_not_trusted")
        if (
            membership_result.get("rows_written")
            and membership_result.get("state") not in STORABLE_STATES
        ):
            fails.append("membership_written_in_an_unstorable_state")
        if membership_result.get("real_customer_rows_written"):
            fails.append("bootstrap_path_reported_real_customer_rows")

    return fails


def acting_membership_states() -> frozenset[str]:
    """Bridged so a caller need not restate which state permits acting."""
    return ACTING_STATES


def classification_failures(result: dict[str, Any]) -> list[str]:
    """Re-exported so a caller checking one module checks both."""
    return classification_invariant_failures(result)
