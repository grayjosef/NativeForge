"""Sprint 54: read-only empty-state read model for ``nf_active_opportunity_sources``.

Aligns application ORM expectations with revision **0019** without creating rows,
activating sources, scraping, ingesting, calling external APIs or LLMs, writing
operator ledger actions, or invoking Alembic.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.services.active_source_runtime_migration_post_apply_verification_service import (
    REQUIRED_COLUMNS,
    TARGET_TABLE as MIGRATION_TARGET_TABLE,
)

ARTIFACT_TYPE = "nf_active_source_empty_state_read_model_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = MIGRATION_TARGET_TABLE

READ_MODEL_STATUS_EMPTY_READY = "empty_state_ready"
READ_MODEL_STATUS_NON_EMPTY = "observed_active_sources_present"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def count_nf_active_opportunity_sources_readonly(
    session: Session,
    *,
    organization_id: uuid.UUID | None = None,
) -> int:
    """Return ``COUNT(*)`` for the active opportunity sources table (read-only)."""
    stmt = select(func.count()).select_from(NfActiveOpportunitySource)
    if organization_id is not None:
        stmt = stmt.where(NfActiveOpportunitySource.organization_id == organization_id)
    return int(session.execute(stmt).scalar_one())


def build_active_source_empty_state_read_model(
    *,
    observed_active_source_count: int,
    organization_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Deterministic read-model artifact (no database IO inside this builder)."""
    n = max(0, int(observed_active_source_count))
    read_model_status = (
        READ_MODEL_STATUS_EMPTY_READY if n == 0 else READ_MODEL_STATUS_NON_EMPTY
    )
    expected_empty_state = n == 0
    org_scope: dict[str, Any] = {
        "organization_id": str(organization_id) if organization_id is not None else None,
        "scope_kind": "organization_scoped" if organization_id is not None else "unspecified",
    }
    orm_cols = {c.name for c in NfActiveOpportunitySource.__table__.columns}
    migration_cols = set(REQUIRED_COLUMNS)
    orm_column_alignment = {
        name: (name in orm_cols) for name in sorted(migration_cols)
    }

    empty_state_message = (
        "Table nf_active_opportunity_sources exists at Alembic revision 0019; "
        "observed active source count is zero; ORM/read-model alignment preserves "
        "the empty-state boundary for Sprint 54."
        if n == 0
        else (
            f"Observed {n} row(s) in nf_active_opportunity_sources; this artifact "
            "remains read-only and does not open row creation, activation, scrape, "
            "ingest, API, LLM, or operator-ledger paths."
        )
    )

    boundary_closed = (
        "closed_read_only_sprint_54_no_side_effects_in_this_module"
    )

    artifact: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "read_model_status": read_model_status,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "orm_model_present": True,
        "orm_table_name": NfActiveOpportunitySource.__tablename__,
        "orm_column_alignment": orm_column_alignment,
        "expected_empty_state": expected_empty_state,
        "observed_active_source_count": n,
        "organization_scope": org_scope,
        "empty_state_message": empty_state_message,
        "next_allowed_step": (
            "author_active_source_creation_request_artifact_next_sprint"
        ),
        "source_row_boundary": boundary_closed,
        "source_activation_boundary": boundary_closed,
        "scrape_boundary": boundary_closed,
        "ingest_boundary": boundary_closed,
        "external_api_boundary": boundary_closed,
        "llm_boundary": boundary_closed,
        "operator_ledger_boundary": boundary_closed,
        "actual_source_row_create_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "actual_schema_change_count_in_sprint_54": 0,
        "actual_alembic_revision_create_count": 0,
        "may_create_source_rows_now": False,
        "may_seed_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
        "may_modify_schema_now": False,
        "may_create_alembic_revision_now": False,
        "sprint_54_execution_proof": {
            "sprint": "54",
            "module_read_only": True,
            "builder_has_no_database_session_parameter": True,
            "count_helper_uses_select_count_only": True,
            "artifact_type": ARTIFACT_TYPE,
        },
    }
    return _json_safe(artifact)


def build_discovery_read_only_active_source_empty_state_attachment(
    *,
    observed_active_source_count: int,
    organization_id: uuid.UUID,
) -> dict[str, Any]:
    """Narrow embedding for ``discovery_source_quality`` (counts supplied by caller)."""
    core = build_active_source_empty_state_read_model(
        observed_active_source_count=observed_active_source_count,
        organization_id=organization_id,
    )
    return _json_safe(
        {
            "read_only_discovery_attachment": True,
            "artifact_type": core["artifact_type"],
            "read_model_status": core["read_model_status"],
            "target_revision_id": core["target_revision_id"],
            "target_table": core["target_table"],
            "observed_active_source_count": core["observed_active_source_count"],
            "expected_empty_state": core["expected_empty_state"],
            "may_create_source_rows_now": core["may_create_source_rows_now"],
            "may_activate_source_now": core["may_activate_source_now"],
        }
    )
