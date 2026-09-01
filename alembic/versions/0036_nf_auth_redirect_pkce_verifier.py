"""Alembic 0036: a retrievable PKCE verifier (Gate 131B).

## Why a hash was not enough

Migration 0030 stored the PKCE verifier as `pkce_verifier_hash`, and for a table
that only ever *validated* a returned state that was right: a digest proves a
value was the one issued without keeping the value.

It is fatal for a table that must also *complete* an exchange. PKCE works by the
client sending the raw `code_verifier` to the token endpoint, where the provider
hashes it and compares against the `code_challenge` it received at the
authorization request. SHA-256 does not reverse, so a stored digest cannot be
presented and the exchange cannot happen.

```text
code_challenge          public - it travels in the authorization URL
pkce_verifier_hash      proves a match, useless for exchange
pkce_verifier_encrypted this column - retrievable, and not plaintext at rest
```

## Encrypted, not raw

The verifier is a bearer secret for the length of one redirect: whoever holds it
and an intercepted code can complete the exchange. Writing it in plaintext would
mean a database read is enough to do that.

It is encrypted with a key derived from `NF_SESSION_SIGNING_KEY`, which lives in
the environment and never in the database. A dump of this table on its own
yields nothing; an attacker needs the row and the deployment's signing key.

The existing `pkce_verifier_hash` stays and stays NOT NULL. It is now an
integrity check: the decrypted verifier must hash to it, so a tampered or
mis-decrypted ciphertext is caught rather than sent to the provider.

## Nullable, deliberately

Rows written before this column existed have no ciphertext, and a row whose
verifier cannot be recovered must fail the exchange rather than block the
migration. Nullable, with the repository refusing to exchange when it is absent.

There is no CHECK requiring it. A NOT NULL here would make migration 0036
un-appliable to any database holding 0030-era rows, and the honest failure is at
use rather than at deploy.

## Rows affected

Zero. `nf_auth_redirect_states` has never held a row: nothing but a demo fixture
has ever called the repository, and no login has ever completed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_auth_redirect_states"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("pkce_verifier_encrypted", sa.Text(), nullable=True),
    )
    # Which key derivation produced the ciphertext. A deployment that rotates
    # its signing key can tell "cannot decrypt" from "encrypted differently",
    # and a future scheme can be added without guessing at old rows.
    op.add_column(
        TABLE,
        sa.Column(
            "pkce_verifier_key_scheme",
            sa.Text(),
            nullable=False,
            server_default="none",
        ),
    )
    # PostgreSQL-only, for the reason migration 0025 recorded: SQLite cannot
    # ALTER a table to add a constraint, and `op.create_check_constraint`
    # raises NotImplementedError on it. batch_alter_table would rebuild the
    # table by copy-and-move, which on this table would drop the partial
    # unique index 0030 created and silently weaken replay detection.
    #
    # The Core table in the repository service restates this constraint, so a
    # test that builds the table from the Python definition still enforces it
    # even where the migrated SQLite table cannot.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_nf_auth_redirect_verifier_scheme",
            TABLE,
            "pkce_verifier_key_scheme IN ('none', 'fernet_hkdf_sha256_v1')",
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_nf_auth_redirect_verifier_scheme", TABLE, type_="check")
    op.drop_column(TABLE, "pkce_verifier_key_scheme")
    op.drop_column(TABLE, "pkce_verifier_encrypted")
