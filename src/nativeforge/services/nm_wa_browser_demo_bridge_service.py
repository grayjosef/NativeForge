"""Read-only bridge from NM/WA offline demo artifacts into frontend/demo runtime.

Preserves missing-data, human-review, next-check, provenance, confidence,
and no-final-claim flags. Offline synthetic only — no live API required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    build_demo_visibility_payload,
    render_demo_html_report,
)

SCHEMA_VERSION = "nf_nm_wa_browser_demo_bridge_v1"

DEFAULT_FRONTEND_JSON = Path("frontend/src/demo/nm_wa_operator_demo.json")
DEFAULT_STATIC_HTML = Path("frontend/public/demo/nm_wa_operator_demo.html")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_browser_demo_bridge_payload(
    *,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sprint 011: frontend-ready bridge payload from offline demo artifact."""
    art = artifact if artifact is not None else build_demo_artifact()
    visibility = build_demo_visibility_payload(art)
    combined = art["combined_review_queue"]
    rows = combined["rows"]

    # Compact row projection for UI (read-only advisory fields only)
    ui_rows = []
    for r in rows:
        ui_rows.append(
            {
                "profile_id": r.get("profile_id"),
                "state_cohort": r.get("state_cohort"),
                "classification_label": r.get("classification_label"),
                "match_readiness_label": r.get("match_readiness_label"),
                "discoverability": r.get("discoverability"),
                "confidence": r.get("confidence"),
                "missing_data": list(r.get("missing_data") or []),
                "blockers": list(r.get("blockers") or []),
                "operator_next_check": list(r.get("operator_next_check") or []),
                "provenance_evidence_notes": list(
                    r.get("provenance_evidence_notes") or []
                ),
                "human_review_required": bool(r.get("human_review_required")),
                "final_eligibility_claim_allowed": bool(
                    r.get("final_eligibility_claim_allowed")
                ),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "NM/WA Operator Surfacing Demo (read-only)",
            "demo_dev_only": True,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "auth_required": False,
            "final_eligibility_claim_allowed": False,
            "prior_offline_smoke_run_id": "nf_os_smoke_20260811T004712Z_9dccb0db",
            "content_digest": art.get("content_digest"),
            "nm_summary": {
                "profile_count": art["fixtures"]["nm_profile_count"],
                "expected": art["fixtures"]["nm_expected"],
                "classify_match_profiles": art["classify_match"]["nm"]["profile_count"],
                "operator_report_rows": art["nm_operator_report"]["total_profiles"],
            },
            "wa_summary": {
                "profile_count": art["fixtures"]["wa_profile_count"],
                "expected": art["fixtures"]["wa_expected"],
                "classify_match_profiles": art["classify_match"]["wa"]["profile_count"],
                "operator_report_rows": art["wa_operator_report"]["total_profiles"],
            },
            "combined_summary": {
                "combined_profile_count": combined["combined_profile_count"],
                "combined_review_needed_count": combined[
                    "combined_review_needed_count"
                ],
                "combined_missing_data_count": combined["combined_missing_data_count"],
                "confidence_distribution": combined["combined_confidence_distribution"],
            },
            "missing_data_summary": art["missing_data_summary"],
            "provenance_evidence_summary": art["provenance_evidence_summary"],
            "operator_next_check_summary": art["operator_next_check_summary"],
            "visibility_sample": visibility.get("sample_rows") or [],
            "rows": ui_rows,
            "ui_flags": {
                "show_activation_controls": False,
                "show_submit_controls": False,
                "advisory_banner": (
                    "Demo/dev only — advisory operator review surface. "
                    "No final eligibility claims. No source activation."
                ),
            },
        }
    )


def bridge_payload_invariant_failures(payload: dict[str, Any]) -> list[str]:
    """Sprint 012: hard invariant checks on bridge payload."""
    failures: list[str] = []
    if payload.get("final_eligibility_claim_allowed") is not False:
        failures.append("final_eligibility_claim_must_be_false")
    if payload.get("missing_data_summary", {}).get("hidden_missing_data") is True:
        failures.append("missing_data_must_not_be_hidden")
    if payload.get("live_ingestion") is True:
        failures.append("live_ingestion_forbidden")
    if payload.get("source_activation") is True:
        failures.append("source_activation_forbidden")
    if payload.get("auth_required") is True:
        failures.append("auth_required_forbidden_for_demo_bridge")
    if payload.get("ui_flags", {}).get("show_activation_controls") is True:
        failures.append("activation_controls_forbidden")
    if payload.get("ui_flags", {}).get("show_submit_controls") is True:
        failures.append("submit_controls_forbidden")

    rows = payload.get("rows") or []
    if not rows:
        failures.append("missing_rows")
    for r in rows:
        if r.get("human_review_required") and not r.get("operator_next_check"):
            failures.append(
                f"missing_next_check:{r.get('state_cohort')}:{r.get('profile_id')}"
            )
        if r.get("final_eligibility_claim_allowed") is True:
            failures.append(
                f"final_claim_allowed:{r.get('state_cohort')}:{r.get('profile_id')}"
            )
        if r.get("discoverability") != "visible_in_operator_review":
            if r.get("missing_data") or r.get("human_review_required"):
                failures.append(
                    f"not_discoverable:{r.get('state_cohort')}:{r.get('profile_id')}"
                )
    return failures


def write_browser_demo_bridge_json(
    path: Path | str | None = None,
    *,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sprint 013: write bridge JSON for frontend static import/fetch."""
    payload = build_browser_demo_bridge_payload(artifact=artifact)
    out = Path(path) if path is not None else DEFAULT_FRONTEND_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def write_browser_demo_static_html(
    path: Path | str | None = None,
    *,
    artifact: dict[str, Any] | None = None,
) -> str:
    """Sprint 014: write static HTML demo page under frontend/public."""
    art = artifact if artifact is not None else build_demo_artifact()
    html_doc = render_demo_html_report(build_demo_visibility_payload(art))
    out = Path(path) if path is not None else DEFAULT_STATIC_HTML
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return html_doc
