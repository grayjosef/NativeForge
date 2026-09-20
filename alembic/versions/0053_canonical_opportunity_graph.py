"""Alembic 0053: the canonical opportunity graph (Gate 167B).

Gates 156-166 built a substrate that can prove where a byte came from. It ends
at `nf_source_collection_raw_payloads`. Nothing turns those bytes into an
opportunity, so every customer-facing capability - matching, deadlines,
amendments, relevance, alerts - is blocked behind one missing store.

## Four tables, because these are four different things

```text
CanonicalOpportunity   the thing that exists in the world
SourceObservation      one source saying it saw that thing, once
OpportunityVersion     what the fields were, at one observation
FieldProvenance        which evidence supports each canonical value
```

`nf_grant_sparks` (0 rows) is what collapsing them looks like: 50 columns
mixing canonical facts, tenant pipeline state and raw NOFO text in one row,
per organization. A schema in that shape cannot answer "which source said
this", cannot hold two sources disagreeing, and multiplies the world by the
customer count.

## No organization_id. Anywhere.

Every opportunity-shaped table in this database carries `organization_id` -
all fifteen of them. That means the same federal opportunity would be stored
once per tenant, and at 1,000 sources and a few hundred Tribes that is the
whole world copied a few hundred times.

Source intelligence is a shared fact about the world. **Tenant state belongs
in tenant tables that REFERENCE a canonical id**, which is the pattern
`nf_tenant_pursuit_suppressions.opportunity_id` already uses. The absence of
`organization_id` here is load-bearing, and Gate 167L asserts it.

## Evidence is required at write time, not audited afterwards

```sql
CHECK (length(raw_payload_sha256) = 64)   -- on observations
CHECK (length(raw_payload_sha256) = 64)   -- on field provenance
```

An observation that names no bytes cannot be written, and neither can a
canonical field value that traces to nothing. Gate 164 learned that the
strongest tamper defence is one where the bad state has no representation at
rest - detecting it afterwards is weaker than making it unwritable.

## Fuzzy identity cannot silently become canonical

```sql
CHECK (identity_layer <> 'L4' OR is_provisional = 1)
```

L4 is the SHA-256 fallback for sources that publish no identifier at all. The
identity service marks it provisional and says it must be promoted to L1 when
a real number appears. This makes "provisional" unforgeable rather than
conventional: an L4 row that claims to be settled has no representation.

## The composite key, and the transition it protects

`(normalized_opportunity_number, doc_type)` is unique. A forecast and the
synopsis it becomes share an opportunity number, so keying on the number alone
merges them and destroys the forecasted -> posted transition - the event a
Tribe watching the forecast has been waiting for.

They must also not become unrelated. `opportunity_number_group` carries the
number without the doc_type, so the two canonical rows are one indexed join
apart and the transition is queryable rather than inferred.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: str | Sequence[str] | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL = "nf_canonical_opportunities"
OBSERVATIONS = "nf_opportunity_source_observations"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

DOC_TYPES = ("forecast", "synopsis", "unknown")

#: The lifecycle a funding opportunity moves through. `unknown` is a real
#: answer - a source that does not publish a status must not be assigned one.
LIFECYCLE_STATES = (
    "forecasted",
    "posted",
    "amended",
    "closed",
    "awarded",
    "archived",
    "unknown",
)

IDENTITY_LAYERS = ("L1", "L4")

OBSERVATION_STATES = ("recorded", "superseded", "unparseable", "withdrawn")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    # ---------------------------------------------------- canonical
    op.create_table(
        CANONICAL,
        sa.Column("canonical_id", sa.Text(), primary_key=True),
        # L1 identity, from opportunity_identity_versioning_service.
        sa.Column("normalized_opportunity_number", sa.Text(), nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("identity_layer", sa.Text(), nullable=False),
        sa.Column(
            "is_provisional", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        # The number WITHOUT doc_type: what joins a forecast to its synopsis.
        sa.Column("opportunity_number_group", sa.Text(), nullable=False),
        # Stable, but agencies do not publish it, so it is never the key.
        sa.Column("surrogate_opportunity_id", sa.Text(), nullable=True),
        # Current canonical values. Each one is backed by a provenance row;
        # none is authoritative on its own.
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("funder_agency_code", sa.Text(), nullable=True),
        sa.Column("funder_agency_name", sa.Text(), nullable=True),
        sa.Column("current_open_date", sa.Text(), nullable=True),
        sa.Column("current_close_date", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("current_version_id", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "observation_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("version_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "has_field_conflicts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in_list("doc_type", DOC_TYPES), name=f"ck_{CANONICAL}_doc"),
        sa.CheckConstraint(
            _in_list("identity_layer", IDENTITY_LAYERS), name=f"ck_{CANONICAL}_layer"
        ),
        sa.CheckConstraint(
            _in_list("lifecycle_state", LIFECYCLE_STATES),
            name=f"ck_{CANONICAL}_lifecycle",
        ),
        # Fuzzy identity may never present itself as settled.
        sa.CheckConstraint(
            "identity_layer <> 'L4' OR is_provisional = 1",
            name=f"ck_{CANONICAL}_l4_is_provisional",
        ),
        # An L1 row without a number is not an L1 row.
        sa.CheckConstraint(
            "identity_layer <> 'L1' OR length(normalized_opportunity_number) > 0",
            name=f"ck_{CANONICAL}_l1_needs_number",
        ),
    )
    op.create_index(
        f"uq_{CANONICAL}_identity",
        CANONICAL,
        ["normalized_opportunity_number", "doc_type"],
        unique=True,
    )
    # The forecast -> synopsis join.
    op.create_index(f"ix_{CANONICAL}_group", CANONICAL, ["opportunity_number_group"])
    op.create_index(f"ix_{CANONICAL}_lifecycle", CANONICAL, ["lifecycle_state"])
    op.create_index(f"ix_{CANONICAL}_last_seen", CANONICAL, ["last_seen_at"])
    op.create_index(f"ix_{CANONICAL}_funder", CANONICAL, ["funder_agency_code"])
    op.create_index(f"ix_{CANONICAL}_close", CANONICAL, ["current_close_date"])
    op.create_index(
        f"ix_{CANONICAL}_current_version", CANONICAL, ["current_version_id"]
    )

    # ------------------------------------------------- observations
    op.create_table(
        OBSERVATIONS,
        sa.Column("observation_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        # What THIS source calls it. Never assumed to match another source.
        sa.Column("source_record_id", sa.Text(), nullable=True),
        sa.Column("source_opportunity_number", sa.Text(), nullable=True),
        sa.Column("source_authority_host", sa.Text(), nullable=True),
        # The evidence. Not nullable, and length-checked: an observation that
        # names no bytes has no representation at rest.
        sa.Column("raw_payload_sha256", sa.Text(), nullable=False),
        sa.Column("raw_payload_attempt_id", sa.Text(), nullable=True),
        sa.Column("parser_name", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_record_fingerprint", sa.Text(), nullable=True),
        sa.Column(
            "observation_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'recorded'"),
        ),
        # Nullable on purpose. Gate 163 never captured it and Gate 164 refused
        # to backfill it from the application errorcode. UNKNOWN is a fact.
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(raw_payload_sha256) = 64", name=f"ck_{OBSERVATIONS}_evidence"
        ),
        sa.CheckConstraint(
            _in_list("observation_state", OBSERVATION_STATES),
            name=f"ck_{OBSERVATIONS}_state",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{OBSERVATIONS}_c"
        ),
    )
    # One source seeing one record in one payload is ONE observation. Replaying
    # the same bytes must not manufacture a second sighting.
    op.create_index(
        f"uq_{OBSERVATIONS}_identity",
        OBSERVATIONS,
        ["source_id", "source_record_id", "raw_payload_sha256"],
        unique=True,
    )
    op.create_index(
        f"ix_{OBSERVATIONS}_canonical", OBSERVATIONS, ["canonical_id", "observed_at"]
    )
    op.create_index(
        f"ix_{OBSERVATIONS}_source", OBSERVATIONS, ["source_id", "source_record_id"]
    )
    op.create_index(f"ix_{OBSERVATIONS}_payload", OBSERVATIONS, ["raw_payload_sha256"])
    op.create_index(f"ix_{OBSERVATIONS}_observed", OBSERVATIONS, ["observed_at"])

    # ----------------------------------------------------- versions
    op.create_table(
        VERSIONS,
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("version_key", sa.Text(), nullable=True),
        sa.Column("revision", sa.Text(), nullable=True),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("normalized_fields_json", sa.Text(), nullable=False),
        # Same normalized content = same version. This is what makes an exact
        # replay idempotent without comparing every field in application code.
        sa.Column("content_fingerprint", sa.Text(), nullable=False),
        sa.Column("supersedes_version_id", sa.Text(), nullable=True),
        sa.Column("superseded_by_version_id", sa.Text(), nullable=True),
        sa.Column(
            "is_material", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("material_categories_json", sa.Text(), nullable=True),
        sa.Column("changed_fields_json", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in_list("doc_type", DOC_TYPES), name=f"ck_{VERSIONS}_doc"),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{VERSIONS}_c"
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            [f"{OBSERVATIONS}.observation_id"],
            name=f"fk_{VERSIONS}_o",
        ),
    )
    op.create_index(
        f"uq_{VERSIONS}_content",
        VERSIONS,
        ["canonical_id", "content_fingerprint"],
        unique=True,
    )
    op.create_index(
        f"ix_{VERSIONS}_canonical", VERSIONS, ["canonical_id", "created_at"]
    )
    op.create_index(f"ix_{VERSIONS}_observation", VERSIONS, ["observation_id"])
    op.create_index(
        f"ix_{VERSIONS}_superseded", VERSIONS, ["superseded_by_version_id"]
    )

    # --------------------------------------------------- provenance
    op.create_table(
        PROVENANCE,
        sa.Column("provenance_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        # The normalized value as text. Not the raw bytes - those stay in the
        # payload store, which is the one evidence ledger.
        sa.Column("field_value", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        # Every canonical field traces to bytes. Unwritable otherwise.
        sa.Column("raw_payload_sha256", sa.Text(), nullable=False),
        sa.Column("selection_rule", sa.Text(), nullable=True),
        sa.Column(
            "is_current_canonical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # Two sources asserting different values for one field share a group.
        # The disagreement is a row, not a lost write.
        sa.Column("conflict_group", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(raw_payload_sha256) = 64", name=f"ck_{PROVENANCE}_evidence"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{PROVENANCE}_c"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], [f"{VERSIONS}.version_id"], name=f"fk_{PROVENANCE}_v"
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            [f"{OBSERVATIONS}.observation_id"],
            name=f"fk_{PROVENANCE}_o",
        ),
    )
    op.create_index(
        f"ix_{PROVENANCE}_field", PROVENANCE, ["canonical_id", "field_name"]
    )
    op.create_index(
        f"ix_{PROVENANCE}_current",
        PROVENANCE,
        ["canonical_id", "field_name", "is_current_canonical"],
    )
    op.create_index(f"ix_{PROVENANCE}_conflict", PROVENANCE, ["conflict_group"])
    op.create_index(f"ix_{PROVENANCE}_payload", PROVENANCE, ["raw_payload_sha256"])
    op.create_index(f"ix_{PROVENANCE}_version", PROVENANCE, ["version_id"])


def downgrade() -> None:
    op.drop_table(PROVENANCE)
    op.drop_table(VERSIONS)
    op.drop_table(OBSERVATIONS)
    op.drop_table(CANONICAL)
