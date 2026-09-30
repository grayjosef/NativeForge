"""Corpus-level known-value composition (concentration, semantics, unknown reasons)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from nativeforge.services.opportunity_value_intelligence_service import (
    ACTIVE_LIFECYCLE_STATES,
    CANONICAL,
    DEFAULT_CURRENCY,
    METHODOLOGY_VERSION,
    SEMANTIC_CEILING_ONLY,
    SEMANTIC_POINT_ESTIMATE,
    SEMANTIC_PROGRAM_FLOOR,
    VALUE_CONFLICTING,
    VALUE_KNOWN,
    VALUE_UNKNOWN,
    _load_active_opportunity_rows,
    enumerate_active_opportunity_values,
)

SCHEMA_VERSION = "nf_funding_landscape_composition_v1"

SEMANTIC_LABELS = {
    SEMANTIC_POINT_ESTIMATE: "PROGRAM_TOTAL_POINT",
    SEMANTIC_PROGRAM_FLOOR: "AWARD_FLOOR_CEILING_RANGE",
    SEMANTIC_CEILING_ONLY: "AWARD_CEILING_ONLY",
}


def _share_pct(part: Decimal, whole: Decimal) -> float | None:
    if whole <= 0:
        return None
    return round(float(part / whole * 100), 4)


def compute_known_value_composition(
    connection: sa.engine.Connection,
    *,
    top_n: int = 10,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    stamp = now or dt.datetime.now(dt.UTC)
    rows = _load_active_opportunity_rows(connection)
    row_by_id = {str(r["canonical_id"]): r for r in rows}
    records = enumerate_active_opportunity_values(connection)

    known_records = [
        r
        for r in records
        if r["value_status"] == VALUE_KNOWN and r.get("selected_amount") is not None
    ]
    totals: dict[str, Decimal] = {}
    for rec in known_records:
        cur = str(rec.get("currency") or DEFAULT_CURRENCY)
        totals[cur] = totals.get(cur, Decimal(0)) + rec["selected_amount"]

    usd_total = totals.get(DEFAULT_CURRENCY, Decimal(0))

    ranked = sorted(
        known_records,
        key=lambda r: (r["selected_amount"], str(r["canonical_id"])),
        reverse=True,
    )

    def cum_share(n: int) -> float | None:
        if usd_total <= 0:
            return None
        top = ranked[:n]
        s = sum(r["selected_amount"] for r in top)
        return _share_pct(s, usd_total)

    contributors: list[dict[str, Any]] = []
    for rec in ranked[:top_n]:
        cid = str(rec["canonical_id"])
        src = row_by_id.get(cid) or {}
        min_src = src.get("min_source")
        amount = rec["selected_amount"]
        contributors.append(
            {
                "canonical_id": cid,
                "selected_semantic": SEMANTIC_LABELS.get(
                    rec.get("semantic"), rec.get("semantic")
                ),
                "value": str(amount.quantize(Decimal("0.01"))),
                "currency": rec.get("currency") or DEFAULT_CURRENCY,
                "share_of_known_usd_pct": _share_pct(amount, usd_total),
                "source_type": min_src or src.get("max_source"),
                "provenance_available": bool(min_src or src.get("max_source")),
                "lifecycle_state": rec.get("lifecycle_state"),
            }
        )

    semantic_breakdown: dict[str, dict[str, Any]] = {}
    for rec in known_records:
        label = SEMANTIC_LABELS.get(rec.get("semantic"), rec.get("semantic") or "OTHER")
        bucket = semantic_breakdown.setdefault(
            label,
            {"count": 0, "known_value_by_currency": {}, "share_of_known_usd_pct": None},
        )
        bucket["count"] += 1
        cur = str(rec.get("currency") or DEFAULT_CURRENCY)
        bucket["known_value_by_currency"][cur] = str(
            (
                Decimal(bucket["known_value_by_currency"].get(cur, "0"))
                + rec["selected_amount"]
            ).quantize(Decimal("0.01"))
        )
    for _label, bucket in semantic_breakdown.items():
        usd = Decimal(bucket["known_value_by_currency"].get(DEFAULT_CURRENCY, "0"))
        bucket["share_of_known_usd_pct"] = _share_pct(usd, usd_total)

    unknown_reasons: dict[str, int] = {}
    for rec in records:
        if rec["value_status"] == VALUE_CONFLICTING:
            unknown_reasons["conflicting"] = unknown_reasons.get("conflicting", 0) + 1
            continue
        if rec["value_status"] != VALUE_UNKNOWN:
            continue
        sem = rec.get("semantic")
        if sem == SEMANTIC_CEILING_ONLY:
            key = "ceiling_only_no_program_floor"
        elif sem is None:
            key = "no_funding_fields"
        else:
            key = "unknown_other"
        unknown_reasons[key] = unknown_reasons.get(key, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "calculated_at": stamp.isoformat(),
        "known_total_by_currency": {
            cur: str(amt.quantize(Decimal("0.01")))
            for cur, amt in sorted(totals.items())
        },
        "known_count": len(known_records),
        "concentration": {
            "currency": DEFAULT_CURRENCY,
            "top_1_share_pct": cum_share(1),
            "top_5_share_pct": cum_share(5),
            "top_10_share_pct": cum_share(10),
            "top_contributors": contributors,
            "note": "Corpus-level source intelligence; no tenant payloads.",
        },
        "semantic_breakdown": semantic_breakdown,
        "unknown_reason_breakdown": unknown_reasons,
    }


def compute_expiring_known_value(
    connection: sa.engine.Connection,
    *,
    windows_days: tuple[int, ...] = (7, 14, 30, 60),
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Uses canonical current_close_date for active opportunities only."""
    stamp = now or dt.datetime.now(dt.UTC)
    today = stamp.date()
    active_list = ", ".join(f"'{s}'" for s in sorted(ACTIVE_LIFECYCLE_STATES))
    rows = connection.execute(
        sa.text(
            f"""
            SELECT canonical_id, current_close_date, lifecycle_state
            FROM {CANONICAL}
            WHERE lifecycle_state IN ({active_list})
              AND current_close_date IS NOT NULL
              AND TRIM(current_close_date) != ''
            """
        )
    ).mappings()
    values = enumerate_active_opportunity_values(connection)
    by_id = {str(v["canonical_id"]): v for v in values}

    def parse_close(raw: str) -> dt.date | None:
        text = str(raw or "").strip()[:10]
        try:
            return dt.date.fromisoformat(text)
        except ValueError:
            return None

    window_stats: dict[str, Any] = {}
    for days in windows_days:
        cutoff = today + dt.timedelta(days=days)
        opp_count = known_count = 0
        totals: dict[str, Decimal] = {}
        for row in rows:
            close = parse_close(row["current_close_date"])
            if close is None or close < today or close > cutoff:
                continue
            cid = str(row["canonical_id"])
            opp_count += 1
            rec = by_id.get(cid)
            if (
                rec
                and rec["value_status"] == VALUE_KNOWN
                and rec.get("selected_amount") is not None
            ):
                known_count += 1
                cur = str(rec.get("currency") or DEFAULT_CURRENCY)
                totals[cur] = totals.get(cur, Decimal(0)) + rec["selected_amount"]
        window_stats[f"{days}d"] = {
            "expiring_opportunity_count": opp_count,
            "expiring_known_count": known_count,
            "expiring_known_value_by_currency": {
                c: str(a.quantize(Decimal("0.01"))) for c, a in sorted(totals.items())
            },
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "supported": True,
        "basis": "nf_canonical_opportunities.current_close_date on active lifecycle",
        "as_of": today.isoformat(),
        "windows": window_stats,
    }


def public_composition_view(full: dict[str, Any]) -> dict[str, Any]:
    """Public-safe subset for hero context (no contributor ids if undesired — keep ids as corpus intel)."""
    return {
        "schema_version": full["schema_version"],
        "methodology_version": full["methodology_version"],
        "calculated_at": full["calculated_at"],
        "known_total_by_currency": full["known_total_by_currency"],
        "known_count": full["known_count"],
        "concentration_shares": {
            k: full["concentration"][k]
            for k in ("top_1_share_pct", "top_5_share_pct", "top_10_share_pct")
        },
        "semantic_breakdown": full["semantic_breakdown"],
    }
