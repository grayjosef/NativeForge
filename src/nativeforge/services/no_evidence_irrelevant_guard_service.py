"""Sprint 342: no-evidence never means irrelevant."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_evidence_quality_service import (
    has_insufficient_eligibility_evidence,
    has_positive_irrelevant_evidence,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_IRRELEVANT,
    LABEL_UNCERTAIN_RELEVANCE,
)
from nativeforge.services.tribal_serving_agency_safety_net_service import (
    apply_tribal_agency_safety_net,
)

SCHEMA_VERSION = "nf_no_evidence_irrelevant_guard_v1"
EVIDENCE_STATUS_INSUFFICIENT_DATA = "insufficient_data"
EVIDENCE_STATUS_SUBSTANTIVE = "substantive"


class NoEvidenceIrrelevantError(ValueError):
    """Raised when insufficient evidence is labeled irrelevant."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def derive_eligibility_evidence_status(grant: dict[str, Any]) -> str:
    if has_insufficient_eligibility_evidence(grant):
        return EVIDENCE_STATUS_INSUFFICIENT_DATA
    return EVIDENCE_STATUS_SUBSTANTIVE


def apply_no_evidence_irrelevant_guard(
    *,
    proposed_label: str,
    grant: dict[str, Any],
) -> dict[str, Any]:
    """Block irrelevant when eligibility evidence is missing, placeholder, or non-positive."""
    insufficient = has_insufficient_eligibility_evidence(grant)
    positive_irrelevant = has_positive_irrelevant_evidence(grant)
    agency_net = apply_tribal_agency_safety_net(
        grant=grant,
        insufficient_evidence=insufficient,
        proposed_label=proposed_label,
    )

    blocked = False
    final_label = proposed_label
    evidence_status = derive_eligibility_evidence_status(grant)

    if proposed_label == LABEL_IRRELEVANT:
        if insufficient or agency_net["safety_net_triggered"] or not positive_irrelevant:
            blocked = True
            final_label = LABEL_UNCERTAIN_RELEVANCE
            evidence_status = EVIDENCE_STATUS_INSUFFICIENT_DATA

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_label": proposed_label,
            "final_label": final_label,
            "no_evidence_blocked": blocked,
            "insufficient_evidence": insufficient,
            "positive_irrelevant_evidence": positive_irrelevant,
            "eligibility_evidence_status": evidence_status,
            "tribal_agency_safety_net": agency_net,
            "guard_reason": (
                "irrelevant requires positive non-tribal source evidence; "
                "missing/placeholder routes to uncertain_relevance"
                if blocked
                else None
            ),
        }
    )


def assert_no_evidence_not_irrelevant(
    *,
    grant_id: str,
    classification_label: str,
    eligibility_evidence_status: str,
) -> None:
    if (
        classification_label == LABEL_IRRELEVANT
        and eligibility_evidence_status == EVIDENCE_STATUS_INSUFFICIENT_DATA
    ):
        raise NoEvidenceIrrelevantError(
            f"grant {grant_id!r} labeled irrelevant with insufficient eligibility evidence"
        )


def build_no_evidence_irrelevant_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "forbidden": "irrelevant_without_positive_evidence",
            "fallback_label": LABEL_UNCERTAIN_RELEVANCE,
            "insufficient_data_status": EVIDENCE_STATUS_INSUFFICIENT_DATA,
            "preview_only": True,
        }
    )
