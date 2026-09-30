"""HABEAS DATA — provenance-backed active opportunity value (V1).

Methodology: nativeforge.opportunity_value.v1
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa

from nativeforge.services.intelligence_sql_dialect_service import (
    is_current_active_sql,
    sql_bool_literal,
)
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT

METHODOLOGY_VERSION = "nativeforge.opportunity_value.v1"
SCHEMA_VERSION = "nf_opportunity_value_intelligence_v1"

CANONICAL = "nf_canonical_opportunities"
PROVENANCE = "nf_opportunity_field_provenance"
ASSESSMENTS = "nf_opportunity_relevance_assessments"

# Lifecycle states that count as active/open for this metric (canonical truth).
ACTIVE_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {"posted", "amended", "forecasted"}
)

FUNDING_MIN = "funding_amount_min"
FUNDING_MAX = "funding_amount_max"
DEFAULT_CURRENCY = "USD"

VALUE_UNKNOWN = "UNKNOWN"
VALUE_CONFLICTING = "CONFLICTING"
VALUE_KNOWN = "KNOWN"

SEMANTIC_POINT_ESTIMATE = "point_estimate_equal_min_max"
SEMANTIC_PROGRAM_FLOOR = "program_floor_from_min"
SEMANTIC_CEILING_ONLY = "award_ceiling_excluded_from_aggregate"

_cache: dict[str, Any] = {"expires_at": None, "payload": None}
_CACHE_TTL_SECONDS = 120


def active_lifecycle_rule() -> dict[str, Any]:
    return {
        "included": sorted(ACTIVE_LIFECYCLE_STATES),
        "excluded": sorted(
            ("closed", "awarded", "archived", "unknown")
        ),
        "note": "Uses nf_canonical_opportunities.lifecycle_state only; not a marketing definition.",
    }


def value_selection_policy() -> dict[str, Any]:
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "fields": [FUNDING_MIN, FUNDING_MAX],
        "rules": [
            "equal min and max → contribute once as point estimate",
            "min < max → contribute min only (conservative program floor)",
            "min only → contribute min as program floor",
            "max only → UNKNOWN (award ceiling is not program total)",
            "neither → UNKNOWN",
            "canonical has_field_conflicts or provenance conflict_group → CONFLICTING",
        ],
        "currency": "USD assumed when no currency field exists on canonical graph",
        "no_fx_conversion": True,
    }


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        cleaned = str(raw).replace(",", "").replace("$", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _select_monetary_value(
    *,
    min_raw: Any,
    max_raw: Any,
    has_field_conflicts: bool,
    min_conflict: Any,
    max_conflict: Any,
) -> dict[str, Any]:
    if has_field_conflicts or (min_conflict and max_conflict and min_conflict != max_conflict):
        return {
            "value_status": VALUE_CONFLICTING,
            "selected_amount": None,
            "currency": DEFAULT_CURRENCY,
            "semantic": None,
        }
    min_amt = _parse_amount(min_raw)
    max_amt = _parse_amount(max_raw)
    if min_amt is not None and max_amt is not None:
        if min_amt == max_amt:
            return {
                "value_status": VALUE_KNOWN,
                "selected_amount": min_amt,
                "currency": DEFAULT_CURRENCY,
                "semantic": SEMANTIC_POINT_ESTIMATE,
            }
        if min_amt < max_amt:
            return {
                "value_status": VALUE_KNOWN,
                "selected_amount": min_amt,
                "currency": DEFAULT_CURRENCY,
                "semantic": SEMANTIC_PROGRAM_FLOOR,
            }
        return {
            "value_status": VALUE_CONFLICTING,
            "selected_amount": None,
            "currency": DEFAULT_CURRENCY,
            "semantic": None,
        }
    if min_amt is not None:
        return {
            "value_status": VALUE_KNOWN,
            "selected_amount": min_amt,
            "currency": DEFAULT_CURRENCY,
            "semantic": SEMANTIC_PROGRAM_FLOOR,
        }
    if max_amt is not None:
        return {
            "value_status": VALUE_UNKNOWN,
            "selected_amount": None,
            "currency": DEFAULT_CURRENCY,
            "semantic": SEMANTIC_CEILING_ONLY,
            "reason": "award_ceiling_without_program_floor",
        }
    return {
        "value_status": VALUE_UNKNOWN,
        "selected_amount": None,
        "currency": DEFAULT_CURRENCY,
        "semantic": None,
    }


def _load_active_opportunity_rows(
    connection: sa.engine.Connection,
) -> list[dict[str, Any]]:
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    current = sql_bool_literal(connection, value=True)
    sql = f"""
        SELECT c.canonical_id, c.lifecycle_state, c.has_field_conflicts, c.last_seen_at,
               pmin.field_value AS min_val, pmin.conflict_group AS min_conflict,
               pmin.source_id AS min_source, pmin.raw_payload_sha256 AS min_sha,
               pmin.observation_id AS min_obs, pmin.version_id AS min_ver,
               pmax.field_value AS max_val, pmax.conflict_group AS max_conflict,
               pmax.source_id AS max_source, pmax.raw_payload_sha256 AS max_sha
        FROM {CANONICAL} c
        LEFT JOIN {PROVENANCE} pmin
          ON pmin.canonical_id = c.canonical_id
         AND pmin.field_name = :fmin
         AND pmin.is_current_canonical = {current}
        LEFT JOIN {PROVENANCE} pmax
          ON pmax.canonical_id = c.canonical_id
         AND pmax.field_name = :fmax
         AND pmax.is_current_canonical = {current}
        WHERE c.lifecycle_state IN ({active_list})
    """
    rows = connection.execute(
        sa.text(sql),
        {"fmin": FUNDING_MIN, "fmax": FUNDING_MAX},
    ).mappings()
    return [dict(r) for r in rows]


def compute_active_opportunity_value_aggregate(
    connection: sa.engine.Connection,
    *,
    use_cache: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Aggregate known monetary value for active canonical opportunities."""
    stamp = now or dt.datetime.now(dt.UTC)
    if use_cache and _cache.get("payload") and _cache.get("expires_at"):
        if stamp < _cache["expires_at"]:
            return dict(_cache["payload"])

    rows = _load_active_opportunity_rows(connection)
    totals: dict[str, Decimal] = {}
    known = unknown = conflicting = 0
    opportunities: list[dict[str, Any]] = []

    for row in rows:
        sel = _select_monetary_value(
            min_raw=row.get("min_val"),
            max_raw=row.get("max_val"),
            has_field_conflicts=bool(row.get("has_field_conflicts")),
            min_conflict=row.get("min_conflict"),
            max_conflict=row.get("max_conflict"),
        )
        status = sel["value_status"]
        if status == VALUE_KNOWN and sel["selected_amount"] is not None:
            known += 1
            cur = str(sel["currency"] or DEFAULT_CURRENCY)
            totals[cur] = totals.get(cur, Decimal(0)) + sel["selected_amount"]
        elif status == VALUE_CONFLICTING:
            conflicting += 1
        else:
            unknown += 1

        opportunities.append(
            {
                "canonical_id": row["canonical_id"],
                "lifecycle_state": row["lifecycle_state"],
                "value_status": status,
                "selected_amount": str(sel["selected_amount"])
                if sel.get("selected_amount") is not None
                else None,
                "currency": sel.get("currency"),
                "semantic": sel.get("semantic"),
                "provenance": {
                    "funding_amount_min": {
                        "source_id": row.get("min_source"),
                        "raw_payload_sha256": row.get("min_sha"),
                        "observation_id": row.get("min_obs"),
                        "version_id": row.get("min_ver"),
                    }
                    if row.get("min_source")
                    else None,
                    "funding_amount_max": {
                        "source_id": row.get("max_source"),
                        "raw_payload_sha256": row.get("max_sha"),
                    }
                    if row.get("max_source")
                    else None,
                },
            }
        )

    active_count = len(rows)
    coverage = (100.0 * known / active_count) if active_count else 0.0
    last_seen = max(
        (r.get("last_seen_at") for r in rows if r.get("last_seen_at")),
        default=None,
    )

    totals_by_currency = {
        cur: str(amt.quantize(Decimal("0.01")))
        for cur, amt in sorted(totals.items())
    }
    usd_total = totals.get(DEFAULT_CURRENCY)

    native_relevant = _native_relevant_value_subset(connection, opportunities)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "active_opportunity_count": active_count,
        "known_value_count": known,
        "unknown_value_count": unknown,
        "conflicting_value_count": conflicting,
        "known_value_coverage_pct": round(coverage, 2),
        "totals_by_currency": totals_by_currency,
        "active_known_value_total_usd": str(usd_total.quantize(Decimal("0.01")))
        if usd_total is not None
        else None,
        "calculated_at": stamp.isoformat(),
        "source_freshness": {
            "latest_last_seen_at": (
                last_seen.isoformat()
                if isinstance(last_seen, dt.datetime)
                else str(last_seen) if last_seen else None
            ),
        },
        "active_lifecycle_rule": active_lifecycle_rule(),
        "value_selection_policy": value_selection_policy(),
        "habeas_data": "no material intelligence claim without retrievable evidence",
        "native_relevance_value": native_relevant,
        "eligibility_value_breakdown": {
            "supported": False,
            "reason": "Gate 174 eligibility-value funnel deferred to V2",
        },
        "blocked_value_future_seam": (
            "Eligibility and requirement evidence from Gate 174/175 may feed "
            "blocked-value-by-reason in a later sprint; not fabricated in V1."
        ),
    }

    if use_cache:
        _cache["payload"] = payload
        _cache["expires_at"] = stamp + dt.timedelta(seconds=_CACHE_TTL_SECONDS)

    return payload


