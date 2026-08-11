"""NM/WA operator surfacing offline smoke runner.

Produces a real run_id and per-surface PASS/FAIL/NOT_RUN.
Offline synthetic fixtures only — no network, live ingest, or source activation.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
    demo_artifact_invariant_failures,
)
from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    build_demo_visibility_payload,
    render_demo_html_report,
    render_demo_text_report,
)
from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
    RUN_ID_PREFIX,
    SmokeStatus,
    empty_smoke_result,
    empty_surface_result,
    validate_run_id,
    validate_smoke_result,
)

SCHEMA_VERSION = "nf_nm_wa_smoke_runner_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def generate_smoke_run_id(*, now: datetime | None = None) -> str:
    """Sprint 031: generate a real smoke run_id (not fabricated for PASS)."""
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(4)
    run_id = f"{RUN_ID_PREFIX}{ts}_{suffix}"
    if not validate_run_id(run_id):
        raise RuntimeError(f"generated invalid run_id: {run_id}")
    return run_id


def _set_surface(
    surfaces: dict[str, dict[str, Any]],
    name: str,
    status: SmokeStatus,
    detail: str,
) -> None:
    surfaces[name] = empty_surface_result(name, status=status, detail=detail)


def evaluate_surfaces(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Sprint 032: evaluate each expected smoke surface against demo artifact."""
    surfaces: dict[str, dict[str, Any]] = {}
    fixtures = artifact.get("fixtures") or {}
    cm = artifact.get("classify_match") or {}
    nm_report = artifact.get("nm_operator_report") or {}
    wa_report = artifact.get("wa_operator_report") or {}
    combined = artifact.get("combined_review_queue") or {}
    rows = combined.get("rows") or []
    missing = artifact.get("missing_data_summary") or {}
    next_chk = artifact.get("operator_next_check_summary") or {}
    provenance = artifact.get("provenance_evidence_summary") or {}

    # Fixture visibility
    if fixtures.get("nm_profile_count") == fixtures.get("nm_expected") == 22:
        _set_surface(surfaces, "nm_fixture_visibility", "PASS", "nm_profiles=22")
    else:
        _set_surface(
            surfaces, "nm_fixture_visibility", "FAIL", "nm_fixture_count_mismatch"
        )

    if fixtures.get("wa_profile_count") == fixtures.get("wa_expected") == 29:
        _set_surface(surfaces, "wa_fixture_visibility", "PASS", "wa_profiles=29")
    else:
        _set_surface(
            surfaces, "wa_fixture_visibility", "FAIL", "wa_fixture_count_mismatch"
        )

    # Classify+match outputs
    if (cm.get("nm") or {}).get("profile_count") == 22:
        _set_surface(
            surfaces, "nm_classify_match_outputs", "PASS", "nm_classify_match_rows=22"
        )
    else:
        _set_surface(
            surfaces, "nm_classify_match_outputs", "FAIL", "nm_classify_match_missing"
        )

    if (cm.get("wa") or {}).get("profile_count") == 29:
        _set_surface(
            surfaces, "wa_classify_match_outputs", "PASS", "wa_classify_match_rows=29"
        )
    else:
        _set_surface(
            surfaces, "wa_classify_match_outputs", "FAIL", "wa_classify_match_missing"
        )

    # Operator reports
    if nm_report.get("total_profiles") == 22 and nm_report.get("rows"):
        _set_surface(surfaces, "nm_operator_report", "PASS", "nm_report_rows=22")
    else:
        _set_surface(
            surfaces, "nm_operator_report", "FAIL", "nm_operator_report_missing"
        )

    if wa_report.get("total_profiles") == 29 and wa_report.get("rows"):
        _set_surface(surfaces, "wa_operator_report", "PASS", "wa_report_rows=29")
    else:
        _set_surface(
            surfaces, "wa_operator_report", "FAIL", "wa_operator_report_missing"
        )

    if combined.get("combined_profile_count") == 51 and rows:
        _set_surface(
            surfaces,
            "combined_review_queue_report",
            "PASS",
            "combined_rows=51",
        )
    else:
        _set_surface(
            surfaces,
            "combined_review_queue_report",
            "FAIL",
            "combined_review_queue_missing",
        )

    # Missing data display (must not hide)
    if (
        missing.get("hidden_missing_data") is False
        and "combined_missing_data_count" in missing
    ):
        _set_surface(
            surfaces,
            "missing_data_display",
            "PASS",
            f"missing_rows={missing.get('combined_missing_data_count')}",
        )
    else:
        _set_surface(
            surfaces, "missing_data_display", "FAIL", "missing_data_hidden_or_absent"
        )

    # Human review display
    human = sum(1 for r in rows if r.get("human_review_required"))
    if human == len(rows) and human > 0:
        _set_surface(
            surfaces, "human_review_display", "PASS", f"human_review_rows={human}"
        )
    else:
        _set_surface(
            surfaces, "human_review_display", "FAIL", "human_review_indicator_missing"
        )

    # Operator next-check
    if next_chk.get("rows_with_next_checks") == len(rows) and len(rows) > 0:
        _set_surface(
            surfaces,
            "operator_next_check_display",
            "PASS",
            f"next_check_rows={next_chk.get('rows_with_next_checks')}",
        )
    else:
        _set_surface(
            surfaces,
            "operator_next_check_display",
            "FAIL",
            "operator_next_check_missing",
        )

    # Provenance/evidence
    if (
        provenance.get("notes_visible") is True
        and provenance.get("combined_evidence_provenance_summary") is not None
    ):
        _set_surface(
            surfaces,
            "provenance_evidence_display",
            "PASS",
            "provenance_summary_present",
        )
    else:
        _set_surface(
            surfaces,
            "provenance_evidence_display",
            "FAIL",
            "provenance_summary_missing",
        )

    # Confidence/readiness
    conf = combined.get("combined_confidence_distribution") or {}
    readiness_ok = all(r.get("match_readiness_label") for r in rows)
    if conf and readiness_ok:
        _set_surface(
            surfaces,
            "confidence_readiness_labels",
            "PASS",
            f"confidence_keys={sorted(conf)}",
        )
    else:
        _set_surface(
            surfaces,
            "confidence_readiness_labels",
            "FAIL",
            "confidence_or_readiness_missing",
        )

    # No final eligibility claim
    if (
        artifact.get("final_eligibility_claim_allowed") is False
        and combined.get("final_eligibility_claim_allowed") is False
        and all(r.get("final_eligibility_claim_allowed") is False for r in rows)
    ):
        _set_surface(
            surfaces,
            "no_final_eligibility_claim_behavior",
            "PASS",
            "no_final_claim_across_rows",
        )
    else:
        _set_surface(
            surfaces,
            "no_final_eligibility_claim_behavior",
            "FAIL",
            "final_claim_without_evidence",
        )

    # Broad/partial relevance discoverable
    if rows and all(
        r.get("discoverability") == "visible_in_operator_review" for r in rows
    ):
        _set_surface(
            surfaces,
            "broad_partial_relevance_discoverable_behavior",
            "PASS",
            "all_rows_visible_in_operator_review",
        )
    else:
        _set_surface(
            surfaces,
            "broad_partial_relevance_discoverable_behavior",
            "FAIL",
            "discoverability_regression",
        )

    # Ensure all expected surfaces present
    for name in EXPECTED_SURFACES:
        if name not in surfaces:
            _set_surface(surfaces, name, "FAIL", "surface_not_evaluated")
    return surfaces


