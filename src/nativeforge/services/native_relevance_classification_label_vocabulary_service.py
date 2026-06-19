"""Sprint 182: Native relevance classification label vocabulary (Stage 6, offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_native_relevance_classification_label_vocabulary_v1"

LABEL_NATIVE_SPECIFIC = "native_specific"
LABEL_TRIBAL_GOVERNMENT_SPECIFIC = "tribal_government_specific"
LABEL_INDIGENOUS_COMMUNITY_RELEVANT = "indigenous_community_relevant"
LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD = "native_entity_eligible_broad"
LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT = "broadly_eligible_potentially_relevant"
LABEL_WEAK_NATIVE_RELEVANCE = "weak_native_relevance"
LABEL_UNCERTAIN_RELEVANCE = "uncertain_relevance"
LABEL_IRRELEVANT = "irrelevant"

CLASSIFICATION_LABELS: tuple[str, ...] = (
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
    LABEL_INDIGENOUS_COMMUNITY_RELEVANT,
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_WEAK_NATIVE_RELEVANCE,
    LABEL_UNCERTAIN_RELEVANCE,
    LABEL_IRRELEVANT,
)

# Specificity rank — higher means more narrowly native-targeted.
_LABEL_SPECIFICITY_RANK: dict[str, int] = {
    LABEL_NATIVE_SPECIFIC: 8,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC: 7,
    LABEL_INDIGENOUS_COMMUNITY_RELEVANT: 6,
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD: 5,
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT: 4,
    LABEL_WEAK_NATIVE_RELEVANCE: 3,
    LABEL_UNCERTAIN_RELEVANCE: 2,
    LABEL_IRRELEVANT: 1,
}

# Labels that must remain discoverable under the over-filter guard.
DISCOVERABLE_LABELS: frozenset[str] = frozenset(
    {
        LABEL_NATIVE_SPECIFIC,
        LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
        LABEL_INDIGENOUS_COMMUNITY_RELEVANT,
        LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
        LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
        LABEL_WEAK_NATIVE_RELEVANCE,
        LABEL_UNCERTAIN_RELEVANCE,
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_classification_label(label: str) -> bool:
    return label in _LABEL_SPECIFICITY_RANK


def label_specificity_rank(label: str) -> int:
    if not is_valid_classification_label(label):
        raise ValueError(f"invalid classification label: {label!r}")
    return _LABEL_SPECIFICITY_RANK[label]


def build_label_vocabulary_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "classification_labels": list(CLASSIFICATION_LABELS),
            "discoverable_labels": sorted(DISCOVERABLE_LABELS),
            "evidence_based": True,
            "preview_only": True,
        }
    )
