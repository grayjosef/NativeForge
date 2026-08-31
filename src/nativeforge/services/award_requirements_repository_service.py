"""Award requirements repository (Gate 125C).

The database boundary for `nf_award_requirements`, anchored on
`organization_id` and linked to `awarded_grant_id`.

## What was missing

Gate 108 built the requirement model, the calendar and the proof audit — three
services, roughly 1,150 lines, all producing dictionaries with nowhere to put
them. Gate 124 gave awards a table and left this half deliberately: a
requirement recurs, so one award produces dozens of rows with their own due
dates and their own proof trail.

## Two identifiers, and only one of them is authority

```text
organization_id    UUID, FK organizations, the RLS predicate's left side
awarded_grant_id   UUID, FK nf_awarded_grants, a row relationship
```

Both are required and they answer different questions. `awarded_grant_id` says
which award this obliges; `organization_id` says who may read the row. Supplying
the first without the second is refused by name, because reaching the
organization through a join would make every policy on this table depend on a
policy on another one — the substitution Gates 110-113 exist to prevent.

```text
tenant_id                refused as an anchor
customer_org_id          refused as an anchor
organization_profile_id  refused as an anchor
awarded_grant_id         refused as an anchor, and required as a relationship
```

Unlike an award, a requirement carries no tenant-facing label of its own. It
inherits its tenant through the award, which is why there are no
`tenant_id_label` / `customer_org_id_label` columns here.

## A projection is not an obligation

Three booleans, all derived from `requirement_source` by Gate 125D and none of
them accepted as input:

```text
requirement_source                    active  projected  unsupported
human_entered / evidence_extracted    true    false      false
projected_from_nofo                   false   true       false
unsupported_document_type             false   false      true
unknown / needs_human_review          false   false      false
```

`prepare_requirement_write` has no parameter for any of the three. The
separation expressed as a signature, the same way Gate 124 refused a projection
parameter on the awards side.

## A projection is stored, and is not an obligation

Gate 125D returns two lists and this repository keeps them apart:

```text
blocked_reasons   the row may not be stored
refused_claims    the row is stored, and something it asserted was not
```

A projection belongs in this table. Recording what a NOFO projected beside the
award it became is how a Tribe sees what they expected against what they got,
and refusing to store it would make `projected_burden` an unreachable column —
which would leave every "a projection is not an obligation" test with no
projection to test.

So `storage_allowed` reads `blocked_reasons` only. `refused_claims` drives
`human_review_required` and appears in the result under its own name.

## An estimate is never counted down

`date_is_calculable` requires `due_date_status` in `{verified, calculated}`.
`estimated` is outside that set and the database agrees
(`ck_nf_award_requirements_calculable_status_needs_a_date` plus the validation's
refusal). A calendar with a visible gap prompts a human; a calendar with an
estimate in it does not.

## proof_document_ref points at nothing

There is no document store — `award_document_store_service` does not exist.
`document_storage_available` is a constant `False` and a reference supplied
without one is refused with a named reason. The column exists so a requirement
can record which document was filed once there is somewhere to file it.

## Archive, never delete

`archive_award_requirement` sets `archived_at` and leaves the row. `rows_deleted`
is a constant `0` and there is no DELETE path. A requirement recorded and later
found not to apply becomes `not_applicable`, which is a status a funder's audit
can read.

## Production writes need two things that are both false

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable so the permitted branch is reachable in a test, both false in
reality.

```text
rows in the application database      0
production award requirements created 0
production proof records created      0
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_requirement_model_service import (
    ACTIVE_CAPABLE_EXTRACTION_STATUSES,
    CLOSED_STATUSES,
    DATE_CALCULABLE_STATUSES,
    DUE_DATE_STATUSES,
    EXTRACTION_STATUSES,
    PROOF_STATUSES,
    RECURRENCES,
    REQUIREMENT_STATUSES,
    REQUIREMENT_TYPES,
    SUBMITTED_STATUSES,
)
from nativeforge.services.award_requirements_persistence_validation_service import (
    SUBMISSION_STATUSES,
    validate_award_requirement,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirements_repository_v1"

TABLE_NAME = "nf_award_requirements"

RLS_ANCHOR_COLUMN = "organization_id"

# Required on every row, and never an anchor. Named separately from the
# forbidden anchors below because those are refused outright and this one is
# refused only as *authority*.
ROW_RELATIONSHIP_COLUMN = "awarded_grant_id"

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_requirement_write",
        "create_award_requirement",
        "get_award_requirement",
        "list_requirements_for_award",
        "list_requirements_for_organization",
        "archive_award_requirement",
        "validate_requirement_persistence",
    }
)

WRITE_OPERATIONS = frozenset({"create_award_requirement", "archive_award_requirement"})
READ_OPERATIONS = frozenset(
    {
        "get_award_requirement",
        "list_requirements_for_award",
        "list_requirements_for_organization",
    }
)

# Names that may never anchor a row. `awarded_grant_id` is in this set because
# it is exactly the substitution this gate is most likely to be asked for.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {
        "tenant_id",
        "customer_org_id",
        "organization_profile_id",
        "awarded_grant_id",
    }
)

# Fields whose value is derived from provenance and can never be supplied.
DERIVED_ONLY_FIELDS: tuple[str, ...] = (
    "active_obligation",
    "projected_burden",
    "unsupported_requirement",
)

_METADATA = sa.MetaData()

# Mirrors migration 0033 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production. Two tests compare the definitions by name.
AWARD_REQUIREMENTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("awarded_grant_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("requirement_type", sa.String(length=48), nullable=False),
    sa.Column("requirement_title", sa.Text(), nullable=False),
    sa.Column("requirement_description", sa.Text(), nullable=True),
    sa.Column("requirement_status", sa.String(length=32), nullable=False),
    sa.Column("requirement_source", sa.String(length=32), nullable=False),
    sa.Column("requirement_source_ref", sa.Text(), nullable=True),
    sa.Column("requirement_due_date", sa.Date(), nullable=True),
    sa.Column("due_date_status", sa.String(length=32), nullable=False),
    sa.Column("recurrence_rule", sa.String(length=32), nullable=False),
    sa.Column("owner_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("proof_required", sa.Boolean(), nullable=False),
    sa.Column("proof_status", sa.String(length=32), nullable=False),
    sa.Column("proof_document_ref", sa.Text(), nullable=True),
    sa.Column("submission_status", sa.String(length=32), nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("active_obligation", sa.Boolean(), nullable=False),
    sa.Column("projected_burden", sa.Boolean(), nullable=False),
    sa.Column("unsupported_requirement", sa.Boolean(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("updated_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "requirement_type IN ('financial_report', 'narrative_report', "
        "'performance_measure', 'audit', 'closeout', 'match_documentation', "
        "'drawdown', 'reimbursement', 'budget_revision', 'subrecipient_report', "
        "'vendor_documentation', 'board_or_council_resolution', "
        "'document_retention', 'other', 'unknown')",
        name="ck_nf_award_requirements_type",
    ),
    sa.CheckConstraint(
        "requirement_status IN ('not_started', 'in_progress', 'submitted', "
        "'accepted', 'rejected', 'overdue', 'waived', 'not_applicable', "
        "'needs_human_review', 'unknown')",
        name="ck_nf_award_requirements_status",
    ),
    sa.CheckConstraint(
        "requirement_source IN ('human_entered', 'evidence_extracted', "
        "'projected_from_nofo', 'unsupported_document_type', "
        "'needs_human_review', 'unknown')",
        name="ck_nf_award_requirements_source",
    ),
    sa.CheckConstraint(
        "due_date_status IN ('verified', 'calculated', 'estimated', 'unknown', "
        "'unsupported', 'needs_human_review')",
        name="ck_nf_award_requirements_due_date_status",
    ),
    sa.CheckConstraint(
        "recurrence_rule IN ('one_time', 'monthly', 'quarterly', 'semi_annual', "
        "'annual', 'on_request', 'unknown')",
        name="ck_nf_award_requirements_recurrence",
    ),
    sa.CheckConstraint(
        "proof_status IN ('not_submitted', 'proof_missing', 'proof_attached', "
        "'proof_accepted', 'proof_rejected', 'unknown')",
        name="ck_nf_award_requirements_proof_status",
    ),
    sa.CheckConstraint(
        "submission_status IN ('not_submitted', 'submitted', 'accepted', "
        "'rejected', 'waived', 'needs_human_review', 'unknown')",
        name="ck_nf_award_requirements_submission_status",
    ),
    sa.CheckConstraint(
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture', "
        "'unknown', 'needs_human_review')",
        name="ck_nf_award_requirements_fact_status",
    ),
    sa.CheckConstraint(
        "length(trim(requirement_title)) > 0",
        name="ck_nf_award_requirements_title_not_blank",
    ),
    sa.CheckConstraint(
        "NOT (active_obligation AND projected_burden)",
        name="ck_nf_award_requirements_not_both_obligation_and_projection",
    ),
    sa.CheckConstraint(
        "NOT active_obligation OR requirement_source IN "
        "('human_entered', 'evidence_extracted')",
        name="ck_nf_award_requirements_obligation_needs_capable_source",
    ),
    sa.CheckConstraint(
        "projected_burden = (requirement_source = 'projected_from_nofo')",
        name="ck_nf_award_requirements_projection_matches_source",
    ),
    sa.CheckConstraint(
        "unsupported_requirement = (requirement_source = 'unsupported_document_type')",
        name="ck_nf_award_requirements_unsupported_matches_source",
    ),
    sa.CheckConstraint(
        "NOT (unsupported_requirement AND active_obligation)",
        name="ck_nf_award_requirements_unsupported_is_not_an_obligation",
    ),
    sa.CheckConstraint(
        "requirement_due_date IS NOT NULL OR NOT due_date_status IN "
        "('verified', 'calculated')",
        name="ck_nf_award_requirements_calculable_status_needs_a_date",
    ),
    sa.CheckConstraint(
        "requirement_due_date IS NULL OR due_date_status <> 'unknown'",
        name="ck_nf_award_requirements_date_needs_a_status",
    ),
    sa.CheckConstraint(
        "accepted_at IS NULL OR submitted_at IS NOT NULL",
        name="ck_nf_award_requirements_accepted_needs_submitted",
    ),
    sa.CheckConstraint(
        "proof_status <> 'proof_accepted' OR proof_document_ref IS NOT NULL",
        name="ck_nf_award_requirements_accepted_proof_needs_a_reference",
    ),
    sa.CheckConstraint(
        "NOT active_obligation OR "
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
        name="ck_nf_award_requirements_obligation_needs_established_facts",
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


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
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
    if moment is None:
        return None
    if isinstance(moment, datetime):
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return aware.isoformat()
    if isinstance(moment, date):
        return moment.isoformat()
    return str(moment)


def _result(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "rls_anchor": RLS_ANCHOR_COLUMN,
        # Constants. This repository inserts and archives; it never deletes,
        # never promotes a projection, and never resolves a document reference.
        "rows_deleted": 0,
        "history_preserved": True,
        "real_customer_rows_written": 0,
        "production_award_requirements_created": 0,
        "production_proof_records_created": 0,
        "projected_burden_promoted": False,
        "obligation_inferred_from_title": False,
        "due_date_inferred": False,
        "document_storage_available": False,
        "proof_audit_persistence_available": False,
    }
    out.update(fields)
    out["refused_claims"] = sorted(set(fields.get("refused_claims") or []))
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    return _json_safe(out)


def prepare_requirement_write(
    *,
    organization_id: Any = None,
    awarded_grant_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    requirement_type: Any = None,
    requirement_title: Any = None,
    requirement_description: Any = None,
    requirement_status: Any = None,
    requirement_source: Any = None,
    requirement_source_ref: Any = None,
    requirement_due_date: Any = None,
    due_date_status: Any = None,
    recurrence_rule: Any = None,
    owner_identity_id: Any = None,
    proof_required: bool = False,
    proof_status: Any = None,
    proof_document_ref: Any = None,
    submission_status: Any = None,
    submitted_at: Any = None,
    accepted_at: Any = None,
    rejected_at: Any = None,
    fact_status: Any = None,
    created_by_identity_id: Any = None,
    updated_by_identity_id: Any = None,
    is_demo: bool = False,
    customer_auth_live: bool = False,
    verified_operational_binding: bool = False,
    document_storage_available: bool = False,
) -> dict[str, Any]:
    """Decide whether a requirement may be written. Touches no database.

    There is deliberately no `active_obligation`, `projected_burden` or
    `unsupported_requirement` parameter. All three are derived from
    `requirement_source`, and a parameter for any of them would be a place to
    assert what the provenance does not support.
    """
    blocked_reasons: list[str] = []

    # -- the anchor ----------------------------------------------------------
    if not str(organization_id or "").strip():
        blocked_reasons.append("requirement_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # -- the relationship, which is required and is not the anchor -----------
    if not str(awarded_grant_id or "").strip():
        blocked_reasons.append("requirement_without_an_awarded_grant_id")
    elif not _uuid_shaped(awarded_grant_id):
        blocked_reasons.append("awarded_grant_id_is_not_uuid_shaped")
    elif not str(organization_id or "").strip():
        # The substitution this gate is most likely to be asked for, named
        # explicitly so a caller who tried it is told why it cannot work.
        blocked_reasons.append("awarded_grant_id_is_not_an_organization_id_anchor")

    # -- labels that are refused outright ------------------------------------
    for name, value in (
        ("tenant_id", tenant_id),
        ("customer_org_id", customer_org_id),
        ("organization_profile_id", organization_profile_id),
    ):
        if str(value or "").strip():
            blocked_reasons.append(f"{name}_is_not_an_organization_id_anchor")

    # -- the requirement itself ----------------------------------------------
    validation = validate_award_requirement(
        requirement_title=requirement_title,
        requirement_type=requirement_type,
        requirement_status=requirement_status,
        requirement_source=requirement_source,
        requirement_source_ref=requirement_source_ref,
        requirement_due_date=requirement_due_date,
        due_date_status=due_date_status,
        recurrence_rule=recurrence_rule,
        proof_required=proof_required,
        proof_status=proof_status,
        proof_document_ref=proof_document_ref,
        submission_status=submission_status,
        submitted_at=submitted_at,
        accepted_at=accepted_at,
        rejected_at=rejected_at,
        fact_status=fact_status,
        document_storage_available=document_storage_available,
    )
    blocked_reasons.extend(validation["blocked_reasons"])
    # Not merged into blocked_reasons: these refuse a claim, not the row.
    refused_claims = list(validation["refused_claims"])

    if owner_identity_id and not _uuid_shaped(owner_identity_id):
        blocked_reasons.append("owner_identity_id_is_not_uuid_shaped")

    # -- who may write, and whether this is a production write ---------------
    demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
    production_write = not demo_fixture

    if production_write and not customer_auth_live:
        blocked_reasons.append(
            "production_requirement_write_requires_live_customer_auth"
        )
    if production_write and not verified_operational_binding:
        blocked_reasons.append(
            "production_requirement_write_requires_a_verified_operational_binding"
        )

    storage_allowed = not blocked_reasons
    production_write_allowed = bool(storage_allowed and production_write)

    result = _result(
        operation="prepare_requirement_write",
        organization_id=str(organization_id or "") or None,
        awarded_grant_id=str(awarded_grant_id or "") or None,
        requirement_type=validation["requirement_type"],
        requirement_title=str(requirement_title or "").strip() or None,
        requirement_description=str(requirement_description or "") or None,
        requirement_status=validation["requirement_status"],
        requirement_source=validation["requirement_source"],
        requirement_source_ref=validation["requirement_source_ref"],
        requirement_due_date=validation["requirement_due_date"],
        due_date_status=validation["due_date_status"],
        date_is_calculable=validation["date_is_calculable"],
        recurrence_rule=validation["recurrence_rule"],
        owner_identity_id=str(owner_identity_id or "") or None,
        proof_required=bool(proof_required),
        proof_status=validation["proof_status"],
        proof_document_ref=validation["proof_document_ref"],
        submission_status=validation["submission_status"],
        submitted_at=_iso(submitted_at),
        accepted_at=_iso(accepted_at),
        rejected_at=_iso(rejected_at),
        # Derived, never supplied.
        active_obligation=validation["active_obligation"],
        projected_burden=validation["projected_burden"],
        unsupported_requirement=validation["unsupported_requirement"],
        fact_status=validation["fact_status"],
        created_by_identity_id=str(created_by_identity_id or "") or None,
        updated_by_identity_id=str(updated_by_identity_id or "") or None,
        archived_at=None,
        demo_fixture=demo_fixture,
        human_review_required=bool(validation["human_review_required"]),
        fact_status_supports_an_obligation=validation[
            "fact_status_supports_an_obligation"
        ],
        refused_claims=refused_claims,
        storage_allowed=storage_allowed,
        production_write_allowed=production_write_allowed,
        write_performed=False,
        read_performed=False,
        rows_written=0,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )
    result["validation"] = validation
    return _json_safe(result)


def create_award_requirement(
    *,
    connection: Any = None,
    requirement_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert one requirement, if ``prepare_requirement_write`` permits it.

    There is no upsert. A requirement that recurs is many rows, one per period,
    because a compliance calendar is a list of dated obligations and overwriting
    last quarter's row erases whether last quarter was met.
    """
    decision = prepare_requirement_write(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if decision["storage_allowed"] and connection is not None:
        connection.execute(
            sa.insert(AWARD_REQUIREMENTS).values(
                id=requirement_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                awarded_grant_id=_as_uuid(decision["awarded_grant_id"]),
                requirement_type=decision["requirement_type"],
                requirement_title=str(decision["requirement_title"]),
                requirement_description=decision["requirement_description"],
                requirement_status=decision["requirement_status"],
                requirement_source=decision["requirement_source"],
                requirement_source_ref=decision["requirement_source_ref"],
                requirement_due_date=_as_date(decision["requirement_due_date"]),
                due_date_status=decision["due_date_status"],
                recurrence_rule=decision["recurrence_rule"],
                owner_identity_id=_as_uuid(decision["owner_identity_id"]),
                proof_required=bool(decision["proof_required"]),
                proof_status=decision["proof_status"],
                proof_document_ref=decision["proof_document_ref"],
                submission_status=decision["submission_status"],
                submitted_at=_as_datetime(decision["submitted_at"]),
                accepted_at=_as_datetime(decision["accepted_at"]),
                rejected_at=_as_datetime(decision["rejected_at"]),
                active_obligation=bool(decision["active_obligation"]),
                projected_burden=bool(decision["projected_burden"]),
                unsupported_requirement=bool(decision["unsupported_requirement"]),
                fact_status=decision["fact_status"],
                human_review_required=bool(decision["human_review_required"]),
                created_by_identity_id=_as_uuid(decision["created_by_identity_id"]),
                updated_by_identity_id=_as_uuid(decision["updated_by_identity_id"]),
                archived_at=None,
                is_demo=bool(decision["demo_fixture"]),
                blocked_reasons=[],
                created_at=moment,
                updated_at=moment,
            )
        )
        written = 1

    return _result(
        **{
            **decision,
            "operation": "create_award_requirement",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "organization_id": str(row["organization_id"]),
        "awarded_grant_id": str(row["awarded_grant_id"]),
        "requirement_type": row["requirement_type"],
        "requirement_title": row["requirement_title"],
        "requirement_description": row["requirement_description"],
        "requirement_status": row["requirement_status"],
        "requirement_source": row["requirement_source"],
        "requirement_source_ref": row["requirement_source_ref"],
        "requirement_due_date": _iso(row["requirement_due_date"]),
        "due_date_status": row["due_date_status"],
        "date_is_calculable": bool(
            row["due_date_status"] in DATE_CALCULABLE_STATUSES
            and row["requirement_due_date"]
        ),
        "recurrence_rule": row["recurrence_rule"],
        "owner_identity_id": (
            str(row["owner_identity_id"]) if row["owner_identity_id"] else None
        ),
        "proof_required": bool(row["proof_required"]),
        "proof_status": row["proof_status"],
        "proof_document_ref": row["proof_document_ref"],
        "submission_status": row["submission_status"],
        "submitted_at": _iso(row["submitted_at"]),
        "accepted_at": _iso(row["accepted_at"]),
        "rejected_at": _iso(row["rejected_at"]),
        "active_obligation": bool(row["active_obligation"]),
        "projected_burden": bool(row["projected_burden"]),
        "unsupported_requirement": bool(row["unsupported_requirement"]),
        "fact_status": row["fact_status"],
        "created_by_identity_id": (
            str(row["created_by_identity_id"])
            if row["created_by_identity_id"]
            else None
        ),
        "updated_by_identity_id": (
            str(row["updated_by_identity_id"])
            if row["updated_by_identity_id"]
            else None
        ),
        "archived_at": _iso(row["archived_at"]),
        "demo_fixture": bool(row["is_demo"]),
        "human_review_required": bool(row["human_review_required"]),
    }


def _empty_facts() -> dict[str, Any]:
    return {
        "awarded_grant_id": None,
        "requirement_type": None,
        "requirement_title": None,
        "requirement_description": None,
        "requirement_status": None,
        "requirement_source": None,
        "requirement_source_ref": None,
        "requirement_due_date": None,
        "due_date_status": None,
        "date_is_calculable": False,
        "recurrence_rule": None,
        "owner_identity_id": None,
        "proof_required": False,
        "proof_status": None,
        "proof_document_ref": None,
        "submission_status": None,
        "submitted_at": None,
        "accepted_at": None,
        "rejected_at": None,
        "active_obligation": False,
        "projected_burden": False,
        "unsupported_requirement": False,
        "fact_status": None,
        "created_by_identity_id": None,
        "updated_by_identity_id": None,
        "archived_at": None,
        "demo_fixture": False,
        "human_review_required": True,
    }


def _scoped_query(organization_id: Any, include_archived: bool) -> Any:
    query = sa.select(AWARD_REQUIREMENTS).where(
        AWARD_REQUIREMENTS.c.organization_id == _as_uuid(organization_id)
    )
    if not include_archived:
        query = query.where(AWARD_REQUIREMENTS.c.archived_at.is_(None))
    return query


def get_award_requirement(
    *,
    connection: Any = None,
    organization_id: Any = None,
    requirement_id: Any = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    """One requirement, anchored on ``organization_id``.

    A requirement id narrows within the organization. It never selects on its
    own, because a read anchored on anything but the organization is a read the
    RLS policy cannot scope.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = _scoped_query(organization_id, include_archived)
        if requirement_id and _uuid_shaped(requirement_id):
            query = query.where(AWARD_REQUIREMENTS.c.id == _as_uuid(requirement_id))
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_award_requirement_for_this_organization")

    facts = _row_to_facts(row) if row is not None else _empty_facts()

    return _result(
        operation="get_award_requirement",
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
    awarded_grant_id: Any,
    include_archived: bool,
) -> dict[str, Any]:
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if awarded_grant_id is not None and not _uuid_shaped(awarded_grant_id):
        blocked_reasons.append("awarded_grant_id_is_not_uuid_shaped")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        query = _scoped_query(organization_id, include_archived)
        if awarded_grant_id is not None:
            query = query.where(
                AWARD_REQUIREMENTS.c.awarded_grant_id == _as_uuid(awarded_grant_id)
            )
        rows = [
            _row_to_facts(r)
            for r in connection.execute(
                query.order_by(
                    AWARD_REQUIREMENTS.c.requirement_due_date,
                    AWARD_REQUIREMENTS.c.created_at,
                )
            ).mappings()
        ]

    result = _result(
        operation=operation,
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "awarded_grant_id": str(awarded_grant_id or "") or None,
        },
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=bool(rows),
        rows_written=0,
        rows_read=len(rows),
        blocked_reasons=blocked_reasons,
    )
    result["requirements"] = rows
    result["archived_count"] = sum(1 for r in rows if r["archived_at"])
    result["active_obligation_count"] = sum(1 for r in rows if r["active_obligation"])
    result["projected_burden_count"] = sum(1 for r in rows if r["projected_burden"])
    result["unsupported_count"] = sum(1 for r in rows if r["unsupported_requirement"])
    # What a calendar could actually count down to, which is not the same as
    # what is stored: an estimate is a row and not a deadline.
    result["calendarable_count"] = sum(1 for r in rows if r["date_is_calculable"])
    return _json_safe(result)


def list_requirements_for_award(
    *,
    connection: Any = None,
    organization_id: Any = None,
    awarded_grant_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Every requirement for one award, still anchored on the organization.

    The award narrows; it does not scope. Both are required, and supplying only
    the award is refused.
    """
    blocked: list[str] = []
    if not str(awarded_grant_id or "").strip():
        blocked.append("listing_for_an_award_without_an_awarded_grant_id")
    if blocked:
        return _result(
            operation="list_requirements_for_award",
            organization_id=str(organization_id or "") or None,
            **_empty_facts(),
            storage_allowed=False,
            production_write_allowed=False,
            write_performed=False,
            read_performed=False,
            rows_written=0,
            rows_read=0,
            blocked_reasons=blocked,
        )
    return _listing(
        operation="list_requirements_for_award",
        connection=connection,
        organization_id=organization_id,
        awarded_grant_id=awarded_grant_id,
        include_archived=include_archived,
    )


def list_requirements_for_organization(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Every requirement one organization holds, across all its awards.

    Archived rows are returned because they are the audit trail. A listing that
    hid a withdrawn requirement would make it indistinguishable from one that
    never existed.
    """
    return _listing(
        operation="list_requirements_for_organization",
        connection=connection,
        organization_id=organization_id,
        awarded_grant_id=None,
        include_archived=include_archived,
    )


def archive_award_requirement(
    *,
    connection: Any = None,
    organization_id: Any = None,
    requirement_id: Any = None,
    archived_by_identity_id: Any = None,
    requirement_status: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Withdraw a requirement. An UPDATE, never a DELETE.

    ``requirement_status`` may be set at the same time - `not_applicable` for
    one that turned out not to apply, `waived` for one the funder waived. They
    are different facts and the row records which.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("archive_without_a_uuid_shaped_anchor")
    if not _uuid_shaped(requirement_id):
        blocked_reasons.append("archive_without_a_requirement_id")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    status = str(requirement_status or "").strip().lower()
    if status and status not in REQUIREMENT_STATUSES:
        blocked_reasons.append(f"requirement_status_not_recognised:{status}")

    moment = now or datetime.now(UTC)
    written = 0

    if not blocked_reasons:
        row = (
            connection.execute(
                sa.select(AWARD_REQUIREMENTS).where(
                    AWARD_REQUIREMENTS.c.organization_id == _as_uuid(organization_id),
                    AWARD_REQUIREMENTS.c.id == _as_uuid(requirement_id),
                    AWARD_REQUIREMENTS.c.archived_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked_reasons.append("no_live_award_requirement_to_archive")
        else:
            values: dict[str, Any] = {
                "archived_at": moment,
                "updated_by_identity_id": _as_uuid(archived_by_identity_id),
                "human_review_required": True,
                "updated_at": moment,
                # An archived requirement obliges nobody, whatever it obliged
                # before. The provenance stays; the obligation does not.
                "active_obligation": False,
            }
            if status:
                values["requirement_status"] = status
            connection.execute(
                sa.update(AWARD_REQUIREMENTS)
                .where(AWARD_REQUIREMENTS.c.id == row["id"])
                .values(**values)
            )
            written = 1

    return _result(
        operation="archive_award_requirement",
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "requirement_status": status or None,
            "archived_at": _iso(moment) if written else None,
            "updated_by_identity_id": str(archived_by_identity_id or "") or None,
        },
        storage_allowed=not blocked_reasons,
        production_write_allowed=False,
        write_performed=bool(written),
        read_performed=False,
        rows_written=written,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def validate_requirement_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
    requirement_id: Any = None,
) -> dict[str, Any]:
    """Is what is stored fit to appear on a compliance calendar?

    Reads the requirement and runs Gate 125D's validation over it, so a caller
    can ask "would this row produce a correct calendar entry" without
    constructing one.
    """
    stored = get_award_requirement(
        connection=connection,
        organization_id=organization_id,
        requirement_id=requirement_id,
    )
    validation = validate_award_requirement(
        requirement_title=stored.get("requirement_title"),
        requirement_type=stored.get("requirement_type"),
        requirement_status=stored.get("requirement_status"),
        requirement_source=stored.get("requirement_source"),
        requirement_source_ref=stored.get("requirement_source_ref"),
        requirement_due_date=stored.get("requirement_due_date"),
        due_date_status=stored.get("due_date_status"),
        recurrence_rule=stored.get("recurrence_rule"),
        proof_required=bool(stored.get("proof_required")),
        proof_status=stored.get("proof_status"),
        proof_document_ref=stored.get("proof_document_ref"),
        submission_status=stored.get("submission_status"),
        submitted_at=stored.get("submitted_at"),
        accepted_at=stored.get("accepted_at"),
        rejected_at=stored.get("rejected_at"),
        fact_status=stored.get("fact_status"),
    )

    result = _result(
        **{
            **stored,
            "operation": "validate_requirement_persistence",
            "blocked_reasons": sorted(
                {*stored["blocked_reasons"], *validation["blocked_reasons"]}
            ),
        }
    )
    result["validation"] = validation
    result["requirement_found"] = bool(stored["rows_read"])
    return _json_safe(result)


def award_requirements_repository_invariant_failures(
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
        failures.append("an_award_requirement_row_was_deleted")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("production_award_requirements_created"):
        failures.append("a_production_award_requirement_was_created")

    if result.get("production_proof_records_created"):
        failures.append("a_production_proof_record_was_created")

    # The rules Gate 91 and Gate 108 exist to protect.
    if result.get("projected_burden_promoted"):
        failures.append("a_projected_burden_was_promoted_to_an_obligation")

    if result.get("active_obligation") and result.get("projected_burden"):
        failures.append("a_projection_was_also_an_active_obligation")

    if result.get("active_obligation") and result.get("unsupported_requirement"):
        failures.append("an_unsupported_requirement_was_an_active_obligation")

    if result.get("obligation_inferred_from_title"):
        failures.append("an_obligation_was_inferred_from_a_title")

    if result.get("due_date_inferred"):
        failures.append("a_due_date_was_inferred")

    # A document store this gate did not build.
    if result.get("document_storage_available"):
        failures.append("the_repository_claimed_a_document_store")

    if result.get("proof_audit_persistence_available"):
        failures.append("the_repository_claimed_proof_audit_persistence")

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

    # An obligation stored without established facts is the failure the table's
    # CHECK exists to catch, asserted here so a contract-mode result cannot
    # claim it either.
    # Matched to ck_nf_award_requirements_obligation_needs_established_facts,
    # which names verified, tenant_supplied and demo_fixture. A fixture row is
    # established to be a fixture; only `unknown` and `needs_human_review` are
    # unestablished.
    if result.get("active_obligation") and result.get("storage_allowed"):
        if result.get("fact_status_supports_an_obligation") is False:
            failures.append("active_obligation_on_an_unestablished_fact_status")

    # A stored projection must name what it refused, or nothing downstream can
    # tell a refused claim from one that was never made.
    if result.get("projected_burden") and not result.get("refused_claims"):
        failures.append("a_projection_was_stored_without_naming_the_refusal")

    if (
        result.get("storage_allowed")
        and not str(result.get("requirement_title") or "").strip()
    ):
        if operation in {
            "prepare_requirement_write",
            "create_award_requirement",
        }:
            failures.append("a_requirement_was_storable_without_a_title")

    # An awarded grant is required on every write, and never as the anchor.
    if operation in {"prepare_requirement_write", "create_award_requirement"}:
        if result.get("storage_allowed") and not result.get("awarded_grant_id"):
            failures.append("a_requirement_was_storable_without_an_award")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))


def repository_vocabularies() -> dict[str, list[str]]:
    """The Gate 103/108 vocabularies this repository bridges rather than owns."""
    return _json_safe(
        {
            "requirement_types": sorted(REQUIREMENT_TYPES),
            "requirement_statuses": sorted(REQUIREMENT_STATUSES),
            "submitted_statuses": sorted(SUBMITTED_STATUSES),
            "closed_statuses": sorted(CLOSED_STATUSES),
            "requirement_sources": sorted(EXTRACTION_STATUSES),
            "active_capable_sources": sorted(ACTIVE_CAPABLE_EXTRACTION_STATUSES),
            "due_date_statuses": sorted(DUE_DATE_STATUSES),
            "date_calculable_statuses": sorted(DATE_CALCULABLE_STATUSES),
            "recurrences": sorted(RECURRENCES),
            "proof_statuses": sorted(PROOF_STATUSES),
            "submission_statuses": sorted(SUBMISSION_STATUSES),
            "fact_statuses": sorted(FACT_STATUSES),
            "actionable_fact_statuses": sorted(ACTIONABLE_FACT_STATUSES),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "derived_only_fields": list(DERIVED_ONLY_FIELDS),
            "row_relationship_column": ROW_RELATIONSHIP_COLUMN,
        }
    )


def prohibited_inferences() -> tuple[tuple[str, str], ...]:
    """What this repository refuses to work out on somebody's behalf."""
    return (
        (
            "obligation_from_requirement_title",
            "a title says what is required, not whether the award requires it. "
            "Only human_entered or evidence_extracted provenance can",
        ),
        (
            "due_date_from_recurrence_rule",
            "quarterly says how often, not when. The quarter boundaries a "
            "funder uses are in the award terms",
        ),
        (
            "submission_from_document_reference",
            "attaching a document is not filing it",
        ),
        (
            "acceptance_from_submission",
            "filing something is not the funder accepting it",
        ),
        (
            "document_from_document_reference",
            "there is no document store. The reference resolves to nothing",
        ),
        (
            "obligation_from_projected_burden",
            "Gate 91 stamps every projection is_active_obligation False, and "
            "this is the other end of that refusal",
        ),
    )
