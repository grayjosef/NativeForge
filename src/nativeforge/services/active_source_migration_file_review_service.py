"""Sprint 46: deterministic review payload for the active source Alembic revision file.

Inspects the on-disk migration under alembic/versions only. Does not apply migrations,
write database rows, activate sources, or touch external systems.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_active_source_migration_file_review_v1"

_TABLE_NAME = "nf_active_opportunity_sources"

_REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "organization_id",
    "source_name",
    "source_type",
    "source_lane",
    "source_url_or_search_target",
    "collection_method",
    "update_frequency",
    "freshness_cadence_days",
    "stale_threshold_days",
    "last_checked_at",
    "last_success_at",
    "last_failure_at",
    "consecutive_failure_count",
    "source_health_status",
    "source_status",
    "dedupe_key_strategy",
    "provenance_capture_plan",
    "native_relevance_basis",
    "broad_eligibility_human_review_required",
    "keyword_only_not_confirmed_eligible",
    "legal_tos_review_required",
    "public_access_basis",
    "activation_approval_artifact_id",
    "activation_command_id",
    "activation_approved_by",
    "activation_approved_at",
    "activation_notes",
    "rollback_contract_id",
    "disabled_at",
    "disabled_by",
    "disabled_reason",
    "created_at",
    "updated_at",
)

_EXPECTED_INDEXES: tuple[str, ...] = (
    "ix_nf_active_opportunity_sources_organization_id",
    "ix_nf_active_opportunity_sources_source_status",
    "ix_nf_active_opportunity_sources_source_health_status",
    "ix_nf_active_opportunity_sources_source_lane",
    "ix_nf_active_opportunity_sources_source_type",
    "ix_nf_active_opportunity_sources_last_checked_at",
    "ix_nf_active_opportunity_sources_last_success_at",
    "ix_nf_active_opportunity_sources_rollback_contract_id",
)

_EXPECTED_CONSTRAINTS: tuple[str, ...] = (
    "uq_nf_active_opportunity_sources_org_name_type_lane",
    "ck_nf_active_opportunity_sources_source_health_status",
)

_RISK_FLAGS: tuple[str, ...] = (
    "migration_file_created_not_applied",
    "future_migration_review_required",
    "future_local_migration_verification_required",
    "no_database_writes_performed",
    "no_actual_activation_performed",
    "no_ingestion_or_scraping_performed",
    "downgrade_review_required",
    "index_constraint_review_required",
    "field_review_required",
    "rollback_path_review_required",
)

_REVIEW_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _versions_dir() -> Path:
    return _repo_root() / "alembic" / "versions"


def _glob_migration_paths(versions_dir: Path) -> list[Path]:
    paths = sorted(versions_dir.glob("*nf_active_opportunity_sources*.py"))
    return [p for p in paths if p.is_file()]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_revision_meta(text: str) -> tuple[str | None, str | None]:
    rev: str | None = None
    down: str | None = None
    m = re.search(
        r"^revision\s*:\s*(?:str\s*)?=\s*[\"']([^\"']+)[\"']",
        text,
        re.MULTILINE,
    )
    if m:
        rev = m.group(1)
    m2 = re.search(
        r"^down_revision\s*:\s*(?:str\s*\|\s*Sequence\[str\]\s*\|\s*None\s*)?=\s*"
        r"(?:[\"']([^\"']+)[\"']|None)",
        text,
        re.MULTILINE,
    )
    if m2 and m2.group(1):
        down = m2.group(1)
    return rev, down


def _has_functions(text: str) -> tuple[bool, bool]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False, False
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    return "upgrade" in names, "downgrade" in names


def _column_names_from_migration(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"sa\.Column\(\s*[\"']([^\"']+)[\"']", text):
        out.append(m.group(1))
    return out


def _index_names_from_migration(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r"op\.create_index\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']"
        f"{re.escape(_TABLE_NAME)}[\"']",
        text,
    ):
        out.append(m.group(1))
    return out


def _constraint_names_from_migration(text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r"name\s*=\s*[\"']([^\"']+)[\"']", text):
        n = m.group(1)
        if n.startswith(
            ("uq_nf_active_opportunity_sources_", "ck_nf_active_opportunity_sources_")
        ):
            names.append(n)
    return sorted(set(names))


def _detected_op_calls(text: str) -> list[str]:
    found = sorted({m.group(1) for m in re.finditer(r"op\.(\w+)\(", text)})
    return found


def _side_effect_scan(text: str) -> dict[str, Any]:
    lower = text.lower()
    bulk = "op.bulk_insert(" in text
    exec_ins = bool(re.search(r"execute\([^)]*insert\s+into", lower))
    plain_ins = "insert(" in lower and (
        "op.insert(" in text or "table.insert(" in lower
    )
    insert_ops = bulk or exec_ins or plain_ins
    update_ops = "op.execute(" in text and "update " in lower
    delete_ops = "op.execute(" in text and "delete " in lower
    seed = "seed" in lower and (
        "seed_" in lower or "fake_" in lower or "fixture" in lower
    )
    ledger = "nf_operator_actions" in text and (
        "insert" in lower or "bulk_insert" in lower
    )
    active_src_ins = _TABLE_NAME in text and (
        "bulk_insert" in text or re.search(r"\.insert\(", text) is not None
    )
    ingest = any(
        tok in lower
        for tok in (
            "ingestion_trigger",
            "start_ingestion",
            "run_ingestion",
            "trigger_ingest",
        )
    )
    scrape = any(
        tok in lower
        for tok in (
            "scrape_trigger",
            "start_scrape",
            "run_scraper",
            "trigger_scrape",
        )
    )
    return {
        "data_seed_detected": seed,
        "insert_operations_detected": insert_ops,
        "update_operations_detected": update_ops,
        "delete_operations_detected": delete_ops,
        "active_source_creation_detected": active_src_ins,
        "operator_ledger_write_detected": ledger,
        "ingestion_trigger_detected": ingest,
        "scraping_trigger_detected": scrape,
    }


def _downgrade_table_targets(text: str) -> list[str]:
    body = text
    m = re.search(r"def downgrade\(\)[^:]*:\s*(.*)$", text, re.DOTALL)
    if m:
        body = m.group(1)
    return re.findall(r"op\.drop_table\(\s*[\"']([^\"']+)[\"']", body)


def _unsafe_ops(text: str) -> list[str]:
    unsafe: list[str] = []
    for tbl in _downgrade_table_targets(text):
        if tbl != _TABLE_NAME:
            unsafe.append(f"drop_table_non_target:{tbl}")
    side = _side_effect_scan(text)
    if side["insert_operations_detected"]:
        unsafe.append("insert_like_operation_in_migration_file")
    if side["operator_ledger_write_detected"]:
        unsafe.append("operator_ledger_touch_in_migration_file")
    return unsafe


def _org_id_from_sq(sq: dict[str, Any] | None) -> str:
    if not isinstance(sq, dict):
        return "unknown"
    scope = sq.get("organization_scope")
    if isinstance(scope, dict):
        oid = scope.get("organization_id") or scope.get("org_id")
        if oid is not None:
            return str(oid)
    return "unknown"


def _posture_from_sq(sq: dict[str, Any] | None) -> str:
    if not isinstance(sq, dict):
        return "unknown"
    return str(sq.get("posture") or "unknown")


def _dq_score_from_sq(sq: dict[str, Any] | None) -> Any:
    if not isinstance(sq, dict):
        return None
    return sq.get("data_quality_score")


def _active_source_count_from_sq(sq: dict[str, Any] | None) -> int:
    if not isinstance(sq, dict):
        return 0
    sc = sq.get("source_counts")
    if isinstance(sc, dict) and isinstance(sc.get("active"), int):
        return int(sc["active"])
    return 0


def build_active_source_migration_file_review(
    discovery_source_quality: dict[str, Any] | None = None,
    *,
    versions_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return nf_active_source_migration_file_review_v1 (JSON-serializable)."""
    vdir = versions_dir if versions_dir is not None else _versions_dir()
    paths = _glob_migration_paths(vdir)
    gen_at = generated_at or datetime.now(tz=UTC)
    org_id = _org_id_from_sq(discovery_source_quality)
    posture = _posture_from_sq(discovery_source_quality)
    dq = _dq_score_from_sq(discovery_source_quality)
    active_n = _active_source_count_from_sq(discovery_source_quality)

    migration_file_count = len(paths)
    expected_count = 1
    unexpected = max(0, migration_file_count - expected_count)
    primary = paths[0] if paths else None
    text = _read_text(primary) if primary else ""
    upgrade_ok, downgrade_ok = _has_functions(text) if primary else (False, False)
    cols = _column_names_from_migration(text) if primary else []
    col_set = set(cols)
    missing_fields = [f for f in _REQUIRED_FIELDS if f not in col_set]
    extra_fields = sorted(col_set.difference(_REQUIRED_FIELDS))
    idxs = _index_names_from_migration(text) if primary else []
    idx_set = set(idxs)
    missing_idx = [i for i in _EXPECTED_INDEXES if i not in idx_set]
    cn = _constraint_names_from_migration(text) if primary else []
    c_set = set(cn)
    missing_c = [c for c in _EXPECTED_CONSTRAINTS if c not in c_set]

    expected_table_present = bool(primary and f'"{_TABLE_NAME}"' in text)
    if primary and not expected_table_present:
        expected_table_present = f"'{_TABLE_NAME}'" in text

    rev_id, down_rev = _parse_revision_meta(text) if primary else (None, None)
    stem = primary.stem if primary else "missing"
    unsafe = _unsafe_ops(text) if primary else ["migration_file_missing"]
    side = (
        _side_effect_scan(text)
        if primary
        else {
            k: False
            for k in (
                "data_seed_detected",
                "insert_operations_detected",
                "update_operations_detected",
                "delete_operations_detected",
                "active_source_creation_detected",
                "operator_ledger_write_detected",
                "ingestion_trigger_detected",
                "scraping_trigger_detected",
            )
        }
    )

    field_status = "complete" if not missing_fields else "incomplete"
    idx_c_status = "complete" if not missing_idx and not missing_c else "needs_review"
    up_rev_st = "passed" if upgrade_ok and expected_table_present else "needs_review"
    dn_rev_st = "passed" if downgrade_ok else "needs_review"
    review_notes: list[str] = []
    if missing_fields:
        review_notes.append("required_field_gap")
    if missing_idx or missing_c:
        review_notes.append("index_or_constraint_gap")
    if unexpected > 0:
        review_notes.append("multiple_migration_files_for_same_table")

    summary = (
        "Active source Alembic revision file is present for inspection; "
        "migration is not applied; counters remain zero; future review "
        "and local verification are required."
    )

    migration_file: dict[str, Any] = {
        "migration_file_status": "created_not_applied",
        "revision_file_path": str(primary.relative_to(_repo_root())) if primary else "",
        "revision_id": rev_id or "",
        "down_revision": down_rev or "",
        "migration_name": stem,
        "table_name": _TABLE_NAME,
        "upgrade_present": upgrade_ok,
        "downgrade_present": downgrade_ok,
        "detected_operations": _detected_op_calls(text) if primary else [],
        "file_boundary": {
            "migration_file_created_now": True,
            "migration_applied_now": False,
            "database_rows_written_now": False,
            "active_sources_created_now": False,
            "may_apply_migration_now": False,
            "requires_future_migration_review_sprint": True,
            "requires_future_local_migration_verification": True,
        },
    }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at.isoformat().replace("+00:00", "Z"),
        },
        "migration_file_review_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dq,
            "active_source_count": active_n,
            "migration_file_count": migration_file_count,
            "expected_migration_file_count": expected_count,
            "unexpected_matching_migration_file_count": unexpected,
            "expected_table_present": expected_table_present,
            "upgrade_function_present": upgrade_ok,
            "downgrade_function_present": downgrade_ok,
            "required_field_count": len(_REQUIRED_FIELDS),
            "detected_required_field_count": len(
                [f for f in _REQUIRED_FIELDS if f in col_set]
            ),
            "missing_required_field_count": len(missing_fields),
            "expected_index_count": len(_EXPECTED_INDEXES),
            "detected_index_count": len(idxs),
            "expected_constraint_count": len(_EXPECTED_CONSTRAINTS),
            "detected_constraint_count": len(cn),
            "actual_migration_apply_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
        },
        "migration_file": migration_file,
        "required_field_review": {
            "expected_fields": list(_REQUIRED_FIELDS),
            "detected_fields": cols,
            "missing_fields": missing_fields,
            "extra_fields": extra_fields,
            "field_review_status": field_status,
        },
        "index_constraint_review": {
            "expected_indexes": list(_EXPECTED_INDEXES),
            "detected_indexes": idxs,
            "missing_indexes": missing_idx,
            "expected_constraints": list(_EXPECTED_CONSTRAINTS),
            "detected_constraints": cn,
            "missing_constraints": missing_c,
            "review_status": idx_c_status,
        },
        "upgrade_downgrade_review": {
            "upgrade_review_status": up_rev_st,
            "downgrade_review_status": dn_rev_st,
            "downgrade_required": True,
            "downgrade_present": downgrade_ok,
            "unsafe_operations_detected": unsafe,
            "review_notes": review_notes,
        },
        "migration_application_boundary": {
            "migration_file_generation_only": True,
            "actual_migration_apply_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
            "may_apply_migration_now": False,
            "may_run_alembic_upgrade_now": False,
            "may_write_database_rows_now": False,
            "may_activate_sources_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_future_review_before_apply": True,
            "requires_future_local_verification": True,
            "should_create_action": False,
        },
        "migration_absence_of_side_effects": side,
        "risk_flags": list(_RISK_FLAGS),
        "summary": summary,
        "recommended_review_interval_days": int(_REVIEW_DAYS.get(posture, 30)),
    }
    return _json_safe(payload)
