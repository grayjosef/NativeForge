"""Sprint 189: deterministic native relevance classification evaluator."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_confidence_service import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_UNKNOWN,
)
from nativeforge.services.native_relevance_classification_human_review_trigger_service import (
    TRIGGER_AMBIGUOUS_ELIGIBILITY,
    TRIGGER_KEYWORD_HYPOTHESIS_ONLY,
    TRIGGER_LOW_CONFIDENCE,
    TRIGGER_MISSING_APPLICANT_TYPES,
    TRIGGER_UNCERTAIN_LABEL,
    evaluate_human_review_required,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_INDIGENOUS_COMMUNITY_RELEVANT,
    LABEL_IRRELEVANT,
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
    LABEL_UNCERTAIN_RELEVANCE,
    LABEL_WEAK_NATIVE_RELEVANCE,
)
from nativeforge.services.native_relevance_classification_over_filter_guard_service import (
    apply_over_filter_guard,
)
from nativeforge.services.native_relevance_classification_overclaim_guard_service import (
    apply_overclaim_guard,
    has_explicit_source_evidence,
)
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    apply_no_evidence_irrelevant_guard,
)

SCHEMA_VERSION = "nf_native_relevance_classification_evaluator_v1"

_TITLE_HINTS = (
    "tribal",
    "native",
    "indian country",
    "indigenous",
    "alaska native",
    "native hawaiian",
)

_STRUCTURAL_TAGS = frozenset(
    {
        "tribal_eligible",
        "tribal_government",
        "federally_recognized_tribe",
        "native_serving_nonprofit",
        "tribal_college",
        "alaska_native",
        "native_hawaiian",
        "ihs_service_population",
    }
)

_COMMUNITY_TAGS = frozenset(
    {
        "native_serving_nonprofit",
        "ihs_service_population",
        "language_preservation",
        "culture",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _tags(raw: dict[str, Any]) -> set[str]:
    tags = raw.get("eligibility_tags") or []
    return {str(t) for t in tags}


def _keyword_hit(raw: dict[str, Any]) -> bool:
    blob = str(raw.get("opportunity_title") or raw.get("title") or "").lower()
    return any(hint in blob for hint in _TITLE_HINTS)


def _structured_signal(raw: dict[str, Any]) -> bool:
    if raw.get("tribal_eligible"):
        return True
    if raw.get("tribal_set_aside"):
        return True
    if raw.get("tribal_priority_points"):
        return True
    if raw.get("applicant_types_include_tribal") is True:
        return True
    return bool(_tags(raw) & _STRUCTURAL_TAGS)


def _propose_label(raw: dict[str, Any]) -> str:
    tags = _tags(raw)
    keyword = _keyword_hit(raw)
    structured = _structured_signal(raw)

    if not keyword and not structured:
        if raw.get("applicant_types_include_tribal") is None and not raw.get("tribal_eligible"):
            if str(raw.get("opportunity_title") or raw.get("title") or "").strip():
                return LABEL_UNCERTAIN_RELEVANCE
        from nativeforge.services.eligibility_evidence_quality_service import (
            has_positive_irrelevant_evidence,
        )

        if has_positive_irrelevant_evidence(raw):
            return LABEL_IRRELEVANT
        return LABEL_UNCERTAIN_RELEVANCE

    if raw.get("tribal_set_aside"):
        return LABEL_NATIVE_SPECIFIC

    if raw.get("applicant_types_include_tribal") is True or "tribal_government" in tags:
        return LABEL_TRIBAL_GOVERNMENT_SPECIFIC

    if tags & _COMMUNITY_TAGS and not raw.get("tribal_eligible"):
        return LABEL_INDIGENOUS_COMMUNITY_RELEVANT

    if raw.get("tribal_eligible") or bool(tags & _STRUCTURAL_TAGS):
        return LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD

    if keyword and not structured:
        return LABEL_WEAK_NATIVE_RELEVANCE

    if raw.get("applicant_types_include_tribal") is None:
        return LABEL_UNCERTAIN_RELEVANCE

    return LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT


def _confidence_for_label(label: str, raw: dict[str, Any], *, overclaim_blocked: bool) -> str:
    explicit = has_explicit_source_evidence(list(raw.get("explicit_source_evidence") or []))
    if overclaim_blocked:
        return CONFIDENCE_LOW
    if label == LABEL_NATIVE_SPECIFIC and explicit:
        return CONFIDENCE_CONFIRMED
    if label in {LABEL_TRIBAL_GOVERNMENT_SPECIFIC, LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD} and explicit:
        return CONFIDENCE_HIGH
    if label == LABEL_INDIGENOUS_COMMUNITY_RELEVANT:
        return CONFIDENCE_MEDIUM
    if label == LABEL_WEAK_NATIVE_RELEVANCE:
        return CONFIDENCE_LOW
    if label == LABEL_UNCERTAIN_RELEVANCE:
        return CONFIDENCE_UNKNOWN
    if label == LABEL_IRRELEVANT:
        return CONFIDENCE_HIGH
    return CONFIDENCE_MEDIUM


def _collect_review_triggers(
    label: str,
    raw: dict[str, Any],
    *,
    overclaim_blocked: bool,
    confidence: str,
    no_evidence_guard: dict[str, Any] | None = None,
) -> list[str]:
    triggers: list[str] = []
    neg = no_evidence_guard or {}
    if overclaim_blocked:
        triggers.append("overclaim_blocked")
    keyword = _keyword_hit(raw)
    structured = _structured_signal(raw)
    if keyword and not structured:
        triggers.append(TRIGGER_KEYWORD_HYPOTHESIS_ONLY)
    if raw.get("applicant_types_include_tribal") is None and not structured:
        triggers.append(TRIGGER_MISSING_APPLICANT_TYPES)
    if raw.get("applicant_types_include_tribal") is None and label == LABEL_UNCERTAIN_RELEVANCE:
        triggers.append(TRIGGER_AMBIGUOUS_ELIGIBILITY)
    if label == LABEL_UNCERTAIN_RELEVANCE:
        triggers.append(TRIGGER_UNCERTAIN_LABEL)
    if neg.get("no_evidence_blocked"):
        triggers.append("insufficient_eligibility_evidence")
    if neg.get("tribal_agency_safety_net", {}).get("safety_net_triggered"):
        triggers.append("tribal_agency_safety_net")
    if confidence in {CONFIDENCE_LOW, CONFIDENCE_UNKNOWN}:
        triggers.append(TRIGGER_LOW_CONFIDENCE)
    return triggers


def classify_native_relevance(raw: dict[str, Any]) -> dict[str, Any]:
    """Deterministic Stage 6 classification with both hard invariants applied."""
    proposed = _propose_label(raw)
    evidence = list(raw.get("explicit_source_evidence") or [])

    if proposed == LABEL_NATIVE_SPECIFIC or (
        raw.get("tribal_set_aside") and _keyword_hit(raw)
    ):
        guard = apply_overclaim_guard(
            proposed_label=LABEL_NATIVE_SPECIFIC,
            evidence_codes=evidence,
            fallback_label=LABEL_WEAK_NATIVE_RELEVANCE
            if _keyword_hit(raw) and not _structured_signal(raw)
            else LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
        )
        final_label = guard["final_label"]
        overclaim_blocked = guard["overclaim_blocked"]
    else:
        guard = apply_overclaim_guard(proposed_label=proposed, evidence_codes=evidence)
        final_label = guard["final_label"]
        overclaim_blocked = guard["overclaim_blocked"]

    no_evidence_guard = apply_no_evidence_irrelevant_guard(
        proposed_label=final_label,
        grant=raw,
    )
    final_label = no_evidence_guard["final_label"]

    confidence = _confidence_for_label(final_label, raw, overclaim_blocked=overclaim_blocked)
    review_triggers = _collect_review_triggers(
        final_label,
        raw,
        overclaim_blocked=overclaim_blocked,
        confidence=confidence,
        no_evidence_guard=no_evidence_guard,
    )
    review = evaluate_human_review_required(trigger_codes=review_triggers)

    proposed_discoverable = final_label != LABEL_IRRELEVANT
    filter_guard = apply_over_filter_guard(
        classification_label=final_label,
        proposed_discoverable=proposed_discoverable,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": raw.get("fixture_key"),
            "proposed_label": proposed,
            "classification_label": final_label,
            "confidence": confidence,
            "human_review_required": review["human_review_required"],
            "human_review_trigger_codes": review["trigger_codes"],
            "discoverable": filter_guard["final_discoverable"],
            "overclaim_guard": guard,
            "over_filter_guard": filter_guard,
            "no_evidence_guard": no_evidence_guard,
            "eligibility_evidence_status": no_evidence_guard.get(
                "eligibility_evidence_status"
            ),
            "evidence_codes": evidence,
            "preview_only": True,
        }
    )
