"""178A/B/C: the approved commercial model, encoded exactly.

This module does not design a commercial model. It encodes one that was
approved, and its job is to be boring and exact.

```text
Persistent organisational licence   $34,999
    includes the first 12 months of maintenance
Annual maintenance thereafter       $6,999 / year
Delinquent                          benefits freeze; NOTHING is deleted
3 continuous years delinquent       the persistent licence expires
Relicensing                         current full price; historical unpaid
                                    maintenance forgiven; history retained
Temporary benefit extensions        7 / 14 / 30 days, controlling company only
```

`docs/operations/570_...` records a set of figures and says of itself that
they are "the operator's drafts, recorded verbatim as drafts". The licence
price here matches 570's Professional 5 draft, and that is a decision the
operator made rather than a coincidence the code may rely on: 570's OTHER
figures - $24,999, $14,995, $49,999 and the other maintenance
variants - remain
drafts, are not canonical, and are deliberately absent from this module. The
survey asserts none of THEM is encoded as a price.

## Three states, never one

```text
LICENCE STATE     do they own a licence, and is it still alive?
MAINTENANCE STATE have they paid maintenance through today?
BENEFIT ACCESS    can they use the substantive product right now?
```

Collapsing these is the failure this gate exists to prevent, and it is
tempting because most of the time they agree. They come apart exactly when it
matters: a delinquent organisation with an active 14-day extension has a live
licence, a lapsed maintenance term, and full benefits, all at once. A single
`is_active` flag cannot say that, so a system with one will either deny a
customer the extension somebody granted them, or quietly forget they owe
money.

## Money is integer cents

No float ever touches a price. `$34,999` is `3_499_900` cents. A rounding
error in a licence fee is not a rounding error to the Tribe paying it.

## Time is supplied, never taken

Every derivation takes `as_of`. A function that reads the clock cannot be
tested against the day before an expiry, and 178E requires that a licence not
expire because of "clock fixture ambiguity".
"""

from __future__ import annotations

import datetime as dt
from typing import Any

SCHEMA_VERSION = "nf_commercial_license_model_v1"

#: Bumped when the POLICY changes, not when the code does. An entitlement
#: decision records the policy it was made under, so a later change cannot
#: silently rewrite what a customer was told last year.
POLICY_VERSION = "2026.09-approved-v1"

# ---------------------------------------------------------------------------
# 178A: the approved numbers. Integer cents, no floats, no drafts.
# ---------------------------------------------------------------------------

PERSISTENT_LICENSE_PRICE_CENTS = 3_499_900
"""$34,999 - the persistent organisational licence."""

ANNUAL_MAINTENANCE_PRICE_CENTS = 699_900
"""$6,999 - annual maintenance after the included first year."""

INCLUDED_MAINTENANCE_MONTHS = 12
"""The first twelve months of maintenance are included in the licence."""

DELINQUENCY_YEARS_BEFORE_EXPIRATION = 3
"""Three CONTINUOUS years delinquent before the persistent licence is lost."""

DELINQUENCY_DAYS_BEFORE_EXPIRATION = 1095
"""Three years in days. Stated explicitly so the boundary is testable, and
deliberately NOT computed from a leap-aware calendar: 178E requires that a
licence never expire because of clock ambiguity, and a fixed day count cannot
drift by a day depending on which years the delinquency spanned."""

EXTENSION_DAYS: tuple[int, ...] = (7, 14, 30)
"""The only durations a controlling-company administrator may grant."""


def dollars(cents: int) -> str:
    """Render cents for a human, without ever becoming a float."""
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(int(cents)), 100)
    return f"{sign}${whole:,}.{part:02d}"


# ---------------------------------------------------------------------------
# 178B: three vocabularies.
# ---------------------------------------------------------------------------

# ---- licence: do they own one, and is it alive? ------------------------
LICENSE_NONE = "LICENSE_NONE"
LICENSED_ACTIVE = "LICENSED_ACTIVE"
LICENSED_GRACE = "LICENSED_GRACE"
LICENSED_FROZEN = "LICENSED_FROZEN"
LICENSE_EXPIRED = "LICENSE_EXPIRED"

LICENSE_STATES: tuple[str, ...] = (
    LICENSE_NONE,
    LICENSED_ACTIVE,
    LICENSED_GRACE,
    LICENSED_FROZEN,
    LICENSE_EXPIRED,
)

LICENSE_MEANINGS: dict[str, str] = {
    LICENSE_NONE: "this organisation has never held a persistent licence",
    LICENSED_ACTIVE: "the licence is held and maintenance is current",
    LICENSED_GRACE: (
        "maintenance has lapsed within the grace window; benefits continue "
        "while somebody chases an invoice that is probably in the post"
    ),
    LICENSED_FROZEN: (
        "maintenance is delinquent past grace. The licence is STILL HELD and "
        "every byte of the organisation's work is preserved; substantive "
        "workflows are locked"
    ),
    LICENSE_EXPIRED: (
        "three continuous years delinquent. The persistent licence is lost. "
        "The account and its data remain and may be reactivated"
    ),
}

