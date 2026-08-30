"""Alembic 0030: nf_auth_redirect_states (Gate 119C).

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-30

Where a redirect state and its PKCE verifier live between ``/login`` and
``/callback``.

## Why this table exists now and did not at Gate 118

Gate 118 declined to add one and 645 gives the reason: a table nothing writes
to. That held while ``/login`` had nowhere to send a browser. Gate 119D builds
an authorization URL, so ``/login`` has something to issue, so there is
something to remember across the redirect.

The in-memory store Gate 118 shipped is a per-process dict. A state that
vanishes on restart cannot survive a redirect in any deployment with more than
one worker, which is why ``in_memory_test`` is named for what it is.

## Hashes, not values

``state_hash`` and ``pkce_verifier_hash`` are SHA-256 digests. The raw state and
the raw verifier are never written here.

A database holding live PKCE verifiers is a database whose backups, replicas and
query logs hold live PKCE verifiers. The callback does not need the value — it
needs to know whether the value it was handed matches the one issued, and a
digest answers that exactly. ``code_challenge`` *is* stored raw because it is
already the public half of the pair: it travelled to the provider in the
authorization URL.

## Why there is no organization_id and no RLS

A redirect state is created **before anybody is authenticated**. At the moment
``/login`` issues one there is no identity, no organization, and nothing to put
in ``app.current_org_id`` — the row exists so that an organization can be
resolved later. Giving it an ``organization_id`` would mean inventing one at
issue time, and a fabricated RLS anchor is worse than no anchor at all.

``nf_identities`` (0023) is the precedent and the closest neighbour: a verified
OIDC subject exists before it belongs to anything, carries no organization, and
has no policy. Seven of the twenty-eight tables in this database are in the same
position.

What protects the row instead is that it is useless. Two digests, single-use,
expiring in at most fifteen minutes, with no customer data, no email, no token
and nothing reversible.

``consumed_by_identity_id`` references ``nf_identities`` and is nullable,
because who consumed a state is only knowable after the callback resolves an
identity — and today no callback can.

## No rows are inserted

Nothing writes here yet. ``/login`` still refuses while no provider is
configured, and this gate does not configure one. The table is built empty, the
same way 0029 was.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_auth_redirect_states"

# Gate 118D's vocabulary, restated because a CHECK constraint cannot import
# Python. A test asserts these match STORAGE_SCOPES exactly, so the two cannot
# drift.
STORAGE_SCOPES = (
    "contract_only",
    "in_memory_test",
    "database",
    "unknown",
)

# RFC 7636. ``plain`` is deliberately absent: it defeats the purpose of PKCE.
CODE_CHALLENGE_METHODS = ("S256",)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # SHA-256 of the state. Unique because a repeated state is either a
        # generator failure or a replay, and both should fail loudly at write.
        sa.Column("state_hash", sa.Text(), nullable=False),
        # SHA-256 of the PKCE verifier. Never the verifier.
        sa.Column("pkce_verifier_hash", sa.Text(), nullable=False),
        # The public half. It already travelled to the provider in the URL.
        sa.Column("code_challenge", sa.Text(), nullable=False),
        sa.Column("code_challenge_method", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # Set once, never cleared. Consumption is one-way.
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consumed_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # A consumed state presented again is somebody resubmitting a captured
        # callback URL. Recorded separately from expiry: they look alike and
        # only one is worth alerting on.
        sa.Column(
            "replay_detected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("storage_scope", sa.Text(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("state_hash", name="uq_nf_auth_redirect_state_hash"),
        sa.CheckConstraint(
            _in_list("storage_scope", STORAGE_SCOPES),
            name="ck_nf_auth_redirect_storage_scope",
        ),
        sa.CheckConstraint(
            _in_list("code_challenge_method", CODE_CHALLENGE_METHODS),
            name="ck_nf_auth_redirect_challenge_method",
        ),
        # A state that never expires is a credential. Enforced in the database
        # because an application bug that omitted the expiry would otherwise
        # produce a row nothing ever invalidates.
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_nf_auth_redirect_expiry_after_creation",
        ),
        # An identity cannot have consumed a state that was never consumed.
        sa.CheckConstraint(
            "consumed_by_identity_id IS NULL OR consumed_at IS NOT NULL",
            name="ck_nf_auth_redirect_consumer_needs_consumption",
        ),
    )

    op.create_index("ix_nf_auth_redirect_expires_at", TABLE, ["expires_at"])
    # Finding unconsumed states is the callback's only read path.
    op.create_index(
        "ix_nf_auth_redirect_unconsumed",
        TABLE,
        ["state_hash"],
        postgresql_where=sa.text("consumed_at IS NULL"),
        sqlite_where=sa.text("consumed_at IS NULL"),
    )

    # No RLS. See the module docstring: this row predates authentication, so
    # there is no organization to scope it to and inventing one would be worse
    # than having none. 0023 nf_identities is the precedent.


def downgrade() -> None:
    op.drop_index("ix_nf_auth_redirect_unconsumed", table_name=TABLE)
    op.drop_index("ix_nf_auth_redirect_expires_at", table_name=TABLE)
    op.drop_table(TABLE)
