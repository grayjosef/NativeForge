"""179J: the customer read paths, defined once.

The dashboard asks these on every page load, for every tenant. They are the
queries that decide whether NativeForge feels instant or feels like a report
somebody runs overnight.

Shared registry, same as the earlier gates: the scale proof EXPLAINs exactly
what the service executes, so the index proof cannot drift from the SQL.
"""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_customer_repository_v1"

DECISIONS = "nf_customer_opportunity_decisions"
HISTORY = "nf_customer_decision_history"

FORBIDDEN_SHAPES: tuple[str, ...] = (
    "scan_every_tenants_decisions_to_answer_one_tenants_question",
    "walk_the_history_to_find_the_current_state",
    "opportunity_by_tenant_by_document_cartesian",
)


def q_my_watch_list(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    """179E. What is this organisation watching?"""
    return (
        f"SELECT canonical_id, decided_at, actor_id FROM {DECISIONS} "
        f"WHERE organization_id = :organization_id AND decision_state = :state "
        f"ORDER BY decided_at DESC LIMIT 200",
        {"organization_id": organization_id, "state": "WATCHED"},
    )


def q_my_active_pursuits(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    return (
        f"SELECT canonical_id, decided_at, actor_id FROM {DECISIONS} "
        f"WHERE organization_id = :organization_id AND decision_state = :state "
        f"ORDER BY decided_at DESC LIMIT 200",
        {"organization_id": organization_id, "state": "PURSUING"},
    )


def q_my_dismissed(*, organization_id: str) -> tuple[str, dict[str, Any]]:
    """Needed to HIDE rows from one feed - never to delete anything."""
    return (
        f"SELECT canonical_id FROM {DECISIONS} "
        f"WHERE organization_id = :organization_id AND decision_state = :state "
        f"LIMIT 500",
        {"organization_id": organization_id, "state": "DISMISSED"},
    )


def q_decision_for_opportunity(
    *, organization_id: str, canonical_id: str
) -> tuple[str, dict[str, Any]]:
    """The primary key lookup behind every opportunity page."""
    return (
        f"SELECT decision_state, previous_state, actor_id, decided_at, reason "
        f"FROM {DECISIONS} WHERE organization_id = :organization_id "
        f"AND canonical_id = :canonical_id",
        {"organization_id": organization_id, "canonical_id": canonical_id},
    )


def q_decision_history(
    *, organization_id: str, canonical_id: str
) -> tuple[str, dict[str, Any]]:
    """ "Why did this stop appearing?" - asked months later."""
    return (
        f"SELECT decision_state, previous_state, actor_id, decided_at, "
        f"reason, superseded_at FROM {HISTORY} "
        f"WHERE organization_id = :organization_id "
        f"AND canonical_id = :canonical_id ORDER BY superseded_at DESC",
        {"organization_id": organization_id, "canonical_id": canonical_id},
    )


CRITICAL_QUERIES: dict[str, dict[str, Any]] = {
    "my_watch_list": {
        "builder": q_my_watch_list,
        "sample_kwargs": {"organization_id": "org:000042"},
        "table": DECISIONS,
    },
    "my_active_pursuits": {
        "builder": q_my_active_pursuits,
        "sample_kwargs": {"organization_id": "org:000042"},
        "table": DECISIONS,
    },
    "my_dismissed": {
        "builder": q_my_dismissed,
        "sample_kwargs": {"organization_id": "org:000042"},
        "table": DECISIONS,
    },
    "decision_for_opportunity": {
        "builder": q_decision_for_opportunity,
        "sample_kwargs": {
            "organization_id": "org:000042",
            "canonical_id": "canon:000042",
        },
        "table": DECISIONS,
    },
    "decision_history": {
        "builder": q_decision_history,
        "sample_kwargs": {
            "organization_id": "org:000042",
            "canonical_id": "canon:000042",
        },
        "table": HISTORY,
    },
}


def plan_is_a_table_scan(plan: str, table: str) -> bool:
    """`SCAN t` is a table scan; `SCAN t USING INDEX i` is an index walk."""
    pattern = re.compile(
        rf"\bSCAN\s+{re.escape(table)}\b(?!\s+USING\s+(?:COVERING\s+)?INDEX)"
    )
    return bool(pattern.search(plan))


def run_critical_query(connection: Any, name: str) -> list[dict[str, Any]]:
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    return [dict(r) for r in connection.execute(sa.text(sql), params).mappings().all()]


def explain_critical_query(connection: Any, name: str) -> dict[str, Any]:
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    rows = connection.execute(sa.text(f"EXPLAIN QUERY PLAN {sql}"), params).fetchall()
    plan = " | ".join(str(r[-1]) for r in rows)
    scans = plan_is_a_table_scan(plan, spec["table"])
    return {
        "query": name,
        "plan": plan,
        "scans_the_table": scans,
        "indexed": ("SEARCH" in plan) and not scans,
    }


def explain_is_falsifiable(connection: Any) -> dict[str, Any]:
    """Prove the scan detector still fires, on a query nothing can serve."""
    sql = (
        f"SELECT canonical_id FROM {DECISIONS} "
        "WHERE reason LIKE '%unindexable%' LIMIT 5"
    )
    rows = connection.execute(sa.text(f"EXPLAIN QUERY PLAN {sql}")).fetchall()
    plan = " | ".join(str(r[-1]) for r in rows)
    return {
        "control_query_plan": plan,
        "detector_reports_a_table_scan": plan_is_a_table_scan(plan, DECISIONS),
    }


def describe_repository() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "critical_query_count": len(CRITICAL_QUERIES),
        "critical_queries": sorted(CRITICAL_QUERIES),
        "forbidden_shapes": list(FORBIDDEN_SHAPES),
        "every_query_is_tenant_scoped": all(
            "organization_id" in spec["sample_kwargs"]
            for spec in CRITICAL_QUERIES.values()
        ),
        "current_state_is_not_derived_from_history": True,
        "queries_are_defined_once": True,
    }
