"""Sprint 173: operator-approved duplicate detection (offline, advisory)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from nativeforge.domain.enums import OpportunitySourceType
from nativeforge.services.opportunity_discovery_service import compute_duplicate_key

SCHEMA_VERSION = "nf_funding_opportunity_operator_duplicate_detection_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _duplicate_key_for_raw(raw: dict[str, Any]) -> str:
    ost = None
    st = raw.get("opportunity_source_type")
    if st:
        try:
            ost = OpportunitySourceType(str(st))
        except ValueError:
            ost = None
    return compute_duplicate_key(
        source_url=raw.get("source_url") or raw.get("url"),
        publisher_name=raw.get("publisher_name"),
        opportunity_number=raw.get("opportunity_number"),
        opportunity_title=raw.get("opportunity_title") or raw.get("title"),
        opportunity_source_type=ost,
    )


def detect_operator_duplicate_groups(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, list[int]] = defaultdict(list)
    for idx, cand in enumerate(candidates):
        raw = dict(cand) if isinstance(cand, dict) else {}
        groups[_duplicate_key_for_raw(raw)].append(idx)

    collisions = [
        {"duplicate_key": k, "batch_indices": v}
        for k, v in sorted(groups.items())
        if len(v) > 1
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "duplicate_collision_count": len(collisions),
            "collision_groups": collisions,
            "requires_operator_approval": bool(collisions),
            "operator_approved_duplicate_resolution": False,
            "advisory_only": True,
        }
    )


def apply_operator_duplicate_approval(
    detection: dict[str, Any],
    *,
    operator_approved: bool,
    operator_note: str = "",
) -> dict[str, Any]:
    out = dict(detection)
    out["operator_approved_duplicate_resolution"] = operator_approved
    out["operator_duplicate_note"] = operator_note
    if operator_approved:
        out["requires_operator_approval"] = False
    return _json_safe(out)
