"""Org-scoped blocked known value from deterministic Gate 174 conditions."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from nativeforge.services.eligibility_requirement_model_service import (
    CONDITIONALLY_ELIGIBLE,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.opportunity_value_intelligence_service import (
    DEFAULT_CURRENCY,
    VALUE_KNOWN,
    enumerate_active_opportunity_values,
)

BLOCKED_VALUE_METHODOLOGY = "nativeforge.blocked_value.v1"
SCHEMA_VERSION = "nf_blocked_value_v1"

MATCHES = "nf_tenant_eligibility_matches"

# Gate 174 persists requirement_kind strings on CONDITIONALLY_ELIGIBLE rows only.
BLOCK_REASON_MATRIX: list[dict[str, Any]] = [
    {
        "block_reason": "condition_to_obtain",
        "persisted": True,
        "current": True,
        "deterministic": True,
        "traceable": True,
        "org_scoped": True,
        "multi_valued": True,
        "safe_for_value_metric": True,
        "source": f"{MATCHES}.conditions_to_obtain_json + eligibility_result=CONDITIONALLY_ELIGIBLE",
    },
    {
        "block_reason": "ineligible_unsatisfied_requirement",
        "persisted": False,
        "current": False,
        "deterministic": False,
        "traceable": False,
        "org_scoped": True,
        "multi_valued": False,
        "safe_for_value_metric": False,
        "source": "unsatisfied requirement kinds not stored on match rows",
    },
]


def blocked_value_support() -> dict[str, Any]:
    safe = [r for r in BLOCK_REASON_MATRIX if r.get("safe_for_value_metric")]
    return {
        "supported": bool(safe),
        "methodology_version": BLOCKED_VALUE_METHODOLOGY if safe else None,
        "blocked_value_dimensions_are_non_additive": True,
        "matrix": BLOCK_REASON_MATRIX,
    }


def compute_org_blocked_known_value(
    connection: sa.engine.Connection,
    *,
    tenant_id: str,
) -> dict[str, Any]:
    support = blocked_value_support()
    if not support["supported"]:
        return {**support, "by_reason": {}}

    current = is_current_active_sql(connection)
    rows = connection.execute(
        sa.text(
            f"""
            SELECT canonical_id, eligibility_result, conditions_to_obtain_json
            FROM {MATCHES}
            WHERE tenant_id = :tid AND {current}
            """
        ),
        {"tid": tenant_id},
    ).fetchall()

    values = {
        str(r["canonical_id"]): r
        for r in enumerate_active_opportunity_values(connection)
    }

    by_reason: dict[str, dict[str, Any]] = {}
    for canonical_id, result, cond_json in rows:
        if str(result) != CONDITIONALLY_ELIGIBLE:
            continue
        try:
            conditions = json.loads(cond_json or "[]")
        except json.JSONDecodeError:
            conditions = []
        if not isinstance(conditions, list) or not conditions:
            continue
        rec = values.get(str(canonical_id))
        if not rec or rec["value_status"] != VALUE_KNOWN:
            continue
        amount = rec.get("selected_amount")
        if amount is None:
            continue
        for kind in conditions:
            reason = str(kind)
            bucket = by_reason.setdefault(
                reason,
                {
                    "blocked_opportunity_count": 0,
                    "blocked_known_value_by_currency": {},
                    "canonical_ids": [],
                },
            )
            bucket["blocked_opportunity_count"] += 1
            cur = str(rec.get("currency") or DEFAULT_CURRENCY)
            bucket["blocked_known_value_by_currency"][cur] = str(
                (
                    Decimal(bucket["blocked_known_value_by_currency"].get(cur, "0"))
                    + amount
                ).quantize(Decimal("0.01"))
            )
            bucket["canonical_ids"].append(str(canonical_id))

    # Operator/org diagnostics may use ids; strip for customer-facing via caller.
    public_by_reason = {
        reason: {
            "blocked_opportunity_count": data["blocked_opportunity_count"],
            "blocked_known_value_by_currency": data["blocked_known_value_by_currency"],
            "gap_closure": {
                "current_block": "CONDITIONALLY_ELIGIBLE",
                "condition_required": reason,
            },
        }
        for reason, data in sorted(by_reason.items())
    }

    return {
        **support,
        "schema_version": SCHEMA_VERSION,
        "by_reason": public_by_reason,
    }
