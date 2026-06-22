"""Sprint 326-327: classify + match real ingested grants against test tribal profile."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.matching_readiness_readiness_evaluator_service import (
    evaluate_readiness,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    EXPECTED_GRANT_COUNT,
    load_nf13_real_ingested_grants,
    load_nf13_test_tribal_profile,
)

SCHEMA_VERSION = "nf_real_grant_classify_match_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _grant_to_opportunity(grant: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_key": grant.get("grant_id"),
        "opportunity_title": grant.get("opportunity_title"),
        "opportunity_number": grant.get("opportunity_number"),
        "agency": grant.get("agency"),
        "eligibility_text": grant.get("eligibility_text"),
        "application_deadline": grant.get("application_deadline"),
        "tribal_eligible": grant.get("tribal_eligible"),
        "applicant_types_include_tribal": grant.get("applicant_types_include_tribal"),
        "from_real_source_text": True,
    }


def classify_and_match_real_grants(
    *,
    grants: list[dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else load_nf13_real_ingested_grants()
    tribal_profile = profile or load_nf13_test_tribal_profile()
    classifications: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for grant in corpus:
        nrc = build_real_grant_native_relevance_record(grant)
        classifications.append(nrc)
        opp = _grant_to_opportunity(grant)
        pair_meta = {
            "fixture_key": str(grant.get("grant_id")),
            "profile_fixture_key": tribal_profile.get("fixture_key"),
        }
        match = evaluate_match(opp, tribal_profile, pair_meta=pair_meta)
        readiness = evaluate_readiness(
            opp, tribal_profile, pair_meta=pair_meta, match_result=match
        )
        matches.append(
            {
                "grant_id": grant.get("grant_id"),
                "opportunity_title": grant.get("opportunity_title"),
                "classification_label": nrc["classification"]["classification_label"],
                "match_label": match["match_label"],
                "readiness_label": readiness["readiness_label"],
                "fit_dimensions": match["eligibility_fit_assessment"]["dimension_results"],
                "blockers": match["eligibility_fit_assessment"]["blockers"],
                "missing_data": match["eligibility_fit_assessment"]["missing_data"],
                "next_action": match.get("next_action_guidance"),
                "applicant_recommendation_blocked": match[
                    "applicant_recommendation_guard"
                ]["recommendation_blocked"],
                "from_real_source_text": True,
            }
        )
    label_dist = Counter(c["classification"]["classification_label"] for c in classifications)
    match_dist = Counter(m["match_label"] for m in matches)
    matched_count = sum(
        1
        for m in matches
        if m["match_label"]
        not in {"not_fit", "blocked", "needs_more_profile_data"}
    )
    worked_examples = _select_worked_examples(classifications, matches)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "expected_grant_count": EXPECTED_GRANT_COUNT,
            "classifications": classifications,
            "matches": matches,
            "label_distribution": dict(label_dist),
            "match_label_distribution": dict(match_dist),
            "profile_fixture_key": tribal_profile.get("fixture_key"),
            "matched_grant_count": matched_count,
            "worked_examples": worked_examples,
            "from_real_source_text": True,
            "honest_labeling": True,
        }
    )


def _select_worked_examples(
    classifications: list[dict[str, Any]],
    matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {m["grant_id"]: m for m in matches}
    examples: list[dict[str, Any]] = []
    for nrc in classifications:
        gid = nrc.get("grant_id")
        match = by_id.get(gid)
        if not match:
            continue
        if match["match_label"] in {"strong_fit", "possible_fit"}:
            examples.append(
                {
                    "grant_id": gid,
                    "opportunity_title": nrc.get("opportunity_title"),
                    "classification_label": nrc["classification"]["classification_label"],
                    "match_label": match["match_label"],
                    "explanation_summary": {
                        "trigger_language": nrc["explanation"]["trigger_language"],
                        "eligible_entity_types": nrc["explanation"]["eligible_entity_types"],
                        "whats_missing": nrc["explanation"]["whats_missing"],
                    },
                    "fit_dimensions": match["fit_dimensions"],
                    "blockers": match["blockers"],
                }
            )
        if len(examples) >= 2:
            break
    if len(examples) < 2:
        for nrc in classifications[:2]:
            gid = nrc.get("grant_id")
            match = by_id.get(gid, {})
            examples.append(
                {
                    "grant_id": gid,
                    "opportunity_title": nrc.get("opportunity_title"),
                    "classification_label": nrc["classification"]["classification_label"],
                    "match_label": match.get("match_label"),
                    "explanation_summary": {
                        "trigger_language": nrc["explanation"]["trigger_language"],
                        "eligible_entity_types": nrc["explanation"]["eligible_entity_types"],
                        "whats_missing": nrc["explanation"]["whats_missing"],
                    },
                }
            )
    return examples[:2]
