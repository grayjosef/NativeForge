"""Tenant beta profile repository (Gate 123B).

The database boundary for `nf_tenant_beta_profiles`, anchored on
`organization_id`.

## Two profiles, and this is the second one

```text
nf_tribal_profiles       who this Tribe is when a form is submitted
                         UEI, EIN, SAM, addresses, contacts, narratives
                         table since 0003, repository since Sprint 0

nf_tenant_beta_profiles  how this tenant wants NativeForge to behave
                         recognition, operating states, applicant classes,
                         watchlist, digest, routing, alerts
                         table as of 0031, this repository
```

Gate 123A found the two share not one column. They are not the same object and
they do not go in the same table.

## organization_id anchors; labels never select

```text
organization_id          UUID, foreign key, the RLS predicate's left-hand side
tenant_id_label          text. Travels with the row. Never selects one.
customer_org_id_label    text. Same.
organization_profile_id  refused outright
```

`organization_profile_id` is refused rather than ignored. It is a real value
from a real column in the wrong identity space — the substitution Gates 110-113
exist to prevent — and silently dropping it would let a caller believe it had
been honoured.

## operating_states drives state matching; an address never does

The most consequential rule here. A tenant may operate, serve and be eligible in
a state it is not headquartered in. Gate 103's `INFERENCE_PROHIBITED` names
`operating_state_from_mailing_address` as a refusal, and this repository
enforces it: `service_area` is free text that describes, and `operating_states`
is the list that decides.

`prepare_profile_write` refuses a write that carries a service area and no
operating states, rather than deriving one from the other.

## Unknown stays unknown

An unknown recognition status may only carry an unestablished fact status, and
the database agrees — `ck_nf_tenant_beta_unknown_recognition_is_unestablished`
refuses the row this module would have had to construct wrongly to get past it.

Nothing here infers a recognition status, a geography, an applicant class, or a
priority. Gate 103's four prohibited inferences are bridged rather than
restated.

## Archive, never delete

`archive_tenant_profile` sets `archived_at` and leaves the row. There is no
DELETE path, `rows_deleted` is a constant `0`, and a test greps this module for
`sa.delete`. A digest complaint is debugged against the profile that produced
it.

The partial unique index (`WHERE archived_at IS NULL`) is what makes that safe:
one live profile per organization, and an archived one stops blocking a
replacement without disappearing.

## Production writes are blocked, and not by this module alone

```text
customer_auth_live              false
verified_operational_binding    false
```

Both are required and both are false. A profile row asserting a tenant's
recognition status while nobody can be authenticated as that tenant is a
fabricated fact in a table, which is worse than an empty table.

Contract mode is the default: without a connection nothing is written and the
result says so. The `database` path is exercised against isolated in-memory
databases in tests and reached by nothing in the running application.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    APPLICANT_CLASSES,
    DIGEST_FREQUENCIES,
    FACT_STATUSES,
    INFERENCE_PROHIBITED,
    RECOGNITION_STATUSES,
    UNESTABLISHED_FACT_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_profile_repository_v1"

TABLE_NAME = "nf_tenant_beta_profiles"

# The anchor, bridged from the binding store rather than restated.
RLS_ANCHOR_COLUMN = "organization_id"

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_profile_write",
        "upsert_tenant_profile",
        "get_tenant_profile",
        "list_tenant_profiles",
        "archive_tenant_profile",
        "validate_profile_persistence",
    }
)

WRITE_OPERATIONS = frozenset({"upsert_tenant_profile", "archive_tenant_profile"})
READ_OPERATIONS = frozenset({"get_tenant_profile", "list_tenant_profiles"})

PROFILE_STATUSES = frozenset({"draft", "active", "archived", "needs_human_review"})

# Names that may never anchor a row. `organization_profile_id` is the one this
# repository is most likely to be offered.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {"tenant_id", "customer_org_id", "organization_profile_id"}
)

_UUID_RE_LEN = 36

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "rls_anchor",
    "organization_id",
    "tenant_id_label",
    "customer_org_id_label",
    "recognition_status",
    "operating_states",
    "service_area",
    "programs",
    "departments",
    "applicant_classes",
    "priority_topics",
    "excluded_topics",
    "source_watchlist_preferences",
    "digest_frequency",
    "routing_rules",
    "custom_alerts",
    "profile_status",
    "created_by_identity_id",
    "updated_by_identity_id",
    "archived_at",
    "human_review_required",
    "storage_allowed",
    "production_write_allowed",
    "write_performed",
    "read_performed",
    "rows_written",
    "rows_read",
    "rows_deleted",
    "blocked_reasons",
)

_METADATA = sa.MetaData()

# Mirrors migration 0031 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production and passed on writes the real database refuses.
# Two tests compare the definitions by name so they cannot drift.
TENANT_BETA_PROFILES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("tenant_id_label", sa.Text(), nullable=False),
    sa.Column("customer_org_id_label", sa.Text(), nullable=True),
    sa.Column("recognition_status", sa.String(length=32), nullable=False),
    sa.Column("recognition_status_fact_status", sa.String(length=32), nullable=False),
    sa.Column("operating_states", sa.JSON(), nullable=False),
    sa.Column("operating_states_fact_status", sa.String(length=32), nullable=False),
    sa.Column("service_area", sa.Text(), nullable=True),
    sa.Column("applicant_classes", sa.JSON(), nullable=False),
    sa.Column("applicant_classes_fact_status", sa.String(length=32), nullable=False),
    sa.Column("programs", sa.JSON(), nullable=False),
    sa.Column("departments", sa.JSON(), nullable=False),
    sa.Column("priority_topics", sa.JSON(), nullable=False),
    sa.Column("excluded_topics", sa.JSON(), nullable=False),
    sa.Column("source_watchlist_preferences", sa.JSON(), nullable=False),
    sa.Column("digest_frequency", sa.String(length=16), nullable=False),
    sa.Column("routing_rules", sa.JSON(), nullable=False),
    sa.Column("custom_alerts", sa.JSON(), nullable=False),
    sa.Column("profile_status", sa.String(length=32), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("updated_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "recognition_status IN ('federally_recognized', 'state_recognized', "
        "'historic_affiliation', 'unrecognized', 'unknown')",
        name="ck_nf_tenant_beta_recognition_status",
    ),
    sa.CheckConstraint(
        "digest_frequency IN ('weekly', 'daily', 'none')",
        name="ck_nf_tenant_beta_digest_frequency",
    ),
    sa.CheckConstraint(
        "profile_status IN ('draft', 'active', 'archived', 'needs_human_review')",
        name="ck_nf_tenant_beta_profile_status",
    ),
    sa.CheckConstraint(
        "recognition_status_fact_status IN ('verified', 'tenant_supplied', "
        "'demo_fixture', 'unknown', 'needs_human_review')",
        name="ck_nf_tenant_beta_recognition_fact_status",
    ),
    sa.CheckConstraint(
        "operating_states_fact_status IN ('verified', 'tenant_supplied', "
        "'demo_fixture', 'unknown', 'needs_human_review')",
        name="ck_nf_tenant_beta_operating_states_fact_status",
    ),
    sa.CheckConstraint(
        "applicant_classes_fact_status IN ('verified', 'tenant_supplied', "
        "'demo_fixture', 'unknown', 'needs_human_review')",
        name="ck_nf_tenant_beta_applicant_classes_fact_status",
    ),
    sa.CheckConstraint(
        "profile_status <> 'archived' OR archived_at IS NOT NULL",
        name="ck_nf_tenant_beta_archived_needs_timestamp",
    ),
    sa.CheckConstraint(
        "recognition_status <> 'unknown' OR "
        "recognition_status_fact_status IN ('unknown', 'needs_human_review')",
        name="ck_nf_tenant_beta_unknown_recognition_is_unestablished",
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


def _list_of(value: Any) -> list[str]:
    """A JSON list of non-empty strings. Never split from a delimited string.

    A state produced by splitting an address on a comma is exactly the inference
    Gate 103 prohibits, so a string input is refused rather than parsed.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return []
    try:
        return [str(v).strip() for v in value if str(v).strip()]
    except TypeError:
        return []


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
        # Constants. This repository inserts, updates and archives; it never
        # deletes, and it never writes a real customer row.
        "rows_deleted": 0,
        "history_preserved": True,
        "real_customer_rows_written": 0,
        "production_tenant_profiles_created": 0,
        # The two prohibited inferences most relevant here, restated per result
        # so a reader of one result sees them.
        "operating_states_inferred_from_address": False,
        "recognition_status_inferred": False,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    return _json_safe(out)


