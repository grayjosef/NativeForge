"""Assemble SC Monday customer demo artifact from profiles + curated pack.

Reuses SC recognition-tier classify/match. Does not claim live ingestion.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_monday_demo_labels_service import (
    REQUIRED_UI_FLAGS,
    build_demo_lane_claim_matrix,
)
from nativeforge.services.sc_pilot_classify_match_orchestrator_service import (
    run_sc_pilot_classify_match_block,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    load_sc_tribal_profiles,
    require_sc_pilot_fixtures,
)

SCHEMA_VERSION = "nf_sc_monday_demo_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _digest(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _profile_summary(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    federal = sum(1 for p in profiles if p.get("recognition_type") == "federal")
    state_only = sum(1 for p in profiles if p.get("recognition_type") == "state_only")
    return {
        "profile_count": len(profiles),
        "federal_recognized_count": federal,
        "state_only_count": state_only,
        "fixture_keys": [str(p.get("fixture_key")) for p in profiles],
    }


def _opportunity_summaries(grants: list[dict[str, Any]]) -> dict[str, Any]:
    sc = [g for g in grants if g.get("funding_geography") == "south_carolina"]
    fed = [g for g in grants if g.get("funding_geography") == "federal"]
    return {
        "total": len(grants),
        "south_carolina_count": len(sc),
        "federal_count": len(fed),
        "by_data_label": _count_by(grants, "data_label"),
        "opportunity_ids": [str(g.get("grant_id")) for g in grants],
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "unknown")
        out[k] = out.get(k, 0) + 1
    return out


def _project_match_rows(cm: dict[str, Any], grants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten classify/match results into customer-demo review rows."""
    grant_meta = {str(g.get("grant_id")): g for g in grants}
    profile_rec = {
        str(p.get("profile_fixture_key")): str(p.get("recognition_type") or "")
        for p in (cm.get("per_profile") or [])
        if isinstance(p, dict)
    }
    rows: list[dict[str, Any]] = []
    for m in cm.get("matches") or []:
        if not isinstance(m, dict):
            continue
        gid = str(m.get("grant_id") or "")
        meta = grant_meta.get(gid) or {}
        profile_id = str(m.get("profile_fixture_key") or "")
        tier = m.get("recognition_tier_gate") or {}
        next_checks: list[str] = []
        if m.get("recognition_tier_mismatch"):
            next_checks.append("Review recognition-tier mismatch before pursuit")
        if m.get("condition_mismatch"):
            next_checks.append("Review condition mismatch (incorporation/501c3/pathway)")
        if m.get("excluded_from_match_set"):
            next_checks.append("Opportunity excluded from match set — confirm why")
        if meta.get("confirm_active_round"):
            next_checks.append("Confirm active funding round with source evidence")
        if not next_checks:
            next_checks.append("Human review required before any eligibility decision")
        blockers = list(m.get("blocker_codes") or [])
        if m.get("recognition_tier_mismatch"):
            blockers.append("recognition_tier_mismatch")
        if m.get("excluded_from_match_set"):
            blockers.append("excluded_from_match_set")
        rows.append(
            {
                "profile_id": profile_id,
                "recognition_type": profile_rec.get(profile_id)
                or str(tier.get("profile_recognition_type") or ""),
                "grant_id": gid,
                "opportunity_title": meta.get("opportunity_title")
                or m.get("opportunity_title")
                or gid,
                "funding_geography": meta.get("funding_geography") or "unknown",
                "data_label": meta.get("data_label") or "fixture_demo",
                "live_ingest_not_claimed": True,
                "classification_label": m.get("classification_label") or "unknown",
                "match_readiness_label": m.get("match_label") or "needs_operator_review",
                "discoverability": (
                    "hidden_by_tier_gate"
                    if m.get("excluded_from_match_set")
                    else "visible"
                ),
                "confidence": "public_inferred_low",
                "missing_data": [],
                "blockers": blockers,
                "operator_next_check": next_checks,
                "provenance_evidence_notes": [
                    str(meta.get("evidence_notes") or ""),
                    f"data_label={meta.get('data_label')}",
                    f"retrieval_date={meta.get('retrieval_date')}",
                    f"recognition_requirement={m.get('recognition_requirement')}",
                ],
                "human_review_required": True,
                "final_eligibility_claim_allowed": False,
                "confirm_active_round": bool(meta.get("confirm_active_round")),
                "excluded_from_match_set": bool(m.get("excluded_from_match_set")),
            }
        )
    return rows


