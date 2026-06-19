"""Sprint 175: hardened funding opportunity intake record assembly (offline)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_fail_closed_gate_service as fc_svc,
)
from nativeforge.services import (
    funding_opportunity_intake_missing_data_flags_service as md_svc,
)
from nativeforge.services import (
    funding_opportunity_intake_operator_duplicate_detection_service as dup_svc,
)
from nativeforge.services import (
    funding_opportunity_intake_opportunity_record_service as rec_svc,
)
from nativeforge.services import funding_opportunity_intake_status_service as st_svc

SCHEMA_VERSION = "nf_funding_opportunity_hardened_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_hardened_opportunity_record(
    raw: dict[str, Any],
    *,
    fixture_key: str,
    batch_candidates: list[dict[str, Any]] | None = None,
    operator_approved_duplicate: bool = False,
) -> dict[str, Any]:
    record = rec_svc.build_provenance_first_opportunity_record(
        raw, fixture_key=fixture_key
    )
    missing = md_svc.evaluate_missing_data_flags(record)
    batch = batch_candidates if batch_candidates is not None else [raw]
    dup_det = dup_svc.detect_operator_duplicate_groups(batch)
    if operator_approved_duplicate:
        dup_det = dup_svc.apply_operator_duplicate_approval(
            dup_det, operator_approved=True
        )
    gates = fc_svc.evaluate_fail_closed_gates(
        record,
        duplicate_detected=dup_det["duplicate_collision_count"] > 0,
        operator_approved_duplicate=operator_approved_duplicate,
    )
    status = st_svc.derive_intake_status(
        fail_closed_blocked=gates["fail_closed_blocked"],
        duplicate_pending_operator=dup_det["requires_operator_approval"],
        operator_approved=operator_approved_duplicate and not gates["fail_closed_blocked"],
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_record": record,
            "missing_data_flags": missing,
            "duplicate_detection": dup_det,
            "fail_closed_gates": gates,
            "intake_status": status,
            "preview_only": True,
            "no_live_ingestion": True,
        }
    )
