"""Combined NM/WA operator review queue and reporting surface.

Advisory only. Does not alter classify+match logic. Offline synthetic fixtures only.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)
from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

SCHEMA_VERSION = "nf_nm_wa_combined_operator_surfacing_v1"

# Stable ordering: incomplete first, then needs_operator_review, then profile_id.
_READINESS_ORDER = {
    "incomplete_profile_data": 0,
    "needs_operator_review": 1,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _row_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    readiness = str(row.get("match_readiness_label") or "")
    return (
        _READINESS_ORDER.get(readiness, 99),
        str(row.get("state_cohort") or ""),
        str(row.get("profile_id") or ""),
    )


def build_combined_operator_review_queue(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 031: combined NM/WA operator review queue with stable ordering."""
    nm = build_nm_operator_surfacing_report(grants=grants)
    wa = build_wa_operator_surfacing_report(grants=grants)
    rows = list(nm["rows"]) + list(wa["rows"])
    ordered = sorted(rows, key=_row_sort_key)

    confidence = Counter(str(r.get("confidence") or "unknown") for r in ordered)
    missing_count = sum(1 for r in ordered if r.get("missing_data"))
    review_needed = sum(1 for r in ordered if r.get("human_review_required"))

    provenance_notes = Counter()
    for r in ordered:
        for note in r.get("provenance_evidence_notes") or []:
            key = str(note).split(":", 1)[0]
            provenance_notes[key] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "does_not_alter_classify_match_logic": True,
            "advisory_only": True,
            "nm_count": nm["total_profiles"],
            "wa_count": wa["total_profiles"],
            "combined_profile_count": len(ordered),
            "combined_review_needed_count": review_needed,
            "combined_missing_data_count": missing_count,
            "combined_confidence_distribution": dict(confidence),
            "combined_evidence_provenance_summary": dict(provenance_notes),
            "stable_ordering": [
                "incomplete_profile_data",
                "needs_operator_review",
                "state_cohort",
                "profile_id",
            ],
            "rows": ordered,
            "final_eligibility_claim_allowed": False,
        }
    )


def build_combined_operator_rollup(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 032: combined rollup summary without full row payload."""
    queue = build_combined_operator_review_queue(grants=grants)
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_rollup",
            "nm_count": queue["nm_count"],
            "wa_count": queue["wa_count"],
            "combined_review_needed_count": queue["combined_review_needed_count"],
            "combined_missing_data_count": queue["combined_missing_data_count"],
            "combined_confidence_distribution": queue[
                "combined_confidence_distribution"
            ],
            "combined_evidence_provenance_summary": queue[
                "combined_evidence_provenance_summary"
            ],
            "final_eligibility_claim_allowed": False,
            "offline_only": True,
            "source_activation": False,
            "live_ingestion": False,
        }
    )
