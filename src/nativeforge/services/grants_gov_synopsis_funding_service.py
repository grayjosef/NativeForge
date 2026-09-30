"""Grants.gov fetchOpportunity synopsis → canonical funding fields (V1.1).

Maps authoritative synopsis fields (Gate 163 / ext-apis-monitoring) onto the
existing canonical vocabulary used by ``nativeforge.opportunity_value.v1``.

Does not multiply award ceiling by expected awards. Does not treat ceiling-only
as program total.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

ENRICHMENT_VERSION = "nf_grants_gov_synopsis_funding_v1"
PARSER_NAME = "grants_gov_fetch_opportunity_synopsis_funding"
ADAPTER_KEY = "grants_gov_fetch_opportunity_funding"

FundingSemantic = Literal[
    "PROGRAM_TOTAL_POINT",
    "AWARD_FLOOR_CEILING_RANGE",
    "AWARD_FLOOR_ONLY",
    "NONE",
]

_NONE_TOKENS = frozenset({"none", "n/a", "na", ""})
_AMOUNT_CLEAN = re.compile(r"[^\d.+-]")


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in _NONE_TOKENS:
        return None
    cleaned = _AMOUNT_CLEAN.sub("", s)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def map_synopsis_funding_to_canonical(
    synopsis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic mapping from synopsis funding fields to min/max + semantics."""
    syn = synopsis or {}
    estimated = _parse_amount(syn.get("estimatedFunding"))
    floor = _parse_amount(syn.get("awardFloor"))
    ceiling = _parse_amount(syn.get("awardCeiling"))

    result: dict[str, Any] = {
        "enrichment_version": ENRICHMENT_VERSION,
        "source_fields": {
            "estimatedFunding": syn.get("estimatedFunding"),
            "awardFloor": syn.get("awardFloor"),
            "awardCeiling": syn.get("awardCeiling"),
            "numberOfAwards": syn.get("numberOfAwards"),
        },
        "funding_semantic": "NONE",
        "funding_amount_min": None,
        "funding_amount_max": None,
        "currency": "USD",
        "currency_basis": (
            "Grants.gov federal opportunity synopsis amounts are published as "
            "USD for this integration; no FX conversion."
        ),
    }

    if estimated is not None:
        amt = str(estimated)
        result["funding_semantic"] = "PROGRAM_TOTAL_POINT"
        result["funding_amount_min"] = amt
        result["funding_amount_max"] = amt
        return result

    if floor is not None and ceiling is not None:
        result["funding_semantic"] = "AWARD_FLOOR_CEILING_RANGE"
        result["funding_amount_min"] = str(floor)
        result["funding_amount_max"] = str(ceiling)
        return result

    if floor is not None:
        result["funding_semantic"] = "AWARD_FLOOR_ONLY"
        result["funding_amount_min"] = str(floor)
        return result

    # Ceiling alone → no canonical funding (V1 aggregate treats max-only as UNKNOWN).
    return result


def build_fetch_opportunity_funding_record(
    *,
    detail: dict[str, Any],
    opportunity_number: str,
    source_record_id: str,
    doc_type: str,
    lifecycle_status: str,
) -> dict[str, Any]:
    """Flat record for ``normalize_record`` with adapter ``grants_gov_fetch_opportunity_funding``."""
    synopsis = detail.get("synopsis") or {}
    funding = map_synopsis_funding_to_canonical(synopsis)
    record: dict[str, Any] = {
        "opportunity_number": opportunity_number,
        "source_record_id": source_record_id,
        "doc_type": doc_type,
        "status": lifecycle_status,
        "funding_enrichment_meta": {
            "funding_semantic": funding["funding_semantic"],
            "enrichment_version": ENRICHMENT_VERSION,
            "grants_gov_opportunity_id": detail.get("id"),
        },
    }
    if funding.get("funding_amount_min") is not None:
        record["funding_amount_min"] = funding["funding_amount_min"]
    if funding.get("funding_amount_max") is not None:
        record["funding_amount_max"] = funding["funding_amount_max"]
    return record


def funding_record_has_aggregate_signal(record: dict[str, Any]) -> bool:
    """True when projection could yield KNOWN under opportunity_value.v1."""
    return bool(record.get("funding_amount_min"))
