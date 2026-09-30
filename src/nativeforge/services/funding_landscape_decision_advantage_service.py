"""Organization-scoped funding decision advantage (no opaque scores)."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from nativeforge.services.eligibility_requirement_model_service import (
    CONDITIONALLY_ELIGIBLE,
)
from nativeforge.services.funding_landscape_blocked_value_service import (
    BLOCKED_VALUE_METHODOLOGY,
    compute_org_blocked_known_value,
)
from nativeforge.services.funding_landscape_composition_service import (
    compute_expiring_known_value,
)
from nativeforge.services.intelligence_sql_dialect_service import is_current_active_sql
from nativeforge.services.opportunity_value_funnel_service import (
    _CONDITIONAL,
    _ELIGIBLE,
    _INELIGIBLE,
    _PURSUING_STATUSES,
    _UNKNOWN_ELIG,
    _filter_eligibility,
    _filter_relevance,
    _load_current_eligibility_map,
    _load_current_relevance_map,
    _metrics_from_records,
    _pursuit_canonical_ids,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    DEFAULT_CURRENCY,
    VALUE_KNOWN,
    enumerate_active_opportunity_values,
)

SCHEMA_VERSION = "nf_funding_landscape_decision_advantage_v1"
MATCHES = "nf_tenant_eligibility_matches"


def _load_active_close_dates(connection: sa.engine.Connection) -> dict[str, str | None]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    rows = connection.execute(
        sa.text(
            f"""
            SELECT canonical_id, current_close_date
            FROM {CANONICAL}
            WHERE lifecycle_state IN ({active_list})
            """
        )
    ).fetchall()
    return {str(r[0]): str(r[1]) if r[1] else None for r in rows}


def _expiring_subset(
    records: list[dict[str, Any]],
    close_map: dict[str, str | None],
    *,
    days: int,
    today: dt.date,
) -> list[dict[str, Any]]:
    cutoff = today + dt.timedelta(days=days)
    out: list[dict[str, Any]] = []
    for rec in records:
        close_raw = close_map.get(str(rec["canonical_id"]))
        if not close_raw:
            continue
        try:
            close = dt.date.fromisoformat(str(close_raw).strip()[:10])
        except ValueError:
            continue
        if close < today or close > cutoff:
            continue
        out.append(rec)
    return out


def compute_org_decision_advantage(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    tenant_id: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    stamp = now or dt.datetime.now(dt.UTC)
    today = stamp.date()
    records = enumerate_active_opportunity_values(connection)
    elig = _load_current_eligibility_map(connection, tenant_id=tenant_id)
    relevance = _load_current_relevance_map(connection)

    eligible_recs = _filter_eligibility(records, elig, _ELIGIBLE)
    conditional_recs = _filter_eligibility(records, elig, _CONDITIONAL)
    ineligible_recs = _filter_eligibility(records, elig, _INELIGIBLE)
    unknown_recs = _filter_eligibility(records, elig, _UNKNOWN_ELIG)
    native_recs = _filter_relevance(records, relevance)

    pursuing_ids = set(
        _pursuit_canonical_ids(
            connection, organization_id=organization_id, statuses=_PURSUING_STATUSES
        )
    )

    accessibility = {
        "eligible_known_value": {
            **_metrics_from_records(eligible_recs),
            "label": "known value on active opportunities classified ELIGIBLE/LIKELY_ELIGIBLE",
        },
        "conditionally_eligible_known_value": {
            **_metrics_from_records(conditional_recs),
            "label": "known value where eligibility is CONDITIONALLY_ELIGIBLE",
        },
        "ineligible_known_value": {
            **_metrics_from_records(ineligible_recs),
            "label": "known value marked INELIGIBLE — still discoverable",
        },
        "unknown_eligibility_known_value": {
            **_metrics_from_records(unknown_recs),
            "label": "known value with UNKNOWN/REVIEW eligibility",
        },
    }

    blocked = compute_org_blocked_known_value(connection, tenant_id=tenant_id)
    gap_closure: dict[str, Any] = {}
    if blocked.get("supported"):
        current = is_current_active_sql(connection)
        rows = connection.execute(
            sa.text(
                f"""
                SELECT canonical_id, conditions_to_obtain_json
                FROM {MATCHES}
                WHERE tenant_id = :tid AND {current}
                  AND eligibility_result = :res
                """
            ),
            {"tid": tenant_id, "res": CONDITIONALLY_ELIGIBLE},
        ).fetchall()
        by_id = {str(r["canonical_id"]): r for r in records}
        for canonical_id, cond_json in rows:
            try:
                conditions = json.loads(cond_json or "[]")
            except json.JSONDecodeError:
                conditions = []
            rec = by_id.get(str(canonical_id))
            if not rec or rec["value_status"] != VALUE_KNOWN:
                continue
            for cond in conditions:
                key = str(cond)
                bucket = gap_closure.setdefault(
                    key,
                    {
                        "condition": key,
                        "opportunity_count": 0,
                        "known_value_count": 0,
                        "known_value_by_currency": {},
                        "canonical_ids": [],
                    },
                )
                bucket["opportunity_count"] += 1
                bucket["known_value_count"] += 1
                cur = str(rec.get("currency") or DEFAULT_CURRENCY)
                amt = rec["selected_amount"]
                bucket["known_value_by_currency"][cur] = str(
                    (
                        Decimal(bucket["known_value_by_currency"].get(cur, "0")) + amt
                    ).quantize(Decimal("0.01"))
                )
                bucket["canonical_ids"].append(str(canonical_id))

    close_map = _load_active_close_dates(connection)
    expiring_base = compute_expiring_known_value(connection, now=stamp)
    expiring_slices: dict[str, Any] = {}
    for window, data in (expiring_base.get("windows") or {}).items():
        days = int(window.replace("d", ""))
        expiring_slices[window] = {
            "active": data,
            "eligible": _metrics_from_records(
                _expiring_subset(eligible_recs, close_map, days=days, today=today)
            ),
            "conditional": _metrics_from_records(
                _expiring_subset(conditional_recs, close_map, days=days, today=today)
            ),
            "pursuing": _metrics_from_records(
                _expiring_subset(
                    [r for r in records if str(r["canonical_id"]) in pursuing_ids],
                    close_map,
                    days=days,
                    today=today,
                )
            ),
        }

    pursuable = eligible_recs + conditional_recs
    not_pursued = [
        r
        for r in pursuable
        if r["value_status"] == VALUE_KNOWN
        and str(r["canonical_id"]) not in pursuing_ids
    ]
    pursuing_recs = [r for r in records if str(r["canonical_id"]) in pursuing_ids]
    pursuing_metrics = _metrics_from_records(pursuing_recs)
    native_known = _metrics_from_records(
        [r for r in native_recs if r["value_status"] == VALUE_KNOWN]
    )
    denom = native_known["known_count"] or native_known["count"]
    pursuit_cov_pct = None
    if denom and pursuing_metrics.get("known_count") is not None:
        pursuit_cov_pct = round(100.0 * pursuing_metrics["known_count"] / denom, 2)

    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": organization_id,
        "tenant_id": tenant_id,
        "calculated_at": stamp.isoformat(),
        "accessibility_model": accessibility,
        "gap_closure": {
            "supported": bool(gap_closure),
            "condition_slices_non_additive": True,
            "methodology_version": BLOCKED_VALUE_METHODOLOGY,
            "by_condition": {
                k: {
                    "condition": v["condition"],
                    "opportunity_count": v["opportunity_count"],
                    "known_value_count": v["known_value_count"],
                    "known_value_by_currency": v["known_value_by_currency"],
                }
                for k, v in sorted(gap_closure.items())
            },
        },
        "expiring_value": {
            "supported": expiring_base.get("supported"),
            "windows": expiring_slices,
        },
        "not_currently_pursued": {
            "supported": True,
            "definition": (
                "ELIGIBLE or CONDITIONALLY_ELIGIBLE with KNOWN value and no "
                "active/paused pursuit"
            ),
            **_metrics_from_records(not_pursued),
            "sort_dimensions": [
                "known_opportunity_value",
                "days_to_close",
                "eligibility_state",
                "native_relevance_class",
                "condition_count",
            ],
        },
        "pursuit_coverage": {
            "supported": bool(denom),
            "numerator": pursuing_metrics.get("known_count"),
            "denominator": denom,
            "denominator_semantics": (
                "native_relevant opportunities with known monetary value"
            ),
            "pursuing_known_value_by_currency": pursuing_metrics.get(
                "totals_by_currency"
            ),
            "pursuing_known_value_coverage_pct": pursuit_cov_pct,
            "note": "Not capture rate or market share",
        },
        "concentration_context": {
            "note": (
                "Use public/operator composition endpoints for corpus-level "
                "top-N concentration; org slices may differ."
            ),
        },
        "no_opaque_priority_score": True,
    }
