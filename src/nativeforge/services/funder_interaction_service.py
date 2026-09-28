"""Record what this organization did with a funder, and read it back.

Contacts (0068) are facts about a notice. This is facts about *us*: a
question we sent, a clarification we received, a webinar we attended.
Those belong to the tenant. They are never promoted onto the opportunity
record another organization would see.

People are not merged. Two emails that look alike stay two rows until a
human says otherwise.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

INTERACTIONS_TABLE = "nf_funder_interactions"

INTERACTION_TYPES: frozenset[str] = frozenset(
    {
        "question_submitted",
        "email",
        "phone_call",
        "technical_assistance",
        "office_hours",
        "webinar",
        "applicant_conference",
        "pre_application_meeting",
        "clarification_received",
        "amendment_communication",
        "other",
    }
)

INTERACTION_STATUSES: frozenset[str] = frozenset(
    {"open", "awaiting_reply", "answered", "closed"}
)

SCHEMA_VERSION = "nf_funder_interaction_v1"

_METADATA = sa.MetaData()

INTERACTIONS = sa.Table(
    INTERACTIONS_TABLE,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("grant_spark_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("grant_pursuit_id", sa.Uuid(as_uuid=True)),
    sa.Column("contact_id", sa.Uuid(as_uuid=True)),
    sa.Column("funder_agency", sa.String(length=512), nullable=False),
    sa.Column("funder_agency_norm", sa.String(length=512), nullable=False),
    sa.Column("program_name", sa.String(length=512)),
    sa.Column("interaction_type", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("follow_up_at", sa.DateTime(timezone=True)),
    sa.Column("subject", sa.String(length=512)),
    sa.Column("notes", sa.Text()),
    sa.Column("evidence_ref", sa.String(length=512)),
    sa.Column("owner_label", sa.String(length=256)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


def normalize_agency(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_when(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return _now()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def record_interaction(
    *,
    connection: Any,
    organization_id: uuid.UUID | str,
    is_demo: bool,
    grant_spark_id: uuid.UUID | str,
    funder_agency: str,
    interaction_type: str,
    grant_pursuit_id: uuid.UUID | str | None = None,
    contact_id: uuid.UUID | str | None = None,
    program_name: str | None = None,
    status: str = "open",
    occurred_at: str | datetime | None = None,
    follow_up_at: str | datetime | None = None,
    subject: str | None = None,
    notes: str | None = None,
    evidence_ref: str | None = None,
    owner_label: str | None = None,
) -> dict[str, Any]:
    """Write one interaction. Refuses unknown types rather than storing 'other' silently."""
    kind = str(interaction_type or "").strip()
    if kind not in INTERACTION_TYPES:
        return {"written": 0, "blocked_reasons": ["unknown_interaction_type"]}
    state = str(status or "open").strip()
    if state not in INTERACTION_STATUSES:
        return {"written": 0, "blocked_reasons": ["unknown_interaction_status"]}
    agency = str(funder_agency or "").strip()
    if not agency:
        return {"written": 0, "blocked_reasons": ["funder_agency_required"]}

    row_id = uuid.uuid4()
    connection.execute(
        sa.insert(INTERACTIONS).values(
            id=row_id,
            organization_id=uuid.UUID(str(organization_id)),
            is_demo=bool(is_demo),
            grant_spark_id=uuid.UUID(str(grant_spark_id)),
            grant_pursuit_id=(
                uuid.UUID(str(grant_pursuit_id)) if grant_pursuit_id else None
            ),
            contact_id=uuid.UUID(str(contact_id)) if contact_id else None,
            funder_agency=agency,
            funder_agency_norm=normalize_agency(agency),
            program_name=(str(program_name).strip() or None) if program_name else None,
            interaction_type=kind,
            status=state,
            occurred_at=_parse_when(occurred_at),
            follow_up_at=_parse_when(follow_up_at) if follow_up_at else None,
            subject=(str(subject).strip() or None) if subject else None,
            notes=(str(notes).strip() or None) if notes else None,
            evidence_ref=(str(evidence_ref).strip() or None) if evidence_ref else None,
            owner_label=(str(owner_label).strip() or None) if owner_label else None,
            created_at=_now(),
        )
    )
    return {"written": 1, "id": str(row_id), "blocked_reasons": []}


def list_interactions(
    *,
    connection: Any,
    organization_id: uuid.UUID | str,
    grant_spark_id: uuid.UUID | str | None = None,
    funder_agency: str | None = None,
    exclude_spark_id: uuid.UUID | str | None = None,
) -> list[dict[str, Any]]:
    """Tenant-scoped reads. Spark and agency filters never cross organizations."""
    org = uuid.UUID(str(organization_id))
    query = sa.select(INTERACTIONS).where(INTERACTIONS.c.organization_id == org)
    if grant_spark_id is not None:
        query = query.where(
            INTERACTIONS.c.grant_spark_id == uuid.UUID(str(grant_spark_id))
        )
    if funder_agency:
        query = query.where(
            INTERACTIONS.c.funder_agency_norm == normalize_agency(funder_agency)
        )
    if exclude_spark_id is not None:
        query = query.where(
            INTERACTIONS.c.grant_spark_id != uuid.UUID(str(exclude_spark_id))
        )
    query = query.order_by(
        INTERACTIONS.c.occurred_at.desc(), INTERACTIONS.c.created_at.desc()
    )
    rows = connection.execute(query).mappings().all()
    return [_public(row) for row in rows]


def _public(row: Any) -> dict[str, Any]:
    def _iso(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    return {
        "schema_version": SCHEMA_VERSION,
        "id": str(row["id"]),
        "grant_spark_id": str(row["grant_spark_id"]),
        "grant_pursuit_id": str(row["grant_pursuit_id"])
        if row["grant_pursuit_id"]
        else None,
        "contact_id": str(row["contact_id"]) if row["contact_id"] else None,
        "funder_agency": row["funder_agency"],
        "program_name": row["program_name"],
        "interaction_type": row["interaction_type"],
        "status": row["status"],
        "occurred_at": _iso(row["occurred_at"]),
        "follow_up_at": _iso(row["follow_up_at"]),
        "subject": row["subject"],
        "notes": row["notes"],
        "evidence_ref": row["evidence_ref"],
        "owner_label": row["owner_label"],
    }
