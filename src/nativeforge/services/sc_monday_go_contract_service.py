"""Normalize SC Monday curated rows to the GO Monday data contract."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_sc_monday_go_contract_v1"

ROUND_CONFIRMED = "confirmed_current"
ROUND_NEEDS_CONFIRMATION = "needs_confirmation"
ROUND_UNKNOWN = "unknown"

FRESHNESS_CURATED = "curated_snapshot"
FRESHNESS_NEEDS_CONFIRMATION = "needs_confirmation"
FRESHNESS_UNKNOWN = "unknown"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not (row.get("source_url") or row.get("source_reference")):
        missing.append("source_url")
    if not (
        row.get("retrieval_date") or row.get("capture_date") or row.get("captured_at")
    ):
        missing.append("retrieved_at")
    if not (row.get("application_deadline") or row.get("deadline_date")):
        missing.append("deadline_date")
    if not (row.get("eligibility_text") or row.get("eligibility_summary")):
        missing.append("eligibility_summary")
    return missing


def normalize_opportunity_to_go_contract(row: dict[str, Any]) -> dict[str, Any]:
    """Add GO-required aliases without inventing live-ingest claims."""
    out = dict(row)
    gid = str(out.get("grant_id") or out.get("opportunity_id") or "")
    title = str(out.get("opportunity_title") or out.get("title") or gid)
    geo = str(out.get("funding_geography") or "")
    if geo == "south_carolina":
        source_layer = "sc_state"
    elif geo == "federal":
        source_layer = "federal"
    else:
        source_layer = "unknown"

    data_label = str(out.get("data_label") or "fixture_demo")
    confirm = bool(out.get("confirm_active_round"))
    if confirm:
        round_status = ROUND_NEEDS_CONFIRMATION
        freshness = FRESHNESS_NEEDS_CONFIRMATION
    elif data_label == "fixture_demo":
        round_status = ROUND_UNKNOWN
        freshness = FRESHNESS_CURATED
    else:
        round_status = ROUND_UNKNOWN
        freshness = FRESHNESS_UNKNOWN

    deadline_raw = out.get("application_deadline") or out.get("deadline_date")
    if deadline_raw:
        deadline_status = "known"
        deadline_date = str(deadline_raw)
    else:
        deadline_status = "unknown"
        deadline_date = None

    captured = str(
        out.get("capture_date")
        or out.get("captured_at")
        or out.get("retrieval_date")
        or ""
    )
    retrieved = str(
        out.get("retrieval_date")
        or out.get("retrieved_at")
        or out.get("capture_date")
        or ""
    )
    missing = _missing_fields(out)
    needs_review = True  # Monday demo always requires human review
    if missing or round_status != ROUND_CONFIRMED:
        needs_review = True

    next_checks = list(out.get("operator_next_check") or [])
    if not next_checks:
        next_checks = ["Human review required before pursuit decision"]
    if round_status == ROUND_NEEDS_CONFIRMATION:
        next_checks.append("Confirm active funding round with source evidence")
    if "deadline_date" in missing:
        next_checks.append("Confirm deadline before calendar commitment")

    out.update(
        {
            "opportunity_id": gid,
            "title": title,
            "source_layer": source_layer,
            "source_name": str(
                out.get("source_name")
                or out.get("agency")
                or (
                    "SC pilot rules"
                    if out.get("sc_pilot_rule_reference")
                    else "offline corpus"
                )
            ),
            "source_url": out.get("source_url") or out.get("source_reference") or "",
            "source_reference": out.get("source_reference")
            or out.get("source_url")
            or "",
            "captured_at": captured,
            "retrieved_at": retrieved,
            "freshness_label": freshness,
            "data_mode": "curated_current",
            "live_ingest_claimed": False,
            "live_ingestion_claimed": False,
            "live_ingest_not_claimed": True,
            "automated_refresh_claimed": False,
            "source_evidence_note": str(
                out.get("source_evidence_note") or out.get("evidence_notes") or ""
            ),
            "current_round_status": round_status,
            "deadline_status": deadline_status,
            "deadline_date": deadline_date,
            "eligibility_summary": str(
                out.get("eligibility_summary")
                or out.get("eligibility_text")
                or out.get("recognition_requirement")
                or "Needs operator review of eligibility evidence"
            ),
            "native_tribal_eligibility_evidence": str(
                out.get("native_tribal_eligibility_evidence")
                or out.get("recognition_requirement")
                or ("tribal_eligible=true" if out.get("tribal_eligible") else "unknown")
            ),
            "sc_relevance_explanation": (
                "South Carolina state program surfaced for SC Native/tribal orgs"
                if source_layer == "sc_state"
                else "Federal opportunity curated for SC Native/tribal relevance"
            ),
            "federal_relevance_explanation": (
                "Federal program with Native/tribal pathway relevance for SC orgs"
                if source_layer == "federal"
                else ""
            ),
            "missing_fields": missing,
            "needs_operator_review": needs_review,
            "operator_next_check": next_checks,
            "provenance_evidence_notes": list(
                out.get("provenance_evidence_notes")
                or [
                    str(out.get("evidence_notes") or ""),
                    f"data_label={data_label}",
                    "data_mode=curated_current",
                    f"freshness_label={freshness}",
                ]
            ),
            "confidence_label": str(
                out.get("confidence_label")
                or out.get("confidence")
                or "public_inferred_low"
            ),
            "demo_real_isolation_label": "demo_curated_current_not_live_ingest",
        }
    )
    return _json_safe(out)


def go_contract_invariant_failures(row: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    required = [
        "opportunity_id",
        "title",
        "source_layer",
        "source_name",
        "captured_at",
        "retrieved_at",
        "freshness_label",
        "data_mode",
        "source_evidence_note",
        "current_round_status",
        "deadline_status",
        "eligibility_summary",
        "missing_fields",
        "needs_operator_review",
        "operator_next_check",
        "confidence_label",
        "demo_real_isolation_label",
    ]
    for key in required:
        if key not in row:
            fails.append(f"missing_{key}")
    if (
        row.get("live_ingest_claimed") is True
        or row.get("live_ingestion_claimed") is True
    ):
        fails.append("live_ingest_claimed_true")
    if row.get("automated_refresh_claimed") is True:
        fails.append("automated_refresh_claimed_true")
    if row.get("data_mode") != "curated_current":
        fails.append("data_mode_not_curated_current")
    if not row.get("retrieved_at") and not row.get("captured_at"):
        fails.append("missing_dates")
        if not row.get("needs_operator_review"):
            fails.append("missing_dates_must_force_review")
    if row.get("current_round_status") in {ROUND_NEEDS_CONFIRMATION, ROUND_UNKNOWN}:
        if not row.get("needs_operator_review"):
            fails.append("uncertain_round_must_force_review")
    return fails
