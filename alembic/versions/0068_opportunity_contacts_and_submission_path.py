"""Alembic 0068: who to contact, and where to submit.

NativeForge could tell a customer what a funding opportunity required and
whether they were eligible for it, and then left them to find an email
address by reading a ninety-page notice. The two questions that follow "should
we apply?" - *who do I deal with* and *what exactly do I do next* - had
nowhere to live: `nf_grant_sparks` carries a `url` and nothing else about
contacting anybody or reaching a submission portal.

Two tables, both tenant-scoped, both carrying their evidence.

## Why contacts are rows and not a JSON blob on the opportunity

A notice names several people with different jobs. The program officer who
can explain whether a project is in scope is usually not the person who can
unstick a portal upload, and neither of them decides the award. Flattening
them into one `contact_email` column produces a product that confidently
routes a technical question to a program officer - and the customer only
finds out after the deadline.

Roles are a constrained vocabulary with `unknown` in it, because a notice
that lists an address under no heading has given us an address and not a
role, and guessing is how the flattening happens anyway.

## Why both tables carry provenance, and keep superseded rows

An amendment that moves the submission address from `applications@` to
`grants@` does not delete the first address; it supersedes it. A customer who
already sent something to the old one needs to see that this happened rather
than find the old value silently gone. So rows are marked superseded, never
overwritten, and each carries the document, page and observation date it came
from.

## Why `submission_completeness` is stored rather than derived at read time

Whether a submission path is usable is a judgement over several fields - a
portal URL with no deadline is not the same as a deadline with no portal -
and two surfaces deriving it independently would eventually disagree. It is
written once, by the service that assembled the row, alongside the reasons.

## Tenant scope

Both tables carry `organization_id` and `is_demo`, which is what
`scripts/check_postgres_tenant_isolation.py` looks for: it discovers tenant
tables by the presence of that column rather than from a list, so a table
added without policies fails the coverage gate rather than passing unnoticed.
They get the same two-GUC predicate, with `FORCE`, and `WITH CHECK` as well as
`USING` - `USING` alone would let a tenant insert a row stamped with another
organization's id.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

CONTACTS = "nf_opportunity_contacts"
SUBMISSION = "nf_opportunity_submission_paths"

#: Who a contact is, in the funder's terms rather than ours.
#:
#: `unknown` is first-class and is the default: a notice that prints an email
#: under no heading has told us an address, not a job. Recording it as a
#: program contact would be an invention, and the one thing a customer must be
#: able to rely on is that a role we state is a role the source stated.
CONTACT_ROLES = (
    "program",
    "application_support",
    "grants_management",
    "submission_support",
    "financial",
    "award_decision",
    "general_office",
    "unknown",
)

#: How an application actually reaches the funder.
SUBMISSION_METHODS = (
    "grants_gov",
    "agency_portal",
    "state_portal",
    "foundation_portal",
    "email",
    "mail",
    "invitation_only",
    "other",
    "unknown",
)

#: Whether the path is usable, as a stored judgement rather than a guess made
#: at render time. `review_required` is for genuine contradictions between
#: sources - two different submission addresses, neither superseding the other.
SUBMISSION_COMPLETENESS = ("verified", "partial", "unclear", "review_required")

#: Where a fact came from. A customer-entered address and one read out of the
#: official notice are both useful and must never be confused: only the second
#: can ever become globally canonical.
PROVENANCE_KINDS = ("source_document", "source_page", "customer_provided")


def _check(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{v}'" for v in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    op.create_table(
        CONTACTS,
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("grant_spark_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("office", sa.String(length=512), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        # -- provenance ---------------------------------------------------
        sa.Column("provenance_kind", sa.String(length=32), nullable=False),
        sa.Column("source_document", sa.String(length=512), nullable=True),
        sa.Column("source_section", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        # -- supersession -------------------------------------------------
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("superseded_reason", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_spark_id"], ["nf_grant_sparks.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            _check("role", CONTACT_ROLES), name="ck_nf_opportunity_contacts_role"
        ),
        sa.CheckConstraint(
            _check("provenance_kind", PROVENANCE_KINDS),
            name="ck_nf_opportunity_contacts_provenance",
        ),
        # A contact with no way to reach anybody is not a contact. Extraction
        # that finds a heading and no address should record nothing rather
        # than a row that looks like an answer.
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL "
            "OR website IS NOT NULL OR office IS NOT NULL",
            name="ck_nf_opportunity_contacts_reachable",
        ),
    )

    op.create_table(
        SUBMISSION,
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("grant_spark_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("portal_name", sa.String(length=256), nullable=True),
        sa.Column("submission_url", sa.String(length=2048), nullable=True),
        sa.Column("package_url", sa.String(length=2048), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("recipient_office", sa.String(length=512), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        # Stored as the source wrote it. "11:59 PM ET" is what the notice says
        # and what the customer must work to; converting it to UTC and back
        # loses which clock the funder meant.
        sa.Column("deadline_timezone", sa.String(length=64), nullable=True),
        sa.Column("loi_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_requirements", sa.Text(), nullable=True),
        sa.Column("submission_format", sa.String(length=256), nullable=True),
        sa.Column("submission_instructions", sa.Text(), nullable=True),
        sa.Column("confirmation_method", sa.String(length=256), nullable=True),
        sa.Column("completeness", sa.String(length=32), nullable=False),
        sa.Column("completeness_reasons_json", sa.JSON(), nullable=True),
        # -- provenance ---------------------------------------------------
        sa.Column("provenance_kind", sa.String(length=32), nullable=False),
        sa.Column("source_document", sa.String(length=512), nullable=True),
        sa.Column("source_section", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        # -- supersession -------------------------------------------------
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("superseded_reason", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_spark_id"], ["nf_grant_sparks.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            _check("method", SUBMISSION_METHODS),
            name="ck_nf_submission_paths_method",
        ),
        sa.CheckConstraint(
            _check("completeness", SUBMISSION_COMPLETENESS),
            name="ck_nf_submission_paths_completeness",
        ),
        sa.CheckConstraint(
            _check("provenance_kind", PROVENANCE_KINDS),
            name="ck_nf_submission_paths_provenance",
        ),
        # `verified` is the one state that tells a customer they may rely on
        # this without checking. It requires a route and a date, enforced here
        # rather than only in the service, because the service is one caller
        # and the constraint is every caller.
        sa.CheckConstraint(
            "completeness <> 'verified' OR ("
            " (submission_url IS NOT NULL OR recipient_email IS NOT NULL)"
            " AND deadline_at IS NOT NULL)",
            name="ck_nf_submission_paths_verified_is_complete",
        ),
    )

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite has no RLS; its isolation comes from the demo-alignment
        # triggers earlier migrations install.
        return

    predicate = (
        "(organization_id = current_setting('app.current_org_id', true)::uuid"
        " AND is_demo = current_setting('app.current_org_is_demo', true)::boolean)"
    )
    for table in (CONTACTS, SUBMISSION):
        policy = f"{table}_org_isolation"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR ALL "
            f"USING {predicate} WITH CHECK {predicate}"
        )


def downgrade() -> None:
    op.drop_table(SUBMISSION)
    op.drop_table(CONTACTS)
