"""Sprint 243: canonicalize application_readiness on readiness_label vocabulary."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_readiness_label_vocabulary_service import (
    READINESS_NOT_READY_MISSING_DOCUMENTS,
    READINESS_READY_WITH_REVIEW,
    is_valid_readiness_label,
)

SCHEMA_VERSION = "nf_readiness_terminology_reconciliation_v1"

# Org-profile / eligibility-fit application_readiness -> canonical readiness_label.
APPLICATION_READINESS_TO_LABEL: dict[str, str] = {
    "incomplete": READINESS_NOT_READY_MISSING_DOCUMENTS,
    "complete": READINESS_READY_WITH_REVIEW,
    "needs_operator_review": READINESS_READY_WITH_REVIEW,
    "ready_for_review": READINESS_READY_WITH_REVIEW,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def canonical_readiness_label(application_readiness: str) -> str:
    key = (application_readiness or "").strip().lower()
    if key not in APPLICATION_READINESS_TO_LABEL:
        raise ValueError(
            f"unknown application_readiness value: {application_readiness!r}"
        )
    label = APPLICATION_READINESS_TO_LABEL[key]
    assert is_valid_readiness_label(label)
    return label


def build_readiness_terminology_reconciliation(
    *,
    application_readiness: str,
) -> dict[str, Any]:
    label = canonical_readiness_label(application_readiness)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "application_readiness_legacy": application_readiness,
            "readiness_label_canonical": label,
            "canonical_field": "readiness_label",
            "legacy_field": "application_readiness",
            "reconciliation_status": "complete",
            "preview_only": True,
        }
    )


def build_terminology_reconciliation_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "application_readiness_to_readiness_label": dict(
                APPLICATION_READINESS_TO_LABEL
            ),
            "canonical_vocabulary": (
                "matching_readiness_readiness_label_vocabulary_service"
            ),
            "reconciliation_status": "complete",
            "preview_only": True,
        }
    )
