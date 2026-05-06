"""Sprint 10: opportunity source registry + Grant Spark discovery metadata.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    FundingInstrument,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceReliabilityRating,
    SparkFreshnessStatus,
)

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _src_type_registry_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OpportunitySourceType)
    return f"source_type IN ({vals})"


def _reliability_sql() -> str:
    vals = ", ".join(f"'{r.value}'" for r in SourceReliabilityRating)
    return f"reliability_rating IN ({vals})"


def _verification_registry_sql() -> str:
    vals = ", ".join(f"'{v.value}'" for v in OpportunityVerificationStatus)
    return f"verification_status IN ({vals})"


def _grant_spark_optional_source_type_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OpportunitySourceType)
    return f"(source_type IS NULL OR source_type IN ({vals}))"


def _grant_spark_optional_freshness_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in SparkFreshnessStatus)
    return f"(freshness_status IS NULL OR freshness_status IN ({vals}))"


def _grant_spark_optional_verification_sql() -> str:
    vals = ", ".join(f"'{v.value}'" for v in OpportunityVerificationStatus)
    return f"(verification_status IS NULL OR verification_status IN ({vals}))"


def _grant_spark_optional_funding_instrument_sql() -> str:
    vals = ", ".join(f"'{i.value}'" for i in FundingInstrument)
    return f"(funding_instrument IS NULL OR funding_instrument IN ({vals}))"


def _sqlite_triggers_opportunity_sources(connection: Connection) -> None:
    table = "nf_opportunity_sources"
    connection.execute(
        text(
            f"""
CREATE TRIGGER trg_{table}_demo_align_ins
BEFORE INSERT ON {table}
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN NEW.organization_id IS NOT NULL AND NEW.is_demo != (
      SELECT CASE WHEN org_type = 'demo' THEN 1 ELSE 0 END
      FROM organizations WHERE id = NEW.organization_id
    )
    THEN RAISE(ABORT, 'nf is_demo does not match organizations.org_type')
  END;
END;
"""
        )
    )
    connection.execute(
        text(
            f"""
CREATE TRIGGER trg_{table}_demo_align_upd
BEFORE UPDATE ON {table}
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN NEW.organization_id IS NOT NULL AND NEW.is_demo != (
      SELECT CASE WHEN org_type = 'demo' THEN 1 ELSE 0 END
      FROM organizations WHERE id = NEW.organization_id
    )
    THEN RAISE(ABORT, 'nf is_demo does not match organizations.org_type')
  END;
END;
"""
        )
    )


def _postgres_function_optional_org(connection: Connection) -> None:
    connection.execute(
        text(
            """
CREATE OR REPLACE FUNCTION nf_check_demo_alignment_optional_org()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.organization_id IS NULL THEN
    RETURN NEW;
  END IF;
  IF NEW.is_demo IS DISTINCT FROM (
    SELECT (org_type = 'demo') FROM organizations WHERE id = NEW.organization_id
  ) THEN
    RAISE EXCEPTION 'nf is_demo/org_type mismatch for %', NEW.organization_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )
    connection.execute(
        text(
            """
DROP TRIGGER IF EXISTS trg_nf_opportunity_sources_demo_align
ON nf_opportunity_sources;
"""
        )
    )
    connection.execute(
        text(
            """
CREATE TRIGGER trg_nf_opportunity_sources_demo_align
BEFORE INSERT OR UPDATE ON nf_opportunity_sources
FOR EACH ROW EXECUTE PROCEDURE nf_check_demo_alignment_optional_org();
"""
        )
    )


def _postgres_rls_opportunity_sources(connection: Connection) -> None:
    connection.execute(
        text("ALTER TABLE nf_opportunity_sources ENABLE ROW LEVEL SECURITY;")
    )
    connection.execute(
        text("ALTER TABLE nf_opportunity_sources FORCE ROW LEVEL SECURITY;")
    )
    connection.execute(
        text(
            """
CREATE POLICY nf_opportunity_sources_org_demo_scope ON nf_opportunity_sources
FOR ALL
USING (
  (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
  OR (
    organization_id IS NULL
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
)
WITH CHECK (
  (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
  OR (
    organization_id IS NULL
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
);
"""
        )
    )


def upgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    op.create_table(
        "nf_opportunity_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("source_name", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("publisher_name", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("geographic_scope_json", sa.JSON(), nullable=True),
        sa.Column("native_relevance_notes", sa.Text(), nullable=True),
        sa.Column(
            "reliability_rating",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("freshness_interval_days", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_successful_check_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "verification_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'unverified'"),
        ),
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
        sa.CheckConstraint(_src_type_registry_sql(), name="ck_nf_opportunity_sources_source_type"),
        sa.CheckConstraint(
            _reliability_sql(),
            name="ck_nf_opportunity_sources_reliability_rating",
        ),
        sa.CheckConstraint(
            _verification_registry_sql(),
            name="ck_nf_opportunity_sources_verification_status",
        ),
    )
    op.create_index(
        "ix_nf_opportunity_sources_organization_id",
        "nf_opportunity_sources",
        ["organization_id"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_triggers_opportunity_sources(connection)
    elif is_pg:
        _postgres_function_optional_org(connection)
        _postgres_rls_opportunity_sources(connection)

    gs_cols = [
        sa.Column(
            "source_registry_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("publisher_name", sa.String(512), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_status", sa.String(32), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=True),
        sa.Column("duplicate_key", sa.String(128), nullable=True),
        sa.Column("duplicate_cluster_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("native_relevance_score", sa.Integer(), nullable=True),
        sa.Column("native_relevance_reasons_json", sa.JSON(), nullable=True),
        sa.Column("eligibility_tags_json", sa.JSON(), nullable=True),
        sa.Column("geographic_scope_json", sa.JSON(), nullable=True),
        sa.Column("funding_instrument", sa.String(32), nullable=True),
        sa.Column("applicant_types_json", sa.JSON(), nullable=True),
    ]

    if is_sqlite:
        with op.batch_alter_table("nf_grant_sparks") as batch_op:
            for c in gs_cols:
                batch_op.add_column(c)
            batch_op.create_foreign_key(
                "fk_nf_grant_sparks_source_registry_id",
                "nf_opportunity_sources",
                ["source_registry_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_nf_grant_sparks_source_registry_id",
                ["source_registry_id"],
            )
            batch_op.create_index(
                "ix_nf_grant_sparks_duplicate_cluster_id",
                ["duplicate_cluster_id"],
            )
            batch_op.create_index(
                "ix_nf_grant_sparks_duplicate_key",
                ["duplicate_key"],
            )
            batch_op.create_check_constraint(
                "ck_nf_grant_sparks_source_type_discovery",
                _grant_spark_optional_source_type_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_grant_sparks_freshness_status",
                _grant_spark_optional_freshness_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_grant_sparks_verification_status_discovery",
                _grant_spark_optional_verification_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_grant_sparks_funding_instrument",
                _grant_spark_optional_funding_instrument_sql(),
            )
    else:
        for c in gs_cols:
            op.add_column("nf_grant_sparks", c)
        op.create_foreign_key(
            "fk_nf_grant_sparks_source_registry_id",
            "nf_grant_sparks",
            "nf_opportunity_sources",
            ["source_registry_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_nf_grant_sparks_source_registry_id",
            "nf_grant_sparks",
            ["source_registry_id"],
            unique=False,
        )
        op.create_index(
            "ix_nf_grant_sparks_duplicate_cluster_id",
            "nf_grant_sparks",
            ["duplicate_cluster_id"],
            unique=False,
        )
        op.create_index(
            "ix_nf_grant_sparks_duplicate_key",
            "nf_grant_sparks",
            ["duplicate_key"],
            unique=False,
        )
        op.create_check_constraint(
            "ck_nf_grant_sparks_source_type_discovery",
            "nf_grant_sparks",
            _grant_spark_optional_source_type_sql(),
        )
        op.create_check_constraint(
            "ck_nf_grant_sparks_freshness_status",
            "nf_grant_sparks",
            _grant_spark_optional_freshness_sql(),
        )
        op.create_check_constraint(
            "ck_nf_grant_sparks_verification_status_discovery",
            "nf_grant_sparks",
            _grant_spark_optional_verification_sql(),
        )
        op.create_check_constraint(
            "ck_nf_grant_sparks_funding_instrument",
            "nf_grant_sparks",
            _grant_spark_optional_funding_instrument_sql(),
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    constraint_names = (
        "ck_nf_grant_sparks_funding_instrument",
        "ck_nf_grant_sparks_verification_status_discovery",
        "ck_nf_grant_sparks_freshness_status",
        "ck_nf_grant_sparks_source_type_discovery",
    )
    index_names = (
        "ix_nf_grant_sparks_duplicate_key",
        "ix_nf_grant_sparks_duplicate_cluster_id",
        "ix_nf_grant_sparks_source_registry_id",
    )
    spark_cols = (
        "applicant_types_json",
        "funding_instrument",
        "geographic_scope_json",
        "eligibility_tags_json",
        "native_relevance_reasons_json",
        "native_relevance_score",
        "duplicate_cluster_id",
        "duplicate_key",
        "verification_status",
        "freshness_status",
        "last_verified_at",
        "discovered_at",
        "publisher_name",
        "source_url",
        "source_type",
        "source_registry_id",
    )

    if is_sqlite:
        with op.batch_alter_table("nf_grant_sparks") as batch_op:
            for cn in constraint_names:
                batch_op.drop_constraint(cn, type_="check")
            for ix in index_names:
                batch_op.drop_index(ix)
            batch_op.drop_constraint(
                "fk_nf_grant_sparks_source_registry_id",
                type_="foreignkey",
            )
            for col in spark_cols:
                batch_op.drop_column(col)
    else:
        for cn in constraint_names:
            op.drop_constraint(cn, "nf_grant_sparks", type_="check")
        for ix in index_names:
            op.drop_index(ix, table_name="nf_grant_sparks")
        op.drop_constraint(
            "fk_nf_grant_sparks_source_registry_id",
            "nf_grant_sparks",
            type_="foreignkey",
        )
        for col in spark_cols:
            op.drop_column("nf_grant_sparks", col)

    if is_sqlite:
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_opportunity_sources_demo_align_upd;")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_opportunity_sources_demo_align_ins;")
        )
    elif is_pg:
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_opportunity_sources_org_demo_scope "
                "ON nf_opportunity_sources;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_opportunity_sources NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text("ALTER TABLE nf_opportunity_sources DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_opportunity_sources_demo_align "
                "ON nf_opportunity_sources;"
            )
        )
        connection.execute(
            text("DROP FUNCTION IF EXISTS nf_check_demo_alignment_optional_org();")
        )

    op.drop_index(
        "ix_nf_opportunity_sources_organization_id",
        table_name="nf_opportunity_sources",
    )
    op.drop_table("nf_opportunity_sources")
