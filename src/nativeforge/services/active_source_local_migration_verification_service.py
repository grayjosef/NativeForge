"""Sprint 47: isolated/local verification artifact for the Sprint 46 Alembic revision.

Verifies ``0019_nf_active_opportunity_sources.py`` via static inspection and (when
requested) a disposable SQLite Alembic cycle. Does not apply migrations to runtime
or developer application databases, activate sources, seed rows, scrape, ingest,
call external services, call LLMs, or write operator ledger actions.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

from nativeforge.lib.settings import get_settings
from nativeforge.services.active_source_migration_file_review_service import (
    _EXPECTED_CONSTRAINTS,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _EXPECTED_INDEXES as _MIGRATION_EXPECTED_INDEXES,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _TABLE_NAME as TARGET_TABLE,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _column_names_from_migration,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _constraint_names_from_migration,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _glob_migration_paths,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _index_names_from_migration,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _parse_revision_meta,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _read_text,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _repo_root,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _versions_dir,
)
from nativeforge.services.active_source_migration_file_review_service import (
    _REQUIRED_FIELDS as EXPECTED_COLUMNS,
)

ARTIFACT_TYPE = "nf_active_source_local_migration_verification_v1"

SOURCE_REVISION_ID = "0019"
SOURCE_DOWN_REVISION_ID = "0018"
MIGRATION_FILE_RELATIVE = "alembic/versions/0019_nf_active_opportunity_sources.py"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _org_id_from_sq(sq: dict[str, Any] | None) -> str:
    if not isinstance(sq, dict):
        return "unknown"
    oid = sq.get("organization_id")
    if oid is not None:
        return str(oid)
    scope = sq.get("organization_scope")
    if isinstance(scope, dict):
        for k in ("organization_id", "org_id"):
            v = scope.get(k)
            if v is not None:
                return str(v)
    return "unknown"


def run_sprint47_isolated_sqlite_verification(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run ``alembic upgrade head`` and ``downgrade 0018`` against a temp SQLite file.

    Temporarily sets ``DATABASE_URL`` for Alembic ``env.py`` (which reads
    :func:`get_settings`) and restores the previous value afterward.

    For explicit local runs and pytest only — not for production/runtime wiring.
    """
    from alembic import command
    from alembic.config import Config

    root = repo_root or _repo_root()
    tmpdir = Path(tempfile.mkdtemp(prefix="nf_sprint47_iso_"))
    dbfile = tmpdir / "verify.sqlite3"
    url = f"sqlite+pysqlite:///{dbfile.as_posix()}"
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()

    proof: dict[str, Any] = {
        "temp_workspace": str(tmpdir),
        "temp_database_path": str(dbfile),
        "database_url_scheme": "sqlite+pysqlite",
        "alembic_upgrade_head_succeeded": False,
        "alembic_downgrade_to_0018_succeeded": False,
        "target_table_present_after_upgrade": False,
        "target_table_absent_after_downgrade": False,
        "nf_active_opportunity_sources_row_count_after_upgrade": None,
        "observed_column_names_after_upgrade": [],
        "observed_index_names_after_upgrade": [],
        "observed_unique_constraint_names_after_upgrade": [],
        "observed_check_constraint_names_after_upgrade": [],
        "check_constraint_inspection_supported": False,
        "table_names_before_downgrade": [],
        "tables_removed_by_downgrade": [],
        "downgrade_only_removed_target_table": False,
        "error": None,
    }

    tables_before: set[str] = set()
    try:
        cfg = Config(str(root / "alembic.ini"))
        command.upgrade(cfg, "head")
        proof["alembic_upgrade_head_succeeded"] = True

        eng = create_engine(url)
        with eng.connect() as conn:
            insp = inspect(conn)
            tables_before = set(insp.get_table_names())
            proof["table_names_before_downgrade"] = sorted(tables_before)
            proof["target_table_present_after_upgrade"] = TARGET_TABLE in tables_before
            if TARGET_TABLE in tables_before:
                cols = {c["name"] for c in insp.get_columns(TARGET_TABLE)}
                proof["observed_column_names_after_upgrade"] = sorted(cols)
                rc = conn.execute(
                    text(f"SELECT COUNT(*) AS n FROM {TARGET_TABLE}")
                ).one()
                proof["nf_active_opportunity_sources_row_count_after_upgrade"] = int(
                    rc[0]
                )
                idx_rows = insp.get_indexes(TARGET_TABLE)
                proof["observed_index_names_after_upgrade"] = sorted(
                    {str(i["name"]) for i in idx_rows if i.get("name")}
                )
                ucs = insp.get_unique_constraints(TARGET_TABLE)
                proof["observed_unique_constraint_names_after_upgrade"] = sorted(
                    {str(u["name"]) for u in ucs if u.get("name")}
                )
                try:
                    chks = insp.get_check_constraints(TARGET_TABLE)
                    proof["check_constraint_inspection_supported"] = True
                    proof["observed_check_constraint_names_after_upgrade"] = sorted(
                        {str(c["name"]) for c in chks if c.get("name")}
                    )
                except Exception:
                    proof["check_constraint_inspection_supported"] = False

        command.downgrade(cfg, SOURCE_DOWN_REVISION_ID)
        proof["alembic_downgrade_to_0018_succeeded"] = True

        eng2 = create_engine(url)
        with eng2.connect() as conn:
            insp2 = inspect(conn)
            tables_after = set(insp2.get_table_names())
        proof["target_table_absent_after_downgrade"] = TARGET_TABLE not in tables_after
        removed = tables_before - tables_after
        proof["tables_removed_by_downgrade"] = sorted(removed)
        proof["downgrade_only_removed_target_table"] = removed == {TARGET_TABLE}
    except Exception as exc:
        proof["error"] = repr(exc)
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev
        get_settings.cache_clear()
        shutil.rmtree(tmpdir, ignore_errors=True)

    return proof


