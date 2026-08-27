"""Alembic 0028: nf_raw_source_payloads (source-response evidence metadata).

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-27

Gate 96. Metadata table only. No production storage claim.

This table stores *references and hashes*, not response bodies. The body lives
in an object store, and as of this migration no object store is configured —
there is no client, no bucket and no credential anywhere in the project. A table
existing is not production storage being live, and nothing here says otherwise.

Deliberately NOT a foreign key to nf_opportunity_sources: `source_id` is the v2
registry's string id (GRANTS-GOV-EXTRACT, DOI-BIA-GRANTS), and none of those 381
rows has been promoted into the DB registry. A FK would make it impossible to
store evidence from a source that has not been promoted yet — which is every
source — and would let a deleted registry row take its evidence with it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_raw_source_payloads"

# Vocabularies, mirrored from raw_payload_evidence_model_service. Kept as SQL
# check constraints so a row that bypasses the service still cannot carry a
# status nobody defined.
REDACTION_STATUSES = ("not_required", "pending", "completed", "failed")
SECRET_SCAN_STATUSES = ("pending", "clean", "findings_blocked", "failed")
PARSER_STATUSES = (
    "not_started",
    "parsed",
    "parse_failed",
    "parser_unavailable",
    "human_review_required",
)
PROMOTION_STATUSES = ("quarantine", "evidence_ready", "rejected", "superseded")
RETENTION_POLICIES = (
    "retain_indefinite",
    "retain_7_days",
    "retain_90_days",
    "retain_1_year",
)


def _in_sql(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # Deterministic: SHA-256(source_id | request_fingerprint | body_hash).
        # Unique, so the same response stored twice is the same row.
        sa.Column("payload_id", sa.String(length=128), nullable=False),
        # The v2 registry's string id. Not a FK — see the module docstring.
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("source_name", sa.String(length=512), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("collector_id", sa.String(length=128), nullable=True),
        # Supplied by the caller, never by the store: a timestamp the store
        # invents describes the store rather than the fetch.
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieval_method", sa.String(length=64), nullable=False),
        sa.Column("request_method", sa.String(length=16), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=512), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        # Headers are hashed, never stored: Authorization and Set-Cookie live
        # in headers.
        sa.Column("response_headers_hash", sa.String(length=64), nullable=True),
        sa.Column("response_body_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body_size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=256), nullable=True),
        # A content-addressed pointer into the body store. Not the body.
        sa.Column("raw_payload_ref", sa.String(length=1024), nullable=False),
        sa.Column("redaction_status", sa.String(length=32), nullable=False),
        sa.Column("secret_scan_status", sa.String(length=32), nullable=False),
        sa.Column("terms_status", sa.String(length=64), nullable=False),
        sa.Column(
            "attribution_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("parser_status", sa.String(length=32), nullable=False),
        sa.Column("promotion_status", sa.String(length=32), nullable=False),
        sa.Column("retention_policy", sa.String(length=32), nullable=False),
        sa.Column(
            "created_from_live_fetch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_from_fixture",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("blocked_reasons_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("payload_id", name="uq_nf_raw_source_payloads_payload_id"),
        # A record cannot claim both provenances. Gate 88 found corpus records
        # whose "recorded" flag described the flag rather than the fetch; this
        # is that failure made unrepresentable at the storage layer.
        sa.CheckConstraint(
            "NOT (created_from_live_fetch AND created_from_fixture)",
            name="ck_nf_raw_source_payloads_provenance_exclusive",
        ),
        sa.CheckConstraint(
            _in_sql("redaction_status", REDACTION_STATUSES),
            name="ck_nf_raw_source_payloads_redaction_status",
        ),
        sa.CheckConstraint(
            _in_sql("secret_scan_status", SECRET_SCAN_STATUSES),
            name="ck_nf_raw_source_payloads_secret_scan_status",
        ),
        sa.CheckConstraint(
            _in_sql("parser_status", PARSER_STATUSES),
            name="ck_nf_raw_source_payloads_parser_status",
        ),
        sa.CheckConstraint(
            _in_sql("promotion_status", PROMOTION_STATUSES),
            name="ck_nf_raw_source_payloads_promotion_status",
        ),
        sa.CheckConstraint(
            _in_sql("retention_policy", RETENTION_POLICIES),
            name="ck_nf_raw_source_payloads_retention_policy",
        ),
        # A promoted row must have a clean scan behind it. Enforced in SQL as
        # well as in the promotion gate, because a row written around the
        # service is exactly the case a database constraint exists for.
        sa.CheckConstraint(
            "promotion_status <> 'evidence_ready' OR secret_scan_status = 'clean'",
            name="ck_nf_raw_source_payloads_promoted_scan_clean",
        ),
    )

    op.create_index(
        "ix_nf_raw_source_payloads_source_id", TABLE, ["source_id"], unique=False
    )
    op.create_index(
        "ix_nf_raw_source_payloads_collector_id", TABLE, ["collector_id"], unique=False
    )
    op.create_index(
        "ix_nf_raw_source_payloads_retrieved_at", TABLE, ["retrieved_at"], unique=False
    )
    op.create_index(
        "ix_nf_raw_source_payloads_response_body_hash",
        TABLE,
        ["response_body_hash"],
        unique=False,
    )
    op.create_index(
        "ix_nf_raw_source_payloads_promotion_status",
        TABLE,
        ["promotion_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_nf_raw_source_payloads_promotion_status", table_name=TABLE)
    op.drop_index("ix_nf_raw_source_payloads_response_body_hash", table_name=TABLE)
    op.drop_index("ix_nf_raw_source_payloads_retrieved_at", table_name=TABLE)
    op.drop_index("ix_nf_raw_source_payloads_collector_id", table_name=TABLE)
    op.drop_index("ix_nf_raw_source_payloads_source_id", table_name=TABLE)
    op.drop_table(TABLE)
