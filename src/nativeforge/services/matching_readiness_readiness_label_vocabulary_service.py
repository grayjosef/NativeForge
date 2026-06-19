"""Sprint 214: application readiness labels for matching + readiness."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_matching_readiness_readiness_label_vocabulary_v1"

READINESS_APPLICATION_READY = "application_ready"
READINESS_READY_WITH_REVIEW = "ready_with_review"
READINESS_NOT_READY_MISSING_DOCUMENTS = "not_ready_missing_documents"
READINESS_NOT_READY_DEADLINE_RISK = "not_ready_deadline_risk"
READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN = "not_ready_eligibility_uncertain"
READINESS_NOT_READY_CAPACITY_GAP = "not_ready_capacity_gap"
READINESS_BLOCKED = "blocked"

READINESS_LABELS: tuple[str, ...] = (
    READINESS_APPLICATION_READY,
    READINESS_READY_WITH_REVIEW,
    READINESS_NOT_READY_MISSING_DOCUMENTS,
    READINESS_NOT_READY_DEADLINE_RISK,
    READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN,
    READINESS_NOT_READY_CAPACITY_GAP,
    READINESS_BLOCKED,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_readiness_label(label: str) -> bool:
    return label in READINESS_LABELS


def build_readiness_label_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "readiness_labels": list(READINESS_LABELS),
            "preview_only": True,
        }
    )