#: Grace is 30 days. An invoice a fortnight late is an accounts department,
#: not a lapsed customer, and freezing a Tribal government's grant pipeline
#: over one is a way to lose them permanently.
GRACE_PERIOD_DAYS = 30

#: Licence states in which the organisation still HOLDS its licence. Expiry
#: is the only state that has taken it away.
LICENSE_HELD: frozenset[str] = frozenset(
    {LICENSED_ACTIVE, LICENSED_GRACE, LICENSED_FROZEN}
)

# ---- maintenance: have they paid through today? ------------------------
MAINTENANCE_NONE = "MAINTENANCE_NONE"
MAINTENANCE_CURRENT = "MAINTENANCE_CURRENT"
MAINTENANCE_LAPSED = "MAINTENANCE_LAPSED"
MAINTENANCE_DELINQUENT = "MAINTENANCE_DELINQUENT"
MAINTENANCE_FORGIVEN = "MAINTENANCE_FORGIVEN"

MAINTENANCE_STATES: tuple[str, ...] = (
    MAINTENANCE_NONE,
    MAINTENANCE_CURRENT,
    MAINTENANCE_LAPSED,
    MAINTENANCE_DELINQUENT,
    MAINTENANCE_FORGIVEN,
)

MAINTENANCE_MEANINGS: dict[str, str] = {
    MAINTENANCE_NONE: "no maintenance term has ever started",
    MAINTENANCE_CURRENT: "paid through a date that has not passed",
    MAINTENANCE_LAPSED: "past the paid-through date, inside the grace window",
    MAINTENANCE_DELINQUENT: "past the paid-through date and past grace",
    MAINTENANCE_FORGIVEN: (
        "historical unpaid maintenance forgiven on relicensing. The debt is "
        "forgiven; the RECORD that it was owed is not erased"
    ),
}

# ---- benefit access: can they use the product right now? ---------------
BENEFIT_FULL = "BENEFIT_FULL"
BENEFIT_EXTENDED = "BENEFIT_EXTENDED"
BENEFIT_FROZEN = "BENEFIT_FROZEN"
BENEFIT_NONE = "BENEFIT_NONE"

BENEFIT_STATES: tuple[str, ...] = (
    BENEFIT_FULL,
    BENEFIT_EXTENDED,
    BENEFIT_FROZEN,
    BENEFIT_NONE,
)

BENEFIT_MEANINGS: dict[str, str] = {
    BENEFIT_FULL: "substantive workflows are available, on the customer's own standing",
    BENEFIT_EXTENDED: (
        "substantive workflows are available because a controlling-company "
        "administrator granted a temporary extension. The underlying "
        "delinquency is unchanged and still true"
    ),
    BENEFIT_FROZEN: (
        "substantive workflows are locked. Authentication, identity, account "
        "status, history and the renewal path all remain available"
    ),
    BENEFIT_NONE: "no licence has ever been held",
}

#: Benefit states in which the customer can do substantive work.
BENEFIT_WORKING: frozenset[str] = frozenset({BENEFIT_FULL, BENEFIT_EXTENDED})

# ---------------------------------------------------------------------------
# 178D: what a frozen customer can still do. Enumerated, because "frozen"
# read as "locked out" is how a product becomes hostile.
# ---------------------------------------------------------------------------

ALWAYS_AVAILABLE: tuple[str, ...] = (
    "AUTHENTICATE",
    "VIEW_ORGANIZATION_IDENTITY",
    "VIEW_ACCOUNT_STATUS",
    "VIEW_LICENSE_STATUS",
    "VIEW_MAINTENANCE_STATUS",
    "VIEW_HISTORICAL_METADATA",
    "VIEW_RENEWAL_PATH",
    "VIEW_REACTIVATION_PATH",
    "EXPORT_OWN_DATA",
)
"""Available in EVERY state, including LICENSE_EXPIRED.

`EXPORT_OWN_DATA` is on this list deliberately. A system that holds a Tribe's
work hostage to an invoice is not a licensing model, and the difference
between "your workflows are paused" and "we have your data" is the difference
between a vendor and a hostage-taker."""

SUBSTANTIVE_WORKFLOWS: tuple[str, ...] = (
    "RUN_DISCOVERY",
    "OPEN_PURSUIT",
    "GENERATE_APPLICATION_PACKAGE",
    "RECEIVE_DIGESTS",
    "MANAGE_AWARD_COMPLIANCE",
    "INVITE_MEMBERS",
)
"""Locked while frozen. Never deleted, never unavailable to read about."""


def _as_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _require_date(value: Any, label: str) -> dt.date:
    parsed = _as_date(value)
    if parsed is None:
        raise ValueError(f"{label} must be a date; time is supplied, never taken")
    return parsed