def run_nm_wa_operator_surfacing_smoke(
    *,
    run_id: str | None = None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sprint 033: execute offline smoke and return honest result with run_id."""
    rid = run_id or generate_smoke_run_id()
    if not validate_run_id(rid):
        raise ValueError(f"invalid run_id: {rid}")

    art = artifact if artifact is not None else build_demo_artifact()
    invariant_failures = demo_artifact_invariant_failures(art)
    surface_map = evaluate_surfaces(art)

    # Hard stops / forbidden modes
    hard_failures: list[str] = list(invariant_failures)
    if art.get("external_urls_used") is True:
        hard_failures.append("external_url_or_network_dependency")
    if art.get("live_ingestion") is True:
        hard_failures.append("live_ingestion_or_source_activation")
    if art.get("source_activation") is True:
        hard_failures.append("live_ingestion_or_source_activation")

    # Demo visibility layer must also be renderable (malformed artifacts => FAIL)
    text = ""
    html_doc = ""
    try:
        payload = build_demo_visibility_payload(art)
        text = render_demo_text_report(payload)
        html_doc = render_demo_html_report(payload)
        if "NM=22" not in text or "WA=29" not in text:
            hard_failures.append("demo_text_render_failed")
        if "<!DOCTYPE html>" not in html_doc:
            hard_failures.append("demo_html_render_failed")
    except Exception as exc:  # noqa: BLE001 — smoke must report FAIL, not crash
        hard_failures.append(f"demo_visibility_render_error:{type(exc).__name__}")

    for name, status_detail in list(surface_map.items()):
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
            and status_detail["status"] == "FAIL"
        ):
            hard_failures.append(f"hard_stop:{name}")

    surface_list = [surface_map[s] for s in EXPECTED_SURFACES]
    any_fail = any(s["status"] == "FAIL" for s in surface_list) or bool(hard_failures)
    overall: SmokeStatus = "FAIL" if any_fail else "PASS"

    result = empty_smoke_result(run_id=rid, status=overall)
    result["schema_version"] = SCHEMA_VERSION
    result["overall_status"] = overall
    result["not_run_reason"] = None
    result["surfaces"] = surface_list
    result["failures"] = hard_failures
    result["artifact_content_digest"] = art.get("content_digest")
    result["demo_text_chars"] = len(text)
    result["demo_html_chars"] = len(html_doc)
    result["offline_only"] = True
    result["live_ingestion"] = False
    result["source_activation"] = False
    result["external_urls_used"] = False

    validation = validate_smoke_result(result)
    if validation:
        result["overall_status"] = "FAIL"
        result["failures"] = hard_failures + [
            f"result_validation:{v}" for v in validation
        ]
    return _json_safe(result)


def smoke_result_not_run(reason: str) -> dict[str, Any]:
    """Sprint 034: honest NOT_RUN result with required reason (no fabricated run_id)."""
    result = empty_smoke_result(run_id=None, status="NOT_RUN", not_run_reason=reason)
    result["schema_version"] = SCHEMA_VERSION
    return _json_safe(result)
