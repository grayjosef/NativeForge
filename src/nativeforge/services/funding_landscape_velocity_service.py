"""Temporal funding landscape metrics — fail closed without durable history."""

from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa

from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
)

VELOCITY_METHODOLOGY = "nativeforge.opportunity_velocity.v1"
SCHEMA_VERSION = "nf_opportunity_velocity_v1"


def velocity_support_audit() -> dict[str, Any]:
    return {
        "supported": False,
        "partial_metrics": ["new_active_opportunities_7d"],
        "unsupported_without_substrate": [
            "new_known_value_7d",
            "known_value_closed_7d",
            "net_known_active_value_change_7d",
        ],
        "required_substrate": (
            "durable value-amendment snapshots or metric history table; "
            "single current provenance graph is insufficient for value delta claims"
        ),
        "methodology_version": None,
    }


def compute_partial_velocity(
    connection: sa.engine.Connection,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    stamp = now or dt.datetime.now(dt.UTC)
    cutoff = stamp - dt.timedelta(days=7)
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    row = connection.execute(
        sa.text(
            f"""
            SELECT COUNT(*) FROM {CANONICAL}
            WHERE lifecycle_state IN ({active_list})
              AND first_seen_at IS NOT NULL
              AND first_seen_at >= :cutoff
            """
        ),
        {"cutoff": cutoff},
    ).fetchone()
    new_active = int(row[0] or 0) if row else 0
    audit = velocity_support_audit()
    return {
        "schema_version": SCHEMA_VERSION,
        "velocity_support": audit["supported"],
        "velocity_support_audit": audit,
        "methodology_version": VELOCITY_METHODOLOGY if audit["supported"] else None,
        "measurements": {
            "new_active_opportunities_7d": new_active,
        },
        "note": "Value velocity metrics omitted until durable temporal substrate exists.",
    }