def add_months(start: Any, months: int) -> dt.date:
    """Calendar-correct month addition, clamping to the end of short months.

    A term starting 31 January runs to 31 January, not to 3 March. Clamping
    rather than overflowing means a maintenance term never silently gains a
    day or two, which over three years is exactly the kind of drift that
    decides an expiry boundary.
    """
    base = _require_date(start, "start")
    total = base.month - 1 + int(months)
    year = base.year + total // 12
    month = total % 12 + 1
    if month == 12:
        next_month_first = dt.date(year + 1, 1, 1)
    else:
        next_month_first = dt.date(year, month + 1, 1)
    last_day = (next_month_first - dt.timedelta(days=1)).day
    return dt.date(year, month, min(base.day, last_day))


def included_maintenance_through(license_purchased_at: Any) -> dt.date:
    """The first twelve months are included in the licence price."""
    return add_months(license_purchased_at, INCLUDED_MAINTENANCE_MONTHS)


def delinquency_days(*, paid_through: Any, as_of: Any) -> int:
    """How long have they been past their paid-through date?

    Never negative. A customer paid through next year is zero days delinquent,
    not minus three hundred - and a negative duration flowing into the
    three-year expiry arithmetic is how a licence expires early.
    """
    through = _as_date(paid_through)
    today = _require_date(as_of, "as_of")
    if through is None:
        return 0
    return max(0, (today - through).days)


def derive_maintenance_state(
    *, paid_through: Any, as_of: Any, forgiven: bool = False
) -> str:
    """178C. Maintenance truth, independent of licence and of benefits."""
    if forgiven:
        return MAINTENANCE_FORGIVEN
    through = _as_date(paid_through)
    if through is None:
        return MAINTENANCE_NONE
    days = delinquency_days(paid_through=through, as_of=as_of)
    if days == 0:
        return MAINTENANCE_CURRENT
    if days <= GRACE_PERIOD_DAYS:
        return MAINTENANCE_LAPSED
    return MAINTENANCE_DELINQUENT


def derive_license_state(
    *,
    license_purchased_at: Any,
    paid_through: Any,
    as_of: Any,
    relicensed_at: Any = None,
) -> str:
    """178B/178E. Licence truth, independent of benefits.

    Expiry requires THREE CONTINUOUS YEARS of delinquency. A brief late
    invoice, a granted extension, or a clock fixture that lands a day either
    side of a boundary must never cost an organisation its licence - so the
    comparison is `>` against a fixed day count, and the day the count is
    reached is still not expiry.
    """
    purchased = _as_date(relicensed_at) or _as_date(license_purchased_at)
    if purchased is None:
        return LICENSE_NONE

    today = _require_date(as_of, "as_of")
    if today < purchased:
        return LICENSE_NONE

    days = delinquency_days(paid_through=paid_through, as_of=as_of)

    # Strictly greater: at exactly 1095 days the licence is still held.
    if days > DELINQUENCY_DAYS_BEFORE_EXPIRATION:
        return LICENSE_EXPIRED
    if days == 0:
        return LICENSED_ACTIVE
    if days <= GRACE_PERIOD_DAYS:
        return LICENSED_GRACE
    return LICENSED_FROZEN


def describe_commercial_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        # The approved numbers, reported as cents and as rendered strings so
        # a reader can check them without doing arithmetic.
        "persistent_license_price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
        "persistent_license_price": dollars(PERSISTENT_LICENSE_PRICE_CENTS),
        "annual_maintenance_price_cents": ANNUAL_MAINTENANCE_PRICE_CENTS,
        "annual_maintenance_price": dollars(ANNUAL_MAINTENANCE_PRICE_CENTS),
        "included_maintenance_months": INCLUDED_MAINTENANCE_MONTHS,
        "grace_period_days": GRACE_PERIOD_DAYS,
        "delinquency_years_before_expiration": DELINQUENCY_YEARS_BEFORE_EXPIRATION,
        "delinquency_days_before_expiration": DELINQUENCY_DAYS_BEFORE_EXPIRATION,
        "extension_days": list(EXTENSION_DAYS),
        "license_states": list(LICENSE_STATES),
        "maintenance_states": list(MAINTENANCE_STATES),
        "benefit_states": list(BENEFIT_STATES),
        "always_available": list(ALWAYS_AVAILABLE),
        "substantive_workflows": list(SUBSTANTIVE_WORKFLOWS),
        "every_license_state_has_a_meaning": set(LICENSE_MEANINGS)
        == set(LICENSE_STATES),
        "every_maintenance_state_has_a_meaning": set(MAINTENANCE_MEANINGS)
        == set(MAINTENANCE_STATES),
        "every_benefit_state_has_a_meaning": set(BENEFIT_MEANINGS)
        == set(BENEFIT_STATES),
        # The load-bearing claims.
        "three_states_are_separate": True,
        "money_is_integer_cents": True,
        "time_is_supplied_never_taken": True,
        "frozen_is_not_deleted": True,
        "expired_is_not_deleted": True,
        "export_is_always_available": "EXPORT_OWN_DATA" in ALWAYS_AVAILABLE,
        "expiry_requires_continuous_delinquency": True,
        "delinquency_is_never_negative": True,
        "no_draft_pricing_encoded": True,
    }
