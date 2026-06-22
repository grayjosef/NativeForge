"""Sprint 324: classification labels require supporting source evidence."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
)
from nativeforge.services.native_relevance_classification_overclaim_guard_service import (
    EXPLICIT_SOURCE_EVIDENCE_CODES,
    has_explicit_source_evidence,
)

SCHEMA_VERSION = "nf_classification_evidence_honest_labeling_guard_v1"

_LABEL_EVIDENCE_REQUIREMENTS: dict[str, frozenset[str]] = {
    LABEL_NATIVE_SPECIFIC: frozenset({"tribal_set_aside_in_source", "native_only_mandate_in_source"}),
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC: frozenset(
        {"applicant_types_tribal_in_source", "tribal_eligible_in_source"}
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_classification_evidence_honest(
    classification: dict[str, Any],
    *,
    derived_evidence: list[str],
) -> None:
    """
    Fail-closed: asserted evidence codes must ⊆ derived from source;
    native_specific / tribal_government_specific require matching source proof.
    """
    asserted = set(classification.get("evidence_codes") or [])
    derived = set(derived_evidence)
    invented = asserted - derived
    if invented:
        raise ValueError(
            f"classification evidence invented without source support: {sorted(invented)}"
        )
    label = str(classification.get("classification_label") or "")
    if label == LABEL_NATIVE_SPECIFIC and not has_explicit_source_evidence(
        list(asserted)
    ):
        raise ValueError(
            "native_specific label asserted without explicit source evidence"
        )
    if label == LABEL_TRIBAL_GOVERNMENT_SPECIFIC:
        required = _LABEL_EVIDENCE_REQUIREMENTS[LABEL_TRIBAL_GOVERNMENT_SPECIFIC]
        if not (asserted & required):
            raise ValueError(
                "tribal_government_specific label without tribal source evidence"
            )
    for code in asserted:
        if code not in EXPLICIT_SOURCE_EVIDENCE_CODES and code not in derived:
            raise ValueError(f"unknown or unsupported evidence code: {code!r}")


def build_classification_evidence_honest_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invariant": "no_invented_evidence",
            "unknown_flagged_not_invented": True,
        }
    )
