"""Sprint 187: over-filter guard — broad opportunities stay discoverable."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    DISCOVERABLE_LABELS,
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_IRRELEVANT,
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_UNCERTAIN_RELEVANCE,
    LABEL_WEAK_NATIVE_RELEVANCE,
    is_valid_classification_label,
)

SCHEMA_VERSION = "nf_native_relevance_classification_over_filter_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def label_must_remain_discoverable(label: str) -> bool:
    return label in DISCOVERABLE_LABELS


def apply_over_filter_guard(
    *,
    classification_label: str,
    proposed_discoverable: bool,
) -> dict[str, Any]:
    """Fail-closed: broad-relevant labels cannot be marked non-discoverable."""
    if not is_valid_classification_label(classification_label):
        raise ValueError(f"invalid classification label: {classification_label!r}")

    must_discover = label_must_remain_discoverable(classification_label)
    over_filtered = must_discover and not proposed_discoverable
    final_discoverable = True if must_discover else proposed_discoverable

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "classification_label": classification_label,
            "proposed_discoverable": proposed_discoverable,
            "final_discoverable": final_discoverable,
            "over_filter_blocked": over_filtered,
            "must_remain_discoverable": must_discover,
            "guard_reason": (
                "broad native-relevant labels must stay discoverable"
                if over_filtered
                else None
            ),
        }
    )


def build_over_filter_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "discoverable_labels": sorted(DISCOVERABLE_LABELS),
            "non_discoverable_labels": [LABEL_IRRELEVANT],
            "protected_broad_labels": [
                LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
                LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
                LABEL_WEAK_NATIVE_RELEVANCE,
                LABEL_UNCERTAIN_RELEVANCE,
            ],
            "preview_only": True,
        }
    )
