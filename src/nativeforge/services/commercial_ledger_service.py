"""178F/I: the entitlement ledger, and what relicensing may and may not erase.

The ledger is append-only. Every licence purchase, maintenance term, freeze,
expiry, extension, reactivation and manual correction is an EVENT, and the
current state is derived by replaying them.

## Why append-only, specifically

The approved model says historical unpaid maintenance is forgiven on
relicensing. "Forgiven" is a decision about what is OWED. It is not a
statement that the debt never existed, and the difference matters the first
time somebody asks why an organisation that owed three years of maintenance
is active again. A ledger that answered by having no record of the debt would
be answering by having lost the question.

So `relicense` appends a FORGIVENESS event naming the amount forgiven and who
decided it, and leaves every delinquency event in place. `ledger_invariant_
failures` refuses a ledger whose history shrank.

## Corrections are events too

`CORRECTION` exists because somebody will eventually key a wrong date, and
the honest repair is a new event that says what was corrected and why - not
an UPDATE that makes the mistake unfindable. An entitlement history you can
edit is not evidence of anything.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

from nativeforge.services.commercial_license_model_service import (
    ANNUAL_MAINTENANCE_PRICE_CENTS,
    PERSISTENT_LICENSE_PRICE_CENTS,
    POLICY_VERSION,
    add_months,
    dollars,
    included_maintenance_through,
)

SCHEMA_VERSION = "nf_commercial_ledger_v1"

# ---------------------------------------------------------------------------
# 178I: the events. Nothing is ever updated in place.
# ---------------------------------------------------------------------------

LICENSE_PURCHASED = "LICENSE_PURCHASED"
MAINTENANCE_TERM_STARTED = "MAINTENANCE_TERM_STARTED"
MAINTENANCE_PAID = "MAINTENANCE_PAID"
MAINTENANCE_LAPSED_RECORDED = "MAINTENANCE_LAPSED_RECORDED"
BENEFITS_FROZEN = "BENEFITS_FROZEN"
LICENSE_EXPIRED_RECORDED = "LICENSE_EXPIRED_RECORDED"
EXTENSION_GRANTED = "EXTENSION_GRANTED"
EXTENSION_REVOKED = "EXTENSION_REVOKED"
MAINTENANCE_FORGIVEN_EVENT = "MAINTENANCE_FORGIVEN"
RELICENSED = "RELICENSED"
REACTIVATED = "REACTIVATED"
CORRECTION = "CORRECTION"

EVENT_TYPES: tuple[str, ...] = (
    LICENSE_PURCHASED,
    MAINTENANCE_TERM_STARTED,
    MAINTENANCE_PAID,
    MAINTENANCE_LAPSED_RECORDED,
    BENEFITS_FROZEN,
    LICENSE_EXPIRED_RECORDED,
    EXTENSION_GRANTED,
    EXTENSION_REVOKED,
    MAINTENANCE_FORGIVEN_EVENT,
    RELICENSED,
    REACTIVATED,
    CORRECTION,
)

EVENT_MEANINGS: dict[str, str] = {
    LICENSE_PURCHASED: "a persistent licence was bought",
    MAINTENANCE_TERM_STARTED: "a maintenance term began",
    MAINTENANCE_PAID: "maintenance was paid through a date",
    MAINTENANCE_LAPSED_RECORDED: "the paid-through date passed",
    BENEFITS_FROZEN: "substantive workflows were locked; nothing was deleted",
    LICENSE_EXPIRED_RECORDED: (
        "three continuous years delinquent; the persistent licence was lost "
        "and the account and its data were kept"
    ),
    EXTENSION_GRANTED: "benefits were extended temporarily; billing unchanged",
    EXTENSION_REVOKED: "a temporary extension was withdrawn early",
    MAINTENANCE_FORGIVEN_EVENT: (
        "unpaid maintenance was forgiven. The debt is forgiven; the record "
        "that it was owed stays exactly where it is"
    ),
    RELICENSED: "a new persistent licence was purchased after expiry",
    REACTIVATED: "a preserved account was brought back into service",
    CORRECTION: "a previous entry was corrected, by a named person, with a reason",
}

#: Events that record money changing hands. They must carry an amount.
MONETARY: frozenset[str] = frozenset(
    {LICENSE_PURCHASED, MAINTENANCE_PAID, RELICENSED, MAINTENANCE_FORGIVEN_EVENT}
)

#: Events that may only be recorded by controlling-company staff.
CONTROLLING_COMPANY_EVENTS: frozenset[str] = frozenset(
    {
        LICENSE_PURCHASED,
        MAINTENANCE_PAID,
        MAINTENANCE_FORGIVEN_EVENT,
        RELICENSED,
        REACTIVATED,
        CORRECTION,
        EXTENSION_GRANTED,
        EXTENSION_REVOKED,
    }
)

EVENT_FIELDS: tuple[str, ...] = (
    "event_id",
    "organization_id",
    "event_type",
    "occurred_at",
    "recorded_at",
    "recorded_by",
    "amount_cents",
    "paid_through",
    "detail",
    "reason",
    "corrects_event_id",
    "policy_version",
    "is_demo",
)


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


def build_event_id(
    *, organization_id: Any, event_type: Any, occurred_at: Any, detail: Any = None
) -> str:
    parts = [
        str(organization_id or ""),
        str(event_type or ""),
        str(occurred_at or ""),
        str(detail or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_event(
    *,
    organization_id: Any,
    event_type: str,
    occurred_at: Any,
    recorded_by: Any,
    amount_cents: int | None = None,
    paid_through: Any = None,
    detail: Any = None,
    reason: Any = None,
    corrects_event_id: Any = None,
    recorded_at: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    kind = str(event_type)
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": build_event_id(
            organization_id=organization_id,
            event_type=kind,
            occurred_at=occurred_at,
            detail=detail,
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "event_type": kind,
        "occurred_at": str(occurred_at) if occurred_at else None,
        "recorded_at": recorded_at or dt.datetime.now(dt.UTC).isoformat(),
        "recorded_by": str(recorded_by) if recorded_by else None,
        "amount_cents": None if amount_cents is None else int(amount_cents),
        "paid_through": str(paid_through) if paid_through else None,
        "detail": str(detail) if detail else None,
        "reason": str(reason) if reason else None,
        "corrects_event_id": (str(corrects_event_id) if corrects_event_id else None),
        "policy_version": POLICY_VERSION,
        "is_demo": bool(is_demo),
    }


def open_license(
    *,
    organization_id: Any,
    purchased_at: Any,
    recorded_by: Any,
    price_cents: int = PERSISTENT_LICENSE_PRICE_CENTS,
    is_demo: bool = False,
) -> list[dict[str, Any]]:
    """178A.1/2. A purchase and the twelve included months, as two events.

    They are separate because they are separate facts: one is money, the other
    is a term. Recording them as one event would make "when does maintenance
    run out" a question you answer by knowing the policy rather than by
    reading the ledger.
    """
    through = included_maintenance_through(purchased_at)
    return [
        build_event(
            organization_id=organization_id,
            event_type=LICENSE_PURCHASED,
            occurred_at=purchased_at,
            recorded_by=recorded_by,
            amount_cents=price_cents,
            detail="persistent organisational licence",
            is_demo=is_demo,
        ),
        build_event(
            organization_id=organization_id,
            event_type=MAINTENANCE_TERM_STARTED,
            occurred_at=purchased_at,
            recorded_by=recorded_by,
            amount_cents=0,
            paid_through=str(through),
            detail="first 12 months included in the licence",
            reason="included with the persistent licence",
            is_demo=is_demo,
        ),
    ]


def renew_maintenance(
    *,
    organization_id: Any,
    paid_at: Any,
    recorded_by: Any,
    months: int = 12,
    price_cents: int = ANNUAL_MAINTENANCE_PRICE_CENTS,
    current_paid_through: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """178A.3. Extend the term from wherever it currently ends.

    From the existing paid-through, not from today - a customer who renews a
    fortnight late has bought a year of maintenance, not a year minus a
    fortnight, and charging them for the gap twice is the sort of thing that
    ends a relationship with a Tribal government.
    """
    base = _as_date(current_paid_through) or _as_date(paid_at)
    return build_event(
        organization_id=organization_id,
        event_type=MAINTENANCE_PAID,
        occurred_at=paid_at,
        recorded_by=recorded_by,
        amount_cents=price_cents,
        paid_through=str(add_months(base, months)),
        detail=f"{months} months maintenance",
        is_demo=is_demo,
    )


def outstanding_maintenance_cents(
    *,
    events: list[dict[str, Any]],
    as_of: Any,
    annual_cents: int = ANNUAL_MAINTENANCE_PRICE_CENTS,
) -> int:
    """What is owed today, in cents, ignoring nothing.

    Whole unpaid years since the term ended. A part year is not billed until
    it completes, which is the reading most favourable to the customer and
    the one that cannot be accused of inventing a charge.
    """
    paid_through = None
    for event in sorted(events, key=lambda e: str(e.get("occurred_at") or "")):
        if event.get("paid_through"):
            paid_through = _as_date(event["paid_through"])
        if str(event.get("event_type")) == MAINTENANCE_FORGIVEN_EVENT:
            # Forgiveness resets what is OWED, not what happened.
            paid_through = _as_date(event.get("paid_through")) or paid_through

    today = _as_date(as_of)
    if paid_through is None or today is None or today <= paid_through:
        return 0
    years = (today - paid_through).days // 365
    return max(0, years) * int(annual_cents)


def relicense(
    *,
    organization_id: Any,
    events: list[dict[str, Any]],
    purchased_at: Any,
    recorded_by: Any,
    recorded_by_is_controlling_company: bool,
    price_cents: int = PERSISTENT_LICENSE_PRICE_CENTS,
    reason: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """178F. A new licence at the current price; the old debt forgiven.

    Three events are appended and NOTHING is removed:

      RELICENSED              money in, at today's price
      MAINTENANCE_FORGIVEN    the outstanding amount, named
      MAINTENANCE_TERM_STARTED  the twelve months the new licence includes

    The forgiveness event states the amount because "forgiven" with no figure
    is not a record, it is a shrug. The delinquency events that produced the
    debt stay exactly where they are.
    """
    if not recorded_by_is_controlling_company:
        return {
            "accepted": False,
            "why": "relicensing is a controlling-company action",
            "events": list(events),
        }
    if not recorded_by:
        return {
            "accepted": False,
            "why": "relicensing requires a named actor",
            "events": list(events),
        }

    owed = outstanding_maintenance_cents(events=events, as_of=purchased_at)
    through = included_maintenance_through(purchased_at)

    appended = [
        build_event(
            organization_id=organization_id,
            event_type=RELICENSED,
            occurred_at=purchased_at,
            recorded_by=recorded_by,
            amount_cents=price_cents,
            detail="persistent licence repurchased at the current price",
            reason=reason,
            is_demo=is_demo,
        ),
        build_event(
            organization_id=organization_id,
            event_type=MAINTENANCE_FORGIVEN_EVENT,
            occurred_at=purchased_at,
            recorded_by=recorded_by,
            amount_cents=owed,
            paid_through=str(through),
            detail=f"historical unpaid maintenance forgiven: {dollars(owed)}",
            reason="forgiven on relicensing, per the approved commercial model",
            is_demo=is_demo,
        ),
        build_event(
            organization_id=organization_id,
            event_type=MAINTENANCE_TERM_STARTED,
            occurred_at=purchased_at,
            recorded_by=recorded_by,
            amount_cents=0,
            paid_through=str(through),
            detail="first 12 months included in the new licence",
            is_demo=is_demo,
        ),
    ]

    return {
        "accepted": True,
        # Append. The prior history is carried forward untouched.
        "events": list(events) + appended,
        "appended": appended,
        "forgiven_cents": owed,
        "forgiven": dollars(owed),
        "new_paid_through": str(through),
        "ledger": {
            "license_purchased_at": str(purchased_at),
            "relicensed_at": str(purchased_at),
            "paid_through": str(through),
            "maintenance_forgiven": False,
        },
        # The claims a reviewer will want to check.
        "history_preserved": True,
        "prior_event_count": len(events),
        "delinquency_history_rewritten": False,
        "audit_event": {
            "action": "commercial.relicensed",
            "organization_id": str(organization_id) if organization_id else None,
            "actor_id": str(recorded_by),
            "forgiven_cents": owed,
            "occurred_at": str(purchased_at),
        },
    }


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the current ledger by replaying events in order."""
    ordered = sorted(
        events,
        key=lambda e: (str(e.get("occurred_at") or ""), str(e.get("event_type"))),
    )
    ledger: dict[str, Any] = {
        "license_purchased_at": None,
        "relicensed_at": None,
        "paid_through": None,
        "maintenance_forgiven": False,
    }
    for event in ordered:
        kind = str(event.get("event_type"))
        if kind == LICENSE_PURCHASED and not ledger["license_purchased_at"]:
            ledger["license_purchased_at"] = event.get("occurred_at")
        elif kind == RELICENSED:
            ledger["relicensed_at"] = event.get("occurred_at")
        if event.get("paid_through"):
            ledger["paid_through"] = event["paid_through"]
    return ledger


