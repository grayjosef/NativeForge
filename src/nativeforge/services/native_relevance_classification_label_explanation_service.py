"""Sprint 183: per-label explanation templates for native relevance classification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    CLASSIFICATION_LABELS,
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_INDIGENOUS_COMMUNITY_RELEVANT,
    LABEL_IRRELEVANT,
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
    LABEL_UNCERTAIN_RELEVANCE,
    LABEL_WEAK_NATIVE_RELEVANCE,
)

SCHEMA_VERSION = "nf_native_relevance_classification_label_explanation_v1"

_LABEL_EXPLANATIONS: dict[str, dict[str, str]] = {
    LABEL_NATIVE_SPECIFIC: {
        "trigger_language": (
            "Explicit tribal set-aside, mandate, or source-documented native-only eligibility."
        ),
        "eligible_entity_types": (
            "Federally recognized tribes, tribal governments, Alaska Native entities, "
            "Native Hawaiian organizations as named in source."
        ),
        "whats_missing": (
            "Without explicit source evidence, native_specific must not be assigned."
        ),
        "operator_next_check": (
            "Verify NOFO or source registry fields cite tribal set-aside or native-only mandate."
        ),
    },
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC: {
        "trigger_language": (
            "Applicant types or eligibility text names tribal governments as primary eligible entity."
        ),
        "eligible_entity_types": "Tribal governments, tribal departments, inter-tribal consortia.",
        "whats_missing": "Structured applicant-type field or eligibility excerpt from source.",
        "operator_next_check": (
            "Confirm applicant_types or eligibility_tags include tribal_government pathway."
        ),
    },
    LABEL_INDIGENOUS_COMMUNITY_RELEVANT: {
        "trigger_language": (
            "Program purpose, tags, or narrative targets indigenous community outcomes."
        ),
        "eligible_entity_types": (
            "Tribal nonprofits, native-serving organizations, community-based indigenous entities."
        ),
        "whats_missing": "Community-impact pathway without broad open eligibility confirmation.",
        "operator_next_check": (
            "Review program description for indigenous community serving language with source cite."
        ),
    },
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD: {
        "trigger_language": (
            "Tribal_eligible flag or structural eligibility tags include native entities among eligible types."
        ),
        "eligible_entity_types": (
            "Tribes, Alaska Native corporations, Native Hawaiian organizations, native-serving nonprofits."
        ),
        "whats_missing": "Explicit native-only mandate required for native_specific upgrade.",
        "operator_next_check": (
            "Check tribal_eligible and eligibility_tags against source registry snapshot."
        ),
    },
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT: {
        "trigger_language": (
            "Open or broad eligibility with incidental native keywords or secondary native pathways."
        ),
        "eligible_entity_types": "General nonprofits plus potentially native entities under broad rules.",
        "whats_missing": "Structured tribal eligibility confirmation.",
        "operator_next_check": (
            "Confirm opportunity stays discoverable; do not over-filter broad relevance."
        ),
    },
    LABEL_WEAK_NATIVE_RELEVANCE: {
        "trigger_language": "Keyword or title hints only — no structured eligibility confirmation.",
        "eligible_entity_types": "Unknown — hypothesis from text signals only.",
        "whats_missing": "Structured tribal_eligible, applicant types, or eligibility tags from source.",
        "operator_next_check": (
            "Human review required before treating as confirmed native eligibility."
        ),
    },
    LABEL_UNCERTAIN_RELEVANCE: {
        "trigger_language": "Ambiguous or incomplete eligibility/applicant-type data.",
        "eligible_entity_types": "Undetermined pending source completeness.",
        "whats_missing": "Applicant types, eligibility excerpt, or provenance for native signals.",
        "operator_next_check": "Queue for operator eligibility review with source document check.",
    },
    LABEL_IRRELEVANT: {
        "trigger_language": "No native, tribal, or indigenous relevance signals detected.",
        "eligible_entity_types": "Non-native general eligibility only.",
        "whats_missing": "Any native relevance evidence.",
        "operator_next_check": (
            "Optional spot-check if source metadata incomplete; otherwise exclude from native queue."
        ),
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def get_label_explanation_template(label: str) -> dict[str, str]:
    if label not in _LABEL_EXPLANATIONS:
        raise ValueError(f"unknown classification label: {label!r}")
    return dict(_LABEL_EXPLANATIONS[label])


def build_label_explanation_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "label_count": len(CLASSIFICATION_LABELS),
            "explanation_fields": [
                "trigger_language",
                "eligible_entity_types",
                "whats_missing",
                "operator_next_check",
            ],
            "templates_by_label": {
                label: get_label_explanation_template(label) for label in CLASSIFICATION_LABELS
            },
            "preview_only": True,
        }
    )
