"""Shared NM/WA pilot rollup — offline batch classify+match summary (no live exec)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as NM_EXPECTED,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    fixtures_present as nm_fixtures_present,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as WA_EXPECTED,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    fixtures_present as wa_fixtures_present,
)

SCHEMA_VERSION = "nf_nm_wa_pilot_rollup_v1"

# Conservative readiness — never claim ready without evidence + operator review.
READINESS_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
READINESS_INCOMPLETE_PROFILE = "incomplete_profile_data"
READINESS_NOT_READY = "not_ready_for_final_claim"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nm_wa_pilot_rollup_skeleton() -> dict[str, Any]:
    """Sprint 21: contract skeleton describing NM/WA rollup surface."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "states": ["NM", "WA"],
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "fixtures": {
                "NM": {
                    "present": nm_fixtures_present().get("profiles", False),
                    "expected_profile_count": NM_EXPECTED,
                },
                "WA": {
                    "present": wa_fixtures_present().get("profiles", False),
                    "expected_profile_count": WA_EXPECTED,
                },
            },
            "capabilities": {
                "batch_classify_match_summary": False,
                "conservative_readiness_labels": False,
                "missing_data_reporting": False,
                "provenance_confidence_reporting": False,
            },
        }
    )
