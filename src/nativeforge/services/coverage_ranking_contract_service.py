"""National/state coverage ranking contract (Campaign Block 27)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_coverage_ranking_contract_v1"

COVERAGE_TIERS = frozenset(
    {
        "top_15_candidate",
        "top_15_selected",
        "watchlist",
        "unsupported",
        "unknown",
    }
)

RANKING_CONFIDENCE = frozenset({"high", "medium", "low", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_coverage_ranking_id(state_code: str, label: str = "v1") -> str:
    raw = f"cov::{state_code}::{label}".encode()
    return f"cov_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_coverage_ranking_record(
    *,
    state_code: str,
    state_name: str,
    coverage_tier: str = "unknown",
    ranking_score: float = 0.0,
    ranking_reasons: list[str] | None = None,
    native_relevance_score: float = 0.0,
    state_grant_density_score: float = 0.0,
    federal_tribe_presence: str = "unknown",
    state_recognized_tribe_presence: str = "unknown",
    source_accessibility_score: float = 0.0,
    source_freshness_status: str = "unknown",
    source_reliability_status: str = "unknown",
    state_portal_status: str = "unknown",
    opportunity_count_known: int | None = None,
    opportunity_count_estimated: int | None = None,
    ranking_evidence_refs: list[str] | None = None,
    ranking_confidence: str = "unknown",
    human_review_required: bool = True,
    top_15_claimed: bool = False,
) -> dict[str, Any]:
    tier = coverage_tier if coverage_tier in COVERAGE_TIERS else "unknown"
    conf = ranking_confidence if ranking_confidence in RANKING_CONFIDENCE else "unknown"
    refs = list(ranking_evidence_refs or [])
    # Hard: top_15_claimed requires evidence refs + human review
    claimed = bool(top_15_claimed)
    if claimed and (not refs or not human_review_required):
        claimed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "coverage_ranking_id": make_coverage_ranking_id(state_code),
            "state_code": state_code.upper(),
            "state_name": state_name,
            "coverage_tier": tier,
            "ranking_score": float(ranking_score),
            "ranking_reasons": list(ranking_reasons or []),
            "native_relevance_score": float(native_relevance_score),
            "state_grant_density_score": float(state_grant_density_score),
            "federal_tribe_presence": federal_tribe_presence,
            "state_recognized_tribe_presence": state_recognized_tribe_presence,
            "source_accessibility_score": float(source_accessibility_score),
            "source_freshness_status": source_freshness_status,
            "source_reliability_status": source_reliability_status,
            "state_portal_status": state_portal_status,
            "opportunity_count_known": opportunity_count_known,
            "opportunity_count_estimated": opportunity_count_estimated,
            "ranking_evidence_refs": refs,
            "ranking_confidence": conf,
            "human_review_required": bool(human_review_required),
            "top_15_claimed": claimed,
            "live_coverage_claimed": False,
            "final_eligibility_claimed": False,
            "all_state_opportunities_live_claimed": False,
        }
    )


def coverage_ranking_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("coverage_tier") not in COVERAGE_TIERS:
        fails.append("bad_coverage_tier")
    if record.get("ranking_confidence") not in RANKING_CONFIDENCE:
        fails.append("bad_ranking_confidence")
    if record.get("live_coverage_claimed") is True:
        fails.append("live_coverage_claimed")
    if record.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if record.get("all_state_opportunities_live_claimed") is True:
        fails.append("all_state_opportunities_live_claimed")
    if record.get("top_15_claimed") is True:
        if not (record.get("ranking_evidence_refs") or []):
            fails.append("top_15_without_evidence_refs")
        if record.get("human_review_required") is not True:
            fails.append("top_15_without_human_review")
    return fails