def prepare_profile_write(
    *,
    organization_id: Any = None,
    tenant_id_label: Any = None,
    customer_org_id_label: Any = None,
    organization_profile_id: Any = None,
    recognition_status: Any = None,
    recognition_status_fact_status: Any = None,
    operating_states: Any = None,
    operating_states_fact_status: Any = None,
    service_area: Any = None,
    programs: Any = None,
    departments: Any = None,
    applicant_classes: Any = None,
    applicant_classes_fact_status: Any = None,
    priority_topics: Any = None,
    excluded_topics: Any = None,
    source_watchlist_preferences: Any = None,
    digest_frequency: Any = None,
    routing_rules: Any = None,
    custom_alerts: Any = None,
    profile_status: Any = None,
    created_by_identity_id: Any = None,
    updated_by_identity_id: Any = None,
    is_demo: bool = False,
    customer_auth_live: bool = False,
    verified_operational_binding: bool = False,
) -> dict[str, Any]:
    """Decide whether a profile may be written. Touches no database.

    Separate from ``upsert_tenant_profile`` on purpose: the verdict is worth
    being able to ask for without a connection, and a caller that wants only the
    verdict should not have to open a session to get one.
    """
    blocked_reasons: list[str] = []

    # -- the anchor ----------------------------------------------------------
    if not str(organization_id or "").strip():
        blocked_reasons.append("profile_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # Refused rather than ignored. Gates 110-113 exist for this substitution.
    if organization_profile_id:
        blocked_reasons.append(
            "organization_profile_id_is_not_an_organization_id_anchor"
        )

    # -- the labels ----------------------------------------------------------
    tenant_label = str(tenant_id_label or "").strip()
    customer_label = str(customer_org_id_label or "").strip()
    if not tenant_label:
        blocked_reasons.append("profile_without_a_tenant_label")

    # -- recognition status, and what may be claimed about it ----------------
    recognition = str(recognition_status or "unknown").strip().lower()
    recognition_fact = str(recognition_status_fact_status or "unknown").strip().lower()
    if recognition not in RECOGNITION_STATUSES:
        blocked_reasons.append(f"recognition_status_not_recognised:{recognition}")
    if recognition_fact not in FACT_STATUSES:
        blocked_reasons.append(
            f"recognition_status_fact_status_not_recognised:{recognition_fact}"
        )
    if recognition == "unknown" and recognition_fact not in UNESTABLISHED_FACT_STATUSES:
        # The constraint the database also enforces. A guess must not be stored
        # as an established fact.
        blocked_reasons.append(
            "unknown_recognition_status_cannot_carry_an_established_fact_status"
        )

    # -- operating states, which decide state matching -----------------------
    states = _list_of(operating_states)
    states_fact = str(operating_states_fact_status or "unknown").strip().lower()
    if states_fact not in FACT_STATUSES:
        blocked_reasons.append(
            f"operating_states_fact_status_not_recognised:{states_fact}"
        )
    if isinstance(operating_states, str):
        # A delimited string is how a state gets produced from an address.
        blocked_reasons.append("operating_states_must_be_a_list_not_a_delimited_string")
    if not states:
        blocked_reasons.append("no_operating_states_so_state_matching_is_refused")

    area = str(service_area or "").strip()
    if area and not states:
        # Named explicitly: this is the moment somebody would be tempted to
        # derive a state from a description.
        blocked_reasons.append(
            "service_area_present_without_operating_states_and_none_is_inferred"
        )

    # -- applicant classes ---------------------------------------------------
    classes = _list_of(applicant_classes)
    classes_fact = str(applicant_classes_fact_status or "unknown").strip().lower()
    if classes_fact not in FACT_STATUSES:
        blocked_reasons.append(
            f"applicant_classes_fact_status_not_recognised:{classes_fact}"
        )
    unknown_classes = [c for c in classes if c not in APPLICANT_CLASSES]
    if unknown_classes:
        blocked_reasons.append(
            f"applicant_class_not_recognised:{sorted(unknown_classes)[0]}"
        )
    if not classes:
        blocked_reasons.append("no_applicant_classes_supplied")

    # -- preferences ---------------------------------------------------------
    frequency = str(digest_frequency or "").strip().lower()
    if frequency not in DIGEST_FREQUENCIES:
        blocked_reasons.append(f"digest_frequency_not_recognised:{frequency}")

    status = str(profile_status or "draft").strip().lower()
    if status not in PROFILE_STATUSES:
        blocked_reasons.append(f"profile_status_not_recognised:{status}")
    if status == "archived":
        blocked_reasons.append("archived_profiles_are_written_by_archive_not_upsert")

    # -- who may write, and whether this is a production write ---------------
    demo_fixture = bool(is_demo)
    production_write = not demo_fixture

    if production_write and not customer_auth_live:
        blocked_reasons.append("production_profile_write_requires_live_customer_auth")
    if production_write and not verified_operational_binding:
        blocked_reasons.append(
            "production_profile_write_requires_a_verified_operational_binding"
        )

    storage_allowed = not blocked_reasons
    production_write_allowed = bool(storage_allowed and production_write)

    # A fact nobody has established, or a class nobody has confirmed, needs a
    # human before it drives anything.
    human_review_required = bool(
        recognition_fact not in ACTIONABLE_FACT_STATUSES
        or states_fact not in ACTIONABLE_FACT_STATUSES
        or classes_fact not in ACTIONABLE_FACT_STATUSES
        or demo_fixture
    )

    return _result(
        operation="prepare_profile_write",
        organization_id=str(organization_id or "") or None,
        tenant_id_label=tenant_label or None,
        customer_org_id_label=customer_label or None,
        recognition_status=recognition,
        recognition_status_fact_status=recognition_fact,
        operating_states=states,
        operating_states_fact_status=states_fact,
        service_area=area or None,
        programs=_list_of(programs),
        departments=_list_of(departments),
        applicant_classes=classes,
        applicant_classes_fact_status=classes_fact,
        priority_topics=_list_of(priority_topics),
        excluded_topics=_list_of(excluded_topics),
        source_watchlist_preferences=_list_of(source_watchlist_preferences),
        digest_frequency=frequency,
        routing_rules=_list_of(routing_rules),
        custom_alerts=_list_of(custom_alerts),
        profile_status=status,
        created_by_identity_id=str(created_by_identity_id or "") or None,
        updated_by_identity_id=str(updated_by_identity_id or "") or None,
        archived_at=None,
        demo_fixture=demo_fixture,
        human_review_required=human_review_required,
        storage_allowed=storage_allowed,
        production_write_allowed=production_write_allowed,
        write_performed=False,
        read_performed=False,
        rows_written=0,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def upsert_tenant_profile(
    *,
    connection: Any = None,
    profile_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert or replace the live profile for an organization.

    The decision is made by ``prepare_profile_write`` rather than duplicated
    here, so the two can never disagree about what is storable.

    "Upsert" means: archive whatever live profile exists, then insert. The
    partial unique index makes that the only safe shape, and it keeps the
    previous profile as the thing a complaint gets debugged against.
    """
    decision = prepare_profile_write(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if decision["storage_allowed"] and connection is not None:
        anchor = _as_uuid(decision["organization_id"])
        # Archive the live one first. Nothing is deleted.
        connection.execute(
            sa.update(TENANT_BETA_PROFILES)
            .where(
                TENANT_BETA_PROFILES.c.organization_id == anchor,
                TENANT_BETA_PROFILES.c.archived_at.is_(None),
            )
            .values(
                profile_status="archived",
                archived_at=moment,
                updated_at=moment,
            )
        )
        connection.execute(
            sa.insert(TENANT_BETA_PROFILES).values(
                id=profile_id or uuid.uuid4(),
                organization_id=anchor,
                tenant_id_label=str(decision["tenant_id_label"]),
                customer_org_id_label=decision["customer_org_id_label"],
                recognition_status=decision["recognition_status"],
                recognition_status_fact_status=decision[
                    "recognition_status_fact_status"
                ],
                operating_states=decision["operating_states"],
                operating_states_fact_status=decision["operating_states_fact_status"],
                service_area=decision["service_area"],
                applicant_classes=decision["applicant_classes"],
                applicant_classes_fact_status=decision["applicant_classes_fact_status"],
                programs=decision["programs"],
                departments=decision["departments"],
                priority_topics=decision["priority_topics"],
                excluded_topics=decision["excluded_topics"],
                source_watchlist_preferences=decision["source_watchlist_preferences"],
                digest_frequency=decision["digest_frequency"],
                routing_rules=decision["routing_rules"],
                custom_alerts=decision["custom_alerts"],
                profile_status=decision["profile_status"],
                created_by_identity_id=_as_uuid(decision["created_by_identity_id"]),
                updated_by_identity_id=_as_uuid(decision["updated_by_identity_id"]),
                archived_at=None,
                is_demo=bool(decision["demo_fixture"]),
                human_review_required=bool(decision["human_review_required"]),
                blocked_reasons=[],
                created_at=moment,
                updated_at=moment,
            )
        )
        written = 1

    return _result(
        **{
            **decision,
            "operation": "upsert_tenant_profile",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "organization_id": str(row["organization_id"]),
        "tenant_id_label": row["tenant_id_label"],
        "customer_org_id_label": row["customer_org_id_label"],
        "recognition_status": row["recognition_status"],
        "recognition_status_fact_status": row["recognition_status_fact_status"],
        "operating_states": list(row["operating_states"] or []),
        "operating_states_fact_status": row["operating_states_fact_status"],
        "service_area": row["service_area"],
        "applicant_classes": list(row["applicant_classes"] or []),
        "applicant_classes_fact_status": row["applicant_classes_fact_status"],
        "programs": list(row["programs"] or []),
        "departments": list(row["departments"] or []),
        "priority_topics": list(row["priority_topics"] or []),
        "excluded_topics": list(row["excluded_topics"] or []),
        "source_watchlist_preferences": list(row["source_watchlist_preferences"] or []),
        "digest_frequency": row["digest_frequency"],
        "routing_rules": list(row["routing_rules"] or []),
        "custom_alerts": list(row["custom_alerts"] or []),
        "profile_status": row["profile_status"],
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
        "tenant_id_label": None,
        "customer_org_id_label": None,
        "recognition_status": None,
        "operating_states": [],
        "service_area": None,
        "programs": [],
        "departments": [],
        "applicant_classes": [],
        "priority_topics": [],
        "excluded_topics": [],
        "source_watchlist_preferences": [],
        "digest_frequency": None,
        "routing_rules": [],
        "custom_alerts": [],
        "profile_status": None,
        "created_by_identity_id": None,
        "updated_by_identity_id": None,
        "archived_at": None,
        "human_review_required": True,
    }


def get_tenant_profile(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    """The live profile for an organization.

    Anchored on ``organization_id``. There is no lookup by label, because a read
    anchored on a label is a read the RLS policy cannot scope.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = sa.select(TENANT_BETA_PROFILES).where(
            TENANT_BETA_PROFILES.c.organization_id == _as_uuid(organization_id)
        )
        if not include_archived:
            query = query.where(TENANT_BETA_PROFILES.c.archived_at.is_(None))
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_tenant_profile_for_this_organization")

    facts = _row_to_facts(row) if row is not None else _empty_facts()

    return _result(
        operation="get_tenant_profile",
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


def list_tenant_profiles(
    *,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Every profile for one organization, archived ones included.

    Archived rows are returned because they are the audit trail. A listing that
    hid them would make an archive indistinguishable from a row that never
    existed.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        rows = [
            _row_to_facts(row)
            for row in connection.execute(
                sa.select(TENANT_BETA_PROFILES)
                .where(
                    TENANT_BETA_PROFILES.c.organization_id == _as_uuid(organization_id)
                )
                .order_by(TENANT_BETA_PROFILES.c.created_at)
            ).mappings()
        ]

    result = _result(
        operation="list_tenant_profiles",
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
    result["profiles"] = rows
    result["archived_count"] = sum(1 for r in rows if r["archived_at"])
    return _json_safe(result)


def archive_tenant_profile(
    *,
    connection: Any = None,
    organization_id: Any = None,
    archived_by_identity_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Withdraw the live profile. An UPDATE, never a DELETE.

    The row stays, `archived_at` is set, and the partial unique index stops
    treating it as the live profile — so a replacement can be created without
    the history disappearing.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("archive_without_a_uuid_shaped_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if not blocked_reasons:
        row = (
            connection.execute(
                sa.select(TENANT_BETA_PROFILES).where(
                    TENANT_BETA_PROFILES.c.organization_id == _as_uuid(organization_id),
                    TENANT_BETA_PROFILES.c.archived_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked_reasons.append("no_live_tenant_profile_to_archive")
        else:
            connection.execute(
                sa.update(TENANT_BETA_PROFILES)
                .where(TENANT_BETA_PROFILES.c.id == row["id"])
                .values(
                    profile_status="archived",
                    archived_at=moment,
                    updated_by_identity_id=_as_uuid(archived_by_identity_id),
                    human_review_required=True,
                    updated_at=moment,
                )
            )
            written = 1

    return _result(
        operation="archive_tenant_profile",
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "profile_status": "archived" if written else None,
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


def validate_profile_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Is what is stored fit to drive matching and digests?

    Reads the live profile and runs Gate 123C's validation over it, so a caller
    can ask "would this profile produce a correct digest" without constructing
    one.
    """
    from nativeforge.services.tenant_profile_persistence_validation_service import (
        validate_tenant_profile,
    )

    stored = get_tenant_profile(connection=connection, organization_id=organization_id)
    validation = validate_tenant_profile(
        recognition_status=stored.get("recognition_status"),
        recognition_status_fact_status=stored.get("recognition_status_fact_status"),
        operating_states=stored.get("operating_states"),
        operating_states_fact_status=stored.get("operating_states_fact_status"),
        service_area=stored.get("service_area"),
        applicant_classes=stored.get("applicant_classes"),
        applicant_classes_fact_status=stored.get("applicant_classes_fact_status"),
        priority_topics=stored.get("priority_topics"),
        excluded_topics=stored.get("excluded_topics"),
        digest_frequency=stored.get("digest_frequency"),
        routing_rules=stored.get("routing_rules"),
        source_watchlist_preferences=stored.get("source_watchlist_preferences"),
    )

    result = _result(
        **{
            **stored,
            "operation": "validate_profile_persistence",
            "blocked_reasons": sorted(
                {*stored["blocked_reasons"], *validation["blocked_reasons"]}
            ),
        }
    )
    result["validation"] = validation
    result["profile_found"] = bool(stored["rows_read"])
    return _json_safe(result)


def profile_repository_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this repository must never be able to produce."""
    failures: list[str] = []

    operation = str(result.get("operation") or "")
    if operation not in REPOSITORY_OPERATIONS:
        failures.append("operation_outside_vocabulary")

    if result.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        failures.append("rls_anchor_is_not_organization_id")

    for name in sorted(FORBIDDEN_ANCHOR_NAMES):
        if result.get(f"{name}_anchor") or result.get(f"anchored_on_{name}"):
            failures.append(f"anchored_on_a_label:{name}")

    if result.get("rows_deleted"):
        failures.append("a_tenant_profile_row_was_deleted")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("production_tenant_profiles_created"):
        failures.append("a_production_tenant_profile_was_created")

    if result.get("operating_states_inferred_from_address"):
        failures.append("an_operating_state_was_inferred_from_an_address")

    if result.get("recognition_status_inferred"):
        failures.append("a_recognition_status_was_inferred")

    if result.get("write_performed") and operation not in WRITE_OPERATIONS:
        failures.append("a_read_operation_reported_a_write")

    if result.get("rows_written") and not result.get("write_performed"):
        failures.append("rows_written_without_a_write")

    if result.get("write_performed") and not result.get("storage_allowed"):
        failures.append("a_write_happened_without_storage_being_allowed")

    if result.get("production_write_allowed") and not result.get("storage_allowed"):
        failures.append("a_production_write_was_allowed_without_storage")

    # The rule this whole gate turns on.
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

    recognition = str(result.get("recognition_status") or "")
    fact = str(result.get("recognition_status_fact_status") or "")
    if (
        recognition == "unknown"
        and fact
        and fact not in UNESTABLISHED_FACT_STATUSES
        and result.get("storage_allowed")
    ):
        failures.append("an_unknown_recognition_status_claimed_an_established_fact")

    if result.get("storage_allowed") and not result.get("operating_states"):
        if operation in {"prepare_profile_write", "upsert_tenant_profile"}:
            failures.append("a_profile_was_storable_without_operating_states")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))


def prohibited_inferences() -> list[dict[str, str]]:
    """Gate 103's refusals, bridged so this repository cannot restate them."""
    return _json_safe(
        [{"inference": name, "why": why} for name, why in INFERENCE_PROHIBITED]
    )
