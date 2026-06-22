"""Sprint 325: real-grant native relevance classification records."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.classification_evidence_honest_labeling_guard_service import (
    assert_classification_evidence_honest,
)
from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.native_relevance_classification_explanation_builder_service import (
    build_classification_explanation,
)
from nativeforge.services.real_grant_classification_input_adapter_service import (
    adapt_grant_to_classification_input,
    derive_explicit_source_evidence,
)

SCHEMA_VERSION = "nf_real_grant_native_relevance_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_real_grant_native_relevance_record(
    grant: dict[str, Any],
) -> dict[str, Any]:
    """Classify real ingested grant with honest evidence + explanation."""
    raw = adapt_grant_to_classification_input(grant)
    derived = derive_explicit_source_evidence(grant)
    classification = classify_native_relevance(raw)
    classification["evidence_codes"] = derived
    assert_classification_evidence_honest(classification, derived_evidence=derived)
    explanation = build_classification_explanation(raw, classification=classification)
    explanation["trigger_language_source"] = "real_source_text"
    explanation["source_eligibility_excerpt"] = str(grant.get("eligibility_text") or "")[
        :500
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant.get("grant_id"),
            "source_seed_id": grant.get("source_seed_id"),
            "opportunity_number": grant.get("opportunity_number"),
            "opportunity_title": grant.get("opportunity_title"),
            "classification": classification,
            "explanation": explanation,
            "discoverable": classification["discoverable"],
            "human_review_required": classification["human_review_required"],
            "derived_evidence_codes": derived,
            "from_real_source_text": True,
            "real_fetch": grant.get("real_fetch"),
            "honest_labeling": True,
            "synthetic_fixture": False,
        }
    )
