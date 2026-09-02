"""Alembic 0039: two columns that make an invite acceptance provable (Gate 136A).

## `nf_membership_invites.invited_email_fingerprint`

Gate 135 stored the domain half of the invited address and a fingerprint of the
invited *provider subject*. That was enough to prove the table keeps no contact
details and not enough to accept an invite safely, because the operator issuing
an invite knows the invitee's email and cannot know their Google subject — so
the subject fingerprint is null on every invite anybody can actually issue.

Measured in Gate 136A: `record_acceptance` reads neither field. Any existing
identity that is not the requester or the approver could accept any invite. An
invite is supposed to name who it is for; it named them and nothing looked.

```text
stored    sha256(lower(strip(email)))[:32]
refused   the address itself, still, on this column and every other
```

A fingerprint of an email address is enumerable — there are not many plausible
addresses — so this is not secrecy, and it is not claimed as secrecy. It is
*matching*: enough for acceptance to require that the identity accepting is the
identity invited, without the row ever holding the address that would let
something else send to it.

## `nf_org_memberships.invite_id`

`TRUSTED_PROVENANCES` is `{"completed_invite"}` and
`evaluate_membership_provenance` refuses that provenance without an invite id:

```text
completed_invite_provenance_without_invite_id
```

Unfalsifiable from the database until now, because no membership row could name
an invite. `nf_org_memberships` had thirteen columns and none of them said how
the membership came to exist beyond `membership_source`, which distinguishes who
approved it and not what produced it.

So `build_invite_binding_evidence` was reduced to inferring: it counted a
membership as invite-derived when the member's `identity_id` appeared among the
identities that had accepted an invite. A membership an operator wrote for
somebody who separately accepted an invite counted. Now it is a join.

Nullable, because the memberships that already exist did not come through an
invite and must not claim to. Gate 132's bootstrap is `org_owner_approved` with
no invite, which is honest and stays that way.

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-02

Gate 136. Demo/dev scope. No production customer claim. No email is sent by this
migration or by anything that reads these columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | Sequence[str] | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INVITES = "nf_membership_invites"
MEMBERSHIPS = "nf_org_memberships"


def upgrade() -> None:
    op.add_column(
        INVITES,
        sa.Column("invited_email_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        MEMBERSHIPS,
        sa.Column("invite_id", sa.String(length=64), nullable=True),
    )
    # A membership that names an invite is looked up by it, and the evidence
    # join is the only reason this column exists.
    op.create_index(
        f"ix_{MEMBERSHIPS}_invite_id",
        MEMBERSHIPS,
        ["invite_id"],
    )

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # A membership claiming an invite must name who invited it. SQLite
        # cannot ALTER a CHECK in without rebuilding the table, and 0025
        # recorded why that trade is not worth it here; the service enforces
        # the same rule on every dialect.
        op.create_check_constraint(
            "ck_nf_org_memberships_invite_names_inviter",
            MEMBERSHIPS,
            "invite_id IS NULL OR invited_by IS NOT NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint(
            "ck_nf_org_memberships_invite_names_inviter",
            MEMBERSHIPS,
            type_="check",
        )
    op.drop_index(f"ix_{MEMBERSHIPS}_invite_id", table_name=MEMBERSHIPS)
    op.drop_column(MEMBERSHIPS, "invite_id")
    op.drop_column(INVITES, "invited_email_fingerprint")
