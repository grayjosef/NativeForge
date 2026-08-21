"""Alembic 0022: nf_evidence_intake_records (local/dev Gate 10).

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-21

Approved environment: local_dev_only. No production/customer data mutation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nf_evidence_intake_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("evidence_intake_id", sa.String(length=64), nullable=False),
        sa.Column("organization_profile_id", sa.String(length=128), nullable=False),
        sa.Column("application_workspace_id", sa.String(length=128), nullable=True),
        sa.Column("pursuit_workspace_id", sa.String(length=128), nullable=True),
        sa.Column("checklist_item_id", sa.String(length=128), nullable=True),
        sa.Column("binder_item_id", sa.String(length=128), nullable=True),
        sa.Column("forms_attachment_map_id", sa.String(length=128), nullable=True),
        sa.Column("package_export_preview_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_label", sa.String(length=512), nullable=False),
        sa.Column("source_context", sa.String(length=256), nullable=True),
        sa.Column("storage_mode", sa.String(length=64), nullable=False),
        sa.Column("storage_reference", sa.String(length=1024), nullable=True),
        sa.Column("hash_or_digest", sa.String(length=128), nullable=True),
        sa.Column("file_name", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "package_unlock_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "upload_persistence_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "persistence_scope",
            sa.String(length=32),
            nullable=False,
            server_default="local_dev_only",
        ),
        sa.Column(
            "customer_data_persistence_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "production_storage_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "evidence_intake_id", name="uq_nf_evidence_intake_records_ei_id"
        ),
        sa.CheckConstraint(
            "storage_mode IN ("
            "'not_supported','planned','fixture_backed','local_dev_only',"
            "'validated_persistent','external_storage_required'"
            ")",
            name="ck_nf_evidence_intake_storage_mode",
        ),
        sa.CheckConstraint(
            "review_status IN ("
            "'not_started','provided','needs_review','approved','rejected',"
            "'needs_more_information','blocked','not_supported','archived'"
            ")",
            name="ck_nf_evidence_intake_review_status",
        ),
        sa.CheckConstraint(
            "persistence_scope IN ('local_dev_only','not_claimed','production_forbidden')",
            name="ck_nf_evidence_intake_persistence_scope",
        ),
    )
    op.create_index(
        "ix_nf_evidence_intake_org_profile",
        "nf_evidence_intake_records",
        ["organization_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_evidence_intake_org_review",
        "nf_evidence_intake_records",
        ["organization_profile_id", "review_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nf_evidence_intake_org_review", table_name="nf_evidence_intake_records"
    )
    op.drop_index(
        "ix_nf_evidence_intake_org_profile", table_name="nf_evidence_intake_records"
    )
    op.drop_table("nf_evidence_intake_records")
