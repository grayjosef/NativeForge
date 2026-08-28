"""Awarded Grants requirements artifacts (Gate 108I).

Six committed files recording what the contract does and, more usefully, what it
declines to do.

## Output root is not inspection root

`repo_root` chooses where files land. It never influences what is measured:
readiness resolves modules through the import system and looks for the frontend
surface under a separately-named `detect_root`. Gate 101 found writers conflating
the two, so a determinism check ended up describing an empty temp directory.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_awarded_grants_requirements_artifact_v1"

ARTIFACT_DIR = "artifacts/awarded_grants_requirements_contract"

DECLARATION_KEYS: tuple[str, ...] = (
    "awarded_grant_record_contract_available",
    "award_transition_contract_available",
    "requirement_model_available",
    "requirements_calendar_available",
    "proof_audit_contract_available",
    "ready_for_demo_contract",
    "ready_for_operational_awarded_tracking",
    "customer_persistence_live",
    "document_storage_live",
    "requirement_extraction_live",
    "live_source_collection_available",
)

REQUIREMENTS_COLUMNS: tuple[str, ...] = (
    "award_id",
    "requirement_id",
    "requirement_type",
    "requirement_title",
    "requirement_status",
    "due_date",
    "due_date_status",
    "extraction_status",
    "evidence_status",
    "is_active_obligation",
    "assigned_owner",
    "proof_of_submission_status",
    "human_review_required",
)

CALENDAR_COLUMNS: tuple[str, ...] = (
    "award_id",
    "requirement_title",
    "due_date",
    "due_date_status",
    "calendar_placement",
    "placement_reason",
    "is_active_obligation",
    "overdue",
    "due_soon",
    "assigned_owner",
)

TRANSITION_COLUMNS: tuple[str, ...] = (
    "source_opportunity_id",
    "award_id",
    "award_status",
    "requirements_extraction_status",
    "evidence_status",
    "active_obligations_supported",
    "pursuit_history_preserved",
    "source_history_preserved",
    "human_review_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _csv(columns: tuple[str, ...], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _flag(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(bool(value)).lower()


def build_contract_declaration(*, detect_root: Any = None) -> dict[str, Any]:
    """What the contract claims, every key measured by the readiness service."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    readiness = build_awarded_requirements_readiness(detect_root=detect_root)
    declaration = {key: readiness.get(key) for key in DECLARATION_KEYS}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **declaration,
            "projected_vs_active_boundary_available": readiness.get(
                "projected_vs_active_boundary_available"
            ),
            "demo_fixture_available": readiness.get("demo_fixture_available"),
            "ui_available": readiness.get("ui_available"),
            "demo_scope": readiness.get("demo_scope"),
            "missing_operational_components": readiness.get(
                "missing_operational_components"
            ),
            "next_required_actions": readiness.get("next_required_actions"),
            # Constants the whole gate holds.
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "requirements_fabricated": False,
            "deadlines_fabricated": False,
            "proof_fabricated": False,
            "live_fetch_performed": False,
        }
    )


def render_requirements_matrix(fixture: dict[str, Any]) -> str:
    rows = []
    for requirement in fixture.get("requirements") or []:
        rows.append(
            [
                requirement.get("award_id"),
                requirement.get("requirement_id"),
                requirement.get("requirement_type"),
                requirement.get("requirement_title"),
                requirement.get("requirement_status"),
                requirement.get("due_date") or "",
                requirement.get("due_date_status"),
                requirement.get("extraction_status"),
                requirement.get("evidence_status"),
                _flag(requirement.get("is_active_obligation")),
                requirement.get("assigned_owner") or "",
                requirement.get("proof_of_submission_status"),
                _flag(requirement.get("human_review_required")),
            ]
        )
    return _csv(REQUIREMENTS_COLUMNS, rows)


def render_calendar_preview(fixture: dict[str, Any]) -> str:
    rows = []
    for calendar in fixture.get("calendars") or []:
        for item in calendar.get("calendar_items") or []:
            rows.append(
                [
                    calendar.get("award_id"),
                    item.get("requirement_title"),
                    item.get("due_date") or "",
                    item.get("due_date_status"),
                    item.get("calendar_placement"),
                    item.get("placement_reason") or "",
                    _flag(item.get("is_active_obligation")),
                    _flag(item.get("overdue")),
                    _flag(item.get("due_soon")),
                    item.get("assigned_owner") or "",
                ]
            )
    return _csv(CALENDAR_COLUMNS, rows)