def build_sc_monday_demo_artifact(
    *,
    require_fixtures: bool = True,
) -> dict[str, Any]:
    if require_fixtures:
        require_sc_pilot_fixtures()
    pack = load_sc_curated_opportunity_pack(require_file=False)
    grants = grants_from_pack(pack)
    profiles = load_sc_tribal_profiles(require_files=require_fixtures)

    cm = run_sc_pilot_classify_match_block(
        grants=grants,
        require_fixtures=require_fixtures,
        nf_live_source_ingestion=False,
        allow_live_completeness_fetch=False,
    )

    # Orchestrator may merge additional rule-refs; keep demo rows to curated pack only.
    curated_ids = {str(g.get("grant_id")) for g in grants}
    if isinstance(cm.get("matches"), list):
        cm = {
            **cm,
            "matches": [
                m
                for m in cm["matches"]
                if isinstance(m, dict) and str(m.get("grant_id")) in curated_ids
            ],
        }

    rows = _project_match_rows(cm, grants)
    # Fallback: if orchestrator shape didn't yield rows, emit profile×opp skeleton
    if not rows:
        for p in profiles:
            for g in grants:
                rows.append(
                    {
                        "profile_id": str(p.get("fixture_key")),
                        "recognition_type": str(p.get("recognition_type")),
                        "grant_id": str(g.get("grant_id")),
                        "opportunity_title": g.get("opportunity_title"),
                        "funding_geography": g.get("funding_geography"),
                        "data_label": g.get("data_label"),
                        "live_ingest_not_claimed": True,
                        "classification_label": "needs_operator_review",
                        "match_readiness_label": "needs_operator_review",
                        "discoverability": "visible",
                        "confidence": "public_inferred_low",
                        "missing_data": ["orchestrator_row_projection_fallback"],
                        "blockers": [],
                        "operator_next_check": [
                            "Review recognition-tier gate output for this org×opportunity"
                        ],
                        "provenance_evidence_notes": [
                            str(g.get("evidence_notes") or ""),
                            f"data_label={g.get('data_label')}",
                        ],
                        "human_review_required": True,
                        "final_eligibility_claim_allowed": False,
                        "confirm_active_round": bool(g.get("confirm_active_round")),
                    }
                )

    sc_rows = [r for r in rows if r.get("funding_geography") == "south_carolina"]
    fed_rows = [r for r in rows if r.get("funding_geography") == "federal"]
    human_review = sum(1 for r in rows if r.get("human_review_required"))

    body = {
        "schema_version": SCHEMA_VERSION,
        "title": "SC Customer Demo — Curated State + Federal Opportunities",
        "demo_dev_only": True,
        "offline_only": True,
        "read_only_advisory": True,
        "live_ingestion": False,
        "source_activation": False,
        "external_urls_used": False,
        "auth_required": False,
        "final_eligibility_claim_allowed": False,
        "pack_id": pack.get("pack_id"),
        "capture_date": pack.get("capture_date"),
        "claim_matrix": build_demo_lane_claim_matrix(),
        "profiles": _profile_summary(profiles),
        "opportunities": _opportunity_summaries(grants),
        "classify_match": {
            "schema_version": cm.get("schema_version"),
            "profile_count": cm.get("profile_count"),
            "grant_count": cm.get("grant_count"),
            "match_pair_count": len(cm.get("matches") or []),
            "all_needs_operator_review": cm.get("all_needs_operator_review"),
            "honest_labeling": cm.get("honest_labeling"),
        },
        "combined_summary": {
            "row_count": len(rows),
            "south_carolina_row_count": len(sc_rows),
            "federal_row_count": len(fed_rows),
            "human_review_required_count": human_review,
            "confidence_distribution": _count_by(rows, "confidence"),
        },
        "missing_data_summary": {
            "rows_with_missing_data": sum(1 for r in rows if r.get("missing_data")),
            "hidden_missing_data": False,
        },
        "provenance_evidence_summary": {
            "notes_visible": True,
            "pack_evidence_required": True,
        },
        "what_nativeforge_did": [
            "Loaded South Carolina tribal organization profiles from operator fixtures",
            "Surfaced curated South Carolina and federal opportunities in one workflow",
            "Applied recognition-tier eligibility gating (federal vs state_only)",
            "Flagged uncertainty, missing data, and human-review requirements",
            "Did not activate sources, scrape live portals, or claim final eligibility",
        ],
        "what_requires_attention": [
            "Confirm active funding rounds (confirm_active_round flags)",
            "Human review of recognition-tier blockers before pursuit",
            "Missing profile evidence where confidence is inferred",
        ],
        "next_actions": [
            "Select an organization profile",
            "Review state + federal opportunities together",
            "Open eligibility explanation and blockers",
            "Decide pursue / defer with human review",
            "Next block: NOFO extraction showcase (not claimed here)",
        ],
        "rows": rows,
        "ui_flags": dict(REQUIRED_UI_FLAGS),
    }
    body["content_digest"] = _digest(
        {"pack_id": body["pack_id"], "row_count": len(rows), "profiles": body["profiles"]}
    )
    return _json_safe(body)


def demo_artifact_invariant_failures(artifact: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if artifact.get("live_ingestion") is not False:
        fails.append("live_ingestion_must_be_false")
    if artifact.get("source_activation") is not False:
        fails.append("source_activation_must_be_false")
    if artifact.get("final_eligibility_claim_allowed") is not False:
        fails.append("final_claim_must_be_false")
    if not artifact.get("rows"):
        fails.append("missing_rows")
    if (artifact.get("opportunities") or {}).get("south_carolina_count", 0) < 1:
        fails.append("missing_sc_opps")
    if (artifact.get("opportunities") or {}).get("federal_count", 0) < 1:
        fails.append("missing_federal_opps")
    for r in artifact.get("rows") or []:
        if r.get("final_eligibility_claim_allowed") is True:
            fails.append("row_final_claim_true")
            break
        if r.get("live_ingest_not_claimed") is not True:
            fails.append("row_live_ingest_claim_missing")
            break
    return fails
