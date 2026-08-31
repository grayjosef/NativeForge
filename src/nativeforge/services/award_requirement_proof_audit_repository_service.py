"""Award requirement proof audit repository (Gate 126C).

The database boundary for `nf_award_requirement_proof_events`, anchored on
`organization_id` and linked to `award_requirement_id`.

## The last post-award persistence lane

```text
Gate 124   nf_awarded_grants          an award
Gate 125   nf_award_requirements      what it obliges
Gate 126   ..._proof_events           what was filed, and what happened to it
```

Gate 108 built the proof/audit contract — `record_proof_action`,
`build_audit_trail`, 329 lines — and had nowhere to put an event.

## Three identifiers, one authority

```text
organization_id       UUID, FK organizations, the RLS predicate's left side
award_requirement_id  UUID, FK nf_award_requirements, a row relationship
awarded_grant_id      UUID, FK nf_awarded_grants, context, nullable
```

Both of the last two are in `FORBIDDEN_ANCHOR_NAMES`, alongside `tenant_id`,
`customer_org_id` and `organization_profile_id`. The policy reads
`organization_id`; reaching it through two joins would make this table's policy
depend on two other tables' policies, which is the substitution Gates 110-113
exist to refuse.

`awarded_grant_id` is denormalised on purpose so a portfolio view need not join
through the requirement. It is context, not a second relationship, and an
invariant refuses it standing in for the anchor.

## Append-first, and the two writes that are not

```text
create_proof_event      INSERT. The only way an event enters the trail.
supersede_proof_event   INSERT a new event, UPDATE the old one's superseded_at
archive_proof_event     UPDATE archived_at
```

Both updates are one-way and touch one column each. Everything else about an
event is written once and `rows_deleted` is a constant `0`.
There is no DELETE path, asserted by parsing this module rather than grepping
it — Gate 123 found a substring search matching the sentence that explains the
absence.

Superseding is the interesting one. It does **not** replace: the prior event
keeps its reference, its timestamps and its actor, and the new event points back
through `supersedes_event_id`. A chain is ordinary, so an event can carry both a
`supersedes_event_id` and a `superseded_at`.

## Four things a proof event is not

```text
a document reference is not a document      there is no document store
a document reference is not a filing        somebody has to submit it
a filing is not an acceptance               a funder has to accept it
a rejection is not a deletion               the reference is retained
```

The last one has a CHECK behind it
(`ck_nf_proof_events_rejection_retains_the_proof`), because a rejection that
erased what was filed would make "we rejected it" indistinguishable from
"nothing was ever filed" — opposite facts about the same Tribe.

## The requirement's proof status is derived, not written back

`derive_current_proof_status` folds a requirement's events and returns what its
proof status is now. It is never written onto `nf_award_requirements`: two
writers on one column is how the two come to disagree, and Gate 125's
`proof_status` already carries its own CHECK constraints.

## Production writes need two things that are both false

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable so the permitted branch is reachable in a test, both false in
reality.

```text
rows in the application database   0
production proof records created   0
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_requirement_proof_audit_persistence_validation_service import (  # noqa: E501
    ADDED_EVENT_TYPES,
    BRIDGED_EVENT_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    FUNDER_DECIDED_STATUSES,
    PROOF_SOURCES,
    derive_current_proof_status,
    validate_proof_event,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirement_proof_audit_repository_v1"

TABLE_NAME = "nf_award_requirement_proof_events"

RLS_ANCHOR_COLUMN = "organization_id"

# Required on every row, and never an anchor.
ROW_RELATIONSHIP_COLUMN = "award_requirement_id"

# Carried for convenience, and never an anchor either.
CONTEXT_COLUMN = "awarded_grant_id"

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_proof_event_write",
        "create_proof_event",
        "get_proof_event",
        "list_proof_events_for_requirement",
        "list_proof_events_for_organization",
        "supersede_proof_event",
        "archive_proof_event",
        "validate_proof_event_persistence",
    }
)

WRITE_OPERATIONS = frozenset(
    {"create_proof_event", "supersede_proof_event", "archive_proof_event"}
)
READ_OPERATIONS = frozenset(
    {
        "get_proof_event",
        "list_proof_events_for_requirement",
        "list_proof_events_for_organization",
    }
)

# Names that may never anchor a row. Both relationship columns are here for the
# same reason: neither can be cast into the RLS predicate.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {
        "tenant_id",
        "customer_org_id",
        "organization_profile_id",
        "award_requirement_id",
        "awarded_grant_id",
    }
)

# The only columns an already-written event may gain. Both one-way.
POST_INSERT_WRITABLE_COLUMNS: tuple[str, ...] = ("superseded_at", "archived_at")

_METADATA = sa.MetaData()

# Mirrors migration 0034 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production. Two tests compare the definitions by name.
PROOF_EVENTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("award_requirement_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("awarded_grant_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("event_type", sa.String(length=32), nullable=False),
    sa.Column("event_status", sa.String(length=32), nullable=False),
    sa.Column("proof_document_ref", sa.Text(), nullable=True),
    sa.Column("proof_document_storage_available", sa.Boolean(), nullable=False),
    sa.Column("proof_summary", sa.Text(), nullable=True),
    sa.Column("proof_source", sa.String(length=32), nullable=False),
    sa.Column("proof_source_ref", sa.Text(), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("supersedes_event_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "event_type IN ('attach_proof', 'mark_submitted', 'mark_accepted', "
        "'mark_rejected', 'mark_waived', 'proof_requested', "
        "'proof_needs_review', 'proof_superseded', 'audit_note_added', "
        "'unknown')",
        name="ck_nf_proof_events_event_type",
    ),
    sa.CheckConstraint(
        "event_status IN ('not_submitted', 'proof_missing', 'proof_attached', "
        "'proof_accepted', 'proof_rejected', 'unknown')",
        name="ck_nf_proof_events_event_status",
    ),
    sa.CheckConstraint(
        "proof_source IN ('human_entered', 'evidence_extracted', "
        "'system_generated', 'unsupported_document_type', 'needs_human_review', "
        "'unknown')",
        name="ck_nf_proof_events_proof_source",
    ),
    sa.CheckConstraint(
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture', "
        "'unknown', 'needs_human_review')",
        name="ck_nf_proof_events_fact_status",
    ),
    sa.CheckConstraint(
        "event_status <> 'proof_accepted' OR accepted_at IS NOT NULL",
        name="ck_nf_proof_events_accepted_needs_a_timestamp",
    ),
    sa.CheckConstraint(
        "accepted_at IS NULL OR submitted_at IS NOT NULL",
        name="ck_nf_proof_events_accepted_needs_submitted",
    ),
    sa.CheckConstraint(
        "event_status <> 'proof_accepted' OR proof_document_ref IS NOT NULL",
        name="ck_nf_proof_events_accepted_needs_a_reference",
    ),
    sa.CheckConstraint(
        "event_status <> 'proof_rejected' OR rejected_at IS NOT NULL",
        name="ck_nf_proof_events_rejected_needs_a_timestamp",
    ),
    sa.CheckConstraint(
        "event_status <> 'proof_rejected' OR proof_document_ref IS NOT NULL",
        name="ck_nf_proof_events_rejection_retains_the_proof",
    ),
    sa.CheckConstraint(
        "accepted_at IS NULL OR rejected_at IS NULL",
        name="ck_nf_proof_events_not_accepted_and_rejected",
    ),
    sa.CheckConstraint(
        "(event_type = 'proof_superseded') = (supersedes_event_id IS NOT NULL)",
        name="ck_nf_proof_events_supersede_names_its_predecessor",
    ),
    sa.CheckConstraint(
        "supersedes_event_id IS NULL OR supersedes_event_id <> id",
        name="ck_nf_proof_events_nothing_supersedes_itself",
    ),
    sa.CheckConstraint(
        "NOT proof_document_storage_available OR proof_document_ref IS NOT NULL",
        name="ck_nf_proof_events_storage_flag_needs_a_store",
    ),
    sa.CheckConstraint(
        "(reviewed_at IS NULL) = (reviewed_by_identity_id IS NULL)",
        name="ck_nf_proof_events_review_pair",
    ),
    sa.CheckConstraint(
        "event_status NOT IN ('proof_accepted', 'proof_rejected') OR "
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
        name="ck_nf_proof_events_funder_decision_needs_established_facts",
    ),
    sa.CheckConstraint(
        "event_type <> 'audit_note_added' OR "
        "(accepted_at IS NULL AND rejected_at IS NULL AND submitted_at IS NULL)",
        name="ck_nf_proof_events_a_note_decides_nothing",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    """Can this survive the ``::uuid`` cast the RLS policy performs?"""
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(moment: Any) -> str | None:
    parsed = _as_datetime(moment)
    return parsed.isoformat() if parsed else None


def _result(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "rls_anchor": RLS_ANCHOR_COLUMN,
        # Constants. This repository appends, supersedes and archives. It never
        # deletes, never resolves a document reference, and never writes back
        # onto the requirement.
        "rows_deleted": 0,
        "history_preserved": True,
        "audit_record_deleted": False,
        "proof_deleted": False,
        "real_customer_rows_written": 0,
        "production_proof_records_created": 0,
        "production_award_requirements_created": 0,
        # This gate built a column that names a document, not a store.
        "document_storage_built_by_gate_126": False,
        "written_back_to_requirement": False,
        "submission_inferred_from_document": False,
        "acceptance_inferred_from_submission": False,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    out["refused_claims"] = sorted(set(fields.get("refused_claims") or []))
    return _json_safe(out)


def prepare_proof_event_write(
    *,
    organization_id: Any = None,
    award_requirement_id: Any = None,
    awarded_grant_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    event_type: Any = None,
    event_status: Any = None,
    proof_document_ref: Any = None,
    proof_document_storage_available: bool = False,
    proof_summary: Any = None,
    proof_source: Any = None,
    proof_source_ref: Any = None,
    submitted_at: Any = None,
    accepted_at: Any = None,
    rejected_at: Any = None,
    reviewed_at: Any = None,
    reviewed_by_identity_id: Any = None,
    supersedes_event_id: Any = None,
    superseded_at: Any = None,
    fact_status: Any = None,
    created_by_identity_id: Any = None,
    is_demo: bool = False,
    customer_auth_live: bool = False,
    verified_operational_binding: bool = False,
    document_storage_available: bool = False,
) -> dict[str, Any]:
    """Decide whether a proof event may be written. Touches no database."""
    blocked_reasons: list[str] = []

    # -- the anchor ----------------------------------------------------------
    if not str(organization_id or "").strip():
        blocked_reasons.append("proof_event_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # -- the relationship, required and never authority ----------------------
    if not str(award_requirement_id or "").strip():
        blocked_reasons.append("proof_event_without_an_award_requirement_id")
    elif not _uuid_shaped(award_requirement_id):
        blocked_reasons.append("award_requirement_id_is_not_uuid_shaped")
    elif not str(organization_id or "").strip():
        blocked_reasons.append("award_requirement_id_is_not_an_organization_id_anchor")

    # -- the context, optional and never authority ---------------------------
    grant = str(awarded_grant_id or "").strip()
    if grant and not _uuid_shaped(grant):
        blocked_reasons.append("awarded_grant_id_is_not_uuid_shaped")
    if grant and not str(organization_id or "").strip():
        blocked_reasons.append("awarded_grant_id_is_not_an_organization_id_anchor")

    # -- labels refused outright ---------------------------------------------
    for name, value in (
        ("tenant_id", tenant_id),
        ("customer_org_id", customer_org_id),
        ("organization_profile_id", organization_profile_id),
    ):
        if str(value or "").strip():
            blocked_reasons.append(f"{name}_is_not_an_organization_id_anchor")

    # -- the event itself ----------------------------------------------------
    validation = validate_proof_event(
        event_type=event_type,
        event_status=event_status,
        proof_document_ref=proof_document_ref,
        proof_document_storage_available=proof_document_storage_available,
        proof_summary=proof_summary,
        proof_source=proof_source,
        proof_source_ref=proof_source_ref,
        submitted_at=submitted_at,
        accepted_at=accepted_at,
        rejected_at=rejected_at,
        reviewed_at=reviewed_at,
        reviewed_by_identity_id=reviewed_by_identity_id,
        supersedes_event_id=supersedes_event_id,
        superseded_at=superseded_at,
        fact_status=fact_status,
        document_storage_available=document_storage_available,
    )
    blocked_reasons.extend(validation["blocked_reasons"])
    # Not merged into blocked_reasons: these refuse a claim, not the row. A
    # rejected proof and a superseded one both belong in the trail.
    refused_claims = list(validation["refused_claims"])

    if reviewed_by_identity_id and not _uuid_shaped(reviewed_by_identity_id):
        blocked_reasons.append("reviewed_by_identity_id_is_not_uuid_shaped")
    if supersedes_event_id and not _uuid_shaped(supersedes_event_id):
        blocked_reasons.append("supersedes_event_id_is_not_uuid_shaped")

    # -- who may write, and whether this is a production write ---------------
    demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
    production_write = not demo_fixture

    if production_write and not customer_auth_live:
        blocked_reasons.append(
            "production_proof_event_write_requires_live_customer_auth"
        )
    if production_write and not verified_operational_binding:
        blocked_reasons.append(
            "production_proof_event_write_requires_a_verified_operational_binding"
        )

    storage_allowed = not blocked_reasons
    production_write_allowed = bool(storage_allowed and production_write)

    result = _result(
        operation="prepare_proof_event_write",
        organization_id=str(organization_id or "") or None,
        award_requirement_id=str(award_requirement_id or "") or None,
        awarded_grant_id=grant or None,
        event_type=validation["event_type"],
        event_status=validation["event_status"],
        proof_document_ref=validation["proof_document_ref"],
        proof_document_storage_available=validation["proof_document_storage_available"],
        proof_summary=validation["proof_summary"],
        proof_source=validation["proof_source"],
        proof_source_ref=validation["proof_source_ref"],
        submitted_at=validation["submitted_at"],
        accepted_at=validation["accepted_at"],
        rejected_at=validation["rejected_at"],
        reviewed_at=validation["reviewed_at"],
        reviewed_by_identity_id=validation["reviewed_by_identity_id"],
        supersedes_event_id=validation["supersedes_event_id"],
        superseded_at=validation["superseded_at"],
        # Derived by Gate 126D, never supplied.
        submission_recorded=validation["submission_recorded"],
        proof_is_accepted=validation["proof_is_accepted"],
        proof_is_rejected=validation["proof_is_rejected"],
        proof_retained=validation["proof_retained"],
        fact_status=validation["fact_status"],
        fact_status_supports_a_decision=validation["fact_status_supports_a_decision"],
        created_by_identity_id=str(created_by_identity_id or "") or None,
        archived_at=None,
        demo_fixture=demo_fixture,
        human_review_required=bool(validation["human_review_required"]),
        storage_allowed=storage_allowed,
        production_write_allowed=production_write_allowed,
        write_performed=False,
        read_performed=False,
        rows_written=0,
        rows_read=0,
        refused_claims=refused_claims,
        blocked_reasons=blocked_reasons,
    )
    result["validation"] = validation
    return _json_safe(result)


def _insert_values(decision: dict[str, Any], event_id: uuid.UUID, moment: datetime):
    return {
        "id": event_id,
        "organization_id": _as_uuid(decision["organization_id"]),
        "award_requirement_id": _as_uuid(decision["award_requirement_id"]),
        "awarded_grant_id": _as_uuid(decision["awarded_grant_id"]),
        "event_type": decision["event_type"],
        "event_status": decision["event_status"],
        "proof_document_ref": decision["proof_document_ref"],
        "proof_document_storage_available": bool(
            decision["proof_document_storage_available"]
        ),
        "proof_summary": decision["proof_summary"],
        "proof_source": decision["proof_source"],
        "proof_source_ref": decision["proof_source_ref"],
        "submitted_at": _as_datetime(decision["submitted_at"]),
        "accepted_at": _as_datetime(decision["accepted_at"]),
        "rejected_at": _as_datetime(decision["rejected_at"]),
        "reviewed_at": _as_datetime(decision["reviewed_at"]),
        "reviewed_by_identity_id": _as_uuid(decision["reviewed_by_identity_id"]),
        "supersedes_event_id": _as_uuid(decision["supersedes_event_id"]),
        "superseded_at": None,
        "fact_status": decision["fact_status"],
        "human_review_required": bool(decision["human_review_required"]),
        "created_by_identity_id": _as_uuid(decision["created_by_identity_id"]),
        "archived_at": None,
        "is_demo": bool(decision["demo_fixture"]),
        "blocked_reasons": [],
        "created_at": moment,
        "updated_at": moment,
    }


def create_proof_event(
    *,
    connection: Any = None,
    event_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Append one proof event. The only way an event enters the trail.

    There is no upsert and no update of an event's own facts. What was believed
    at the time is what the row says, forever.
    """
    decision = prepare_proof_event_write(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if decision["storage_allowed"] and connection is not None:
        connection.execute(
            sa.insert(PROOF_EVENTS).values(
                **_insert_values(decision, event_id or uuid.uuid4(), moment)
            )
        )
        written = 1

    return _result(
        **{
            **decision,
            "operation": "create_proof_event",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "event_id": str(row["id"]),
        "organization_id": str(row["organization_id"]),
        "award_requirement_id": str(row["award_requirement_id"]),
        "awarded_grant_id": (
            str(row["awarded_grant_id"]) if row["awarded_grant_id"] else None
        ),
        "event_type": row["event_type"],
        "event_status": row["event_status"],
        "proof_document_ref": row["proof_document_ref"],
        "proof_document_storage_available": bool(
            row["proof_document_storage_available"]
        ),
        "proof_summary": row["proof_summary"],
        "proof_source": row["proof_source"],
        "proof_source_ref": row["proof_source_ref"],
        "submitted_at": _iso(row["submitted_at"]),
        "accepted_at": _iso(row["accepted_at"]),
        "rejected_at": _iso(row["rejected_at"]),
        "reviewed_at": _iso(row["reviewed_at"]),
        "reviewed_by_identity_id": (
            str(row["reviewed_by_identity_id"])
            if row["reviewed_by_identity_id"]
            else None
        ),
        "supersedes_event_id": (
            str(row["supersedes_event_id"]) if row["supersedes_event_id"] else None
        ),
        "superseded_at": _iso(row["superseded_at"]),
        "fact_status": row["fact_status"],
        "created_by_identity_id": (
            str(row["created_by_identity_id"])
            if row["created_by_identity_id"]
            else None
        ),
        "archived_at": _iso(row["archived_at"]),
        "created_at": _iso(row["created_at"]),
        "demo_fixture": bool(row["is_demo"]),
        "human_review_required": bool(row["human_review_required"]),
    }


def _empty_facts() -> dict[str, Any]:
    return {
        "event_id": None,
        "award_requirement_id": None,
        "awarded_grant_id": None,
        "event_type": None,
        "event_status": None,
        "proof_document_ref": None,
        "proof_document_storage_available": False,
        "proof_summary": None,
        "proof_source": None,
        "proof_source_ref": None,
        "submitted_at": None,
        "accepted_at": None,
        "rejected_at": None,
        "reviewed_at": None,
        "reviewed_by_identity_id": None,
        "supersedes_event_id": None,
        "superseded_at": None,
        "fact_status": None,
        "created_by_identity_id": None,
        "archived_at": None,
        "created_at": None,
        "demo_fixture": False,
        "human_review_required": True,
    }


def _scoped(organization_id: Any, include_archived: bool) -> Any:
    query = sa.select(PROOF_EVENTS).where(
        PROOF_EVENTS.c.organization_id == _as_uuid(organization_id)
    )
    if not include_archived:
        query = query.where(PROOF_EVENTS.c.archived_at.is_(None))
    return query


def get_proof_event(
    *,
    connection: Any = None,
    organization_id: Any = None,
    event_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One event, anchored on ``organization_id``.

    Archived events are included by default: an audit trail that hid one would
    make it indistinguishable from an event that never happened.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = _scoped(organization_id, include_archived)
        if event_id and _uuid_shaped(event_id):
            query = query.where(PROOF_EVENTS.c.id == _as_uuid(event_id))
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_proof_event_for_this_organization")

    facts = _row_to_facts(row) if row is not None else _empty_facts()

    return _result(
        operation="get_proof_event",
        organization_id=str(organization_id or "") or None,
        **{k: v for k, v in facts.items() if k != "organization_id"},
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=row is not None,
        rows_written=0,
        rows_read=1 if row is not None else 0,
        blocked_reasons=blocked_reasons,
    )


def _listing(
    *,
    operation: str,
    connection: Any,
    organization_id: Any,
    award_requirement_id: Any,
    include_archived: bool,
) -> dict[str, Any]:
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if award_requirement_id is not None and not _uuid_shaped(award_requirement_id):
        blocked_reasons.append("award_requirement_id_is_not_uuid_shaped")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        query = _scoped(organization_id, include_archived)
        if award_requirement_id is not None:
            query = query.where(
                PROOF_EVENTS.c.award_requirement_id == _as_uuid(award_requirement_id)
            )
        rows = [
            _row_to_facts(r)
            for r in connection.execute(
                query.order_by(PROOF_EVENTS.c.created_at, PROOF_EVENTS.c.id)
            ).mappings()
        ]

    result = _result(
        operation=operation,
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "award_requirement_id": str(award_requirement_id or "") or None,
        },
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=bool(rows),
        rows_written=0,
        rows_read=len(rows),
        blocked_reasons=blocked_reasons,
    )
    result["events"] = rows
    result["archived_count"] = sum(1 for r in rows if r["archived_at"])
    result["superseded_count"] = sum(1 for r in rows if r["superseded_at"])
    result["live_count"] = sum(
        1 for r in rows if not r["archived_at"] and not r["superseded_at"]
    )
    result["accepted_count"] = sum(
        1 for r in rows if r["event_status"] == "proof_accepted"
    )
    result["rejected_count"] = sum(
        1 for r in rows if r["event_status"] == "proof_rejected"
    )
    # Derived over the trail. Never written back onto the requirement.
    result["derived_proof_status"] = derive_current_proof_status(rows)
    return _json_safe(result)


def list_proof_events_for_requirement(
    *,
    connection: Any = None,
    organization_id: Any = None,
    award_requirement_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One requirement's trail, still anchored on the organization.

    The requirement narrows; it does not scope. Both are required.
    """
    if not str(award_requirement_id or "").strip():
        return _result(
            operation="list_proof_events_for_requirement",
            organization_id=str(organization_id or "") or None,
            **_empty_facts(),
            storage_allowed=False,
            production_write_allowed=False,
            write_performed=False,
            read_performed=False,
            rows_written=0,
            rows_read=0,
            blocked_reasons=["listing_for_a_requirement_without_a_requirement_id"],
        )
    return _listing(
        operation="list_proof_events_for_requirement",
        connection=connection,
        organization_id=organization_id,
        award_requirement_id=award_requirement_id,
        include_archived=include_archived,
    )


def list_proof_events_for_organization(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Every proof event one organization holds, across every requirement."""
    return _listing(
        operation="list_proof_events_for_organization",
        connection=connection,
        organization_id=organization_id,
        award_requirement_id=None,
        include_archived=include_archived,
    )


def supersede_proof_event(
    *,
    connection: Any = None,
    organization_id: Any = None,
    superseded_event_id: Any = None,
    event_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Replace an event without removing it.

    Two rows change and neither loses anything:

    ```text
    the NEW row       inserted, carrying supersedes_event_id
    the REPLACED row  gains superseded_at, and keeps everything else
    ```

    The replaced row keeps its reference, its timestamps and its actor, so a
    funder's auditor can still read what was believed before the correction.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("supersede_without_a_uuid_shaped_anchor")
    if not _uuid_shaped(superseded_event_id):
        blocked_reasons.append("supersede_without_a_predecessor_id")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    decision = prepare_proof_event_write(
        organization_id=organization_id,
        supersedes_event_id=superseded_event_id,
        event_type="proof_superseded",
        **fields,
    )
    blocked_reasons.extend(decision["blocked_reasons"])

    moment = now or datetime.now(UTC)
    written = 0
    predecessor_retained = False

    if not blocked_reasons:
        prior = (
            connection.execute(
                sa.select(PROOF_EVENTS).where(
                    PROOF_EVENTS.c.organization_id == _as_uuid(organization_id),
                    PROOF_EVENTS.c.id == _as_uuid(superseded_event_id),
                    PROOF_EVENTS.c.superseded_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if prior is None:
            blocked_reasons.append("no_live_proof_event_to_supersede")
        else:
            connection.execute(
                sa.insert(PROOF_EVENTS).values(
                    **_insert_values(decision, event_id or uuid.uuid4(), moment)
                )
            )
            # The one permitted update: a single column, one-way. Everything
            # else about the replaced event is exactly as it was written.
            connection.execute(
                sa.update(PROOF_EVENTS)
                .where(PROOF_EVENTS.c.id == prior["id"])
                .values(superseded_at=moment, updated_at=moment)
            )
            written = 1
            predecessor_retained = True

    result = _result(
        **{
            **decision,
            "operation": "supersede_proof_event",
            "write_performed": bool(written),
            "rows_written": written,
            "superseded_event_id": str(superseded_event_id or "") or None,
            "predecessor_retained": predecessor_retained,
            "blocked_reasons": blocked_reasons,
        }
    )
    return result


def archive_proof_event(
    *,
    connection: Any = None,
    organization_id: Any = None,
    event_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Take an event out of the active view. An UPDATE, never a DELETE.

    Archiving does not change what the event says. It changes whether it is
    current, and a listing returns it regardless.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("archive_without_a_uuid_shaped_anchor")
    if not _uuid_shaped(event_id):
        blocked_reasons.append("archive_without_an_event_id")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if not blocked_reasons:
        row = (
            connection.execute(
                sa.select(PROOF_EVENTS).where(
                    PROOF_EVENTS.c.organization_id == _as_uuid(organization_id),
                    PROOF_EVENTS.c.id == _as_uuid(event_id),
                    PROOF_EVENTS.c.archived_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked_reasons.append("no_live_proof_event_to_archive")
        else:
            connection.execute(
                sa.update(PROOF_EVENTS)
                .where(PROOF_EVENTS.c.id == row["id"])
                .values(archived_at=moment, updated_at=moment)
            )
            written = 1

    return _result(
        operation="archive_proof_event",
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "event_id": str(event_id or "") or None,
            "archived_at": _iso(moment) if written else None,
        },
        storage_allowed=not blocked_reasons,
        production_write_allowed=False,
        write_performed=bool(written),
        read_performed=False,
        rows_written=written,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def validate_proof_event_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
    event_id: Any = None,
) -> dict[str, Any]:
    """Is what is stored fit to be read as an audit record?"""
    stored = get_proof_event(
        connection=connection, organization_id=organization_id, event_id=event_id
    )
    validation = validate_proof_event(
        event_type=stored.get("event_type"),
        event_status=stored.get("event_status"),
        proof_document_ref=stored.get("proof_document_ref"),
        proof_document_storage_available=bool(
            stored.get("proof_document_storage_available")
        ),
        proof_summary=stored.get("proof_summary"),
        proof_source=stored.get("proof_source"),
        proof_source_ref=stored.get("proof_source_ref"),
        submitted_at=stored.get("submitted_at"),
        accepted_at=stored.get("accepted_at"),
        rejected_at=stored.get("rejected_at"),
        reviewed_at=stored.get("reviewed_at"),
        reviewed_by_identity_id=stored.get("reviewed_by_identity_id"),
        supersedes_event_id=stored.get("supersedes_event_id"),
        superseded_at=stored.get("superseded_at"),
        fact_status=stored.get("fact_status"),
    )

    result = _result(
        **{
            **stored,
            "operation": "validate_proof_event_persistence",
            "blocked_reasons": sorted(
                {*stored["blocked_reasons"], *validation["blocked_reasons"]}
            ),
            "refused_claims": list(validation["refused_claims"]),
        }
    )
    result["validation"] = validation
    result["event_found"] = bool(stored["rows_read"])
    return _json_safe(result)


def proof_audit_repository_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    """Contradictions this repository must never be able to produce."""
    failures: list[str] = []

    operation = str(result.get("operation") or "")
    if operation not in REPOSITORY_OPERATIONS:
        failures.append("operation_outside_vocabulary")

    if result.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        failures.append("rls_anchor_is_not_organization_id")

    for name in sorted(FORBIDDEN_ANCHOR_NAMES):
        if result.get(f"{name}_anchor") or result.get(f"anchored_on_{name}"):
            failures.append(f"anchored_on_a_non_authority:{name}")

    if result.get("rows_deleted"):
        failures.append("a_proof_event_row_was_deleted")

    if result.get("audit_record_deleted") or result.get("proof_deleted"):
        failures.append("the_repository_claimed_a_deletion")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("production_proof_records_created"):
        failures.append("a_production_proof_record_was_created")

    if result.get("document_storage_built_by_gate_126"):
        failures.append("the_repository_claimed_it_built_a_document_store")

    if result.get("written_back_to_requirement"):
        failures.append("a_proof_status_was_written_back_onto_the_requirement")

    for field in (
        "submission_inferred_from_document",
        "acceptance_inferred_from_submission",
    ):
        if result.get(field):
            failures.append(f"the_repository_claimed_{field}")

    # The rules Gate 108 exists to protect. `proof_is_accepted` already
    # requires a submission, a reference and an established fact status, so
    # restating those here would be three lines that can never fail - the
    # shape Gate 125 found twice and this gate found five times. What is
    # checked instead is the pair drifting apart, guarded on storable so
    # ordinary bad input cannot reach it.
    storable = bool(result.get("storage_allowed"))
    if storable and result.get("event_status") == "proof_accepted":
        if not result.get("proof_is_accepted"):
            failures.append("a_storable_acceptance_did_not_derive_as_accepted")
    if storable and result.get("event_status") == "proof_rejected":
        if not result.get("proof_is_rejected"):
            failures.append("a_storable_rejection_did_not_derive_as_rejected")

    # A property of the service, not of the input.
    if result.get("proof_retained") is False:
        failures.append("the_repository_stopped_retaining_a_proof")

    if result.get("write_performed") and operation not in WRITE_OPERATIONS:
        failures.append("a_read_operation_reported_a_write")

    if result.get("rows_written") and not result.get("write_performed"):
        failures.append("rows_written_without_a_write")

    if result.get("write_performed") and not result.get("storage_allowed"):
        failures.append("a_write_happened_without_storage_being_allowed")

    if result.get("production_write_allowed") and result.get("demo_fixture"):
        failures.append("a_demo_fixture_claimed_a_production_write")

    if result.get("storage_allowed") and result.get("blocked_reasons"):
        remaining = [
            reason
            for reason in result["blocked_reasons"]
            if not reason.startswith("no_connection_supplied")
        ]
        if remaining:
            failures.append("storage_allowed_with_blocked_reasons_present")

    # Superseding retains. If it ever stopped, this is where it shows.
    if operation == "supersede_proof_event" and result.get("write_performed"):
        if not result.get("predecessor_retained"):
            failures.append("a_supersede_did_not_retain_its_predecessor")

    if operation in {"prepare_proof_event_write", "create_proof_event"}:
        if result.get("storage_allowed") and not result.get("award_requirement_id"):
            failures.append("an_event_was_storable_without_a_requirement")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))


def repository_vocabularies() -> dict[str, list[str]]:
    """The Gate 103/108 vocabularies this repository bridges, and what it adds."""
    return _json_safe(
        {
            "event_types": sorted(EVENT_TYPES),
            "event_types_bridged_from_gate_108": sorted(BRIDGED_EVENT_TYPES),
            "event_types_added_by_gate_126": sorted(ADDED_EVENT_TYPES),
            "event_statuses": sorted(EVENT_STATUSES),
            "funder_decided_statuses": sorted(FUNDER_DECIDED_STATUSES),
            "proof_sources": sorted(PROOF_SOURCES),
            "fact_statuses": sorted(FACT_STATUSES),
            "actionable_fact_statuses": sorted(ACTIONABLE_FACT_STATUSES),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "post_insert_writable_columns": list(POST_INSERT_WRITABLE_COLUMNS),
            "row_relationship_column": ROW_RELATIONSHIP_COLUMN,
            "context_column": CONTEXT_COLUMN,
        }
    )


def prohibited_inferences() -> tuple[tuple[str, str], ...]:
    """What this repository refuses to work out on somebody's behalf."""
    return (
        (
            "submission_from_document_reference",
            "attaching a document is not filing it",
        ),
        (
            "acceptance_from_submission",
            "filing something is not the funder accepting it",
        ),
        (
            "rejection_from_review_note",
            "a note records what somebody said. It decides nothing",
        ),
        (
            "document_from_document_reference",
            "there is no document store. The reference resolves to nothing",
        ),
        (
            "requirement_status_from_this_trail",
            "the current proof status is derived and returned, never written "
            "back. Two writers on one column is how the two come to disagree",
        ),
        (
            "deletion_from_rejection_or_supersession",
            "a rejected proof and a superseded one are both retained. An audit "
            "trail that can be rewritten is not one",
        ),
    )
