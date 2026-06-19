"""Sprint 176: bridge hardened intake preview into discovery intake summaries."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_hardened_record_service as hard_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_intake_discovery_bridge_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def attach_hardened_preview_to_intake_summary(
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Advisory hardened previews; does not change intake acceptance logic."""
    previews: list[dict[str, Any]] = []
    for idx, cand in enumerate(candidates):
        raw = dict(cand) if isinstance(cand, dict) else {}
        fk = str(raw.get("fixture_key") or f"batch_index_{idx}")
        previews.append(
            hard_svc.build_hardened_opportunity_record(
                raw,
                fixture_key=fk,
                batch_candidates=candidates,
            )
        )
    merged = dict(summary)
    merged["funding_opportunity_intake_hardening_preview"] = {
        "schema_version": SCHEMA_VERSION,
        "preview_count": len(previews),
        "previews": previews,
        "advisory_only": True,
    }
    return _json_safe(merged)
