"""NM/WA browser/UI demo visibility contract.

Honest PASS / FAIL / NOT_RUN only. No fabricated run_ids.
Read-only demo/runtime surfaces over offline synthetic fixtures.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

SCHEMA_VERSION = "nf_nm_wa_browser_demo_contract_v1"

BrowserSmokeStatus = Literal["PASS", "FAIL", "NOT_RUN"]

RUN_ID_PREFIX = "nf_os_browser_"
RUN_ID_PATTERN = re.compile(r"^nf_os_browser_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}$")

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

# Playwright is not a repo dependency; demo-runtime (static/Vitest) is the
# supported unattended path for this block.
PLAYWRIGHT_AVAILABLE = False
PLAYWRIGHT_NOT_RUN_REASON = (
    "Playwright/browser e2e not installed in frontend; "
    "demo-runtime static/Vitest path is the supported unattended smoke mode"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_browser_demo_contract() -> dict[str, Any]:
    """Sprint 001: browser/UI demo visibility contract."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id_prefix": RUN_ID_PREFIX,
            "run_id_pattern": RUN_ID_PATTERN.pattern,
            "expected_screens": list(EXPECTED_SCREENS),
            "valid_statuses": sorted(VALID_STATUSES),
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_allowed": False,
            "auth_changes_allowed": False,
            "fabricated_pass_forbidden": True,
            "fabricated_run_id_forbidden": True,
            "does_not_alter_classify_match_logic": True,
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "playwright_not_run_reason": PLAYWRIGHT_NOT_RUN_REASON,
            "supported_smoke_mode": "demo_runtime_static_vitest",
            "demo_view_query": "view=nm_wa_operator_demo",
            "mode": "offline_synthetic_demo_ui",
        }
    )


def validate_browser_run_id(run_id: str) -> bool:
    """Sprint 002: validate browser/demo run_id format."""
    return bool(RUN_ID_PATTERN.fullmatch(run_id))


def empty_screen_result(
    screen: str,
    *,
    status: BrowserSmokeStatus = "NOT_RUN",
    detail: str = "",
) -> dict[str, Any]:
    """Sprint 003: one screen result row."""
    if screen not in EXPECTED_SCREENS:
        raise ValueError(f"unknown browser demo screen: {screen!r}")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid browser smoke status: {status!r}")
    return _json_safe({"screen": screen, "status": status, "detail": detail})


def empty_browser_smoke_result(
    *,
    run_id: str | None = None,
    status: BrowserSmokeStatus = "NOT_RUN",
    not_run_reason: str | None = None,
) -> dict[str, Any]:
    """Sprint 004: full browser/demo smoke result scaffold."""
    if run_id is not None and not validate_browser_run_id(run_id):
        raise ValueError(f"invalid browser run_id format: {run_id!r}")
    screens = [
        empty_screen_result(s, status="NOT_RUN", detail="not_yet_evaluated")
        for s in EXPECTED_SCREENS
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "overall_status": status,
            "not_run_reason": not_run_reason,
            "smoke_mode": "demo_runtime_static_vitest",
            "playwright_status": "NOT_RUN",
            "playwright_not_run_reason": PLAYWRIGHT_NOT_RUN_REASON,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "auth_changed": False,
            "screens": screens,
            "failures": [],
            "prior_offline_smoke_run_id": "nf_os_smoke_20260811T004712Z_9dccb0db",
        }
    )


def validate_browser_smoke_result(result: dict[str, Any]) -> list[str]:
    """Sprint 005: validate browser smoke honesty invariants."""
    failures: list[str] = []
    if result.get("overall_status") not in VALID_STATUSES:
        failures.append("invalid_overall_status")
    run_id = result.get("run_id")
    if result.get("overall_status") in {"PASS", "FAIL"}:
        if not run_id or not validate_browser_run_id(str(run_id)):
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
