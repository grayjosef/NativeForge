"""Alembic 0037: nf_auth_validation_events (Gate 133B).

## The fact that kept not existing

The callback verifies Google's ID token against Google's JWKS on every single
login. Gate 131 proved it, Gate 132 proved it again. And
`issuer_jwks_validated` has been false the whole time, because the verification
result lived in a local named `verification` and was discarded when the request
ended.

```python
# api/auth.py, before this migration
verification = verify_oidc_token(token=..., jwks=..., ...)
if verification.get("verified"):
    ...                      # used, and then gone
```

`auth0_live_validation_runner_service` meanwhile had
`provider_validated = False` as a literal - assigned once, never assigned again.
So the gate read a constant while the thing it described happened repeatedly.

This table is where it gets written down. A row here is the difference between
"validation happens" and "validation is measured", and only the second one can
satisfy a gate. Gate 132 settled the same question for two neighbouring gates by
deriving them from rows; this one had no rows to derive from.

## What is stored, and what is refused

```text
issuer                 the URL. Public, and needed to know WHICH issuer passed.
                       0030 stores it in plaintext already.
verification_state     the outcome name: verified, signature_invalid,
                       unknown_kid, expired - one of fourteen
algorithm              RS256. Public metadata from the token header.
key_id_fingerprint     sha256(kid)[:32]. The kid is public JWKS metadata; a
                       fingerprint correlates rows across logins without
                       inviting an argument about whether it should be here.
booleans               issuer/jwks/signature/audience validated, provider called
```

Refused: the token, any part of it, the JWKS document, the key material, the
audience value, the subject, the email, and every claim. There is no column any
of them could go in, which is stronger than a rule about what to put in one.

A CHECK constrains `evidence_source` to `oauth_callback`. If a second source
ever records validation it has to say so in a migration, rather than a caller
inventing a label.

## Why no organization_id and no RLS

The same reason migration 0030 gives for `nf_auth_redirect_states`: this row is
written before any organization is known. Validation happens against the
provider; the organization comes later from a membership row. Giving this table
an `organization_id` would mean inventing one at insert time, and an invented
anchor is worse than an honest absence - it would make the RLS predicate pass on
a value nobody chose.

It holds no tenant data. Every column is provider metadata or a boolean about
one verification attempt.

## Append-only by intent

Nothing updates or deletes a row here. An event is a record that something
happened at a time, and editing one would make the audit trail an opinion. No
`updated_at` column exists, which is the schema saying so.

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-01

Gate 133. Demo/dev scope. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_auth_validation_events"

#: The only source permitted to write one. Widening this is a migration.
EVIDENCE_SOURCES = ("oauth_callback",)

#: `oidc_token_verification_service`'s fourteen states plus `verified`.
VERIFICATION_STATES = (
    "verified",
    "missing_token",
    "malformed_token",
    "unsupported_algorithm",
    "missing_kid",
    "unknown_kid",
    "jwks_unavailable",
    "signature_invalid",
    "issuer_invalid",
    "audience_invalid",
    "expired",
    "not_yet_valid",
    "subject_missing",
    "verification_error",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("evidence_source", sa.String(length=32), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("verification_state", sa.String(length=32), nullable=False),
        sa.Column("algorithm", sa.String(length=16), nullable=True),
        # sha256(kid) truncated. Never the key, never the token.
        sa.Column("key_id_fingerprint", sa.String(length=32), nullable=True),
        sa.Column("provider_called", sa.Boolean(), nullable=False),
        sa.Column("issuer_validated", sa.Boolean(), nullable=False),
        sa.Column("jwks_validated", sa.Boolean(), nullable=False),
        sa.Column("id_token_signature_validated", sa.Boolean(), nullable=False),
        sa.Column("audience_validated", sa.Boolean(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.CheckConstraint(
            _in_list("evidence_source", EVIDENCE_SOURCES),
            name="ck_nf_auth_validation_events_source",
        ),
        sa.CheckConstraint(
            _in_list("verification_state", VERIFICATION_STATES),
            name="ck_nf_auth_validation_events_state",
        ),
        # A signature cannot verify without the JWKS it verified against, and a
        # fully-verified event cannot claim otherwise. Enforced here as well as
        # in the service, so a direct INSERT cannot forge the gate's input.
        sa.CheckConstraint(
            "id_token_signature_validated = false OR jwks_validated = true",
            name="ck_nf_auth_validation_events_signature_needs_jwks",
        ),
        sa.CheckConstraint(
            "verification_state <> 'verified' OR ("
            "issuer_validated = true AND jwks_validated = true "
            "AND id_token_signature_validated = true "
            "AND audience_validated = true)",
            name="ck_nf_auth_validation_events_verified_needs_all",
        ),
    )
    op.create_index(f"ix_{TABLE}_occurred_at", TABLE, ["occurred_at"])
    op.create_index(f"ix_{TABLE}_verification_state", TABLE, ["verification_state"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_verification_state", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_occurred_at", table_name=TABLE)
    op.drop_table(TABLE)
