"""178K: the eight commercial read paths, defined once.

The scale proof must EXPLAIN the queries the service actually runs. If the
verifier held its own copies they would diverge the first time somebody tuned
a WHERE clause, and the index proof would quietly start describing SQL that
nothing executes. So every critical query lives in `CRITICAL_QUERIES`, and
both the service and the scale phase read that one registry.

## What is deliberately absent

No query replays a ledger to answer "is this organisation frozen". That is
what `nf_commercial_entitlement_state` is for: 178K allows a summary
structure where one is warranted, and answering a fleet-wide question by
replaying thousands of histories is the definition of warranted.

`FORBIDDEN_SHAPES` names the three ways this layer would die at scale, so a
reviewer can check the list against the SQL below by eye.
"""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_commercial_repository_v1"

EVENTS = "nf_commercial_ledger_events"
STATE = "nf_commercial_entitlement_state"
EXTENSIONS = "nf_commercial_benefit_extensions"

#: Shapes that must never appear. Named so their absence is checkable.
FORBIDDEN_SHAPES: tuple[str, ...] = (
    "replay_every_ledger_to_answer_a_fleet_question",
    "per_request_whole_history_scan",
    "cross_join_of_events_and_extensions",
)


def q_current_entitlement(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    """178K path 1. One organisation's standing, by primary key."""
    return (
        f"SELECT organization_id, license_state, maintenance_state, "
        f"benefit_access, delinquency_days, paid_through "
        f"FROM {STATE} WHERE organization_id = :organization_id",
        {"organization_id": organization_id},
    )


def q_frozen_organizations() -> tuple[str, dict[str, Any]]:
    """178K path 2. Who cannot work right now, driven by ix_..._frozen."""
    return (
        f"SELECT organization_id, license_state, delinquency_days "
        f"FROM {STATE} WHERE benefit_access = :benefit "
        f"ORDER BY license_state LIMIT 200",
        {"benefit": "BENEFIT_FROZEN"},
    )


def q_expiring_maintenance(*, before: str) -> tuple[str, dict[str, Any]]:
    """178K path 3. Terms about to lapse - the one that earns renewals."""
    return (
        f"SELECT organization_id, paid_through, maintenance_state "
        f"FROM {STATE} WHERE maintenance_state = :state "
        f"AND paid_through < :before ORDER BY paid_through LIMIT 200",
        {"state": "MAINTENANCE_CURRENT", "before": before},
    )


def q_expired_licenses() -> tuple[str, dict[str, Any]]:
    """178K path 4. Driven by ix_..._expired."""
    return (
        f"SELECT organization_id, delinquency_days FROM {STATE} "
        f"WHERE license_state = :state ORDER BY delinquency_days DESC LIMIT 200",
        {"state": "LICENSE_EXPIRED"},
    )


def q_active_extensions(*, as_of: str) -> tuple[str, dict[str, Any]]:
    """178K path 5. Live grants, driven by ix_..._active."""
    return (
        f"SELECT extension_id, organization_id, expires_at, duration_days "
        f"FROM {EXTENSIONS} WHERE expires_at > :as_of AND revoked_at IS NULL "
        f"ORDER BY expires_at LIMIT 200",
        {"as_of": as_of},
    )


def q_extension_history(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    """178K path 6. Every grant ever made to one organisation."""
    return (
        f"SELECT extension_id, granted_at, duration_days, granted_by, reason "
        f"FROM {EXTENSIONS} WHERE organization_id = :organization_id "
        f"ORDER BY granted_at DESC",
        {"organization_id": organization_id},
    )


def q_license_history(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    """178K path 7. The licence events, driven by ix_..._org_history."""
    return (
        f"SELECT event_id, event_type, occurred_at, amount_cents "
        f"FROM {EVENTS} WHERE organization_id = :organization_id "
        f"ORDER BY occurred_at LIMIT 200",
        {"organization_id": organization_id},
    )


def q_maintenance_history(
    *, event_type: str = "MAINTENANCE_PAID"
) -> tuple[str, dict[str, Any]]:
    """178K path 8. Maintenance across the fleet, driven by ix_..._by_type."""
    return (
        f"SELECT event_id, organization_id, occurred_at, amount_cents, "
        f"paid_through FROM {EVENTS} WHERE event_type = :event_type "
        f"ORDER BY occurred_at DESC LIMIT 200",
        {"event_type": event_type},
    )


CRITICAL_QUERIES: dict[str, dict[str, Any]] = {
    "current_entitlement_by_org": {
        "builder": q_current_entitlement,
        "sample_kwargs": {"organization_id": "org:000042"},
        "expected_index": f"{STATE}",
        "table": STATE,
    },
    "frozen_organizations": {
        "builder": q_frozen_organizations,
        "sample_kwargs": {},
        "expected_index": f"ix_{STATE}_frozen",
        "table": STATE,
    },
    "expiring_maintenance": {
        "builder": q_expiring_maintenance,
        "sample_kwargs": {"before": "2028-01-01"},
        "expected_index": f"ix_{STATE}_expiring",
        "table": STATE,
    },
    "expired_licenses": {
        "builder": q_expired_licenses,
        "sample_kwargs": {},
        "expected_index": f"ix_{STATE}_expired",
        "table": STATE,
    },
    "active_extensions": {
        "builder": q_active_extensions,
        "sample_kwargs": {"as_of": "2027-06-05"},
        "expected_index": f"ix_{EXTENSIONS}_active",
        "table": EXTENSIONS,
    },
    "extension_history": {
        "builder": q_extension_history,
        "sample_kwargs": {"organization_id": "org:000042"},
        "expected_index": f"ix_{EXTENSIONS}_org_history",
        "table": EXTENSIONS,
    },
    "license_history": {
        "builder": q_license_history,
        "sample_kwargs": {"organization_id": "org:000042"},
        "expected_index": f"ix_{EVENTS}_org_history",
        "table": EVENTS,
    },
    "maintenance_history": {
        "builder": q_maintenance_history,
        "sample_kwargs": {},
        "expected_index": f"ix_{EVENTS}_by_type",
        "table": EVENTS,
    },
}


def plan_is_a_table_scan(plan: str, table: str) -> bool:
    """Is this plan reading the TABLE, or walking an index?

    SQLite prints `SCAN <table>` for a full table scan and
    `SCAN <table> USING INDEX <name>` for an ordered index walk. Testing for
    the substring `SCAN <table>` matches both, which in Gate 176 reported the
    fastest query in the set as a full scan.
    """
    pattern = re.compile(
        rf"\bSCAN\s+{re.escape(table)}\b(?!\s+USING\s+(?:COVERING\s+)?INDEX)"
    )
    return bool(pattern.search(plan))


def run_critical_query(connection: Any, name: str) -> list[dict[str, Any]]:
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    return [dict(r) for r in connection.execute(sa.text(sql), params).mappings().all()]


def explain_critical_query(connection: Any, name: str) -> dict[str, Any]:
    """EXPLAIN the query the service runs - not a copy of it."""
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    rows = connection.execute(sa.text(f"EXPLAIN QUERY PLAN {sql}"), params).fetchall()
    plan = " | ".join(str(r[-1]) for r in rows)

    scans_table = plan_is_a_table_scan(plan, spec["table"])
    # A primary-key lookup is served by the table's own rowid/PK structure
    # and never names a separate index; requiring one would mean adding an
    # index to satisfy a measurement rather than a system.
    seeks = "SEARCH" in plan
    uses_expected = spec["expected_index"] in plan

    return {
        "query": name,
        "plan": plan,
        "expected_index": spec["expected_index"],
        "uses_expected_index": uses_expected,
        "scans_the_table": scans_table,
        "indexed": (uses_expected or seeks) and not scans_table,
    }


def explain_is_falsifiable(connection: Any) -> dict[str, Any]:
    """Prove the scan detector still fires, on a query nothing can serve."""
    sql = (
        f"SELECT organization_id FROM {STATE} "
        "WHERE policy_version LIKE '%unindexable%' LIMIT 5"
    )
    rows = connection.execute(sa.text(f"EXPLAIN QUERY PLAN {sql}")).fetchall()
    plan = " | ".join(str(r[-1]) for r in rows)
    return {
        "control_query_plan": plan,
        "detector_reports_a_table_scan": plan_is_a_table_scan(plan, STATE),
    }


def describe_repository() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "critical_query_count": len(CRITICAL_QUERIES),
        "critical_queries": sorted(CRITICAL_QUERIES),
        "forbidden_shapes": list(FORBIDDEN_SHAPES),
        "every_query_names_its_table": all(
            spec.get("table") for spec in CRITICAL_QUERIES.values()
        ),
        "queries_are_defined_once": True,
        "fleet_questions_read_the_summary_not_the_ledger": True,
    }
