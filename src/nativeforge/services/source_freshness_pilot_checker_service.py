"""Read-only source freshness / staleness pilot (Campaign Block 10).

Fixture-backed by default. Does not pretend network ran if it did not.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.source_freshness_pilot_contract_service import (
    build_source_freshness_record,
    source_freshness_invariant_failures,
)

SCHEMA_VERSION = "nf_source_freshness_pilot_checker_v1"
DEFAULT_FIXTURE = Path("fixtures/source_freshness_pilot/controlled_sources.json")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _deadline_risk(deadline_iso: str | None, *, today: date) -> str:
    d = _parse_iso_date(deadline_iso)
    if d is None:
        return "needs_confirmation"
    days = (d - today).days
    if days < 0:
        return "expired_or_past"
    if days <= 7:
        return "due_within_7_days"
    if days <= 30:
        return "due_within_30_days"
    return "not_imminent"


def _expiration_risk(archive_iso: str | None, *, today: date) -> str:
    d = _parse_iso_date(archive_iso)
    if d is None:
        return "needs_confirmation"
    if d < today:
        return "archived_or_expired"
    if (d - today).days <= 14:
        return "archive_soon"
    return "not_imminent"


def _change_status(row: dict[str, Any]) -> str:
    cur = row.get("content_digest")
    prior = row.get("prior_content_digest")
    if cur is None or prior is None:
        return "unknown"
    if cur == prior:
        return "unchanged"
    return "changed"


def run_fixture_backed_source_checks(
    *,
    fixture_path: Path | None = None,
    reference_today: date | None = None,
) -> dict[str, Any]:
    path = fixture_path or DEFAULT_FIXTURE
    doc = json.loads(path.read_text(encoding="utf-8"))
    today = reference_today or datetime.now(UTC).date()
    records: list[dict[str, Any]] = []
    duplicate_warnings: list[str] = []
    seen_opps: dict[str, str] = {}

    for row in doc.get("sources") or []:
        unsupported = bool(row.get("unsupported"))
        checked_at = row.get("fixture_checked_at")
        if unsupported or row.get("retrieval_status") == "not_checked":
            rec = build_source_freshness_record(
                source_id=str(row["source_id"]),
                source_name=str(row["source_name"]),
                source_layer=str(row["source_layer"]),
                source_type=str(row["source_type"]),
                source_url_or_reference=str(row.get("source_url_or_reference") or ""),
                data_mode="fixture_backed_read_only_pilot",
                read_mode="not_checked",
                freshness_status="unsupported" if unsupported else "not_checked",
                last_checked_at=None,
                retrieval_status="not_checked",
                change_status="unknown",
                known_deadline_risk="needs_confirmation",
                known_expiration_risk="needs_confirmation",
                source_health="unsupported" if unsupported else "not_checked",
                operator_next_check="Do not claim live monitoring; implement approved read-only check first",
                opportunity_ids=list(row.get("opportunity_ids") or []),
                notes=[
                    "fixture_backed_read_only_pilot",
                    "external_live_check_not_run",
                    "SC/portal live monitor not implemented",
                ],
            )
        else:
            layer = str(row.get("source_layer"))
            freshness = (
                "curated_current"
                if row.get("source_type") == "curated_pack"
                else "read_only_checked"
            )
            # Stale if fixture check older than 14 days relative to today
            stale = False
            if checked_at:
                try:
                    checked_day = date.fromisoformat(str(checked_at)[:10])
                    if (today - checked_day).days > 14:
                        stale = True
                        freshness = "stale"
                except ValueError:
                    freshness = "needs_confirmation"

            deadline_risk = _deadline_risk(row.get("deadline_iso"), today=today)
            expiration_risk = _expiration_risk(row.get("archive_iso"), today=today)
            health = "stale" if stale else "healthy"
            if deadline_risk == "expired_or_past":
                health = "needs_confirmation"
            change = _change_status(row)
            rec = build_source_freshness_record(
                source_id=str(row["source_id"]),
                source_name=str(row["source_name"]),
                source_layer=layer,
                source_type=str(row["source_type"]),
                source_url_or_reference=str(row.get("source_url_or_reference") or ""),
                data_mode="fixture_backed_read_only_pilot",
                read_mode="fixture_backed_read_only_pilot",
                freshness_status=freshness,
                last_checked_at=checked_at,
                retrieval_status=str(row.get("retrieval_status") or "success_fixture"),
                change_status=change,
                known_deadline_risk=deadline_risk,
                known_expiration_risk=expiration_risk,
                source_health=health,
                operator_next_check=(
                    "Re-verify deadline and source digest before customer reliance"
                    if deadline_risk
                    in {"due_within_7_days", "due_within_30_days", "expired_or_past"}
                    else "Fixture-backed check only — schedule approved live read-only check when authorized"
                ),
                opportunity_ids=list(row.get("opportunity_ids") or []),
                notes=[
                    "fixture_backed_read_only_pilot",
                    "external_live_check_not_run",
                    f"change_status={change}",
                ],
            )
            if deadline_risk == "expired_or_past":
                rec["notes"].append("opportunity_deadline_past_in_fixture")
            if stale:
                rec["notes"].append("stale_curated_or_fixture_snapshot")

        for oid in rec.get("opportunity_ids") or []:
            if oid in seen_opps:
                duplicate_warnings.append(
                    f"duplicate_opportunity_warning:{oid} in {seen_opps[oid]} and {rec['source_id']}"
                )
            else:
                seen_opps[oid] = rec["source_id"]

        fails = source_freshness_invariant_failures(rec)
        rec["invariant_failures"] = fails
        records.append(rec)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 10,
            "data_mode": "fixture_backed_read_only_pilot",
            "external_live_check_not_run": True,
            "live_ingest_claimed": False,
            "continuous_monitoring_claimed": False,
            "production_activation_claimed": False,
            "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_count": len(records),
            "records": records,
            "duplicate_warnings": duplicate_warnings,
            "reference_today": today.isoformat(),
            "buyer_summary": [
                "Read-only source freshness pilot for controlled sources",
                "Fixture-backed checks only — external live network check not run",
                "Distinguishes curated-current, fixture, unsupported portal monitor",
                "Deadline/staleness risks labeled; opportunities not auto-removed",
                "live_ingest_claimed=false; continuous_monitoring_claimed=false",
            ],
        }
    )


def build_source_freshness_demo_surface(
    *,
    reference_today: date | None = None,
) -> dict[str, Any]:
    pack = run_fixture_backed_source_checks(reference_today=reference_today)
    return _json_safe(
        {
            "schema_version": "nf_source_freshness_pilot_assembler_v1",
            "campaign_block": 10,
            "title": "Source freshness / source health",
            **{k: pack[k] for k in pack if k != "schema_version"},
            "readiness_integration": {
                "feeds_package_readiness": True,
                "feeds_operator_review_queue": True,
                "feeds_opportunity_cards": True,
                "feeds_nofo_extraction_pilot": True,
                "notes": [
                    "Stale or unsupported sources become readiness / review blockers",
                    "Freshness does not prove eligibility",
                    "NOFO extraction pilot remains fixture-controlled even when source is labeled healthy",
                ],
            },
            "what_must_be_verified_before_customer_reliance": [
                "Confirm whether fixture digest still matches latest public source",
                "Confirm deadlines independently",
                "Do not treat fixture-backed freshness as continuous live monitoring",
                "Do not activate sources or claim production ingestion",
            ],
        }
    )


def source_freshness_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "live_ingest_claimed",
        "continuous_monitoring_claimed",
        "production_activation_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("external_live_check_not_run") is not True:
        fails.append("external_live_check_lied")
    if (surface.get("source_count") or 0) < 1:
        fails.append("no_sources")
    for rec in surface.get("records") or []:
        fails.extend(source_freshness_invariant_failures(rec))
    return fails
