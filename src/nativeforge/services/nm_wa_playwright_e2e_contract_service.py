"""NM/WA Playwright E2E smoke contract.

Honest PASS / FAIL / NOT_RUN only. No fabricated run_ids.
Read-only demo route over offline synthetic fixtures.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

SCHEMA_VERSION = "nf_nm_wa_playwright_e2e_contract_v1"

PlaywrightStatus = Literal["PASS", "FAIL", "NOT_RUN"]

RUN_ID_PREFIX = "nf_os_playwright_"
RUN_ID_PATTERN = re.compile(r"^nf_os_playwright_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}$")

EXPECTED_SCREENS: tuple[str, ...] = (
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

DEMO_ROUTE_PATH = "/?view=nm_wa_operator_demo"
PRIOR_DEMO_RUNTIME_RUN_ID = "nf_os_browser_20260811T094927Z_920a291f"
ARTIFACT_DIR_REL = "artifacts/nm_wa_playwright_smoke"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_playwright_e2e_contract() -> dict[str, Any]:
    """Sprint 001: Playwright E2E visibility contract."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id_prefix": RUN_ID_PREFIX,
            "run_id_pattern": RUN_ID_PATTERN.pattern,
            "expected_screens": list(EXPECTED_SCREENS),
            "valid_statuses": sorted(VALID_STATUSES),
            "demo_route_path": DEMO_ROUTE_PATH,
            "artifact_dir": ARTIFACT_DIR_REL,
            "prior_demo_runtime_run_id": PRIOR_DEMO_RUNTIME_RUN_ID,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_allowed": False,
            "auth_changes_allowed": False,
            "fabricated_pass_forbidden": True,
            "fabricated_run_id_forbidden": True,
            "does_not_alter_classify_match_logic": True,
            "smoke_mode": "playwright_e2e",
            "distinguishes_from_demo_runtime": True,
            "uv_lock_must_remain_untouched": True,
        }
    )


def validate_playwright_run_id(run_id: str) -> bool:
    """Sprint 002: validate Playwright run_id format."""
    return bool(RUN_ID_PATTERN.fullmatch(run_id))


def empty_playwright_screen_result(
    screen: str,
    *,
    status: PlaywrightStatus = "NOT_RUN",
    detail: str = "",
) -> dict[str, Any]:
    """Sprint 003: one Playwright screen result row."""
    if screen not in EXPECTED_SCREENS:
        raise ValueError(f"unknown playwright screen: {screen!r}")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid playwright status: {status!r}")
    return _json_safe({"screen": screen, "status": status, "detail": detail})


def empty_playwright_smoke_result(
    *,
    run_id: str | None = None,
    status: PlaywrightStatus = "NOT_RUN",
    not_run_reason: str | None = None,
) -> dict[str, Any]:
    """Sprint 004: full Playwright smoke result scaffold."""
    if run_id is not None and not validate_playwright_run_id(run_id):
        raise ValueError(f"invalid playwright run_id format: {run_id!r}")
    screens = [
        empty_playwright_screen_result(s, status="NOT_RUN", detail="not_yet_evaluated")
        for s in EXPECTED_SCREENS
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "overall_status": status,
            "not_run_reason": not_run_reason,
            "smoke_mode": "playwright_e2e",
            "demo_route_path": DEMO_ROUTE_PATH,
            "prior_demo_runtime_run_id": PRIOR_DEMO_RUNTIME_RUN_ID,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "auth_changed": False,
            "headless": None,
            "screens": screens,
            "failures": [],
            "artifact_paths": [],
        }
    )


def validate_playwright_smoke_result(result: dict[str, Any]) -> list[str]:
    """Sprint 005: validate Playwright smoke honesty invariants."""
    failures: list[str] = []
    if result.get("overall_status") not in VALID_STATUSES:
        failures.append("invalid_overall_status")
    run_id = result.get("run_id")
    if result.get("overall_status") in {"PASS", "FAIL"}:
        if not run_id or not validate_playwright_run_id(str(run_id)):
            failures.append("missing_or_invalid_run_id_for_executed_smoke")
    if result.get("overall_status") == "NOT_RUN" and not result.get("not_run_reason"):
        failures.append("not_run_requires_reason")
    screens = result.get("screens") or []
    seen = {s.get("screen") for s in screens if isinstance(s, dict)}
    for expected in EXPECTED_SCREENS:
        if expected not in seen:
            failures.append(f"missing_screen:{expected}")
    for s in screens:
        if not isinstance(s, dict):
            failures.append("screen_not_object")
            continue
        if s.get("status") not in VALID_STATUSES:
            failures.append(f"invalid_screen_status:{s.get('screen')}")
    if result.get("external_urls_used") is True:
        failures.append("external_urls_not_allowed")
    if result.get("live_ingestion") is True:
        failures.append("live_ingestion_not_allowed")
    if result.get("source_activation") is True:
        failures.append("source_activation_not_allowed")
    if result.get("auth_changed") is True:
        failures.append("auth_changes_not_allowed")
    return failures
