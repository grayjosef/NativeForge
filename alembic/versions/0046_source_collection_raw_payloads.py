"""Alembic 0046: somewhere for the bytes to land (Gate 160C).

## Why a new table and not a column on 0028

`nf_raw_source_payloads` (migration 0028) already holds raw payload METADATA,
and `production_raw_payload_repository_service` refuses to write a body into it
for a stated reason:

    A 78 MB Grants.gov extract is not a database row, and a table that
    sometimes holds bodies is a table whose size nobody can predict.

That argument is correct, and Gate 160 does not get to overturn it by widening
the same table. 0028 keeps its metadata-only contract; this is a separate,
size-capped, controlled-dev-demo landing zone.

## Why a database row at all

Measured in doc 832:

```text
raw_payload_object_store_bucket          ''
build_client_config(...).configured      False
body_store_configured                    FALSE
production_raw_payload_store_available   False
```

The production body store (`s3_raw_payload_body_store_service`, Gate 97C) is
built and unconfigured. Adding a second object-store abstraction to satisfy this
gate would produce two stores, one of them fake, which Gate 160's rules forbid
outright. The only storage this environment actually has is the database.

## One megabyte, and refused above it

```text
Gate 141 object adapter    16 MiB     an OBJECT is not a row
Gate 160 this table         1 MiB     a row is not an object
```

Large enough for a synthetic fixture or a realistic API page; small enough that
nobody mistakes it for the production path. `payload_size_bytes` is CHECKed, so
an oversize body is refused by the database and not only by the service.

## What it refuses to hold

```text
no Authorization        no Cookie / Set-Cookie   no API key
no bearer token         no OAuth state           no PKCE verifier
no provider subject     no customer data         no recipient address
no request URL          - a FINGERPRINT instead, because URLs carry
                          credentials in query strings
```

`response_header_metadata` is populated only by
`source_response_metadata_filter_service`, which keeps a header if its name is
on an explicit ALLOWLIST and refuses everything else - including headers nobody
has classified.

## What it does not create

There is **no execution-proof column here, and no completion status.** Gate 158
left `completed` unreachable because the gate that defines what an execution
proof IS has not been written, and a stored payload is not one: these bytes are
supplied by a caller, and a row proves the spine works rather than that a source
was contacted.

`collector_invoked` and `live_fetch_performed` are declared so a read can assert
them, and the database refuses any value but false - the same shape 0043 used
for its three booleans.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | Sequence[str] | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYLOADS = "nf_source_collection_raw_payloads"

#: One megabyte. See the module docstring.
MAX_PAYLOAD_BYTES = 1024 * 1024

#: Where the bytes actually are. Only the first is implemented; the second is
#: named so the column does not have to change when Gate 97C's store is
#: configured, and the third records a payload whose body was refused.
BODY_STORAGE_MODES = (
    "controlled_dev_demo_database",
    "object_store_reference",
    "body_not_stored",
)

#: The lifecycle of a stored payload.
#:
#: `archived` is a state, not a deletion. Deletion needs an approved retention
#: policy and none exists, so nothing here deletes.
PAYLOAD_STATUSES = (
    "active",
    "archived",
    "refused",
    "unknown",
)

#: Composed from `raw_payload_store_contract_service.RETENTION_POLICIES`, plus
#: the honest default.
#:
#: `retention_unknown` is the DEFAULT on purpose. Nobody has approved a
#: retention policy for source evidence, and picking `retain_90_days` here
#: would be inventing one. UNKNOWN stays UNKNOWN.
RETENTION_POLICIES = (
    "retention_unknown",
    "retain_7_days",
    "retain_90_days",
    "retain_1_year",
    "retain_indefinite",
)

FACT_STATUSES = ("demo_fixture", "synthetic_fixture", "tenant_supplied", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        PAYLOADS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        # -- identity: the ATTEMPT, deterministic ---------------------------
        #
        # attempt_id digests (job_id, source_id, attempt_number,
        # collector_version). A retry is a DIFFERENT attempt, so attempt 2's
        # bytes never overwrite attempt 1's - which is the whole reason a raw
        # payload spine exists.
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("collector_version", sa.String(length=128), nullable=False),
        # -- provenance: attempt -> job -> source ---------------------------
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        # -- when -----------------------------------------------------------
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        # -- the response, as metadata --------------------------------------
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("media_type", sa.String(length=256), nullable=True),
        sa.Column("encoding", sa.String(length=64), nullable=True),
        # A FINGERPRINT, never the URL. Query strings carry api keys.
        sa.Column("source_url_fingerprint", sa.String(length=64), nullable=True),
        # Populated only by the allowlist filter.
        sa.Column("response_header_metadata", sa.JSON(), nullable=True),
        # -- the body -------------------------------------------------------
        sa.Column("body_storage_mode", sa.String(length=48), nullable=False),
        sa.Column("body_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        # -- lifecycle ------------------------------------------------------
        sa.Column("payload_status", sa.String(length=32), nullable=False),
        sa.Column("retention_policy", sa.String(length=32), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        # -- declared so a read can assert them -----------------------------
        #
        # The database refuses any value but false. Same shape as 0043's three
        # booleans: a claim the store cannot make rather than a convention
        # somebody could forget.
        sa.Column(
            "collector_invoked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "live_fetch_performed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # -- provenance ------------------------------------------------------
        sa.Column("fact_status", sa.String(length=32), nullable=False),
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
            _in_list("body_storage_mode", BODY_STORAGE_MODES),
            name="ck_nf_source_collection_raw_payloads_storage_mode",
        ),
        sa.CheckConstraint(
            _in_list("payload_status", PAYLOAD_STATUSES),
            name="ck_nf_source_collection_raw_payloads_status",
        ),
        sa.CheckConstraint(
            _in_list("retention_policy", RETENTION_POLICIES),
            name="ck_nf_source_collection_raw_payloads_retention",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_collection_raw_payloads_fact_status",
        ),
        # THE size constraint. An oversize body is refused by the database,
        # not only by the service that should have caught it first.
        sa.CheckConstraint(
            f"payload_size_bytes >= 0 AND payload_size_bytes <= {MAX_PAYLOAD_BYTES}",
            name="ck_nf_source_collection_raw_payloads_size_bounded",
        ),
        # A hash is 64 hex characters or it is not a sha256.
        sa.CheckConstraint(
            "length(payload_sha256) = 64",
            name="ck_nf_source_collection_raw_payloads_hash_is_sha256",
        ),
        # THE constraints that keep this a spine rather than a claim.
        sa.CheckConstraint(
            "collector_invoked = false",
            name="ck_nf_source_collection_raw_payloads_no_collector",
        ),
        sa.CheckConstraint(
            "live_fetch_performed = false",
            name="ck_nf_source_collection_raw_payloads_no_live_fetch",
        ),
        # A body stored in the database has bytes; one stored elsewhere does
        # not. A row claiming database storage with no body would be a hash
        # pointing at nothing.
        sa.CheckConstraint(
            "body_storage_mode <> 'controlled_dev_demo_database' "
            "OR body_bytes IS NOT NULL",
            name="ck_nf_source_collection_raw_payloads_db_mode_has_bytes",
        ),
        # An archived payload carries its timestamp, and a live one does not.
        sa.CheckConstraint(
            "(payload_status = 'archived' AND archived_at IS NOT NULL) "
            "OR (payload_status <> 'archived' AND archived_at IS NULL)",
            name="ck_nf_source_collection_raw_payloads_archived_has_a_timestamp",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_nf_source_collection_raw_payloads_attempt_is_positive",
        ),
    )

    # An attempt has ONE payload. A second write for the same attempt is
    # refused by the index, which is what makes "the same attempt cannot
    # silently overwrite different bytes" a database fact.
    op.create_index(
        "ux_nf_source_collection_raw_payloads_attempt",
        PAYLOADS,
        ["organization_id", "attempt_id"],
        unique=True,
    )
    # Deliberately NOT unique: two attempts may legitimately retrieve
    # identical bytes, and that is worth seeing rather than refusing.
    op.create_index(
        "ix_nf_source_collection_raw_payloads_hash",
        PAYLOADS,
        ["organization_id", "payload_sha256"],
    )
    op.create_index(
        "ix_nf_source_collection_raw_payloads_job",
        PAYLOADS,
        ["organization_id", "job_id"],
    )
    op.create_index(
        "ix_nf_source_collection_raw_payloads_source",
        PAYLOADS,
        ["organization_id", "source_id", "received_at"],
    )
    op.create_index(
        "ix_nf_source_collection_raw_payloads_status",
        PAYLOADS,
        ["organization_id", "payload_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nf_source_collection_raw_payloads_status", table_name=PAYLOADS
    )
    op.drop_index(
        "ix_nf_source_collection_raw_payloads_source", table_name=PAYLOADS
    )
    op.drop_index("ix_nf_source_collection_raw_payloads_job", table_name=PAYLOADS)
    op.drop_index("ix_nf_source_collection_raw_payloads_hash", table_name=PAYLOADS)
    op.drop_index(
        "ux_nf_source_collection_raw_payloads_attempt", table_name=PAYLOADS
    )
    op.drop_table(PAYLOADS)
