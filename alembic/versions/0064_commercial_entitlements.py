"""Alembic 0064: the persistent licence, its maintenance, and who may use it.

The Gate 178 survey found no commercial state at all: no licence table, no
maintenance term, no entitlement. What existed was
`tenant_beta_feature_entitlement_service`, which is about BETA FEATURES and
mentions no money - a different question that happens to share a word.

Three tables:

```text
nf_commercial_ledger_events      append-only: what happened, and when
nf_commercial_entitlement_state  derived current state, for the read paths
nf_commercial_benefit_extensions temporary benefit grants
```

## Why a derived table exists at all

The ledger is the truth and replaying it is how the truth is computed. But
178K requires answering "which organisations are frozen" across thousands of
tenants without replaying every history on every request, so the current
state is materialised. That is a cache, and a cache can go stale, which is
why `current_entitlement_disagrees_with_ledger` is one of the nine detectors:
the structure that makes the read fast also makes a new way to be wrong.

## The constraints that carry the gate

`ck_..._extension_duration_is_allowed` - 7, 14 or 30 days. Not 31, not 90.

`ck_..._extension_is_controlling_company` - a customer administrator cannot
extend their own benefits, enforced where no service call can bypass it.

`ck_..._extension_records_its_delinquency` - an extension must record the
maintenance state it did NOT cure. An extension claiming the customer was
current is a lie with a timestamp, and this is the shape that quietly
forgives debt nobody decided to forgive.

`ck_..._expiry_needs_three_years` - a licence may not be recorded as expired
at or below 1095 days of delinquency. The most expensive arithmetic error
this system can make is taking somebody's licence away early.

`ck_..._working_benefits_need_a_reason` - full or extended benefits require
either a live licence state or a named extension. "Active for no reason" is
somebody getting the product free without anyone deciding so.

`ck_..._amounts_are_not_negative` - money is integer cents and never below
zero; a negative forgiveness is a charge wearing a refund's name.

`ck_..._delinquency_is_not_negative` - a negative duration flows into the
three-year arithmetic and expires a licence early.

Preserves 0056 through 0063.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | None = None
depends_on: str | None = None

EVENTS = "nf_commercial_ledger_events"
STATE = "nf_commercial_entitlement_state"
EXTENSIONS = "nf_commercial_benefit_extensions"

EVENT_TYPES = (
    "LICENSE_PURCHASED",
    "MAINTENANCE_TERM_STARTED",
    "MAINTENANCE_PAID",
    "MAINTENANCE_LAPSED_RECORDED",
    "BENEFITS_FROZEN",
    "LICENSE_EXPIRED_RECORDED",
    "EXTENSION_GRANTED",
    "EXTENSION_REVOKED",
    "MAINTENANCE_FORGIVEN",
    "RELICENSED",
    "REACTIVATED",
    "CORRECTION",
)

#: Events that record money changing hands and must carry an amount.
MONETARY_EVENTS = (
    "LICENSE_PURCHASED",
    "MAINTENANCE_PAID",
    "RELICENSED",
    "MAINTENANCE_FORGIVEN",
)

LICENSE_STATES = (
    "LICENSE_NONE",
    "LICENSED_ACTIVE",
    "LICENSED_GRACE",
    "LICENSED_FROZEN",
    "LICENSE_EXPIRED",
)

#: Licence states in which the organisation still holds its licence.
LICENSE_HELD = ("LICENSED_ACTIVE", "LICENSED_GRACE", "LICENSED_FROZEN")

#: Licence states whose benefits stand on the customer's own footing.
LICENSE_SELF_SUPPORTING = ("LICENSED_ACTIVE", "LICENSED_GRACE")

MAINTENANCE_STATES = (
    "MAINTENANCE_NONE",
    "MAINTENANCE_CURRENT",
    "MAINTENANCE_LAPSED",
    "MAINTENANCE_DELINQUENT",
    "MAINTENANCE_FORGIVEN",
)

BENEFIT_STATES = ("BENEFIT_FULL", "BENEFIT_EXTENDED", "BENEFIT_FROZEN", "BENEFIT_NONE")

#: Benefit states in which substantive work is possible.
BENEFIT_WORKING = ("BENEFIT_FULL", "BENEFIT_EXTENDED")

#: Three continuous years, as a fixed day count. Not computed from a
#: leap-aware calendar: 178E requires that a licence never expire because of
#: clock ambiguity, and a fixed count cannot drift by a day depending on
#: which years the delinquency happened to span.
DELINQUENCY_DAYS_BEFORE_EXPIRATION = 1095

CONTROLLING_COMPANY_ADMIN = "CONTROLLING_COMPANY_ADMIN"


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # ---------------- the ledger --------------------------------------
    op.create_table(
        EVENTS,
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=True),
        sa.Column("paid_through", sa.Date(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("corrects_event_id", sa.String(length=64), nullable=True),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            _in_list("event_type", EVENT_TYPES), name=f"ck_{EVENTS}_type"
        ),
        # Money is integer cents and never negative. A negative forgiveness
        # is a charge wearing a refund's name.
        sa.CheckConstraint(
            "amount_cents IS NULL OR amount_cents >= 0",
            name=f"ck_{EVENTS}_amounts_are_not_negative",
        ),
        sa.CheckConstraint(
            f"{_in_list('event_type', MONETARY_EVENTS)} = false "
            "OR amount_cents IS NOT NULL",
            name=f"ck_{EVENTS}_monetary_event_records_an_amount",
        ),
        # A correction is an event, not an edit, and it must say what it
        # corrects and why.
        sa.CheckConstraint(
            "event_type <> 'CORRECTION' OR "
            "(corrects_event_id IS NOT NULL AND reason IS NOT NULL)",
            name=f"ck_{EVENTS}_correction_names_its_target",
        ),
        sa.CheckConstraint(
            "event_type <> 'MAINTENANCE_FORGIVEN' OR reason IS NOT NULL",
            name=f"ck_{EVENTS}_forgiveness_states_a_reason",
        ),
        sa.CheckConstraint(
            "corrects_event_id IS NULL OR corrects_event_id <> event_id",
            name=f"ck_{EVENTS}_no_self_correction",
        ),
    )
    # 178K: licence history, maintenance history, per organisation.
    op.create_index(
        f"ix_{EVENTS}_org_history", EVENTS, ["organization_id", "occurred_at"]
    )
    op.create_index(
        f"ix_{EVENTS}_by_type", EVENTS, ["event_type", "occurred_at"]
    )

    # ---------------- derived current state ---------------------------
    op.create_table(
        STATE,
        sa.Column("organization_id", sa.Text(), primary_key=True),
        # THREE states, kept apart here as in the model.
        sa.Column("license_state", sa.String(length=24), nullable=False),
        sa.Column("maintenance_state", sa.String(length=28), nullable=False),
        sa.Column("benefit_access", sa.String(length=24), nullable=False),
        sa.Column("paid_through", sa.Date(), nullable=True),
        sa.Column("delinquency_days", sa.Integer(), nullable=False),
        sa.Column("days_until_license_expiration", sa.Integer(), nullable=True),
        sa.Column("active_extension_id", sa.String(length=64), nullable=True),
        sa.Column("extension_expires_at", sa.Date(), nullable=True),
        sa.Column("maintenance_forgiven", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            _in_list("license_state", LICENSE_STATES), name=f"ck_{STATE}_license"
        ),
        sa.CheckConstraint(
            _in_list("maintenance_state", MAINTENANCE_STATES),
            name=f"ck_{STATE}_maintenance",
        ),
        sa.CheckConstraint(
            _in_list("benefit_access", BENEFIT_STATES), name=f"ck_{STATE}_benefit"
        ),
        # A negative duration flows into the expiry arithmetic.
        sa.CheckConstraint(
            "delinquency_days >= 0", name=f"ck_{STATE}_delinquency_is_not_negative"
        ),
        # The most expensive arithmetic error this system can make.
        sa.CheckConstraint(
            "license_state <> 'LICENSE_EXPIRED' OR delinquency_days > "
            f"{DELINQUENCY_DAYS_BEFORE_EXPIRATION}",
            name=f"ck_{STATE}_expiry_needs_three_years",
        ),
        # Working benefits need a reason: a live licence, or a named
        # extension. "Active for no reason" is the product given away by
        # nobody's decision.
        sa.CheckConstraint(
            f"{_in_list('benefit_access', BENEFIT_WORKING)} = false "
            f"OR {_in_list('license_state', LICENSE_SELF_SUPPORTING)} "
            "OR active_extension_id IS NOT NULL",
            name=f"ck_{STATE}_working_benefits_need_reason",
        ),
        # An extended benefit must name the extension that justifies it.
        sa.CheckConstraint(
            "benefit_access <> 'BENEFIT_EXTENDED' "
            "OR active_extension_id IS NOT NULL",
            name=f"ck_{STATE}_ext_benefits_name_their_ext",
        ),
    )
    # 178K: the frozen queue, the expiring queue, the expired queue.
    op.create_index(
        f"ix_{STATE}_frozen", STATE, ["benefit_access", "license_state"]
    )
    op.create_index(
        f"ix_{STATE}_expiring", STATE, ["maintenance_state", "paid_through"]
    )
    op.create_index(
        f"ix_{STATE}_expired", STATE, ["license_state", "delinquency_days"]
    )

    # ---------------- temporary benefit extensions --------------------
    op.create_table(
        EXTENSIONS,
        sa.Column("extension_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.Text(), nullable=False),
        sa.Column("granted_by_role", sa.String(length=32), nullable=False),
        sa.Column("granted_at", sa.Date(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        # What was TRUE when it was granted. Recorded so the grant can never
        # be mistaken for a statement that the customer was current.
        sa.Column("underlying_license_state", sa.String(length=24), nullable=False),
        sa.Column(
            "underlying_maintenance_state", sa.String(length=28), nullable=False
        ),
        sa.Column("underlying_delinquency_days", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.Date(), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "duration_days IN (7, 14, 30)",
            name=f"ck_{EXTENSIONS}_ext_duration_is_allowed",
        ),
        # A customer administrator cannot extend their own benefits.
        sa.CheckConstraint(
            f"granted_by_role = '{CONTROLLING_COMPANY_ADMIN}'",
            name=f"ck_{EXTENSIONS}_ext_is_ctrl_co",
        ),
        sa.CheckConstraint(
            "expires_at > granted_at",
            name=f"ck_{EXTENSIONS}_expires_after_it_begins",
        ),
        sa.CheckConstraint(
            "underlying_delinquency_days >= 0",
            name=f"ck_{EXTENSIONS}_delinquency_is_not_negative",
        ),
        # The load-bearing one. An extension is granted to somebody who is
        # NOT current; recording them as current is the lie that quietly
        # forgives a debt nobody decided to forgive.
        sa.CheckConstraint(
            _in_list(
                "underlying_maintenance_state",
                ("MAINTENANCE_LAPSED", "MAINTENANCE_DELINQUENT", "MAINTENANCE_NONE"),
            ),
            name=f"ck_{EXTENSIONS}_ext_records_its_delinq",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_by IS NOT NULL",
            name=f"ck_{EXTENSIONS}_revocation_is_attributed",
        ),
    )
    # 178K: active extensions, and one organisation's extension history.
    op.create_index(
        f"ix_{EXTENSIONS}_active", EXTENSIONS, ["expires_at", "revoked_at"]
    )
    op.create_index(
        f"ix_{EXTENSIONS}_org_history",
        EXTENSIONS,
        ["organization_id", "granted_at"],
    )


def downgrade() -> None:
    op.drop_index(f"ix_{EXTENSIONS}_org_history", table_name=EXTENSIONS)
    op.drop_index(f"ix_{EXTENSIONS}_active", table_name=EXTENSIONS)
    op.drop_table(EXTENSIONS)

    op.drop_index(f"ix_{STATE}_expired", table_name=STATE)
    op.drop_index(f"ix_{STATE}_expiring", table_name=STATE)
    op.drop_index(f"ix_{STATE}_frozen", table_name=STATE)
    op.drop_table(STATE)

    op.drop_index(f"ix_{EVENTS}_by_type", table_name=EVENTS)
    op.drop_index(f"ix_{EVENTS}_org_history", table_name=EVENTS)
    op.drop_table(EVENTS)
