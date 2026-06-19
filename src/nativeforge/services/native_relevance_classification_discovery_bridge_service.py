"""Sprint 192: bridge native relevance classification preview into discovery intake."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    native_relevance_classification_record_service as nrc_rec_svc,
)

SCHEMA_VERSION = "nf_native_relevance_classification_discovery_bridge_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def attach_classification_preview_to_intake_summary(
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Advisory classification previews; does not change intake acceptance logic."""
    previews: list[dict[str, Any]] = []
    for idx, cand in enumerate(candidates):
        raw = dict(cand) if isinstance(cand, dict) else {}
        fk = str(raw.get("fixture_key") or f"batch_index_{idx}")
        previews.append(nrc_rec_svc.build_native_relevance_classification_record(raw, fixture_key=fk))
    merged = dict(summary)
    merged["native_relevance_classification_preview"] = {
        "schema_version": SCHEMA_VERSION,
        "preview_count": len(previews),
        "previews": previews,
        "advisory_only": True,
    }
    return _json_safe(merged)