def build_active_source_local_migration_verification(
    discovery_source_quality: dict[str, Any] | None = None,
    *,
    versions_dir: Path | None = None,
    repo_root: Path | None = None,
    generated_at: datetime | None = None,
    isolated_sqlite_proof: dict[str, Any] | None = None,
    verification_scope_override: str | None = None,
) -> dict[str, Any]:
    """Return ``nf_active_source_local_migration_verification_v1`` (JSON-serializable).

    When ``isolated_sqlite_proof`` is omitted (normal discovery embedding), static
    file inspection is populated and isolated SQLite fields indicate that the
    disposable-database cycle was not executed in this request path.
    """
    gen_at = generated_at or datetime.now(tz=UTC)
    vdir = versions_dir if versions_dir is not None else _versions_dir()
    root = repo_root or _repo_root()
    paths = _glob_migration_paths(vdir)
    primary = paths[0] if paths else None
    text = _read_text(primary) if primary else ""

    rev_id, down_rev = _parse_revision_meta(text) if primary else (None, None)
    chain_ok = (
        rev_id == SOURCE_REVISION_ID and down_rev == SOURCE_DOWN_REVISION_ID
    )
    revision_chain_check: dict[str, Any] = {
        "check_status": "passed" if chain_ok else "failed",
        "expected_revision": SOURCE_REVISION_ID,
        "expected_down_revision": SOURCE_DOWN_REVISION_ID,
        "parsed_revision": rev_id or "",
        "parsed_down_revision": down_rev or "",
    }

    rel_path = (
        str(primary.relative_to(root))
        if primary
        else MIGRATION_FILE_RELATIVE
    )
    migration_file_presence_check: dict[str, Any] = {
        "check_status": "passed" if primary is not None else "failed",
        "migration_file_path": rel_path,
    }

    cols = _column_names_from_migration(text) if primary else []
    col_set = set(cols)
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in col_set]

    expected_columns_check: dict[str, Any] = {
        "check_status": "passed" if not missing_cols else "failed",
        "expected_column_count": len(EXPECTED_COLUMNS),
        "detected_column_count": len(col_set),
        "missing_columns": missing_cols,
        "expected_columns": list(EXPECTED_COLUMNS),
        "detected_columns": cols,
    }

    idxs = _index_names_from_migration(text) if primary else []
    idx_set = set(idxs)
    missing_idx = [i for i in _MIGRATION_EXPECTED_INDEXES if i not in idx_set]

    cn = _constraint_names_from_migration(text) if primary else []
    c_set = set(cn)
    missing_c = [c for c in _EXPECTED_CONSTRAINTS if c not in c_set]

    expected_indexes_check: dict[str, Any] = {
        "check_status": "passed" if not missing_idx else "failed",
        "expected_indexes": list(_MIGRATION_EXPECTED_INDEXES),
        "detected_indexes": idxs,
        "missing_indexes": missing_idx,
    }

    expected_constraints_check: dict[str, Any] = {
        "check_status": "passed" if not missing_c else "failed",
        "expected_constraints": list(_EXPECTED_CONSTRAINTS),
        "detected_constraints": cn,
        "missing_constraints": missing_c,
    }

    scope = verification_scope_override or (
        "isolated_sqlite_injected"
        if isolated_sqlite_proof is not None
        else "static_embed_read_only"
    )

    iso = isolated_sqlite_proof or {}
    iso_err = iso.get("error")
    iso_upgrade_ok = bool(iso.get("alembic_upgrade_head_succeeded"))
    iso_down_ok = bool(iso.get("alembic_downgrade_to_0018_succeeded"))
    row_ct = iso.get("nf_active_opportunity_sources_row_count_after_upgrade")
    seed_ok = row_ct == 0 if row_ct is not None else None

    upgrade_verification: dict[str, Any] = {
        "execution_context": (
            "isolated_temp_sqlite"
            if isolated_sqlite_proof is not None
            else "not_run_embed_path"
        ),
        "check_status": (
            "passed"
            if isolated_sqlite_proof is not None and iso_upgrade_ok and not iso_err
            else ("failed" if isolated_sqlite_proof is not None else "not_executed")
        ),
        "alembic_upgrade_head_succeeded": iso.get("alembic_upgrade_head_succeeded"),
        "notes": (
            None
            if isolated_sqlite_proof is not None
            else (
                "Alembic upgrade was not executed in this read-only embed path; "
                "run isolated_sqlite verification from tests or an explicit local gate."
            )
        ),
    }

    downgrade_verification: dict[str, Any] = {
        "execution_context": upgrade_verification["execution_context"],
        "check_status": (
            "passed"
            if isolated_sqlite_proof is not None and iso_down_ok and not iso_err
            else ("failed" if isolated_sqlite_proof is not None else "not_executed")
        ),
        "alembic_downgrade_to_0018_succeeded": iso.get(
            "alembic_downgrade_to_0018_succeeded"
        ),
        "notes": upgrade_verification["notes"],
    }

    table_presence_after_upgrade: dict[str, Any] = {
        "check_status": (
            "not_measured_embed_path"
            if isolated_sqlite_proof is None
            else ("passed" if iso.get("target_table_present_after_upgrade") else "failed")
        ),
        "target_table": TARGET_TABLE,
        "observed_via_isolated_sqlite": iso.get("target_table_present_after_upgrade"),
    }

    table_absence_after_downgrade: dict[str, Any] = {
        "check_status": (
            "not_measured_embed_path"
            if isolated_sqlite_proof is None
            else (
                "passed" if iso.get("target_table_absent_after_downgrade") else "failed"
            )
        ),
        "target_table": TARGET_TABLE,
        "observed_via_isolated_sqlite": iso.get("target_table_absent_after_downgrade"),
    }

    row_seed_check: dict[str, Any] = {
        "check_status": (
            "not_measured_embed_path"
            if isolated_sqlite_proof is None
            else ("passed" if seed_ok else "failed")
        ),
        "expected_seed_rows": 0,
        "observed_row_count_after_upgrade": row_ct,
        "notes": (
            None
            if isolated_sqlite_proof is not None
            else "Row count not measured in embed path (no disposable DB cycle)."
        ),
    }

    sqlite_idx_ok = True
    sqlite_uc_ok = True
    sqlite_ck_ok = True
    sqlite_ck_note: str | None = None
    if isolated_sqlite_proof is not None and iso_upgrade_ok and not iso_err:
        obs_idx = set(iso.get("observed_index_names_after_upgrade") or [])
        sqlite_idx_ok = all(n in obs_idx for n in _MIGRATION_EXPECTED_INDEXES)
        obs_uc = set(iso.get("observed_unique_constraint_names_after_upgrade") or [])
        sqlite_uc_ok = (
            "uq_nf_active_opportunity_sources_org_name_type_lane" in obs_uc
        )
        if iso.get("check_constraint_inspection_supported"):
            obs_ck = set(iso.get("observed_check_constraint_names_after_upgrade") or [])
            sqlite_ck_ok = (
                "ck_nf_active_opportunity_sources_source_health_status" in obs_ck
            )
        else:
            sqlite_ck_ok = True
            sqlite_ck_note = "sqlite_inspector_check_constraints_unavailable"

    sqlite_shape: dict[str, Any] = {
        "indexes_match_expected": sqlite_idx_ok,
        "unique_constraint_present": sqlite_uc_ok,
        "check_constraint_recognized_or_skipped": sqlite_ck_ok,
        "sqlite_inspection_notes": sqlite_ck_note,
    }

    blockers: list[str] = []
    warnings: list[str] = []
    if not chain_ok:
        blockers.append("revision_chain_mismatch")
    if primary is None:
        blockers.append("migration_file_missing")
    if missing_cols:
        blockers.append("expected_column_gap")
    if missing_idx:
        blockers.append("expected_index_gap")
    if missing_c:
        blockers.append("expected_constraint_gap")
    if isolated_sqlite_proof is not None:
        if iso_err:
            blockers.append(f"isolated_sqlite_error:{iso_err}")
        if not iso_upgrade_ok:
            blockers.append("isolated_upgrade_failed")
        if not iso_down_ok:
            blockers.append("isolated_downgrade_failed")
        if not iso.get("target_table_present_after_upgrade"):
            blockers.append("table_missing_after_isolated_upgrade")
        if not iso.get("target_table_absent_after_downgrade"):
            blockers.append("table_still_present_after_isolated_downgrade")
        if seed_ok is False:
            blockers.append("unexpected_seed_rows_in_target_table")
        if not iso.get("downgrade_only_removed_target_table"):
            blockers.append("downgrade_removed_unexpected_tables")
        if not sqlite_idx_ok:
            blockers.append("sqlite_index_mismatch_after_upgrade")
        if not sqlite_uc_ok:
            blockers.append("sqlite_unique_constraint_missing_after_upgrade")
        if isolated_sqlite_proof is not None and iso.get(
            "check_constraint_inspection_supported"
        ):
            if not sqlite_ck_ok:
                warnings.append("sqlite_check_constraint_name_mismatch")

    static_ok = (
        chain_ok
        and primary is not None
        and not missing_cols
        and not missing_idx
        and not missing_c
    )
    isolated_ok = (
        isolated_sqlite_proof is not None
        and not iso_err
        and iso_upgrade_ok
        and iso_down_ok
        and iso.get("target_table_present_after_upgrade")
        and iso.get("target_table_absent_after_downgrade")
        and seed_ok is True
        and iso.get("downgrade_only_removed_target_table")
        and sqlite_idx_ok
        and sqlite_uc_ok
        and sqlite_ck_ok
    )

    if isolated_sqlite_proof is None:
        verification_status = "passed_static_embed" if static_ok else "blocked"
    else:
        verification_status = (
            "passed" if static_ok and isolated_ok else "blocked"
        )

    required_human_review = True
    next_allowed_step = (
        "human_approved_runtime_migration_application_sprint"
        if verification_status.startswith("passed")
        else "resolve_sprint_47_blockers"
    )

    rollback_confidence = (
        "high"
        if isolated_sqlite_proof is not None and isolated_ok
        else ("medium" if static_ok else "low")
    )

    org_id = _org_id_from_sq(discovery_source_quality)

    payload: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": ARTIFACT_TYPE,
        "verification_status": verification_status,
        "source_revision_id": SOURCE_REVISION_ID,
        "source_down_revision_id": SOURCE_DOWN_REVISION_ID,
        "migration_file_path": rel_path,
        "target_table": TARGET_TABLE,
        "verification_scope": scope,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at.isoformat().replace("+00:00", "Z"),
        },
        "revision_chain_check": revision_chain_check,
        "migration_file_presence_check": migration_file_presence_check,
        "upgrade_verification": upgrade_verification,
        "downgrade_verification": downgrade_verification,
        "table_presence_after_upgrade": table_presence_after_upgrade,
        "table_absence_after_downgrade": table_absence_after_downgrade,
        "expected_columns_check": expected_columns_check,
        "expected_indexes_check": expected_indexes_check,
        "expected_constraints_check": expected_constraints_check,
        "expected_sqlite_object_observation": sqlite_shape,
        "row_seed_check": row_seed_check,
        "production_apply_boundary": {
            "migration_apply_allowed": False,
            "runtime_database_targeting_allowed": False,
            "may_apply_migration_to_runtime_now": False,
            "notes": "No production/dev app DATABASE_URL migration apply path is opened.",
        },
        "activation_boundary": {
            "may_activate_source_now": False,
            "notes": "Source activation remains closed.",
        },
        "database_write_boundary": {
            "may_create_source_rows_now": False,
            "may_write_runtime_database_now": False,
            "notes": "No runtime database writes are authorized by this artifact.",
        },
        "scrape_boundary": {"may_scrape_now": False},
        "ingest_boundary": {"may_ingest_now": False},
        "external_api_boundary": {"may_call_external_api_now": False},
        "llm_boundary": {"may_call_llm_now": False},
        "operator_ledger_boundary": {"may_create_operator_ledger_actions_now": False},
        "actual_activation_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_runtime_database_write_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "may_activate_source_now": False,
        "may_create_source_rows_now": False,
        "may_apply_migration_to_runtime_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
        "rollback_confidence": rollback_confidence,
        "blockers": blockers,
        "warnings": warnings,
        "required_human_review": required_human_review,
        "next_allowed_step": next_allowed_step,
        "sprint_47_execution_proof": {
            "static_file_inspection_completed": True,
            "isolated_sqlite_cycle_completed": isolated_sqlite_proof is not None,
            "isolated_sqlite_proof_summary": (
                {k: iso[k] for k in iso if k != "error"}
                if isolated_sqlite_proof is not None
                else None
            ),
        },
    }
    return _json_safe(payload)
