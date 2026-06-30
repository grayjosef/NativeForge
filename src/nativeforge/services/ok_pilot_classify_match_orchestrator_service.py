"""OK-4: OK pilot classify+match — all federal tribes, grant_posture advisory only."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (  # noqa: E501
    DIMENSION_PROGRAM_FIT,
    FIT_STATUS_UNKNOWN,
)
from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.ok_pilot_fixture_loader_service import (
    load_ok_tribal_profiles,
    require_ok_pilot_fixtures,
)
from nativeforge.services.ok_pilot_profile_loader_service import (
    resolve_ok_pilot_profile,
)
from nativeforge.services.pilot_grant_posture_advisory_service import (
    build_grant_posture_advisory,
    classify_grant_funding_style,
)
from nativeforge.services.real_grant_classify_match_service import (
    _grant_to_opportunity,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    apply_recognition_tier_eligibility_gate,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    build_sc_pilot_rule_reference_grants,
    load_sc_eligibility_rules,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
)

SCHEMA_VERSION = "nf_ok_pilot_classify_match_orchestrator_v1"


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


def _program_fit_from_match(match: dict[str, Any]) -> dict[str, Any] | None:
    dims = match.get("eligibility_fit_assessment", {}).get("dimension_results") or []
    for d in dims:
        if d.get("dimension") == DIMENSION_PROGRAM_FIT:
            return d
    fit_dims = match.get("fit_dimensions") or []
    for d in fit_dims:
        if d.get("dimension") == DIMENSION_PROGRAM_FIT:
            return d
    return None


def _summarize_program_fit_resolution(matches: list[dict[str, Any]]) -> dict[str, Any]:
    grant_has_program = 0
    resolved = 0
    profile_unknown = 0
    grant_unknown = 0
    for m in matches:
        opp = m.get("opportunity_metadata") or {}
        program = opp.get("program_area")
        if not program:
            grant_unknown += 1
            continue
        grant_has_program += 1
        if m.get("profile_program_areas_unknown"):
            profile_unknown += 1
            continue
        pf = m.get("program_fit") or {}
        if pf.get("fit_status") != FIT_STATUS_UNKNOWN:
            resolved += 1
    rate = (resolved / grant_has_program) if grant_has_program else 0.0
    return {
        "grant_with_program_area_count": grant_has_program,
        "grant_program_area_unknown_count": grant_unknown,
        "profile_program_areas_unknown_rows": profile_unknown,
        "program_fit_resolved_count": resolved,
        "program_fit_resolution_rate": round(rate, 4),
    }


def run_ok_pilot_classify_match_block(
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
        require_ok_pilot_fixtures()
    rules = load_sc_eligibility_rules(require_files=False)
    profiles_raw = load_ok_tribal_profiles(require_files=require_fixtures)
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
    posture_on_matches: Counter[str] = Counter()

    for fk in keys:
        profile = resolve_ok_pilot_profile(fk, require_files=require_fixtures)
        grant_posture = str(profile.get("grant_posture") or "UNKNOWN")
        profile_matches: list[dict[str, Any]] = []
        tier_mismatch_count = 0
        federal_required_tier_blocks = 0
        discretionary_advisory_lower = 0
        discretionary_still_included = 0

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
            if has_tier_mismatch:
                tier_mismatch_count += 1
                if opp.get("recognition_requirement") == "federal_required":
                    federal_required_tier_blocks += 1

            posture_advisory = build_grant_posture_advisory(
                grant_posture=grant_posture,
                grant=grant,
            )
            posture_on_matches[grant_posture] += 1
            if (
                posture_advisory["advisory_ranking_hint"] == "lower"
                and classify_grant_funding_style(grant) == "discretionary"
            ):
                discretionary_advisory_lower += 1
                if not tier_gate["excluded_from_match_set"]:
                    discretionary_still_included += 1

            program_fit = _program_fit_from_match(match)
            if program_fit is None:
                for d in match.get("eligibility_fit_assessment", {}).get(
                    "dimension_results", []
                ):
                    if d.get("dimension") == DIMENSION_PROGRAM_FIT:
                        program_fit = d
                        break

            profile_matches.append(
                {
                    "grant_id": grant.get("grant_id"),
                    "profile_fixture_key": fk,
                    "organization_name": profile.get("organization_name"),
                    "opportunity_title": grant.get("opportunity_title"),
                    "recognition_requirement": opp.get("recognition_requirement"),
                    "classification_label": nrc["classification"][
                        "classification_label"
                    ],
                    "match_label": LABEL_NEEDS_OPERATOR_REVIEW,
                    "recognition_tier_gate": tier_gate,
                    "recognition_tier_mismatch": has_tier_mismatch,
                    "excluded_from_match_set": tier_gate["excluded_from_match_set"],
                    "blocker_codes": blockers,
                    "fit_dimensions": assessment["dimension_results"],
                    "program_fit": program_fit,
                    "profile_program_areas_unknown": profile.get(
                        "program_areas_unknown"
                    ),
                    "opportunity_metadata": {
                        "program_area": opp.get("program_area"),
                        "required_geography": opp.get("required_geography"),
                    },
                    "grant_posture_advisory": posture_advisory,
                }
            )

        all_matches.extend(profile_matches)
        per_profile.append(
            {
                "profile_fixture_key": fk,
                "organization_name": profile.get("organization_name"),
                "recognition_type": profile.get("recognition_type"),
                "grant_posture": grant_posture,
                "program_areas_unknown": profile.get("program_areas_unknown"),
                "capture_method": profile.get("capture_method"),
                "match_count": len(profile_matches),
                "recognition_tier_mismatch_count": tier_mismatch_count,
                "federal_required_tier_block_count": federal_required_tier_blocks,
                "discretionary_advisory_lower_count": discretionary_advisory_lower,
                "discretionary_advisory_lower_still_included": (
                    discretionary_still_included
                ),
            }
        )

    program_fit_summary = _summarize_program_fit_resolution(all_matches)

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
            "program_fit_summary": program_fit_summary,
            "grant_posture_distribution_on_matches": dict(posture_on_matches),
            "all_needs_operator_review": True,
            "grant_posture_advisory_only": True,
            "honest_labeling": True,
        }
    )
