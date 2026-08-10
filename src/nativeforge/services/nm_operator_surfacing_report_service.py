"""NM operator surfacing report builder — review visibility over existing outputs.

Does not alter classify+match logic. Offline synthetic fixtures only.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as NM_EXPECTED,
)
from nativeforge.services.nm_wa_operator_review_service import (
    derive_next_check_guidance,
    derive_review_reasons,
)
from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_rows,
)
from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    READINESS_NEEDS_OPERATOR_REVIEW,
    assign_conservative_readiness_label,
    build_missing_data_report,
)

SCHEMA_VERSION = "nf_nm_operator_surfacing_report_v1"

_DEFAULT_GRANTS: list[dict[str, Any]] = [
    {
        "grant_id": "os-nm-001",
        "opportunity_title": "Federal Tribal Discretionary Support",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _gaps_for_state(
    state: str, grants: list[dict[str, Any]] | None
) -> dict[str, list[str]]:
    report = build_missing_data_report(grants=grants)
    out: dict[str, list[str]] = {}
    for gap in report["gaps"]:
        if gap.get("state") != state:
            continue
        out[str(gap["profile_fixture_key"])] = list(gap["missing_fields"])
    return out


def build_nm_operator_review_items(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sprint 011: NM review items from existing classify+match / readiness."""
    corpus = grants if grants is not None else _DEFAULT_GRANTS
    block = run_nm_pilot_classify_match_block(
        grants=corpus, allow_live_completeness_fetch=False
    )
    gaps = _gaps_for_state("NM", corpus)
    items: list[dict[str, Any]] = []
    for row in block["per_profile"]:
        pid = str(row["profile_fixture_key"])
        missing = gaps.get(pid, [])
        readiness = assign_conservative_readiness_label(row)
        reasons = derive_review_reasons(
            {
                "program_areas_unknown": "program_areas" in missing
                or row.get("program_areas_unknown") is True,
                "grant_posture": (
                    "UNKNOWN"
                    if "grant_posture" in missing
                    or row.get("grant_posture") in (None, "", "UNKNOWN")
                    else row.get("grant_posture")
                ),
            }
        )
        items.append(
            {
                "state": "NM",
                "profile_fixture_key": pid,
                "organization_name": row.get("organization_name"),
                "readiness_label": readiness,
                "review_reasons": reasons,
                "next_checks": derive_next_check_guidance(reasons),
                "missing_fields": missing,
                "match_count": row.get("match_count"),
            }
        )
    return _json_safe(items)


def build_nm_operator_surfacing_report(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 012–015: NM operator report + rollup summary."""
    corpus = grants if grants is not None else _DEFAULT_GRANTS
    items = build_nm_operator_review_items(grants=corpus)
    gaps = {i["profile_fixture_key"]: i.get("missing_fields") or [] for i in items}
    rows = build_operator_report_rows(items, gaps_by_profile=gaps)

    readiness_counts = Counter(i["readiness_label"] for i in items)
    missing_categories: Counter[str] = Counter()
    for fields in gaps.values():
        for f in fields:
            missing_categories[f] += 1

    review_needed = sum(
        1
        for i in items
        if i["readiness_label"]
        in {READINESS_NEEDS_OPERATOR_REVIEW, READINESS_INCOMPLETE_PROFILE}
    )
    incomplete = readiness_counts.get(READINESS_INCOMPLETE_PROFILE, 0)
    no_final_claim = sum(
        1 for r in rows if r.get("final_eligibility_claim_allowed") is False
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state_cohort": "NM",
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "does_not_alter_classify_match_logic": True,
            "expected_profile_count": NM_EXPECTED,
            "total_profiles": len(rows),
            "rows": rows,
            "rollup": {
                "total_profiles": len(rows),
                "review_ready_count": 0,  # conservative: never claim review-ready final
                "needs_operator_review_count": review_needed,
                "incomplete_data_count": incomplete,
                "conservative_no_final_claim_count": no_final_claim,
                "missing_evidence_categories": dict(missing_categories),
                "all_human_review_required": all(
                    r.get("human_review_required") for r in rows
                ),
                "all_discoverable": all(
                    r.get("discoverability") == "visible_in_operator_review"
                    for r in rows
                ),
            },
        }
    )