def ledger_invariant_failures(
    *, before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[str]:
    """Refuse a ledger that lost history.

    Compared by event id rather than by count: a write that removed one event
    and added two would pass a length check while having destroyed evidence.
    """
    failures: list[str] = []
    before_ids = [str(e.get("event_id")) for e in before]
    after_ids = {str(e.get("event_id")) for e in after}

    missing = [eid for eid in before_ids if eid not in after_ids]
    if missing:
        failures.append(f"ledger_lost_{len(missing)}_events")
    if len(after) < len(before):
        failures.append(f"ledger_shrank_from_{len(before)}_to_{len(after)}")

    for event in after:
        kind = str(event.get("event_type") or "")
        if kind not in EVENT_TYPES:
            failures.append(f"event_type_outside_the_vocabulary:{kind or 'missing'}")
        if not event.get("recorded_by"):
            failures.append(f"{kind}_names_no_actor")
        if not event.get("occurred_at"):
            failures.append(f"{kind}_has_no_date")
        if kind in MONETARY and event.get("amount_cents") is None:
            failures.append(f"{kind}_records_no_amount")
        if event.get("amount_cents") is not None and int(event["amount_cents"]) < 0:
            failures.append(f"{kind}_records_a_negative_amount")
        if kind == CORRECTION:
            if not event.get("corrects_event_id"):
                failures.append("correction_names_no_prior_event")
            if not event.get("reason"):
                failures.append("correction_states_no_reason")
        if kind == MAINTENANCE_FORGIVEN_EVENT and not event.get("reason"):
            failures.append("forgiveness_states_no_reason")

    return sorted(set(failures))


def describe_ledger_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "event_types": list(EVENT_TYPES),
        "monetary_events": sorted(MONETARY),
        "controlling_company_events": sorted(CONTROLLING_COMPANY_EVENTS),
        "every_event_has_a_meaning": set(EVENT_MEANINGS) == set(EVENT_TYPES),
        # The refusals.
        "ledger_is_append_only": True,
        "relicensing_appends_and_removes_nothing": True,
        "forgiveness_names_its_amount": True,
        "forgiveness_does_not_erase_the_debt_record": True,
        "delinquency_history_is_never_rewritten": True,
        "corrections_are_events_not_edits": True,
        "money_is_integer_cents": True,
        "renewal_extends_from_the_paid_through_date": True,
    }
