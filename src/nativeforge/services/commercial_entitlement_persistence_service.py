"""Persist ledger events and materialise entitlement state (Gate 178)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa

from nativeforge.services.commercial_entitlement_service import derive_entitlement
from nativeforge.services.commercial_ledger_service import open_license, replay
from nativeforge.services.commercial_license_model_service import POLICY_VERSION
from nativeforge.services.commercial_repository_service import EVENTS, STATE

SCHEMA_VERSION = "nf_commercial_entitlement_persistence_v1"


def persist_license_purchase(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    purchased_at: str | dt.date,
    recorded_by: str,
    is_demo: bool = False,
) -> dict[str, Any]:
    """Record a legitimate licence purchase via the canonical ledger."""
    events = open_license(
        organization_id=organization_id,
        purchased_at=purchased_at,
        recorded_by=recorded_by,
        is_demo=is_demo,
    )
    for event in events:
        _insert_event(connection, event)
    material = _load_events(connection, organization_id=organization_id)
    entitlement = derive_entitlement(
        organization_id=organization_id,
        ledger=replay(material),
        extensions=[],
        as_of=dt.date.today(),
    )
    _upsert_state(connection, organization_id=organization_id, entitlement=entitlement, is_demo=is_demo)
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": organization_id,
        "events_written": len(events),
        "benefit_access": entitlement.get("benefit_access"),
        "license_state": entitlement.get("license_state"),
    }


def _load_events(connection: sa.engine.Connection, *, organization_id: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in connection.execute(
            sa.text(
                f"SELECT event_id, event_type, occurred_at, amount_cents, paid_through, "
                f"organization_id, recorded_at, recorded_by, detail, reason, "
                f"corrects_event_id, policy_version, is_demo "
                f"FROM {EVENTS} WHERE organization_id = :org "
                f"ORDER BY occurred_at, event_id"
            ),
            {"org": organization_id},
        ).mappings()
    ]


def _insert_event(connection: sa.engine.Connection, event: dict[str, Any]) -> None:
    recorded_at = event.get("recorded_at")
    if isinstance(recorded_at, str):
        recorded_at = dt.datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    connection.execute(
        sa.text(
            f"INSERT INTO {EVENTS} "
            f"(event_id, organization_id, event_type, occurred_at, recorded_at, "
            f"recorded_by, amount_cents, paid_through, detail, reason, "
            f"corrects_event_id, policy_version, is_demo) "
            f"VALUES (:eid, :org, :etype, :occ, :rec, :by, :amt, :pt, :det, "
            f":reason, :corr, :pv, :demo)"
        ),
        {
            "eid": event["event_id"],
            "org": event["organization_id"],
            "etype": event["event_type"],
            "occ": event["occurred_at"],
            "rec": recorded_at or dt.datetime.now(dt.UTC),
            "by": event["recorded_by"],
            "amt": event.get("amount_cents"),
            "pt": event.get("paid_through"),
            "det": event.get("detail"),
            "reason": event.get("reason"),
            "corr": event.get("corrects_event_id"),
            "pv": event["policy_version"],
            "demo": bool(event.get("is_demo")),
        },
    )


def _upsert_state(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    entitlement: dict[str, Any],
    is_demo: bool,
) -> None:
    connection.execute(
        sa.text(f"DELETE FROM {STATE} WHERE organization_id = :org"),
        {"org": organization_id},
    )
    paid_through = entitlement.get("paid_through")
    if isinstance(paid_through, str) and paid_through:
        paid_through = dt.date.fromisoformat(paid_through[:10])
    connection.execute(
        sa.text(
            f"INSERT INTO {STATE} "
            f"(organization_id, license_state, maintenance_state, benefit_access, "
            f"paid_through, delinquency_days, days_until_license_expiration, "
            f"active_extension_id, extension_expires_at, maintenance_forgiven, "
            f"policy_version, computed_at, is_demo) "
            f"VALUES (:org, :lic, :maint, :ben, :pt, :del, :days, :ext, :extexp, "
            f":forgiven, :pv, :computed, :demo)"
        ),
        {
            "org": organization_id,
            "lic": entitlement.get("license_state"),
            "maint": entitlement.get("maintenance_state"),
            "ben": entitlement.get("benefit_access"),
            "pt": paid_through,
            "del": int(entitlement.get("delinquency_days") or 0),
            "days": int(entitlement.get("days_until_license_expiration") or 0),
            "ext": entitlement.get("active_extension_id"),
            "extexp": entitlement.get("extension_expires_at"),
            "forgiven": bool(entitlement.get("maintenance_forgiven")),
            "pv": entitlement.get("policy_version") or POLICY_VERSION,
            "computed": dt.datetime.now(dt.UTC),
            "demo": bool(is_demo),
        },
    )
