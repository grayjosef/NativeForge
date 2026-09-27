"""Persist and read back who to contact and where to submit.

The extractor reads a notice; this decides what becomes a row, what
supersedes what, and what a customer is told about how much of it can be
relied on.

## Supersession, not overwriting

An amendment that moves the submission address from `applications@` to
`grants@` does not delete the first address. A customer who already sent
something to the old one has to be able to see that this happened; finding
the old value silently gone tells them nothing and leaves them assuming they
did it right.

So a re-extraction marks the rows it replaces `superseded_at` and writes new
ones. Reads return current rows by default and superseded ones on request.

## Customer-provided facts never become source-verified

A customer who already knows the program officer can record them, and that is
worth having. But `provenance_kind` keeps it distinct from a fact read out of
the official notice, permanently, because only the second could ever be
promoted to something another organization sees. A single "contact" field
with no provenance is how one tenant's private relationship becomes another
tenant's canonical truth.

## Absence still proves nothing

`contacts_are_complete` is returned as a separate fact from `contacts`. An
empty list from a notice that was read in full means the notice names nobody;
an empty list from a notice that could not be read means nothing at all. The
two are indistinguishable from the list alone, which is exactly the mistake
the evidence rules exist to prevent, so the caller is told which it has.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.opportunity_contact_extraction_service import (
    ExtractionResult,
    assess_completeness,
    extract,
)

CONTACTS_TABLE = "nf_opportunity_contacts"
SUBMISSION_TABLE = "nf_opportunity_submission_paths"

#: Read from the official material. The only kind that could ever become a
#: fact another organization sees.
SOURCE_DOCUMENT = "source_document"
#: Entered by the customer. Useful, private, and never promoted.
CUSTOMER_PROVIDED = "customer_provided"


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------
#
# Declared as Core tables rather than written as text SQL, because the types
# have to travel. `organization_id` is a UUID, and SQLite stores it as a
# 32-character hex string while PostgreSQL stores a native uuid; raw text SQL
# binds whatever object it is handed and fails on SQLite with "type 'UUID' is
# not supported". A typed column lets the dialect do the conversion, which is
# the difference between a service that works on both engines and one that
# works on the developer's.
#
# These mirror migration 0068. They are not the schema - the migration is -
# and they carry only the columns this service reads or writes.

_METADATA = sa.MetaData()

CONTACTS = sa.Table(
    CONTACTS_TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("grant_spark_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("role", sa.String(length=32), nullable=False),
    sa.Column("name", sa.String(length=256)),
    sa.Column("title", sa.String(length=256)),
    sa.Column("office", sa.String(length=512)),
    sa.Column("email", sa.String(length=320)),
    sa.Column("phone", sa.String(length=64)),
    sa.Column("website", sa.String(length=2048)),
    sa.Column("provenance_kind", sa.String(length=32), nullable=False),
    sa.Column("source_document", sa.String(length=512)),
    sa.Column("source_section", sa.String(length=512)),
    sa.Column("source_url", sa.String(length=2048)),
    sa.Column("source_page", sa.Integer()),
    sa.Column("observed_at", sa.DateTime(timezone=True)),
    sa.Column("superseded_at", sa.DateTime(timezone=True)),
    sa.Column("superseded_by_id", sa.Uuid(as_uuid=True)),
    sa.Column("superseded_reason", sa.String(length=256)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

SUBMISSION = sa.Table(
    SUBMISSION_TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("grant_spark_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("method", sa.String(length=32), nullable=False),
    sa.Column("portal_name", sa.String(length=256)),
    sa.Column("submission_url", sa.String(length=2048)),
    sa.Column("package_url", sa.String(length=2048)),
    sa.Column("recipient_email", sa.String(length=320)),
    sa.Column("recipient_office", sa.String(length=512)),
    sa.Column("deadline_at", sa.DateTime(timezone=True)),
    sa.Column("deadline_timezone", sa.String(length=64)),
    sa.Column("loi_deadline_at", sa.DateTime(timezone=True)),
    sa.Column("registration_requirements", sa.Text()),
    sa.Column("submission_format", sa.String(length=256)),
    sa.Column("submission_instructions", sa.Text()),
    sa.Column("confirmation_method", sa.String(length=256)),
    sa.Column("completeness", sa.String(length=32), nullable=False),
    sa.Column("completeness_reasons_json", sa.JSON()),
    sa.Column("provenance_kind", sa.String(length=32), nullable=False),
    sa.Column("source_document", sa.String(length=512)),
    sa.Column("source_section", sa.String(length=512)),
    sa.Column("source_url", sa.String(length=2048)),
    sa.Column("source_page", sa.Integer()),
    sa.Column("observed_at", sa.DateTime(timezone=True)),
    sa.Column("superseded_at", sa.DateTime(timezone=True)),
    sa.Column("superseded_by_id", sa.Uuid(as_uuid=True)),
    sa.Column("superseded_reason", sa.String(length=256)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in result.mappings().all()]


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------


def record_extraction(
    *,
    connection: Any,
    organization_id: uuid.UUID | str,
    is_demo: bool,
    grant_spark_id: uuid.UUID | str,
    notice_text: str,
    text_complete: bool,
    source_document: str | None = None,
    source_url: str | None = None,
    reason: str = "re-read of the funding notice",
) -> dict[str, Any]:
    """Extract from a notice and store the result, superseding what it replaces.

    Returns counts and the extraction's own notes rather than the rows. A
    caller that wants the rows reads them back, which keeps one answer to
    "what does NativeForge currently hold" instead of two that can disagree.
    """
    org = uuid.UUID(str(organization_id))
    spark = uuid.UUID(str(grant_spark_id))
    moment = _now()

    result: ExtractionResult = extract(notice_text, text_complete=text_complete)
    completeness, reasons = assess_completeness(result.submission)

    superseded = _supersede(
        connection=connection,
        organization_id=org,
        grant_spark_id=spark,
        moment=moment,
        reason=reason,
    )

    contacts_written = 0
    for contact in result.contacts:
        connection.execute(
            sa.insert(CONTACTS).values(
                id=uuid.uuid4(),
                organization_id=org,
                is_demo=is_demo,
                grant_spark_id=spark,
                role=contact.role,
                name=contact.name,
                title=contact.title,
                office=contact.office,
                email=contact.email,
                phone=contact.phone,
                website=contact.website,
                provenance_kind=SOURCE_DOCUMENT,
                source_document=source_document,
                source_section=contact.source_section,
                source_url=source_url,
                observed_at=moment,
                created_at=moment,
            )
        )
        contacts_written += 1

    submission_written = 0
    if result.submission is not None:
        path = result.submission
        connection.execute(
            sa.insert(SUBMISSION).values(
                id=uuid.uuid4(),
                organization_id=org,
                is_demo=is_demo,
                grant_spark_id=spark,
                method=path.method,
                portal_name=path.portal_name,
                submission_url=path.submission_url,
                recipient_email=path.recipient_email,
                deadline_at=path.deadline_at,
                deadline_timezone=path.deadline_timezone,
                submission_instructions=path.deadline_text,
                completeness=completeness,
                completeness_reasons_json=reasons,
                provenance_kind=SOURCE_DOCUMENT,
                source_document=source_document,
                source_section=path.source_section,
                source_url=source_url,
                observed_at=moment,
                created_at=moment,
            )
        )
        submission_written = 1

    return {
        "contacts_written": contacts_written,
        "submission_written": submission_written,
        "contacts_superseded": superseded["contacts"],
        "submission_superseded": superseded["submission"],
        "submission_completeness": completeness,
        "completeness_reasons": reasons,
        "text_complete": text_complete,
        "notes": list(result.notes),
    }



def _supersede(
    *,
    connection: Any,
    organization_id: uuid.UUID,
    grant_spark_id: uuid.UUID,
    moment: datetime,
    reason: str,
) -> dict[str, int]:
    """Mark current rows superseded. Nothing is deleted."""
    counts: dict[str, int] = {}
    for key, table in (("contacts", CONTACTS), ("submission", SUBMISSION)):
        result = connection.execute(
            sa.update(table)
            .where(
                table.c.organization_id == organization_id,
                table.c.grant_spark_id == grant_spark_id,
                table.c.superseded_at.is_(None),
            )
            .values(superseded_at=moment, superseded_reason=reason)
        )
        counts[key] = int(result.rowcount or 0)
    return counts


def add_customer_contact(
    *,
    connection: Any,
    organization_id: uuid.UUID | str,
    is_demo: bool,
    grant_spark_id: uuid.UUID | str,
    role: str = "unknown",
    name: str | None = None,
    title: str | None = None,
    office: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
) -> dict[str, Any]:
    """Record a contact the customer already knows.

    `provenance_kind` is `customer_provided` and there is no parameter to make
    it anything else. A customer's private relationship with a program officer
    is theirs; it is not evidence about the opportunity, and nothing in the
    promotion path can mistake it for evidence if the column cannot say so.
    """
    if not any((email, phone, website, office)):
        return {
            "written": 0,
            "blocked_reasons": ["contact_has_no_way_to_reach_anybody"],
        }

    connection.execute(
        sa.insert(CONTACTS).values(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(str(organization_id)),
            is_demo=is_demo,
            grant_spark_id=uuid.UUID(str(grant_spark_id)),
            role=role,
            name=name,
            title=title,
            office=office,
            email=email,
            phone=phone,
            website=website,
            provenance_kind=CUSTOMER_PROVIDED,
            observed_at=_now(),
            created_at=_now(),
        )
    )
    return {"written": 1, "blocked_reasons": []}


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


def read_apply_path(
    *,
    connection: Any,
    organization_id: uuid.UUID | str,
    grant_spark_id: uuid.UUID | str,
    include_superseded: bool = False,
) -> dict[str, Any]:
    """Everything NativeForge holds about reaching and applying to a funder."""
    org = uuid.UUID(str(organization_id))
    spark = uuid.UUID(str(grant_spark_id))

    def _scoped(table):
        query = sa.select(table).where(
            table.c.organization_id == org,
            table.c.grant_spark_id == spark,
        )
        if not include_superseded:
            query = query.where(table.c.superseded_at.is_(None))
        return query

    contacts = _rows(
        connection.execute(
            _scoped(CONTACTS).order_by(CONTACTS.c.role, CONTACTS.c.created_at)
        )
    )
    submissions = _rows(
        connection.execute(_scoped(SUBMISSION).order_by(SUBMISSION.c.created_at.desc()))
    )

    current = submissions[0] if submissions else None
    return {
        "contacts": [_public_contact(c) for c in contacts],
        "submission": _public_submission(current) if current else None,
        # Separate from the list on purpose: an empty list means one thing
        # when the notice was read in full and nothing at all when it was not.
        "extraction_performed": bool(contacts or submissions),
        "superseded_included": include_superseded,
    }


def _public_contact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "role": row["role"],
        "name": row["name"],
        "title": row["title"],
        "office": row["office"],
        "email": row["email"],
        "phone": row["phone"],
        "website": row["website"],
        "provenance_kind": row["provenance_kind"],
        "source_document": row["source_document"],
        "source_section": row["source_section"],
        "source_url": row["source_url"],
        "observed_at": row["observed_at"].isoformat() if row["observed_at"] else None,
        "superseded": row["superseded_at"] is not None,
    }


def _public_submission(row: dict[str, Any]) -> dict[str, Any]:
    reasons = row.get("completeness_reasons_json")
    if isinstance(reasons, str):
        import json

        try:
            reasons = json.loads(reasons)
        except ValueError:
            reasons = []
    return {
        "id": str(row["id"]),
        "method": row["method"],
        "portal_name": row["portal_name"],
        "submission_url": row["submission_url"],
        "package_url": row["package_url"],
        "recipient_email": row["recipient_email"],
        "recipient_office": row["recipient_office"],
        "deadline_at": row["deadline_at"].isoformat() if row["deadline_at"] else None,
        "deadline_timezone": row["deadline_timezone"],
        "submission_instructions": row["submission_instructions"],
        "completeness": row["completeness"],
        "completeness_reasons": list(reasons or []),
        "provenance_kind": row["provenance_kind"],
        "source_document": row["source_document"],
        "source_section": row["source_section"],
        "source_url": row["source_url"],
        "observed_at": row["observed_at"].isoformat() if row["observed_at"] else None,
        "superseded": row["superseded_at"] is not None,
    }