def compute_operator_diagnostics(
    connection: sa.engine.Connection,
) -> dict[str, Any]:
    agg = compute_active_opportunity_value_aggregate(connection, use_cache=False)
    return {
        "schema_version": "nf_opportunity_value_diagnostics_v1",
        "methodology_version": agg.get("methodology_version"),
        "calculated_at": agg.get("calculated_at"),
        "counts": {
            "active": agg.get("active_opportunity_count"),
            "known": agg.get("known_value_count"),
            "unknown": agg.get("unknown_value_count"),
            "conflicting": agg.get("conflicting_value_count"),
            "coverage_pct": agg.get("known_value_coverage_pct"),
        },
        "totals_by_currency": agg.get("totals_by_currency"),
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "refresh": "recomputed on read; public endpoint uses short TTL cache",
    }


def _native_relevant_value_subset(
    connection: sa.engine.Connection,
    opportunities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Gate 173 subset when assessments exist; otherwise documented unsupported."""
    try:
        current_sql = is_current_active_sql(connection)
        rows = connection.execute(
            sa.text(
                f"SELECT canonical_id, relevance_class FROM {ASSESSMENTS} "
                f"WHERE {current_sql}"
            )
        ).fetchall()
    except Exception:
        return {"supported": False, "reason": "assessment_table_unavailable"}

    if not rows:
        return {"supported": False, "reason": "no_current_relevance_assessments"}

    native_classes = set(APPLICANT_RELEVANT)
    by_id = {str(r[0]): str(r[1]) for r in rows}
    relevant_known = Decimal(0)
    relevant_count = 0
    known_count = 0
    for opp in opportunities:
        cid = opp["canonical_id"]
        if by_id.get(cid) not in native_classes:
            continue
        relevant_count += 1
        if opp["value_status"] == VALUE_KNOWN and opp.get("selected_amount"):
            known_count += 1
            relevant_known += Decimal(opp["selected_amount"])

    return {
        "supported": True,
        "native_relevant_active_count": relevant_count,
        "native_relevant_known_value_count": known_count,
        "native_relevant_known_value_total_usd": str(
            relevant_known.quantize(Decimal("0.01"))
        ),
    }


def invalidate_public_cache() -> None:
    _cache["expires_at"] = None
    _cache["payload"] = None


def public_aggregate_view(full: dict[str, Any]) -> dict[str, Any]:
    """Strip internal opportunity list for anonymous hero."""
    return {
        "schema_version": full["schema_version"],
        "methodology_version": full["methodology_version"],
        "active_opportunity_count": full["active_opportunity_count"],
        "known_value_count": full["known_value_count"],
        "unknown_value_count": full["unknown_value_count"],
        "conflicting_value_count": full["conflicting_value_count"],
        "known_value_coverage_pct": full["known_value_coverage_pct"],
        "totals_by_currency": full["totals_by_currency"],
        "active_known_value_total_usd": full.get("active_known_value_total_usd"),
        "calculated_at": full["calculated_at"],
        "source_freshness": full.get("source_freshness"),
        "label": "known active opportunity value",
        "habeas_data": full.get("habeas_data"),
    }


def provenance_detail_for_opportunity(
    connection: sa.engine.Connection, *, canonical_id: str
) -> dict[str, Any]:
    """Operator-safe trace for one opportunity."""
    rows = connection.execute(
        sa.text(
            f"SELECT field_name, field_value, source_id, raw_payload_sha256, "
            f"observation_id, version_id, is_current_canonical, conflict_group "
            f"FROM {PROVENANCE} WHERE canonical_id = :cid "
            f"AND field_name IN (:fmin, :fmax)"
        ),
        {"cid": canonical_id, "fmin": FUNDING_MIN, "fmax": FUNDING_MAX},
    ).mappings()
    return {
        "canonical_id": canonical_id,
        "provenance_rows": [dict(r) for r in rows],
    }
