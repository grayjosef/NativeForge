"""Sprint 185: human-review trigger vocabulary for native relevance classification."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_native_relevance_classification_human_review_trigger_v1"

TRIGGER_KEYWORD_HYPOTHESIS_ONLY = "keyword_hypothesis_only"
TRIGGER_AMBIGUOUS_ELIGIBILITY = "ambiguous_eligibility"
TRIGGER_MISSING_APPLICANT_TYPES = "missing_applicant_types"
TRIGGER_OVERCLAIM_BLOCKED = "overclaim_blocked"
TRIGGER_LOW_CONFIDENCE = "low_confidence"
TRIGGER_CONFLICTING_EVIDENCE = "conflicting_evidence"
TRIGGER_UNCERTAIN_LABEL = "uncertain_label"

HUMAN_REVIEW_TRIGGERS: tuple[str, ...] = (
    TRIGGER_KEYWORD_HYPOTHESIS_ONLY,
    TRIGGER_AMBIGUOUS_ELIGIBILITY,
    TRIGGER_MISSING_APPLICANT_TYPES,
    TRIGGER_OVERCLAIM_BLOCKED,
    TRIGGER_LOW_CONFIDENCE,
    TRIGGER_CONFLICTING_EVIDENCE,
    TRIGGER_UNCERTAIN_LABEL,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_human_review_trigger(code: str) -> bool:
    return code in HUMAN_REVIEW_TRIGGERS


def build_human_review_trigger_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "human_review_triggers": list(HUMAN_REVIEW_TRIGGERS),
            "preview_only": True,
        }
    )


def evaluate_human_review_required(
    *,
    trigger_codes: list[str],
) -> dict[str, Any]:
    valid = [c for c in trigger_codes if is_valid_human_review_trigger(c)]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "human_review_required": bool(valid),
            "trigger_codes": sorted(set(valid)),
        }
    )
