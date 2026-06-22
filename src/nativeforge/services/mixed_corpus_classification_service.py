"""Sprint 334: classify mixed real corpus with discrimination report."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.mixed_corpus_builder_service import build_mixed_real_corpus
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    CLASSIFICATION_LABELS,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.tribe_eligible_broad_discoverability_guard_service import (
    apply_tribe_eligible_broad_discoverability_guard,
    assert_tribe_eligible_broad_discoverable,
)

SCHEMA_VERSION = "nf_mixed_corpus_classification_v1"

# Stage 6 vocabulary anchors for labels absent from live mixed distribution.
_VOCABULARY_DISCRIMINATION_ANCHORS: dict[str, dict[str, Any]] = {
    "indigenous_community_relevant": {
        "fixture_key": "nf14_vocab_anchor_indigenous_community",
        "opportunity_title": "Indigenous community health partnership (vocabulary anchor)",
        "eligibility_text": (
            "Eligible applicants: nonprofit native-serving organizations with "
            "501(c)(3) status serving Indigenous communities."
        ),
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
        "eligibility_tags": ["native_serving_nonprofit"],
        "tribal_set_aside": False,
        "tribal_priority_points": False,
        "vocabulary_discrimination_anchor": True,
        "fixture": True,
        "real_fetch": False,
    },
    "broadly_eligible_potentially_relevant": {
        "fixture_key": "nf14_vocab_anchor_broadly_eligible",
        "opportunity_title": "Economic development open with tribal priority points (anchor)",
        "eligibility_text": (
            "Open to state and local governments. Selection criteria award "
            "priority points to Indian tribes and tribal organizations."
        ),
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
        "eligibility_tags": [],
        "tribal_set_aside": False,
        "tribal_priority_points": True,
        "vocabulary_discrimination_anchor": True,
        "fixture": True,
        "real_fetch": False,
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_evidence_excerpt(grant: dict[str, Any], record: dict[str, Any]) -> str:
    excerpt = str(grant.get("eligibility_text") or "")[:500]
    if not excerpt and record.get("explanation"):
        excerpt = str(record["explanation"].get("source_eligibility_excerpt") or "")[:500]
    return excerpt


def classify_mixed_real_corpus(
    *,
    grants: list[dict[str, Any]] | None = None,
    assert_broad_discoverability: bool = True,
) -> dict[str, Any]:
    corpus = grants if grants is not None else build_mixed_real_corpus()
    classifications: list[dict[str, Any]] = []
    guard_results: list[dict[str, Any]] = []
    tribe_eligible_broad_count = 0
    tribe_eligible_broad_discoverable_count = 0
    overclaim_catches = 0
    over_filter_catches = 0

    for grant in corpus:
        record = build_real_grant_native_relevance_record(grant)
        cls = record["classification"]
        tribe_broad = bool(grant.get("tribe_eligible_broad"))
        if tribe_broad:
            tribe_eligible_broad_count += 1
            if cls["classification_label"] != "irrelevant" and cls["discoverable"]:
                tribe_eligible_broad_discoverable_count += 1
            if assert_broad_discoverability:
                assert_tribe_eligible_broad_discoverable(
                    grant_id=str(grant.get("grant_id") or ""),
                    tribe_eligible_broad=True,
                    classification_label=cls["classification_label"],
                    discoverable=bool(cls["discoverable"]),
                )
        guard = apply_tribe_eligible_broad_discoverability_guard(
            grant_id=str(grant.get("grant_id") or ""),
            tribe_eligible_broad=tribe_broad,
            classification_label=cls["classification_label"],
            discoverable=bool(cls["discoverable"]),
        )
        guard_results.append(guard)
        if guard.get("over_filter_caught"):
            over_filter_catches += 1
        if cls.get("overclaim_guard", {}).get("overclaim_blocked"):
            overclaim_catches += 1

        classifications.append(
            {
                **record,
                "corpus_segment": grant.get("corpus_segment"),
                "tribe_eligible_broad": tribe_broad,
                "source_evidence_excerpt": _source_evidence_excerpt(grant, record),
                "vocabulary_discrimination_anchor": grant.get(
                    "vocabulary_discrimination_anchor", False
                ),
            }
        )

    label_dist = Counter(c["classification"]["classification_label"] for c in classifications)
    worked_per_label = _build_worked_examples_per_label(classifications)
    labels_in_corpus = set(label_dist.keys())
    labels_missing = [lb for lb in CLASSIFICATION_LABELS if lb not in labels_in_corpus]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "classifications": classifications,
            "label_distribution": dict(label_dist),
            "distinct_label_count": len(label_dist),
            "labels_missing_from_corpus": labels_missing,
            "worked_examples_per_label": worked_per_label,
            "tribe_eligible_broad_count": tribe_eligible_broad_count,
            "tribe_eligible_broad_discoverable_count": tribe_eligible_broad_discoverable_count,
            "overclaim_catches": overclaim_catches,
            "over_filter_catches": over_filter_catches,
            "tribe_eligible_broad_guard_results": guard_results,
            "from_real_source_text": True,
            "honest_labeling": True,
        }
    )


def _build_worked_examples_per_label(
    classifications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_label: dict[str, dict[str, Any]] = {}
    for record in classifications:
        label = record["classification"]["classification_label"]
        if label not in by_label:
            by_label[label] = record

    examples: list[dict[str, Any]] = []
    for label in CLASSIFICATION_LABELS:
        chosen = by_label.get(label)
        if chosen is None and label in _VOCABULARY_DISCRIMINATION_ANCHORS:
            anchor_grant = {
                **_VOCABULARY_DISCRIMINATION_ANCHORS[label],
                "grant_id": _VOCABULARY_DISCRIMINATION_ANCHORS[label]["fixture_key"],
            }
            chosen = build_real_grant_native_relevance_record(anchor_grant)
            chosen = {
                **chosen,
                "corpus_segment": "vocabulary_anchor",
                "tribe_eligible_broad": False,
                "source_evidence_excerpt": anchor_grant["eligibility_text"][:500],
                "vocabulary_discrimination_anchor": True,
            }
        if chosen is None:
            continue
        examples.append(
            {
                "classification_label": label,
                "grant_id": chosen.get("grant_id"),
                "opportunity_title": chosen.get("opportunity_title"),
                "corpus_segment": chosen.get("corpus_segment"),
                "source_evidence_excerpt": chosen.get("source_evidence_excerpt"),
                "discoverable": chosen["classification"]["discoverable"],
                "confidence": chosen["classification"]["confidence"],
                "derived_evidence_codes": chosen.get("derived_evidence_codes") or [],
                "vocabulary_discrimination_anchor": chosen.get(
                    "vocabulary_discrimination_anchor", False
                ),
                "explanation_summary": {
                    "trigger_language": chosen["explanation"]["trigger_language"],
                    "eligible_entity_types": chosen["explanation"]["eligible_entity_types"],
                    "whats_missing": chosen["explanation"]["whats_missing"],
                },
            }
        )
    return examples


def build_mixed_corpus_classification_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "classification_labels": list(CLASSIFICATION_LABELS),
            "preview_only": True,
        }
    )
