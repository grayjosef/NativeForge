"""Operator surfacing report schema for NM/WA classify+match review visibility.

Advisory/review surface only. Does not change classify+match scoring or eligibility.
Offline synthetic fixtures only — no live ingestion or source activation.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_nm_wa_operator_surfacing_report_schema_v1"

# Required report row fields (Sprint 1 foundation).
OPERATOR_REPORT_REQUIRED_FIELDS: tuple[str, ...] = (
    "profile_id",
    "state_cohort",
    "classification_label",
    "match_readiness_label",
    "discoverability",
    "confidence",
    "missing_data",
    "blockers",
    "operator_next_check",
    "provenance_evidence_notes",
    "human_review_required",
    "final_eligibility_claim_allowed",
)

DISCOVERABILITY_VISIBLE = "visible_in_operator_review"
DISCOVERABILITY_EXPLICITLY_IRRELEVANT = "explicitly_irrelevant_by_evidence"

CONFIDENCE_PUBLIC_INFERRED_LOW = "public_inferred_low"
CONFIDENCE_UNKNOWN = "unknown"

CLASSIFICATION_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
CLASSIFICATION_INCOMPLETE_PROFILE = "incomplete_profile_data"

BLOCK_ADVISORY_ONLY = True
NO_SOURCE_ACTIVATION = True
NO_LIVE_INGESTION = True
NO_FINAL_CLAIM_WITHOUT_EVIDENCE = True


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_report_schema_contract() -> dict[str, Any]:
    """Sprint 001: operator-facing report schema contract."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_fields": list(OPERATOR_REPORT_REQUIRED_FIELDS),
            "advisory_only": BLOCK_ADVISORY_ONLY,
            "final_eligibility_claim_allowed_default": False,
            "no_final_claim_without_evidence": NO_FINAL_CLAIM_WITHOUT_EVIDENCE,
            "live_ingestion": False,
            "source_activation": False,
            "offline_only": True,
            "does_not_alter_classify_match_logic": True,
        }
    )


def empty_operator_report_row(
    *,
    profile_id: str,
    state_cohort: str,
) -> dict[str, Any]:
    """Sprint 002: empty conservative report row template."""
    return _json_safe(
        {
            "profile_id": profile_id,
            "state_cohort": state_cohort,
            "classification_label": CLASSIFICATION_NEEDS_OPERATOR_REVIEW,
            "match_readiness_label": CLASSIFICATION_NEEDS_OPERATOR_REVIEW,
            "discoverability": DISCOVERABILITY_VISIBLE,
            "confidence": CONFIDENCE_PUBLIC_INFERRED_LOW,
            "missing_data": [],
            "blockers": [],
            "operator_next_check": [
                "human_review_classify_match_rows_before_any_claim"
            ],
            "provenance_evidence_notes": [],
            "human_review_required": True,
            "final_eligibility_claim_allowed": False,
        }
    )


def validate_operator_report_row(row: dict[str, Any]) -> list[str]:
    """Sprint 003: validate required fields and hard invariant flags."""
    failures: list[str] = []
    for field in OPERATOR_REPORT_REQUIRED_FIELDS:
        if field not in row:
            failures.append(f"missing_field:{field}")
    if row.get("final_eligibility_claim_allowed") is True:
        failures.append("final_eligibility_claim_not_allowed_without_evidence")
    if row.get("human_review_required") is True and not row.get("operator_next_check"):
        failures.append("operator_next_check_required_when_human_review_required")
    if row.get("discoverability") not in {
        DISCOVERABILITY_VISIBLE,
        DISCOVERABILITY_EXPLICITLY_IRRELEVANT,
        None,
    }:
        # None counted as missing via required fields; invalid strings fail here.
        if "discoverability" in row:
            failures.append("invalid_discoverability")
    return failures
