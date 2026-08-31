"""Alembic 0035: nf_award_documents (Gate 127B).

Metadata about a Tribe's compliance documents. Not the documents.

## The distinction the whole table turns on

```text
document metadata   which document, for what, filed when, what digest
document storage    somewhere the bytes actually live
```

This is the first. `sha256_digest`, `content_length`, `content_type` and
`object_key` describe a file this table has never seen and this repository never
opens. There are no bytes in any column.

`nf_raw_source_payloads` (0028) settled the same shape for the other corpus —
`response_body_hash`, `response_body_size_bytes`, `content_type`,
`raw_payload_ref`, and no body. One difference: that table has no
`organization_id` and no RLS, because a fetched public NOFO belongs to nobody.
An award document belongs to exactly one Tribe.

## object_key is refused unless a store exists

```text
object_store_configured false  ->  object_key must be NULL
object_store_configured true   ->  object_key may name a location
```

`ck_..._object_key_needs_a_configured_store` enforces it. The flag is bridged
from `detect_body_store_mode()`, which reports `unconfigured` today, so every
row this repository can currently write is metadata-only.

A key with no store is a path into nothing, and a row carrying one would read as
"the file is at this location" to everything downstream.

## Three relationships, at least one, none an authority

```text
awarded_grant_id      nullable
award_requirement_id  nullable
proof_event_id        nullable
```

All optional because an award-level document that no requirement has claimed yet
is ordinary. At least one required, because a document attached to nothing is a
file in a drawer nobody can find.

None is an anchor. The RLS predicate reads `organization_id`; reaching it
through whichever of three joins happened to be populated would make this
table's policy depend on three other tables' policies.

## Legal hold refuses archive

`ck_..._legal_hold_refuses_archive` is a row-level constraint rather than a
convention. A document under legal hold is one a lawyer has said must not move,
and archiving is the only lifecycle operation this table has.

## customer_visible defaults false

Never derived from upload status, from a digest, or from anything else. Whether
a Tribe's own document is shown back to them is a decision somebody makes, and a
default of true would show a draft to the wrong person exactly once.

## No rows are inserted, and no object store is contacted

A production write needs `customer_auth_live` and a verified operational
binding, and Gates 115-126 measured both as false.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0035"
down_revision: str | Sequence[str] | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_award_documents"

# What kind of document this is. New in Gate 127: nothing existing describes a
# Tribe's own filing, so this is named as added rather than bridged.
DOCUMENT_KINDS = (
    "award_letter",
    "award_terms",
    "financial_report",
    "narrative_report",
    "performance_report",
    "audit_report",
    "match_documentation",
    "invoice_or_receipt",
    "board_or_council_resolution",
    "correspondence",
    "closeout_package",
    "other",
    "unknown",
)

# Where the document is in its own lifecycle. Also new in Gate 127.
DOCUMENT_STATUSES = (
    "reference_recorded",
    "awaiting_upload",
    "stored",
    "superseded",
    "withdrawn",
    "needs_human_review",
    "unknown",
)

# The one status that asserts bytes exist somewhere.
STORED_STATUSES = ("stored",)

# Where the metadata came from. Same shape as Gate 125/126's source columns.
DOCUMENT_SOURCES = (
    "tenant_supplied",
    "human_entered",
    "evidence_extracted",
    "system_generated",
    "unsupported_document_type",
    "needs_human_review",
    "unknown",
)

# Gate 96's retention vocabulary, restated because a CHECK cannot import Python.
# A test asserts it matches raw_payload_store_contract_service exactly.
RETENTION_CLASSES = (
    "retain_7_days",
    "retain_90_days",
    "retain_1_year",
    "retain_indefinite",
)

# Gate 103's status vocabulary, reused: a fact somebody guessed and one somebody
# confirmed are different objects.
FACT_STATUSES = (
    "verified",
    "tenant_supplied",
    "demo_fixture",
    "unknown",
    "needs_human_review",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The RLS anchor. Everything else is a relationship, metadata or an
        # audit trail.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Three relationships, all optional, at least one required. None is an
        # authority: no policy reads any of them.
        sa.Column(
            "awarded_grant_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_awarded_grants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "award_requirement_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_award_requirements.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "proof_event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_award_requirement_proof_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # -- what the document is ---------------------------------------------
        sa.Column("document_kind", sa.String(length=48), nullable=False),
        sa.Column("document_status", sa.String(length=32), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=False),
        sa.Column("document_description", sa.Text(), nullable=True),
        sa.Column("document_source", sa.String(length=32), nullable=False),
        sa.Column("document_source_ref", sa.Text(), nullable=True),
        # -- where the bytes would be, if there were anywhere -----------------
        # Bridged from detect_body_store_mode(), which reports `unconfigured`.
        # Recorded per row so a row says what was true when it was written.
        sa.Column(
            "object_store_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("object_store_provider", sa.String(length=32), nullable=True),
        sa.Column("object_bucket", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("object_version", sa.Text(), nullable=True),
        # -- metadata ABOUT a document this table has never seen --------------
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("content_length", sa.BigInteger(), nullable=True),
        sa.Column("sha256_digest", sa.String(length=64), nullable=True),
        # -- how long, and who may see it -------------------------------------
        sa.Column("retention_class", sa.String(length=32), nullable=False),
        sa.Column(
            "legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        # Never derived from upload status. Somebody decides this.
        sa.Column(
            "customer_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # -- lifecycle and audit ------------------------------------------------
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Set once, never cleared. Archiving is one-way.
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Matches the 0003/0027/0031/0032/0033/0034 policy shape.
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
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
        sa.CheckConstraint(
            _in_list("document_kind", DOCUMENT_KINDS),
            name="ck_nf_award_documents_kind",
        ),
        sa.CheckConstraint(
            _in_list("document_status", DOCUMENT_STATUSES),
            name="ck_nf_award_documents_status",
        ),
        sa.CheckConstraint(
            _in_list("document_source", DOCUMENT_SOURCES),
            name="ck_nf_award_documents_source",
        ),
        sa.CheckConstraint(
            _in_list("retention_class", RETENTION_CLASSES),
            name="ck_nf_award_documents_retention_class",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_award_documents_fact_status",
        ),
        # A document nobody can name is a document nobody can find.
        sa.CheckConstraint(
            "length(trim(document_title)) > 0",
            name="ck_nf_award_documents_title_not_blank",
        ),
        # A document attached to nothing is a file in a drawer.
        sa.CheckConstraint(
            "awarded_grant_id IS NOT NULL OR award_requirement_id IS NOT NULL "
            "OR proof_event_id IS NOT NULL",
            name="ck_nf_award_documents_needs_a_relationship",
        ),
        # A key with no store is a path into nothing.
        sa.CheckConstraint(
            "object_key IS NULL OR object_store_configured",
            name="ck_nf_award_documents_object_key_needs_a_configured_store",
        ),
        # The rest of the object reference travels with the key.
        sa.CheckConstraint(
            "object_bucket IS NULL OR object_store_configured",
            name="ck_nf_award_documents_bucket_needs_a_configured_store",
        ),
        sa.CheckConstraint(
            "object_version IS NULL OR object_key IS NOT NULL",
            name="ck_nf_award_documents_version_needs_a_key",
        ),
        sa.CheckConstraint(
            "object_store_provider IS NULL OR object_store_configured",
            name="ck_nf_award_documents_provider_needs_a_configured_store",
        ),
        # `stored` asserts bytes exist somewhere, which requires somewhere.
        sa.CheckConstraint(
            "document_status <> 'stored' OR "
            "(object_store_configured AND object_key IS NOT NULL)",
            name="ck_nf_award_documents_stored_needs_a_location",
        ),
        # Metadata about a file nobody has is still metadata, but a length
        # cannot be negative and a digest is 64 hex characters.
        sa.CheckConstraint(
            "content_length IS NULL OR content_length >= 0",
            name="ck_nf_award_documents_content_length_not_negative",
        ),
        sa.CheckConstraint(
            "sha256_digest IS NULL OR length(sha256_digest) = 64",
            name="ck_nf_award_documents_digest_is_sha256_shaped",
        ),
        # A lawyer said this must not move.
        sa.CheckConstraint(
            "NOT legal_hold OR archived_at IS NULL",
            name="ck_nf_award_documents_legal_hold_refuses_archive",
        ),
        # An unestablished document cannot be shown back to a Tribe as theirs.
        sa.CheckConstraint(
            "NOT customer_visible OR "
            "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
            name="ck_nf_award_documents_visible_needs_established_facts",
        ),
    )

    op.create_index("ix_nf_award_documents_organization", TABLE, ["organization_id"])
    op.create_index("ix_nf_award_documents_award", TABLE, ["awarded_grant_id"])
    op.create_index(
        "ix_nf_award_documents_requirement", TABLE, ["award_requirement_id"]
    )
    op.create_index("ix_nf_award_documents_proof_event", TABLE, ["proof_event_id"])

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002, 0027, 0029, 0031,
        # 0032, 0033 and 0034 behave.
        return
    conn.execute(text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;"))
    conn.execute(text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;"))
    conn.execute(
        text(
            f"""
CREATE POLICY {TABLE}_org_demo_scope ON {TABLE}
  USING (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
  WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  );
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"DROP POLICY IF EXISTS {TABLE}_org_demo_scope ON {TABLE};"))
    op.drop_index("ix_nf_award_documents_proof_event", table_name=TABLE)
    op.drop_index("ix_nf_award_documents_requirement", table_name=TABLE)
    op.drop_index("ix_nf_award_documents_award", table_name=TABLE)
    op.drop_index("ix_nf_award_documents_organization", table_name=TABLE)
    op.drop_table(TABLE)
