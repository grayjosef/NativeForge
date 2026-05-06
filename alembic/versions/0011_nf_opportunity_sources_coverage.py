"""Sprint 11: opportunity source coverage metadata on nf_opportunity_sources.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from nativeforge.domain.enums import (
    ExpectedOpportunityFrequency,
    SourceCheckMethod,
    SourcePriorityLevel,
)

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _check_method_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in SourceCheckMethod)
    return f"check_method IN ({vals})"


def _frequency_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in ExpectedOpportunityFrequency)
    return f"expected_opportunity_frequency IN ({vals})"


def _priority_sql() -> str:
    vals = ", ".join(f"'{p.value}'" for p in SourcePriorityLevel)
    return f"priority_level IN ({vals})"


def upgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"

    cols = [
        sa.Column("funding_domains_json", sa.JSON(), nullable=True),
        sa.Column("applicant_types_json", sa.JSON(), nullable=True),
        sa.Column("covered_states_json", sa.JSON(), nullable=True),
        sa.Column("covered_regions_json", sa.JSON(), nullable=True),
        sa.Column("covered_tribal_groups_json", sa.JSON(), nullable=True),
        sa.Column("coverage_notes", sa.Text(), nullable=True),
        sa.Column(
            "check_method",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{SourceCheckMethod.unknown.value}'"),
        ),
        sa.Column(
            "expected_opportunity_frequency",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{ExpectedOpportunityFrequency.unknown.value}'"),
        ),
        sa.Column(
            "priority_level",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{SourcePriorityLevel.medium.value}'"),
        ),
    ]

    if is_sqlite:
        with op.batch_alter_table("nf_opportunity_sources") as batch_op:
            for c in cols:
                batch_op.add_column(c)
            batch_op.create_check_constraint(
                "ck_nf_opportunity_sources_check_method",
                _check_method_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_opportunity_sources_expected_frequency",
                _frequency_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_opportunity_sources_priority_level",
                _priority_sql(),
            )
    else:
        for c in cols:
            op.add_column("nf_opportunity_sources", c)
        op.create_check_constraint(
            "ck_nf_opportunity_sources_check_method",
            "nf_opportunity_sources",
            _check_method_sql(),
        )
        op.create_check_constraint(
            "ck_nf_opportunity_sources_expected_frequency",
            "nf_opportunity_sources",
            _frequency_sql(),
        )
        op.create_check_constraint(
            "ck_nf_opportunity_sources_priority_level",
            "nf_opportunity_sources",
            _priority_sql(),
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"

    constraint_names = (
        "ck_nf_opportunity_sources_priority_level",
        "ck_nf_opportunity_sources_expected_frequency",
        "ck_nf_opportunity_sources_check_method",
    )
    col_names = (
        "priority_level",
        "expected_opportunity_frequency",
        "check_method",
        "coverage_notes",
        "covered_tribal_groups_json",
        "covered_regions_json",
        "covered_states_json",
        "applicant_types_json",
        "funding_domains_json",
    )

    if is_sqlite:
        with op.batch_alter_table("nf_opportunity_sources") as batch_op:
            for cn in constraint_names:
                batch_op.drop_constraint(cn, type_="check")
            for col in col_names:
                batch_op.drop_column(col)
    else:
        for cn in constraint_names:
            op.drop_constraint(cn, "nf_opportunity_sources", type_="check")
        for col in col_names:
            op.drop_column("nf_opportunity_sources", col)
