"""Federal + SC eligibility handoff for SC customers (Campaign Block 02)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_evidence_contract_service import (
    eligibility_evidence_invariant_failures,
)
from nativeforge.services.recognition_tier_explanation_service import (
    explain_recognition_tier,
    recognition_tier_explanation_invariant_failures,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_eligibility_handoff_pack_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_eligibility_handoff_for_pair(
    profile: dict[str, Any], opportunity: dict[str, Any]
) -> dict[str, Any]:
    explanation = explain_recognition_tier(profile=profile, opportunity=opportunity)
    layer = str(
        opportunity.get("source_layer")
        or (
            "sc_state"
            if opportunity.get("funding_geography") == "south_carolina"
            else "federal"
            if opportunity.get("funding_geography") == "federal"
            else "unknown"
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_id": profile.get("fixture_key")
            or profile.get("profile_fixture_key"),
            "opportunity_id": opportunity.get("opportunity_id")
            or opportunity.get("grant_id"),
            "source_layer": layer,
            "funding_geography": opportunity.get("funding_geography"),
            "organization_geography": "south_carolina",
            "org_geo_filters_federal": False,
            "explanation": explanation,
            "eligibility_evidence": explanation.get("eligibility_evidence"),
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "human_review_required": True,
        }
    )


def build_sc_customer_eligibility_handoff_pack(
    *,
    max_profiles: int = 3,
    max_opps_per_layer: int = 4,
) -> dict[str, Any]:
    """Sample handoff pack: SC profiles × SC + federal curated opportunities."""
    profiles = load_sc_tribal_profiles()[:max_profiles]
    grants = grants_from_pack(load_sc_curated_opportunity_pack())
    sc = [
        g
        for g in grants
        if g.get("funding_geography") == "south_carolina"
        or g.get("source_layer") == "sc_state"
    ][:max_opps_per_layer]
    fed = [
        g
        for g in grants
        if g.get("funding_geography") == "federal" or g.get("source_layer") == "federal"
    ][:max_opps_per_layer]

    pairs: list[dict[str, Any]] = []
    for p in profiles:
        for g in [*sc, *fed]:
            pairs.append(build_eligibility_handoff_for_pair(p, g))

    federal_visible = any(r.get("source_layer") == "federal" for r in pairs)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "SC customer eligibility handoff pack",
            "profile_count": len(profiles),
            "pair_count": len(pairs),
            "federal_pairs_visible": federal_visible,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "pairs": pairs,
        }
    )


def eligibility_handoff_pack_invariant_failures(pack: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if pack.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if pack.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if pack.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if not pack.get("federal_pairs_visible"):
        fails.append("federal_not_visible")
    if (pack.get("pair_count") or 0) < 1:
        fails.append("no_pairs")
    for pair in pack.get("pairs") or []:
        if pair.get("org_geo_filters_federal") is True:
            fails.append("org_geo_filters_federal")
        if pair.get("human_review_required") is not True:
            fails.append("human_review_false")
        fails.extend(
            eligibility_evidence_invariant_failures(
                pair.get("eligibility_evidence") or {}
            )
        )
        fails.extend(
            recognition_tier_explanation_invariant_failures(
                pair.get("explanation") or {}
            )
        )
        # Incomplete evidence must stay human-review gated
        ev = pair.get("eligibility_evidence") or {}
        if ev.get("evidence_status") in {"missing", "partial", "needs_confirmation"}:
            if pair.get("human_review_required") is not True:
                fails.append("incomplete_without_human_review")
    return fails
