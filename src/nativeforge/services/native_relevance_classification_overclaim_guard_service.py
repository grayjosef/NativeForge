"""Sprint 186: overclaim guard — never native_specific without explicit source evidence."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_human_review_trigger_service import (
    TRIGGER_OVERCLAIM_BLOCKED,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
    LABEL_WEAK_NATIVE_RELEVANCE,
)

SCHEMA_VERSION = "nf_native_relevance_classification_overclaim_guard_v1"

# Evidence codes that satisfy explicit source evidence for native_specific.
EXPLICIT_SOURCE_EVIDENCE_CODES: frozenset[str] = frozenset(
    {
        "tribal_set_aside_in_source",
        "tribal_eligible_in_source",
        "applicant_types_tribal_in_source",
        "native_only_mandate_in_source",
        "eligibility_tag_structural_in_source",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def has_explicit_source_evidence(evidence_codes: list[str]) -> bool:
    return bool(set(evidence_codes) & EXPLICIT_SOURCE_EVIDENCE_CODES)


def apply_overclaim_guard(
    *,
    proposed_label: str,
    evidence_codes: list[str],
    fallback_label: str = LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
) -> dict[str, Any]:
    """Fail-closed: downgrade native_specific when explicit source evidence absent."""
    if proposed_label != LABEL_NATIVE_SPECIFIC:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_label": proposed_label,
                "final_label": proposed_label,
                "overclaim_blocked": False,
                "explicit_source_evidence_present": has_explicit_source_evidence(
                    evidence_codes
                ),
                "human_review_trigger_codes": [],
            }
        )

    explicit = has_explicit_source_evidence(evidence_codes)
    if explicit:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_label": proposed_label,
                "final_label": LABEL_NATIVE_SPECIFIC,
                "overclaim_blocked": False,
                "explicit_source_evidence_present": True,
                "human_review_trigger_codes": [],
            }
        )

    # Keyword-only or weak signals attempted native_specific — downgrade.
    downgrade = fallback_label
    if fallback_label == LABEL_NATIVE_SPECIFIC:
        downgrade = LABEL_WEAK_NATIVE_RELEVANCE

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_label": proposed_label,
            "final_label": downgrade,
            "overclaim_blocked": True,
            "explicit_source_evidence_present": False,
            "human_review_trigger_codes": [TRIGGER_OVERCLAIM_BLOCKED],
            "guard_reason": (
                "native_specific requires explicit source evidence; downgraded to preserve accuracy"
            ),
        }
    )


def build_overclaim_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "protected_label": LABEL_NATIVE_SPECIFIC,
            "required_evidence_codes": sorted(EXPLICIT_SOURCE_EVIDENCE_CODES),
            "typical_downgrade_labels": [
                LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
                LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
                LABEL_WEAK_NATIVE_RELEVANCE,
            ],
            "preview_only": True,
        }
    )
