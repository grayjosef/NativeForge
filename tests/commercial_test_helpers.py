"""Persist a working commercial licence for HTTP integration tests."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.services.commercial_ledger_service import open_license
from nativeforge.services.commercial_repository_service import EVENTS

PURCHASED = "2026-03-15"


def persist_working_license(
    connection: sa.engine.Connection,
    *,
    organization_id: uuid.UUID | str,
    is_demo: bool = False,
) -> None:
    org = str(organization_id)
    events = open_license(
        organization_id=org,
        purchased_at=PURCHASED,
        recorded_by="test:commercial_helper",
        is_demo=is_demo,
    )
    for event in events:
        _insert_event(connection, event)


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
            "demo": 1 if event.get("is_demo") else 0,
        },
    )
