"""SC-4: SC pilot classify+match with independent recognition-tier gate."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_ELIGIBILITY_EVIDENCE_GAP,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.real_grant_classify_match_service import (
    _grant_to_opportunity,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    apply_recognition_tier_eligibility_gate,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    build_sc_pilot_rule_reference_grants,
    load_sc_eligibility_rules,
    load_sc_tribal_profiles,
    require_sc_pilot_fixtures,
)
from nativeforge.services.sc_pilot_profile_loader_service import (
    resolve_sc_pilot_profile,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
)

SCHEMA_VERSION = "nf_sc_pilot_classify_match_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _load_corpus(
    grants: list[dict[str, Any]] | None,
    *,
    rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if grants is not None:
        base = grants
    else:
        base = load_mixed_tier13_corpus()
    rule_refs = build_sc_pilot_rule_reference_grants(rules)
    seen_ids = {str(g.get("grant_id")) for g in base}
    merged = list(base)
    for ref in rule_refs:
        if str(ref.get("grant_id")) not in seen_ids:
            merged.append(ref)
    return merged


def run_sc_pilot_classify_match_block(
    *,
    org_id: Any = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    grants: list[dict[str, Any]] | None = None,
    profile_fixture_keys: list[str] | None = None,
    require_fixtures: bool = True,
    allow_live_completeness_fetch: bool = False,
) -> dict[str, Any]:
    if require_fixtures:
        require_sc_pilot_fixtures()
    rules = load_sc_eligibility_rules(require_files=require_fixtures)
    profiles_raw = load_sc_tribal_profiles(require_files=require_fixtures)
    keys = profile_fixture_keys or [str(p["fixture_key"]) for p in profiles_raw]
    corpus = [
        enrich_grant_with_eligibility_metadata(
            g,
            rules=rules,
            allow_live_completeness_fetch=allow_live_completeness_fetch,
        )
        for g in _load_corpus(grants, rules=rules)
    ]

    all_matches: list[dict[str, Any]] = []
    per_profile: list[dict[str, Any]] = []

    for fk in keys:
        profile = resolve_sc_pilot_profile(fk, require_files=require_fixtures)
        profile_matches: list[dict[str, Any]] = []
        tier_mismatch_count = 0
        condition_mismatch_count = 0
        member_level_count = 0
        evidence_gap_count = 0
        included_count = 0
        excluded_count = 0

        for grant in corpus:
            nrc = build_real_grant_native_relevance_record(grant)
            opp = _grant_to_opportunity(grant)
            tier_gate = apply_recognition_tier_eligibility_gate(
                opportunity=opp, profile=profile
            )
            pair_meta = {
                "fixture_key": str(grant.get("grant_id")),
                "profile_fixture_key": fk,
            }
            match = evaluate_match(opp, profile, pair_meta=pair_meta)
            assessment = match["eligibility_fit_assessment"]
            blockers = list(assessment["blockers"]["blocker_codes"])

            has_tier_mismatch = tier_gate.get("recognition_tier_mismatch") is True
            has_condition_mismatch = tier_gate.get("condition_mismatch") is True
            has_evidence_gap = BLOCKER_ELIGIBILITY_EVIDENCE_GAP in blockers
            if has_tier_mismatch:
                tier_mismatch_count += 1
            if has_condition_mismatch:
                condition_mismatch_count += 1
            if tier_gate.get("member_level_only"):
                member_level_count += 1
            if has_evidence_gap:
                evidence_gap_count += 1

            excluded = tier_gate["excluded_from_match_set"]
            if excluded:
                excluded_count += 1
            else:
                included_count += 1

            profile_matches.append(
                {
                    "grant_id": grant.get("grant_id"),
                    "profile_fixture_key": fk,
                    "opportunity_title": grant.get("opportunity_title"),
                    "recognition_requirement": opp.get("recognition_requirement"),
                    "classification_label": nrc["classification"]["classification_label"],
                    "match_label": LABEL_NEEDS_OPERATOR_REVIEW,
                    "recognition_tier_gate": tier_gate,
                    "recognition_tier_mismatch": has_tier_mismatch,
                    "condition_mismatch": has_condition_mismatch,
                    "member_level_only": tier_gate.get("member_level_only"),
                    "eligibility_evidence_gap": has_evidence_gap,
                    "excluded_from_match_set": excluded,
                    "blocker_codes": blockers,
                    "fit_dimensions": match["eligibility_fit_assessment"]["dimension_results"],
                }
            )

        all_matches.extend(profile_matches)
        per_profile.append(
            {
                "profile_fixture_key": fk,
                "recognition_type": profile.get("recognition_type"),
                "capture_method": profile.get("capture_method"),
                "match_count": len(profile_matches),
                "included_in_match_set": included_count,
                "excluded_from_match_set": excluded_count,
                "recognition_tier_mismatch_count": tier_mismatch_count,
                "condition_mismatch_count": condition_mismatch_count,
                "member_level_only_count": member_level_count,
                "eligibility_evidence_gap_count": evidence_gap_count,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "grant_count": len(corpus),
            "profile_count": len(keys),
            "matches": all_matches,
            "per_profile": per_profile,
            "all_needs_operator_review": True,
            "recognition_tier_gate_independent": True,
            "honest_labeling": True,
        }
    )
