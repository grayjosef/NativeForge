"""Sprint 190: per-classification label explanation builder."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.native_relevance_classification_label_explanation_service import (
    get_label_explanation_template,
)

SCHEMA_VERSION = "nf_native_relevance_classification_explanation_builder_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_classification_explanation(
    raw: dict[str, Any],
    *,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = classification or classify_native_relevance(raw)
    label = str(cls["classification_label"])
    template = get_label_explanation_template(label)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": raw.get("fixture_key"),
            "classification_label": label,
            "confidence": cls.get("confidence"),
            "trigger_language": template["trigger_language"],
            "eligible_entity_types": template["eligible_entity_types"],
            "whats_missing": template["whats_missing"],
            "operator_next_check": template["operator_next_check"],
            "human_review_required": cls.get("human_review_required"),
            "human_review_trigger_codes": cls.get("human_review_trigger_codes", []),
            "preview_only": True,
        }
    )
