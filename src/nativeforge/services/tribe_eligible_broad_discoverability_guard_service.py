"""Sprint 335: guard — tribe-eligible broad grants must not be filtered to irrelevant."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_IRRELEVANT,
)

SCHEMA_VERSION = "nf_tribe_eligible_broad_discoverability_guard_v1"


class TribeEligibleBroadFilteredError(ValueError):
    """Raised when a tribe-eligible broad grant is classified irrelevant."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_tribe_eligible_broad_discoverable(
    *,
    grant_id: str,
    tribe_eligible_broad: bool,
    classification_label: str,
    discoverable: bool,
) -> None:
    """Fail closed when a tribe-eligible broad grant is dropped to irrelevant."""
    if not tribe_eligible_broad:
        return
    if classification_label == LABEL_IRRELEVANT or not discoverable:
        raise TribeEligibleBroadFilteredError(
            f"tribe-eligible broad grant {grant_id!r} filtered to "
            f"{classification_label!r} discoverable={discoverable}"
        )


def apply_tribe_eligible_broad_discoverability_guard(
    *,
    grant_id: str,
    tribe_eligible_broad: bool,
    classification_label: str,
    discoverable: bool,
) -> dict[str, Any]:
    blocked = tribe_eligible_broad and (
        classification_label == LABEL_IRRELEVANT or not discoverable
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant_id,
            "tribe_eligible_broad": tribe_eligible_broad,
            "classification_label": classification_label,
            "discoverable": discoverable,
            "over_filter_caught": blocked,
            "guard_reason": (
                "tribe-eligible broad grant must remain discoverable (not irrelevant)"
                if blocked
                else None
            ),
        }
    )


def build_tribe_eligible_broad_discoverability_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "protected_segment": "tribe_eligible_broad",
            "forbidden_label": LABEL_IRRELEVANT,
            "requires_discoverable": True,
            "preview_only": True,
        }
    )
