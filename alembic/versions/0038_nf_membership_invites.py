"""Alembic 0038: nf_membership_invites (Gate 135C).

## The decision that had nowhere to go

`membership_invite_approval_service` is 694 lines of invite and approval logic
with no `sa.insert`, no connection parameter, and `persisted: False` on every
result. It also has zero callers anywhere in `src/`.

So the contract that decides whether a membership may exist could be asked and
could not be recorded, and `invite_binding_passed` read a parameter no caller
passed. Same shape as `org_binding_passed` before Gate 132 and
`issuer_jwks_validated` before Gate 133: a gate reading a value nobody supplies.

An invite is the one piece of membership provenance that is an **event** rather
than a row that already exists. A membership says who belongs; only an invite
says how they came to. `TRUSTED_PROVENANCES` is `{"completed_invite"}` and a
completed invite must name itself:

```text
completed_invite_provenance_without_invite_id
```

That refusal is unfalsifiable without somewhere for the invite to be.

## Scope

```text
organization_id   the anchor. NOT NULL, and the RLS predicate's left-hand side.
is_demo           pairs with the predicate, as every tenant table does
invite_state      draft | pending_approval | approved | sent | accepted |
                  expired | revoked | rejected
approval_state    not_required | required | pending | approved | rejected |
                  expired | revoked
```

Both vocabularies are the service's, restated as CHECKs. A test parses this
migration and compares.

## What is stored, and what is refused

```text
invited_email_domain   the domain half only. `gmail.com`, never the address.
invited_subject_fingerprint  sha256(subject)[:32] when an invite names one
requested_by / approved_by   identity ids, which are internal
```

Refused: the invitee's email address, the provider subject, any token. An invite
carries a person's contact details by nature and this table is the place that
must not keep them — the address is what an invite *is sent to*, and nothing in
NativeForge sends one.

## Two CHECKs that make the gate's input un-forgeable

```sql
accepted_at IS NULL OR invite_state = 'accepted'
invite_state <> 'accepted' OR accepted_by_identity_id IS NOT NULL
```

An accepted invite names who accepted it. Without that, `invite_binding_passed`
could be satisfied by an UPDATE setting one column.

## Self-dealing

`requested_by`, `approved_by` and `accepted_by_identity_id` may not all be the
same identity — an invite where the requester, the approver and the invitee are
one person authorizes nothing, and the whole contract exists because somebody
else has to say yes. Enforced as a CHECK on PostgreSQL and in the repository on
every dialect; SQLite cannot express it against three nullable columns without
rebuilding the table, and 0025 recorded why a rebuild here is not worth it.

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-02

Gate 135. Demo/dev scope. No production customer claim. No email is sent by
this migration, by the repository above it, or by anything that reads it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | Sequence[str] | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_membership_invites"

#: `membership_invite_approval_service.INVITE_STATES`, restated.
INVITE_STATES = (
    "draft",
    "pending_approval",
    "approved",
    "sent",
    "accepted",
    "expired",
    "revoked",
    "rejected",
    "unknown",
)

#: `membership_invite_approval_service.APPROVAL_STATES`, restated.
APPROVAL_STATES = (
    "not_required",
    "required",
    "pending",
    "approved",
    "rejected",
    "expired",
    "revoked",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("invite_id", sa.String(length=128), nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_role", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_role", sa.String(length=64), nullable=False),
        # The domain half only. The address is what an invite is sent to, and
        # nothing here sends one.
        sa.Column("invited_email_domain", sa.String(length=255), nullable=True),
        sa.Column("invited_subject_fingerprint", sa.String(length=32), nullable=True),
        sa.Column("invite_state", sa.String(length=32), nullable=False),
        sa.Column("approval_state", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("approved_by_role", sa.String(length=64), nullable=True),
        sa.Column("accepted_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("seat_cap", sa.Integer(), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.CheckConstraint(
            _in_list("invite_state", INVITE_STATES),
            name="ck_nf_membership_invites_state",
        ),
        sa.CheckConstraint(
            _in_list("approval_state", APPROVAL_STATES),
            name="ck_nf_membership_invites_approval_state",
        ),
        # An acceptance timestamp without the state, or the state without an
        # accepter, would let one UPDATE manufacture a completed invite.
        sa.CheckConstraint(
            "accepted_at IS NULL OR invite_state = 'accepted'",
            name="ck_nf_membership_invites_accepted_at_needs_state",
        ),
        sa.CheckConstraint(
            "invite_state <> 'accepted' OR accepted_by_identity_id IS NOT NULL",
            name="ck_nf_membership_invites_accepted_needs_accepter",
        ),
        # One live invite per id. A revoked one stops blocking a replacement
        # without disappearing, the same shape as migration 0029's bindings.
        sa.UniqueConstraint(
            "organization_id", "invite_id", name="uq_nf_membership_invites_org_invite"
        ),
    )
    op.create_index(f"ix_{TABLE}_organization_id", TABLE, ["organization_id"])
    op.create_index(f"ix_{TABLE}_invite_state", TABLE, ["invite_state"])

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # The self-dealing refusal. SQLite cannot ALTER a CHECK in, and
        # batch_alter_table would rebuild the table - 0025 recorded why that
        # trade is not worth it. The repository enforces it on every dialect.
        op.create_check_constraint(
            "ck_nf_membership_invites_not_self_dealt",
            TABLE,
            "accepted_by_identity_id IS NULL"
            " OR requested_by <> accepted_by_identity_id"
            " OR approved_by IS NULL"
            " OR approved_by <> accepted_by_identity_id",
        )

        op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {TABLE}_org_isolation ON {TABLE}
            USING (
                organization_id = current_setting('app.current_org_id', true)::uuid
                AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"DROP POLICY IF EXISTS {TABLE}_org_isolation ON {TABLE}")
    op.drop_index(f"ix_{TABLE}_invite_state", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_organization_id", table_name=TABLE)
    op.drop_table(TABLE)
