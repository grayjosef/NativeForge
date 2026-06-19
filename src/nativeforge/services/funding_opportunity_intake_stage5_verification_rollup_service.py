"""Sprint 180: Stage 5 funding opportunity intake verification rollup."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_stage5_gate_verification_service as gv_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_stage5_verification_rollup_v1"

_COMPONENTS: tuple[tuple[int, str, str], ...] = (
    (167, "field confidence vocabulary", "nf_funding_opportunity_field_confidence_v1"),
    (168, "field provenance contract", "nf_funding_opportunity_field_provenance_v1"),
    (169, "provenance-first opportunity record", "nf_funding_opportunity_record_v1"),
    (170, "missing-data flags", "nf_funding_opportunity_missing_data_flags_v1"),
    (171, "intake status model", "nf_funding_opportunity_intake_status_v1"),
    (172, "fail-closed gates", "nf_funding_opportunity_fail_closed_gate_v1"),
    (173, "operator duplicate detection", "nf_funding_opportunity_operator_duplicate_detection_v1"),
    (174, "synthetic demo fixtures", "nf_funding_opportunity_demo_fixture_corpus_v1"),
    (175, "hardened record assembly", "nf_funding_opportunity_hardened_record_v1"),
    (176, "discovery intake bridge", "nf_funding_opportunity_intake_discovery_bridge_v1"),
    (177, "confidence rollup", "nf_funding_opportunity_confidence_rollup_v1"),
    (178, "operator review queue metadata", "nf_funding_opportunity_operator_review_queue_v1"),
    (179, "stage5 gate verification", "nf_funding_opportunity_stage5_gate_verification_v1"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_stage5_verification_rollup() -> dict[str, Any]:
    gate_report = gv_svc.verify_stage5_gates_on_demo_corpus()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sprint_range": "167-179",
            "components": [
                {"sprint_number": sp, "component": name, "artifact_type": at}
                for sp, name, at in _COMPONENTS
            ],
            "gate_verification": gate_report,
            "synthetic_only": True,
            "no_live_ingestion": True,
            "preview_only": True,
        }
    )
