"""Sprint 46: nf_active_opportunity_sources table (file generation only).

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-08

DDL is authored here; Sprint 46 does not apply this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from nativeforge.domain.enums import SourceHealthStatus

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _source_health_sql() -> str:
    vals = ", ".join(f"'{h.value}'" for h in SourceHealthStatus)
    return f"source_health_status IN ({vals})"


def upgrade() -> None:
    op.create_table(
        "nf_active_opportunity_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=128), nullable=False),
        sa.Column("source_lane", sa.String(length=128), nullable=False),
        sa.Column("source_url_or_search_target", sa.Text(), nullable=True),
        sa.Column(
            "collection_method",
            sa.String(length=128),
            nullable=False,
            server_default=sa.text("'manual_review_only'"),
        ),
        sa.Column(
            "update_frequency",
            sa.String(length=128),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column(
            "freshness_cadence_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "stale_threshold_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consecutive_failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "source_health_status",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text(f"'{SourceHealthStatus.unknown.value}'"),
        ),
        sa.Column(
            "source_status",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'activation_pending'"),
        ),
        sa.Column(
            "dedupe_key_strategy",
            sa.String(length=256),
            nullable=False,
            server_default=sa.text("'pending_operator_assignment'"),
        ),
        sa.Column(
            "provenance_capture_plan",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("native_relevance_basis", sa.Text(), nullable=True),
        sa.Column(
            "broad_eligibility_human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "keyword_only_not_confirmed_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "legal_tos_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("public_access_basis", sa.Text(), nullable=True),
        sa.Column(
            "activation_approval_artifact_id", sa.String(length=512), nullable=True
        ),
        sa.Column("activation_command_id", sa.String(length=512), nullable=True),
        sa.Column("activation_approved_by", sa.String(length=512), nullable=True),
        sa.Column("activation_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activation_notes", sa.Text(), nullable=True),
        sa.Column("rollback_contract_id", sa.String(length=512), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.String(length=512), nullable=True),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            _source_health_sql(),
            name="ck_nf_active_opportunity_sources_source_health_status",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source_name",
            "source_type",
            "source_lane",
            name="uq_nf_active_opportunity_sources_org_name_type_lane",
        ),
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_organization_id",
        "nf_active_opportunity_sources",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_source_status",
        "nf_active_opportunity_sources",
        ["source_status"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_source_health_status",
        "nf_active_opportunity_sources",
        ["source_health_status"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_source_lane",
        "nf_active_opportunity_sources",
        ["source_lane"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_source_type",
        "nf_active_opportunity_sources",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_last_checked_at",
        "nf_active_opportunity_sources",
        ["last_checked_at"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_last_success_at",
        "nf_active_opportunity_sources",
        ["last_success_at"],
        unique=False,
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_rollback_contract_id",
        "nf_active_opportunity_sources",
        ["rollback_contract_id"],
        unique=False,
    )


def downgrade() -> None:
    for ix in (
        "ix_nf_active_opportunity_sources_rollback_contract_id",
        "ix_nf_active_opportunity_sources_last_success_at",
        "ix_nf_active_opportunity_sources_last_checked_at",
        "ix_nf_active_opportunity_sources_source_type",
        "ix_nf_active_opportunity_sources_source_lane",
        "ix_nf_active_opportunity_sources_source_health_status",
        "ix_nf_active_opportunity_sources_source_status",
        "ix_nf_active_opportunity_sources_organization_id",
    ):
        op.drop_index(ix, table_name="nf_active_opportunity_sources")
    op.drop_table("nf_active_opportunity_sources")
