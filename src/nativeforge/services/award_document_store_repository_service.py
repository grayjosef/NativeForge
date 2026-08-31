"""Award document store repository (Gate 127C).

The database boundary for `nf_award_documents`, anchored on `organization_id`.

## What this is, and what it deliberately is not

```text
this            metadata about a Tribe's compliance documents
not this        the documents
```

No column holds bytes. No function opens a file. No call reaches an object
store. `object_store_contacted` and `document_content_read` are constants
`False` with invariants behind them.

## The name this module does not have

It is **not** called `award_document_store_service`, and that is deliberate.
Two probes watch for that exact name:

```text
spine     DOCUMENT_STORAGE: _module_importable("...award_document_store_service")
readiness document_storage_live = _module_importable("...same...")
```

Both are module-existence proxies. Creating a file with that name — even an
empty one — would flip `DOCUMENT_STORAGE` true, clear the last unmet
prerequisite on `award_requirements_persistence` and `proof_audit_persistence`,
and tell both lanes their evidence has somewhere to live. With zero bytes stored
anywhere.

Gate 127E replaces both probes with derived answers. This module keeps the name
the brief gave it, which is also the honest one: it is a **repository** for
document metadata, not a document store.

## Three relationships, at least one, none an authority

```text
organization_id       UUID, FK organizations, the RLS predicate's left side
awarded_grant_id      UUID, FK nf_awarded_grants, nullable
award_requirement_id  UUID, FK nf_award_requirements, nullable
proof_event_id        UUID, FK nf_award_requirement_proof_events, nullable
```

All three optional because an award-level document no requirement has claimed
yet is ordinary. At least one required, because a document attached to nothing
is a file in a drawer.

All three are in `FORBIDDEN_ANCHOR_NAMES`. Reaching the organization through
whichever of three joins happened to be populated would make this table's policy
depend on three other tables' policies, and on which one a caller filled in.

## object_key is refused unless a store exists

`object_store_configured` is bridged from Gate 96's `detect_body_store_mode()`,
never accepted from a caller, and reports `unconfigured` today. Every document
this repository can currently write is a reference and nothing more.

## Legal hold refuses archive

`archive_award_document` returns `legal_hold_refuses_archive` rather than
archiving, and the database refuses it too
(`ck_nf_award_documents_legal_hold_refuses_archive`). A document under legal
hold is one a lawyer has said must not move, and archiving is the only lifecycle
operation this table has.

## Archive, never delete

`rows_deleted` is a constant `0` and there is no DELETE path — asserted by
parsing this module rather than grepping it.

## Production writes need two things that are both false

```text
customer_auth_live              false
verified_operational_binding    false
```

```text
rows in the application database     0
production document records created  0
object store calls                   0
document bytes written               0
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_document_store_persistence_validation_service import (
    DOCUMENT_KINDS,
    DOCUMENT_SOURCES,
    DOCUMENT_STATUSES,
    RELATIONSHIP_FIELDS,
    RETENTION_CLASSES,
    STORED_STATUSES,
    detect_object_store_configured,
    validate_award_document,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_document_store_repository_v1"

TABLE_NAME = "nf_award_documents"

RLS_ANCHOR_COLUMN = "organization_id"

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_document_write",
        "create_award_document",
        "get_award_document",
        "list_documents_for_award",
        "list_documents_for_requirement",
        "list_documents_for_proof_event",
        "list_documents_for_organization",
        "archive_award_document",
        "validate_document_persistence",
    }
)

WRITE_OPERATIONS = frozenset({"create_award_document", "archive_award_document"})
READ_OPERATIONS = frozenset(
    {
        "get_award_document",
        "list_documents_for_award",
        "list_documents_for_requirement",
        "list_documents_for_proof_event",
        "list_documents_for_organization",
    }
)

# Names that may never anchor a row. All three relationship columns are here for
# one reason: none can be cast into the RLS predicate, and which one is even
# present varies per row.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {
        "tenant_id",
        "customer_org_id",
        "organization_profile_id",
        "awarded_grant_id",
        "award_requirement_id",
        "proof_event_id",
    }
)

# Bridged from Gate 96's detector, never supplied by a caller.
DERIVED_ONLY_FIELDS: tuple[str, ...] = ("object_store_configured",)

_METADATA = sa.MetaData()

# Mirrors migration 0035 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production. Two tests compare the definitions by name.
AWARD_DOCUMENTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("awarded_grant_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("award_requirement_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("proof_event_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("document_kind", sa.String(length=48), nullable=False),
    sa.Column("document_status", sa.String(length=32), nullable=False),
    sa.Column("document_title", sa.Text(), nullable=False),
    sa.Column("document_description", sa.Text(), nullable=True),
    sa.Column("document_source", sa.String(length=32), nullable=False),
    sa.Column("document_source_ref", sa.Text(), nullable=True),
    sa.Column("object_store_configured", sa.Boolean(), nullable=False),
    sa.Column("object_store_provider", sa.String(length=32), nullable=True),
    sa.Column("object_bucket", sa.Text(), nullable=True),
    sa.Column("object_key", sa.Text(), nullable=True),
    sa.Column("object_version", sa.Text(), nullable=True),
    sa.Column("content_type", sa.String(length=128), nullable=True),
    sa.Column("content_length", sa.BigInteger(), nullable=True),
    sa.Column("sha256_digest", sa.String(length=64), nullable=True),
    sa.Column("retention_class", sa.String(length=32), nullable=False),
    sa.Column("legal_hold", sa.Boolean(), nullable=False),
    sa.Column("customer_visible", sa.Boolean(), nullable=False),
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
        "document_kind IN ('award_letter', 'award_terms', 'financial_report', "
        "'narrative_report', 'performance_report', 'audit_report', "
        "'match_documentation', 'invoice_or_receipt', "
        "'board_or_council_resolution', 'correspondence', 'closeout_package', "
        "'other', 'unknown')",
        name="ck_nf_award_documents_kind",
    ),
    sa.CheckConstraint(
        "document_status IN ('reference_recorded', 'awaiting_upload', 'stored', "
        "'superseded', 'withdrawn', 'needs_human_review', 'unknown')",
        name="ck_nf_award_documents_status",
    ),
    sa.CheckConstraint(
        "document_source IN ('tenant_supplied', 'human_entered', "
        "'evidence_extracted', 'system_generated', 'unsupported_document_type', "
        "'needs_human_review', 'unknown')",
        name="ck_nf_award_documents_source",
    ),
    sa.CheckConstraint(
        "retention_class IN ('retain_7_days', 'retain_90_days', 'retain_1_year', "
        "'retain_indefinite')",
        name="ck_nf_award_documents_retention_class",
    ),
    sa.CheckConstraint(
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture', "
        "'unknown', 'needs_human_review')",
        name="ck_nf_award_documents_fact_status",
    ),
    sa.CheckConstraint(
        "length(trim(document_title)) > 0",
        name="ck_nf_award_documents_title_not_blank",
    ),
    sa.CheckConstraint(
        "awarded_grant_id IS NOT NULL OR award_requirement_id IS NOT NULL "
        "OR proof_event_id IS NOT NULL",
        name="ck_nf_award_documents_needs_a_relationship",
    ),
    sa.CheckConstraint(
        "object_key IS NULL OR object_store_configured",
        name="ck_nf_award_documents_object_key_needs_a_configured_store",
    ),
    sa.CheckConstraint(
        "object_bucket IS NULL OR object_store_configured",
        name="ck_nf_award_documents_bucket_needs_a_configured_store",
    ),
    sa.CheckConstraint(
        "object_version IS NULL OR object_key IS NOT NULL",
        name="ck_nf_award_documents_version_needs_a_key",
    ),
    sa.CheckConstraint(
        "object_store_provider IS NULL OR object_store_configured",
        name="ck_nf_award_documents_provider_needs_a_configured_store",
    ),
    sa.CheckConstraint(
        "document_status <> 'stored' OR "
        "(object_store_configured AND object_key IS NOT NULL)",
        name="ck_nf_award_documents_stored_needs_a_location",
    ),
    sa.CheckConstraint(
        "content_length IS NULL OR content_length >= 0",
        name="ck_nf_award_documents_content_length_not_negative",
    ),
    sa.CheckConstraint(
        "sha256_digest IS NULL OR length(sha256_digest) = 64",
        name="ck_nf_award_documents_digest_is_sha256_shaped",
    ),
    sa.CheckConstraint(
        "NOT legal_hold OR archived_at IS NULL",
        name="ck_nf_award_documents_legal_hold_refuses_archive",
    ),
    sa.CheckConstraint(
        "NOT customer_visible OR "
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
        name="ck_nf_award_documents_visible_needs_established_facts",
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


def _iso(moment: Any) -> str | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return aware.isoformat()
    return str(moment)


def _result(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "rls_anchor": RLS_ANCHOR_COLUMN,
        # Constants. This repository records metadata. It never deletes, never
        # opens a document, and never reaches an object store.
        "rows_deleted": 0,
        "history_preserved": True,
        "real_customer_rows_written": 0,
        "production_document_records_created": 0,
        "document_content_read": False,
        "document_bytes_written": 0,
        "object_store_contacted": False,
        "content_verified": False,
        "acceptance_inferred_from_document": False,
        "visibility_inferred_from_upload": False,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    out["refused_claims"] = sorted(set(fields.get("refused_claims") or []))
    return _json_safe(out)


def prepare_document_write(
    *,
    organization_id: Any = None,
    awarded_grant_id: Any = None,
    award_requirement_id: Any = None,
    proof_event_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    document_kind: Any = None,
    document_status: Any = None,
    document_title: Any = None,
    document_description: Any = None,
    document_source: Any = None,
    document_source_ref: Any = None,
    object_store_provider: Any = None,
    object_bucket: Any = None,
    object_key: Any = None,
    object_version: Any = None,
    content_type: Any = None,
    content_length: Any = None,
    sha256_digest: Any = None,
    retention_class: Any = None,
    legal_hold: bool = False,
    customer_visible: bool = False,
    fact_status: Any = None,
    created_by_identity_id: Any = None,
    updated_by_identity_id: Any = None,
    is_demo: bool = False,
    customer_auth_live: bool = False,
    verified_operational_binding: bool = False,
    object_store_configured: bool | None = None,
) -> dict[str, Any]:
    """Decide whether a document reference may be written. Touches no database.

    There is deliberately no way to pass document bytes. Not a `content`
    parameter, not a file handle, not a path this reads. The separation
    expressed as a signature, the way Gate 125 refused a projection parameter.
    """
    blocked_reasons: list[str] = []

    # -- the anchor ----------------------------------------------------------
    if not str(organization_id or "").strip():
        blocked_reasons.append("document_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # -- the relationships, each refused as authority under its own name -----
    supplied_relationships = {
        "awarded_grant_id": str(awarded_grant_id or "").strip(),
        "award_requirement_id": str(award_requirement_id or "").strip(),
        "proof_event_id": str(proof_event_id or "").strip(),
    }
    for name, value in supplied_relationships.items():
        if value and not _uuid_shaped(value):
            blocked_reasons.append(f"{name}_is_not_uuid_shaped")
        if value and not str(organization_id or "").strip():
            blocked_reasons.append(f"{name}_is_not_an_organization_id_anchor")

    # -- labels refused outright ---------------------------------------------
    for name, value in (
        ("tenant_id", tenant_id),
        ("customer_org_id", customer_org_id),
        ("organization_profile_id", organization_profile_id),
    ):
        if str(value or "").strip():
            blocked_reasons.append(f"{name}_is_not_an_organization_id_anchor")

    # -- the document reference itself ---------------------------------------
    validation = validate_award_document(
        document_kind=document_kind,
        document_status=document_status,
        document_title=document_title,
        document_description=document_description,
        document_source=document_source,
        document_source_ref=document_source_ref,
        awarded_grant_id=awarded_grant_id,
        award_requirement_id=award_requirement_id,
        proof_event_id=proof_event_id,
        object_store_provider=object_store_provider,
        object_bucket=object_bucket,
        object_key=object_key,
        object_version=object_version,
        content_type=content_type,
        content_length=content_length,
        sha256_digest=sha256_digest,
        retention_class=retention_class,
        legal_hold=legal_hold,
        customer_visible=customer_visible,
        fact_status=fact_status,
        object_store_configured=object_store_configured,
    )
    blocked_reasons.extend(validation["blocked_reasons"])
    refused_claims = list(validation["refused_claims"])

    for name, value in (
        ("created_by_identity_id", created_by_identity_id),
        ("updated_by_identity_id", updated_by_identity_id),
    ):
        if value and not _uuid_shaped(value):
            blocked_reasons.append(f"{name}_is_not_uuid_shaped")

    # -- who may write, and whether this is a production write ---------------
    demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
    production_write = not demo_fixture

    if production_write and not customer_auth_live:
        blocked_reasons.append("production_document_write_requires_live_customer_auth")
    if production_write and not verified_operational_binding:
        blocked_reasons.append(
            "production_document_write_requires_a_verified_operational_binding"
        )

    storage_allowed = not blocked_reasons
    production_write_allowed = bool(storage_allowed and production_write)

    result = _result(
        operation="prepare_document_write",
        organization_id=str(organization_id or "") or None,
        awarded_grant_id=validation["awarded_grant_id"],
        award_requirement_id=validation["award_requirement_id"],
        proof_event_id=validation["proof_event_id"],
        relationship_present=validation["relationship_present"],
        relationship_count=validation["relationship_count"],
        document_kind=validation["document_kind"],
        document_status=validation["document_status"],
        document_title=validation["document_title"],
        document_description=validation["document_description"],
        document_source=validation["document_source"],
        document_source_ref=validation["document_source_ref"],
        object_store_configured=validation["object_store_configured"],
        object_store_provider=validation["object_store_provider"],
        object_bucket=validation["object_bucket"],
        object_key=validation["object_key"],
        object_version=validation["object_version"],
        content_type=validation["content_type"],
        content_length=validation["content_length"],
        sha256_digest=validation["sha256_digest"],
        retention_class=validation["retention_class"],
        legal_hold=validation["legal_hold"],
        archivable=validation["archivable"],
        customer_visible=validation["customer_visible"],
        document_is_stored=validation["document_is_stored"],
        document_is_metadata_only=validation["document_is_metadata_only"],
        fact_status=validation["fact_status"],
        created_by_identity_id=str(created_by_identity_id or "") or None,
        updated_by_identity_id=str(updated_by_identity_id or "") or None,
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


def create_award_document(
    *,
    connection: Any = None,
    document_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert one document reference, if ``prepare_document_write`` permits it.

    No bytes are read, written, hashed or transmitted. The row describes a
    document; it does not contain one.
    """
    decision = prepare_document_write(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if decision["storage_allowed"] and connection is not None:
        connection.execute(
            sa.insert(AWARD_DOCUMENTS).values(
                id=document_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                awarded_grant_id=_as_uuid(decision["awarded_grant_id"]),
                award_requirement_id=_as_uuid(decision["award_requirement_id"]),
                proof_event_id=_as_uuid(decision["proof_event_id"]),
                document_kind=decision["document_kind"],
                document_status=decision["document_status"],
                document_title=str(decision["document_title"]),
                document_description=decision["document_description"],
                document_source=decision["document_source"],
                document_source_ref=decision["document_source_ref"],
                object_store_configured=bool(decision["object_store_configured"]),
                object_store_provider=decision["object_store_provider"],
                object_bucket=decision["object_bucket"],
                object_key=decision["object_key"],
                object_version=decision["object_version"],
                content_type=decision["content_type"],
                content_length=decision["content_length"],
                sha256_digest=decision["sha256_digest"],
                retention_class=decision["retention_class"],
                legal_hold=bool(decision["legal_hold"]),
                customer_visible=bool(decision["customer_visible"]),
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
            "operation": "create_award_document",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "document_id": str(row["id"]),
        "organization_id": str(row["organization_id"]),
        "awarded_grant_id": (
            str(row["awarded_grant_id"]) if row["awarded_grant_id"] else None
        ),
        "award_requirement_id": (
            str(row["award_requirement_id"]) if row["award_requirement_id"] else None
        ),
        "proof_event_id": (
            str(row["proof_event_id"]) if row["proof_event_id"] else None
        ),
        "document_kind": row["document_kind"],
        "document_status": row["document_status"],
        "document_title": row["document_title"],
        "document_description": row["document_description"],
        "document_source": row["document_source"],
        "document_source_ref": row["document_source_ref"],
        "object_store_configured": bool(row["object_store_configured"]),
        "object_store_provider": row["object_store_provider"],
        "object_bucket": row["object_bucket"],
        "object_key": row["object_key"],
        "object_version": row["object_version"],
        "content_type": row["content_type"],
        "content_length": row["content_length"],
        "sha256_digest": row["sha256_digest"],
        "retention_class": row["retention_class"],
        "legal_hold": bool(row["legal_hold"]),
        "archivable": not bool(row["legal_hold"]),
        "customer_visible": bool(row["customer_visible"]),
        "document_is_stored": bool(
            row["document_status"] in STORED_STATUSES
            and row["object_store_configured"]
            and row["object_key"]
        ),
        "document_is_metadata_only": not bool(row["object_key"]),
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
        "document_id": None,
        "awarded_grant_id": None,
        "award_requirement_id": None,
        "proof_event_id": None,
        "document_kind": None,
        "document_status": None,
        "document_title": None,
        "document_description": None,
        "document_source": None,
        "document_source_ref": None,
        "object_store_configured": False,
        "object_store_provider": None,
        "object_bucket": None,
        "object_key": None,
        "object_version": None,
        "content_type": None,
        "content_length": None,
        "sha256_digest": None,
        "retention_class": None,
        "legal_hold": False,
        "archivable": True,
        "customer_visible": False,
        "document_is_stored": False,
        "document_is_metadata_only": True,
        "fact_status": None,
        "created_by_identity_id": None,
        "updated_by_identity_id": None,
        "archived_at": None,
        "demo_fixture": False,
        "human_review_required": True,
    }


def _scoped(organization_id: Any, include_archived: bool) -> Any:
    query = sa.select(AWARD_DOCUMENTS).where(
        AWARD_DOCUMENTS.c.organization_id == _as_uuid(organization_id)
    )
    if not include_archived:
        query = query.where(AWARD_DOCUMENTS.c.archived_at.is_(None))
    return query


def get_award_document(
    *,
    connection: Any = None,
    organization_id: Any = None,
    document_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One document reference, anchored on ``organization_id``.

    Returns metadata. There is no operation on this repository that returns a
    document's contents, because there are no contents to return.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = _scoped(organization_id, include_archived)
        if document_id and _uuid_shaped(document_id):
            query = query.where(AWARD_DOCUMENTS.c.id == _as_uuid(document_id))
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_award_document_for_this_organization")

    facts = _row_to_facts(row) if row is not None else _empty_facts()

    return _result(
        operation="get_award_document",
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
    relationship_column: str | None,
    relationship_value: Any,
    include_archived: bool,
) -> dict[str, Any]:
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if relationship_column is not None and not _uuid_shaped(relationship_value):
        blocked_reasons.append(f"{relationship_column}_is_not_uuid_shaped")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        query = _scoped(organization_id, include_archived)
        if relationship_column is not None:
            query = query.where(
                AWARD_DOCUMENTS.c[relationship_column] == _as_uuid(relationship_value)
            )
        rows = [
            _row_to_facts(r)
            for r in connection.execute(
                query.order_by(AWARD_DOCUMENTS.c.created_at, AWARD_DOCUMENTS.c.id)
            ).mappings()
        ]

    result = _result(
        operation=operation,
        organization_id=str(organization_id or "") or None,
        **_empty_facts(),
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=bool(rows),
        rows_written=0,
        rows_read=len(rows),
        blocked_reasons=blocked_reasons,
    )
    result["documents"] = rows
    result["archived_count"] = sum(1 for r in rows if r["archived_at"])
    result["legal_hold_count"] = sum(1 for r in rows if r["legal_hold"])
    result["customer_visible_count"] = sum(1 for r in rows if r["customer_visible"])
    # What is actually retrievable, which is not the same as what is described.
    result["stored_count"] = sum(1 for r in rows if r["document_is_stored"])
    result["metadata_only_count"] = sum(
        1 for r in rows if r["document_is_metadata_only"]
    )
    return _json_safe(result)


def list_documents_for_award(
    *,
    connection: Any = None,
    organization_id: Any = None,
    awarded_grant_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One award's documents, still anchored on the organization."""
    return _listing(
        operation="list_documents_for_award",
        connection=connection,
        organization_id=organization_id,
        relationship_column="awarded_grant_id",
        relationship_value=awarded_grant_id,
        include_archived=include_archived,
    )


def list_documents_for_requirement(
    *,
    connection: Any = None,
    organization_id: Any = None,
    award_requirement_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One requirement's documents, still anchored on the organization."""
    return _listing(
        operation="list_documents_for_requirement",
        connection=connection,
        organization_id=organization_id,
        relationship_column="award_requirement_id",
        relationship_value=award_requirement_id,
        include_archived=include_archived,
    )


def list_documents_for_proof_event(
    *,
    connection: Any = None,
    organization_id: Any = None,
    proof_event_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """One proof event's documents, still anchored on the organization."""
    return _listing(
        operation="list_documents_for_proof_event",
        connection=connection,
        organization_id=organization_id,
        relationship_column="proof_event_id",
        relationship_value=proof_event_id,
        include_archived=include_archived,
    )


def list_documents_for_organization(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Every document one organization holds, across every relationship."""
    return _listing(
        operation="list_documents_for_organization",
        connection=connection,
        organization_id=organization_id,
        relationship_column=None,
        relationship_value=None,
        include_archived=include_archived,
    )


def archive_award_document(
    *,
    connection: Any = None,
    organization_id: Any = None,
    document_id: Any = None,
    archived_by_identity_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Take a document reference out of the active view. Never a DELETE.

    Refuses while the document is under legal hold. A lawyer saying a document
    must not move is not a preference this repository may weigh against
    tidiness, and the database refuses it too.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("archive_without_a_uuid_shaped_anchor")
    if not _uuid_shaped(document_id):
        blocked_reasons.append("archive_without_a_document_id")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0
    legal_hold = False

    if not blocked_reasons:
        row = (
            connection.execute(
                sa.select(AWARD_DOCUMENTS).where(
                    AWARD_DOCUMENTS.c.organization_id == _as_uuid(organization_id),
                    AWARD_DOCUMENTS.c.id == _as_uuid(document_id),
                    AWARD_DOCUMENTS.c.archived_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked_reasons.append("no_live_award_document_to_archive")
        elif row["legal_hold"]:
            legal_hold = True
            blocked_reasons.append("legal_hold_refuses_archive")
        else:
            connection.execute(
                sa.update(AWARD_DOCUMENTS)
                .where(AWARD_DOCUMENTS.c.id == row["id"])
                .values(
                    archived_at=moment,
                    updated_by_identity_id=_as_uuid(archived_by_identity_id),
                    human_review_required=True,
                    updated_at=moment,
                )
            )
            written = 1

    return _result(
        operation="archive_award_document",
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "document_id": str(document_id or "") or None,
            "legal_hold": legal_hold,
            "archivable": not legal_hold,
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


def validate_document_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
    document_id: Any = None,
) -> dict[str, Any]:
    """Is what is stored fit to act on?"""
    stored = get_award_document(
        connection=connection,
        organization_id=organization_id,
        document_id=document_id,
    )
    validation = validate_award_document(
        document_kind=stored.get("document_kind"),
        document_status=stored.get("document_status"),
        document_title=stored.get("document_title"),
        document_description=stored.get("document_description"),
        document_source=stored.get("document_source"),
        document_source_ref=stored.get("document_source_ref"),
        awarded_grant_id=stored.get("awarded_grant_id"),
        award_requirement_id=stored.get("award_requirement_id"),
        proof_event_id=stored.get("proof_event_id"),
        object_store_provider=stored.get("object_store_provider"),
        object_bucket=stored.get("object_bucket"),
        object_key=stored.get("object_key"),
        object_version=stored.get("object_version"),
        content_type=stored.get("content_type"),
        content_length=stored.get("content_length"),
        sha256_digest=stored.get("sha256_digest"),
        retention_class=stored.get("retention_class"),
        legal_hold=bool(stored.get("legal_hold")),
        customer_visible=bool(stored.get("customer_visible")),
        fact_status=stored.get("fact_status"),
        object_store_configured=bool(stored.get("object_store_configured")),
    )

    result = _result(
        **{
            **stored,
            "operation": "validate_document_persistence",
            "blocked_reasons": sorted(
                {*stored["blocked_reasons"], *validation["blocked_reasons"]}
            ),
            "refused_claims": list(validation["refused_claims"]),
        }
    )
    result["validation"] = validation
    result["document_found"] = bool(stored["rows_read"])
    return _json_safe(result)


def document_store_repository_invariant_failures(
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
        failures.append("an_award_document_row_was_deleted")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("production_document_records_created"):
        failures.append("a_production_document_record_was_created")

    # The three this gate exists to keep false.
    if result.get("document_content_read"):
        failures.append("the_repository_read_a_document")

    if result.get("document_bytes_written"):
        failures.append("the_repository_wrote_document_bytes")

    if result.get("object_store_contacted"):
        failures.append("the_repository_contacted_an_object_store")

    if result.get("content_verified"):
        failures.append("the_repository_claimed_it_verified_content")

    for field in (
        "acceptance_inferred_from_document",
        "visibility_inferred_from_upload",
    ):
        if result.get(field):
            failures.append(f"the_repository_claimed_{field}")

    # Guarded on storage_allowed for the reason Gate 126 established: a caller
    # supplying an object_key with no store is bad input, already named in
    # blocked_reasons, and an unguarded invariant would fire on it.
    if result.get("storage_allowed"):
        if result.get("object_key") and not result.get("object_store_configured"):
            failures.append("a_storable_object_key_without_a_configured_store")
        if result.get("document_is_stored") and not result.get("object_key"):
            failures.append("a_storable_stored_document_without_a_location")

    # Legal hold is not a preference.
    if result.get("legal_hold") and result.get("archivable"):
        failures.append("a_document_under_legal_hold_was_archivable")

    if operation == "archive_award_document" and result.get("write_performed"):
        if result.get("legal_hold"):
            failures.append("a_document_under_legal_hold_was_archived")

    # Visibility is decided, never derived.
    if result.get("customer_visible") and result.get("storage_allowed"):
        if str(result.get("fact_status") or "") in {"unknown", "needs_human_review"}:
            failures.append("a_visible_document_on_an_unestablished_fact_status")

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

    if operation in {"prepare_document_write", "create_award_document"}:
        if result.get("storage_allowed") and not result.get("relationship_present"):
            failures.append("a_document_was_storable_without_a_relationship")
        if (
            result.get("storage_allowed")
            and not str(result.get("document_title") or "").strip()
        ):
            failures.append("a_document_was_storable_without_a_title")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))


def repository_vocabularies() -> dict[str, list[str]]:
    """What this repository bridges, and what it adds."""
    return _json_safe(
        {
            "document_kinds": sorted(DOCUMENT_KINDS),
            "document_statuses": sorted(DOCUMENT_STATUSES),
            "stored_statuses": sorted(STORED_STATUSES),
            "document_sources": sorted(DOCUMENT_SOURCES),
            "retention_classes_bridged_from_gate_96": sorted(RETENTION_CLASSES),
            "fact_statuses": sorted(FACT_STATUSES),
            "actionable_fact_statuses": sorted(ACTIONABLE_FACT_STATUSES),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "relationship_fields": list(RELATIONSHIP_FIELDS),
            "derived_only_fields": list(DERIVED_ONLY_FIELDS),
        }
    )


def prohibited_inferences() -> tuple[tuple[str, str], ...]:
    """What this repository refuses to work out on somebody's behalf."""
    return (
        (
            "storage_from_object_key",
            "a key is a path. Whether anything is at the end of it is what "
            "detect_body_store_mode() answers, and it answers unconfigured",
        ),
        (
            "content_from_metadata",
            "a digest and a length describe a file this repository has never "
            "opened. Neither is evidence the file exists",
        ),
        (
            "submission_from_document",
            "attaching a document is not filing it. Gate 126 owns that boundary",
        ),
        (
            "acceptance_from_document",
            "a funder accepting something is a separate event with its own timestamp",
        ),
        (
            "visibility_from_upload",
            "whether a Tribe is shown their own document is a decision "
            "somebody makes. A default of true shows a draft to the wrong "
            "person exactly once",
        ),
        (
            "document_kind_from_title_or_content_type",
            "Report.pdf could be financial, narrative or performance, and the "
            "three have different retention",
        ),
    )


def object_store_status() -> dict[str, Any]:
    """What this repository knows about where bytes would go.

    Reported so a reader can see that the answer comes from Gate 96's detector
    rather than from this gate having built anything.
    """
    from nativeforge.services.raw_payload_body_store_contract_service import (
        detect_body_store_mode,
    )

    mode = detect_body_store_mode()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "object_store_configured": detect_object_store_configured(),
            "body_store_mode": mode,
            "detector": (
                "nativeforge.services.raw_payload_body_store_contract_service"
                ".detect_body_store_mode"
            ),
            "built_by_gate_127": False,
            "object_store_contacted": False,
            "document_bytes_written": 0,
        }
    )