def render_transition_matrix(fixture: dict[str, Any]) -> str:
    rows = []
    for award in fixture.get("awards") or []:
        rows.append(
            [
                award.get("source_opportunity_id"),
                award.get("award_id"),
                award.get("award_status"),
                award.get("requirements_extraction_status"),
                award.get("evidence_status"),
                _flag(award.get("active_obligations_supported")),
                _flag(award.get("pursuit_history_preserved")),
                _flag(award.get("source_history_preserved")),
                _flag(award.get("human_review_required")),
            ]
        )
    return _csv(TRANSITION_COLUMNS, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Awarded Grants requirements tracking")
    lines.append("")
    lines.append(
        "A contract over labelled demo fixtures. No award package was read, "
        "nothing was fetched, and no compliance calendar is running for anybody."
    )
    lines.append("")
    lines.append("## What exists")
    lines.append("")
    lines.append("```text")
    for key in (
        "awarded_grant_record_contract_available",
        "award_transition_contract_available",
        "requirement_model_available",
        "requirements_calendar_available",
        "proof_audit_contract_available",
        "projected_vs_active_boundary_available",
        "demo_fixture_available",
        "ready_for_demo_contract",
    ):
        lines.append(f"{key:<46} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## What does not")
    lines.append("")
    lines.append(
        "An operational compliance tracker promises that a missed deadline will "
        "be caught. Nothing below can make that promise yet."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "ready_for_operational_awarded_tracking",
        "ui_available",
        "customer_persistence_live",
        "document_storage_live",
        "requirement_extraction_live",
        "live_source_collection_available",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        lines.append(f"{key:<46} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## Nothing here is invented")
    lines.append("")
    lines.append("```text")
    for key in (
        "requirements_fabricated",
        "deadlines_fabricated",
        "proof_fabricated",
        "live_fetch_performed",
    ):
        lines.append(f"{key:<46} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "A projected burden stays projected, an unreadable document produces no "
        "verified requirement, an unknown due date stays unknown and visible, "
        "and proof of submission exists only where a caller supplied it or a "
        "demo fixture says so on its face."
    )
    lines.append("")
    lines.append("## Next")
    lines.append("")
    for entry in declaration.get("next_required_actions") or []:
        lines.append(f"1. **{entry.get('action')}** — {entry.get('why')}")
    lines.append("")
    return "\n".join(lines)


def write_awarded_requirements_artifacts(
    *, repo_root: Any = None, detect_root: Any = None
) -> dict[str, Any]:
    """Write all six artifacts. Output root only; inspection is by import."""
    from nativeforge.services.awarded_grants_demo_fixture_service import (
        build_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_contract_declaration(detect_root=detect_root)
    fixture = build_demo_fixture_set()

    written: dict[str, Any] = {}

    contract_path = out_dir / "awarded_grants_requirements_contract.json"
    contract_path.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["contract"] = str(contract_path)

    awards_path = out_dir / "awarded_grants_demo_awards.json"
    awards_path.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_awards"] = str(awards_path)

    matrix_path = out_dir / "awarded_grants_requirements_matrix.csv"
    matrix_path.write_text(render_requirements_matrix(fixture), encoding="utf-8")
    written["requirements_matrix"] = str(matrix_path)

    calendar_path = out_dir / "awarded_grants_calendar_preview.csv"
    calendar_path.write_text(render_calendar_preview(fixture), encoding="utf-8")
    written["calendar_preview"] = str(calendar_path)

    transition_path = out_dir / "awarded_grants_transition_matrix.csv"
    transition_path.write_text(render_transition_matrix(fixture), encoding="utf-8")
    written["transition_matrix"] = str(transition_path)

    summary_path = out_dir / "awarded_grants_readiness_summary.md"
    summary_path.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary_path)

    written["declaration"] = declaration
    written["fixture"] = fixture
    return written


def artifact_invariant_failures(declaration: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for key in DECLARATION_KEYS:
        if key not in declaration:
            fails.append(f"declaration_missing_key:{key}")

    for constant in (
        "source_monitoring_live",
        "source_coverage_claimed",
        "requirements_fabricated",
        "deadlines_fabricated",
        "proof_fabricated",
        "live_fetch_performed",
        "live_source_collection_available",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"artifact_claimed:{constant}")

    # Operational readiness may never be declared true here.
    if declaration.get("ready_for_operational_awarded_tracking") is not False:
        fails.append("artifact_claimed_operational_awarded_tracking")

    # A demo claim needs the fixtures behind it.
    if declaration.get("ready_for_demo_contract") and not declaration.get(
        "demo_fixture_available"
    ):
        fails.append("demo_contract_claimed_without_fixtures")

    return fails
