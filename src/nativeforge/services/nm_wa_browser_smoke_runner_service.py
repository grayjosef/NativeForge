"""NM/WA browser/UI demo-runtime smoke runner.

Produces a real run_id for demo-runtime static/Vitest validation.
Playwright e2e remains honestly NOT_RUN (not installed).
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_browser_demo_bridge_payload,
)
from nativeforge.services.nm_wa_browser_demo_contract_service import (
    EXPECTED_SCREENS,
    PLAYWRIGHT_NOT_RUN_REASON,
    RUN_ID_PREFIX,
    BrowserSmokeStatus,
    empty_browser_smoke_result,
    empty_screen_result,
    validate_browser_run_id,
    validate_browser_smoke_result,
)

SCHEMA_VERSION = "nf_nm_wa_browser_smoke_runner_v1"

STATIC_HTML_PATH = Path("frontend/public/demo/nm_wa_operator_demo.html")
PAGE_PATH = Path("frontend/src/pages/NmWaOperatorDemoPage.tsx")
BRIDGE_JSON_PATH = Path("frontend/src/demo/nm_wa_operator_demo.json")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def generate_browser_smoke_run_id(*, now: datetime | None = None) -> str:
    """Sprint 031: generate real browser/demo run_id."""
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{RUN_ID_PREFIX}{ts}_{secrets.token_hex(4)}"
    if not validate_browser_run_id(run_id):
        raise RuntimeError(f"generated invalid browser run_id: {run_id}")
    return run_id


def _set_screen(
    screens: dict[str, dict[str, Any]],
    name: str,
    status: BrowserSmokeStatus,
    detail: str,
) -> None:
    screens[name] = empty_screen_result(name, status=status, detail=detail)


def evaluate_browser_screens(
    payload: dict[str, Any],
    *,
    page_source: str,
    static_html: str,
) -> dict[str, dict[str, Any]]:
    """Sprint 032: evaluate expected UI/demo screens against bridge + UI sources."""
    screens: dict[str, dict[str, Any]] = {}
    nm = payload.get("nm_summary") or {}
    wa = payload.get("wa_summary") or {}
    combined = payload.get("combined_summary") or {}
    rows = payload.get("rows") or []
    missing = payload.get("missing_data_summary") or {}
    next_chk = payload.get("operator_next_check_summary") or {}
    provenance = payload.get("provenance_evidence_summary") or {}

    if (
        nm.get("profile_count") == nm.get("expected") == 22
        and "nm-wa-demo-nm-summary" in page_source
        and ("NM=22" in static_html or "fixtures={" in page_source)
    ):
        _set_screen(screens, "nm_fixture_visibility", "PASS", "nm_fixtures=22")
    else:
        _set_screen(screens, "nm_fixture_visibility", "FAIL", "nm_fixture_missing")

    if (
        wa.get("profile_count") == wa.get("expected") == 29
        and "nm-wa-demo-wa-summary" in page_source
        and ("WA=29" in static_html or "fixtures={" in page_source)
    ):
        _set_screen(screens, "wa_fixture_visibility", "PASS", "wa_fixtures=29")
    else:
        _set_screen(screens, "wa_fixture_visibility", "FAIL", "wa_fixture_missing")

    if nm.get("classify_match_profiles") == 22 and "classify+match=" in page_source:
        _set_screen(screens, "nm_classify_match_outputs", "PASS", "nm_cm=22")
    else:
        _set_screen(screens, "nm_classify_match_outputs", "FAIL", "nm_cm_missing")

    if wa.get("classify_match_profiles") == 29 and "classify+match=" in page_source:
        _set_screen(screens, "wa_classify_match_outputs", "PASS", "wa_cm=29")
    else:
        _set_screen(screens, "wa_classify_match_outputs", "FAIL", "wa_cm_missing")

    if nm.get("operator_report_rows") == 22 and "nm-wa-demo-nm-summary" in page_source:
        _set_screen(screens, "nm_operator_report", "PASS", "nm_report=22")
    else:
        _set_screen(screens, "nm_operator_report", "FAIL", "nm_report_missing")

    if wa.get("operator_report_rows") == 29 and "nm-wa-demo-wa-summary" in page_source:
        _set_screen(screens, "wa_operator_report", "PASS", "wa_report=29")
    else:
        _set_screen(screens, "wa_operator_report", "FAIL", "wa_report_missing")

    if (
        combined.get("combined_profile_count") == 51
        and "nm-wa-demo-combined-summary" in page_source
        and "combined=51" in static_html
    ):
        _set_screen(screens, "combined_review_queue_report", "PASS", "combined=51")
    else:
        _set_screen(screens, "combined_review_queue_report", "FAIL", "combined_missing")

    missing_visible = (
        missing.get("hidden_missing_data") is False
        and "nm-wa-demo-missing-data" in page_source
        and "hidden_missing_data" in page_source
    )
    if missing_visible:
        _set_screen(
            screens,
            "missing_data_display",
            "PASS",
            f"missing_rows={missing.get('combined_missing_data_count')}",
        )
    else:
        _set_screen(screens, "missing_data_display", "FAIL", "missing_data_hidden")

    human = sum(1 for r in rows if r.get("human_review_required"))
    if human == len(rows) == 51 and "human_review_required_count" in page_source:
        _set_screen(screens, "human_review_display", "PASS", f"human_review={human}")
    else:
        _set_screen(screens, "human_review_display", "FAIL", "human_review_missing")

    if (
        next_chk.get("rows_with_next_checks") == 51
        and "nm-wa-demo-next-check" in page_source
    ):
        _set_screen(screens, "operator_next_check_display", "PASS", "next_checks=51")
    else:
        _set_screen(
            screens, "operator_next_check_display", "FAIL", "next_check_missing"
        )

    if (
        provenance.get("notes_visible") is True
        and "nm-wa-demo-provenance" in page_source
    ):
        _set_screen(
            screens, "provenance_evidence_display", "PASS", "provenance_visible"
        )
    else:
        _set_screen(
            screens, "provenance_evidence_display", "FAIL", "provenance_missing"
        )

    conf = combined.get("confidence_distribution") or {}
    if (
        conf
        and "nm-wa-demo-confidence" in page_source
        and all(r.get("match_readiness_label") for r in rows)
    ):
        _set_screen(
            screens,
            "confidence_readiness_labels",
            "PASS",
            f"confidence_keys={sorted(conf)}",
        )
    else:
        _set_screen(
            screens, "confidence_readiness_labels", "FAIL", "confidence_missing"
        )

    if (
        payload.get("final_eligibility_claim_allowed") is False
        and all(r.get("final_eligibility_claim_allowed") is False for r in rows)
        and "final_eligibility_claim_allowed" in page_source
        and (
            "final_eligibility_claim_allowed=False" in static_html
            or "final_eligibility_claim_allowed={String" in page_source
        )
    ):
        _set_screen(
            screens,
            "no_final_eligibility_claim_behavior",
            "PASS",
            "no_final_claim",
        )
    else:
        _set_screen(
            screens,
            "no_final_eligibility_claim_behavior",
            "FAIL",
            "final_claim_present",
        )

    if rows and all(
        r.get("discoverability") == "visible_in_operator_review" for r in rows
    ):
        _set_screen(
            screens,
            "broad_partial_relevance_discoverable_behavior",
            "PASS",
            "all_visible",
        )
    else:
        _set_screen(
            screens,
            "broad_partial_relevance_discoverable_behavior",
            "FAIL",
            "discoverability_regression",
        )

    for name in EXPECTED_SCREENS:
        if name not in screens:
            _set_screen(screens, name, "FAIL", "screen_not_evaluated")
    return screens


def run_nm_wa_browser_demo_smoke(
    *,
    run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sprint 033: execute demo-runtime browser/UI smoke with real run_id."""
    rid = run_id or generate_browser_smoke_run_id()
    if not validate_browser_run_id(rid):
        raise ValueError(f"invalid browser run_id: {rid}")

    pl = payload if payload is not None else build_browser_demo_bridge_payload()
    page_source = PAGE_PATH.read_text(encoding="utf-8") if PAGE_PATH.is_file() else ""
    static_html = (
        STATIC_HTML_PATH.read_text(encoding="utf-8")
        if STATIC_HTML_PATH.is_file()
        else ""
    )
    bridge_json_ok = BRIDGE_JSON_PATH.is_file()

    hard_failures = list(bridge_payload_invariant_failures(pl))
    if not page_source:
        hard_failures.append("missing_demo_page_source")
    if not static_html:
        hard_failures.append("missing_static_html_demo")
    if not bridge_json_ok:
        hard_failures.append("missing_bridge_json")
    if pl.get("external_urls_used") is True:
        hard_failures.append("external_url_or_network_dependency")
    if pl.get("live_ingestion") is True or pl.get("source_activation") is True:
        hard_failures.append("live_ingestion_or_source_activation")
    if pl.get("auth_required") is True:
        hard_failures.append("auth_wall_without_documented_demo_shim")
    if pl.get("ui_flags", {}).get("show_activation_controls") is True:
        hard_failures.append("activation_or_submission_controls")
    if "Activate" in page_source or "Submit to Grants" in page_source:
        hard_failures.append("activation_or_submission_controls")

    screen_map = evaluate_browser_screens(
        pl, page_source=page_source, static_html=static_html
    )
    for name, row in screen_map.items():
        if (
            name
            in {
                "nm_fixture_visibility",
                "wa_fixture_visibility",
                "combined_review_queue_report",
                "human_review_display",
                "operator_next_check_display",
                "missing_data_display",
                "no_final_eligibility_claim_behavior",
            }
            and row["status"] == "FAIL"
        ):
            hard_failures.append(f"hard_stop:{name}")

    screen_list = [screen_map[s] for s in EXPECTED_SCREENS]
    any_fail = any(s["status"] == "FAIL" for s in screen_list) or bool(hard_failures)
    overall: BrowserSmokeStatus = "FAIL" if any_fail else "PASS"

    result = empty_browser_smoke_result(run_id=rid, status=overall)
    result["schema_version"] = SCHEMA_VERSION
    result["overall_status"] = overall
    result["not_run_reason"] = None
    result["smoke_mode"] = "demo_runtime_static_vitest"
    result["playwright_status"] = "NOT_RUN"
    result["playwright_not_run_reason"] = PLAYWRIGHT_NOT_RUN_REASON
    result["screens"] = screen_list
    result["failures"] = hard_failures
    result["bridge_content_digest"] = pl.get("content_digest")
    result["static_html_chars"] = len(static_html)
    result["page_source_chars"] = len(page_source)

    validation = validate_browser_smoke_result(result)
    if validation:
        result["overall_status"] = "FAIL"
        result["failures"] = hard_failures + [
            f"result_validation:{v}" for v in validation
        ]
    return _json_safe(result)


def browser_smoke_result_not_run(reason: str) -> dict[str, Any]:
    """Sprint 034: honest NOT_RUN browser smoke result (no fabricated run_id)."""
    result = empty_browser_smoke_result(
        run_id=None, status="NOT_RUN", not_run_reason=reason
    )
    result["schema_version"] = SCHEMA_VERSION
    return _json_safe(result)
