"""Sprint 191: hardened native relevance classification record assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.native_relevance_classification_explanation_builder_service import (
    build_classification_explanation,
)

SCHEMA_VERSION = "nf_native_relevance_classification_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_native_relevance_classification_record(
    raw: dict[str, Any],
    *,
    fixture_key: str | None = None,
) -> dict[str, Any]:
    fk = fixture_key or str(raw.get("fixture_key") or "unspecified_fixture")
    classification = classify_native_relevance(raw)
    explanation = build_classification_explanation(raw, classification=classification)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fk,
            "classification": classification,
            "explanation": explanation,
            "discoverable": classification["discoverable"],
            "human_review_required": classification["human_review_required"],
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixture": True,
        }
    )
