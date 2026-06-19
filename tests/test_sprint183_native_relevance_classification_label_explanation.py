"""Sprint 183: per-label explanation templates."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_label_explanation_service import (
    SCHEMA_VERSION,
    build_label_explanation_contract,
    get_label_explanation_template,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_NATIVE_SPECIFIC,
)


def test_each_label_has_four_explanation_fields() -> None:
    contract = build_label_explanation_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    for label, template in contract["templates_by_label"].items():
        assert set(template.keys()) == {
            "trigger_language",
            "eligible_entity_types",
            "whats_missing",
            "operator_next_check",
        }, label


def test_native_specific_explanation_requires_source_evidence() -> None:
    template = get_label_explanation_template(LABEL_NATIVE_SPECIFIC)
    assert "explicit source evidence" in template["whats_missing"].lower()
