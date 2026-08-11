"""NM/WA operator surfacing smoke/demo validation contract.

Honest PASS / FAIL / NOT_RUN only. No fabricated run_ids.
Offline synthetic fixtures only — no live ingestion or source activation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

SCHEMA_VERSION = "nf_nm_wa_smoke_validation_contract_v1"

SmokeStatus = Literal["PASS", "FAIL", "NOT_RUN"]

RUN_ID_PREFIX = "nf_os_smoke_"
RUN_ID_PATTERN = re.compile(r"^nf_os_smoke_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}$")

EXPECTED_SURFACES: tuple[str, ...] = (
    "nm_fixture_visibility",
    "wa_fixture_visibility",
    "nm_classify_match_outputs",
    "wa_classify_match_outputs",
    "nm_operator_report",
    "wa_operator_report",
    "combined_review_queue_report",
    "missing_data_display",
    "human_review_display",
    "operator_next_check_display",
    "provenance_evidence_display",
    "confidence_readiness_labels",
    "no_final_eligibility_claim_behavior",
    "broad_partial_relevance_discoverable_behavior",
)

VALID_STATUSES: frozenset[str] = frozenset({"PASS", "FAIL", "NOT_RUN"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_smoke_validation_contract() -> dict[str, Any]:
    """Sprint 001: smoke/demo validation contract."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id_prefix": RUN_ID_PREFIX,
            "run_id_pattern": RUN_ID_PATTERN.pattern,
            "expected_surfaces": list(EXPECTED_SURFACES),
            "valid_statuses": sorted(VALID_STATUSES),
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_allowed": False,
            "fabricated_pass_forbidden": True,
            "fabricated_run_id_forbidden": True,
            "does_not_alter_classify_match_logic": True,
            "mode": "offline_synthetic",
        }
    )


def validate_run_id(run_id: str) -> bool:
    """Sprint 002: validate run_id format."""
    return bool(RUN_ID_PATTERN.fullmatch(run_id))


def empty_surface_result(
    surface: str,
    *,
    status: SmokeStatus = "NOT_RUN",
    detail: str = "",
) -> dict[str, Any]:
    """Sprint 003: one surface result row."""
    if surface not in EXPECTED_SURFACES:
        raise ValueError(f"unknown smoke surface: {surface!r}")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid smoke status: {status!r}")
    return _json_safe(
        {
            "surface": surface,
            "status": status,
            "detail": detail,
        }
    )


def empty_smoke_result(
    *,
    run_id: str | None = None,
    status: SmokeStatus = "NOT_RUN",
    not_run_reason: str | None = None,
) -> dict[str, Any]:
    """Sprint 004: full smoke result scaffold."""
    if run_id is not None and not validate_run_id(run_id):
        raise ValueError(f"invalid run_id format: {run_id!r}")
    surfaces = [
        empty_surface_result(s, status="NOT_RUN", detail="not_yet_evaluated")
        for s in EXPECTED_SURFACES
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "overall_status": status,
            "not_run_reason": not_run_reason,
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "surfaces": surfaces,
            "failures": [],
        }
    )


def validate_smoke_result(result: dict[str, Any]) -> list[str]:
    """Sprint 005: validate smoke result honesty invariants."""
    failures: list[str] = []
    if result.get("overall_status") not in VALID_STATUSES:
        failures.append("invalid_overall_status")
    run_id = result.get("run_id")
    if result.get("overall_status") in {"PASS", "FAIL"}:
        if not run_id or not validate_run_id(str(run_id)):
            failures.append("missing_or_invalid_run_id_for_executed_smoke")
    if result.get("overall_status") == "NOT_RUN" and not result.get("not_run_reason"):
        failures.append("not_run_requires_reason")
    surfaces = result.get("surfaces") or []
    seen = {s.get("surface") for s in surfaces if isinstance(s, dict)}
    for expected in EXPECTED_SURFACES:
        if expected not in seen:
            failures.append(f"missing_surface:{expected}")
    for s in surfaces:
        if not isinstance(s, dict):
            failures.append("surface_not_object")
            continue
        if s.get("status") not in VALID_STATUSES:
            failures.append(f"invalid_surface_status:{s.get('surface')}")
    if result.get("external_urls_used") is True:
        failures.append("external_urls_not_allowed")
    if result.get("live_ingestion") is True:
        failures.append("live_ingestion_not_allowed")
    if result.get("source_activation") is True:
        failures.append("source_activation_not_allowed")
    return failures
