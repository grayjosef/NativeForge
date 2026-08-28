"""Award requirements calendar (Gate 108E).

A compliance calendar for one awarded grant, built from tracked requirement
records.

## Why this is not Gate 91's calendar

`awarded_grant_portfolio_service.build_reporting_calendar` splits requirements
into dated and undated and refuses to compute a date. That rule is right and is
inherited here. What it cannot do is say whether a dated obligation is overdue,
who owns it, or whether anything was filed - because Gate 91's requirements had
no status, owner or proof.

This builds over Gate 108D records, which do.

## Unknown is not "no deadline"

The failure this exists to prevent. A calendar that silently omits requirements
it cannot date shows a tenant a short, clean list and lets a real obligation pass
unnoticed. Absence of a date is not absence of a duty.

So every requirement appears in `calendar_items`. The ones that cannot be dated
carry `calendar_placement: undated` with a reason, and they are counted in
`items_unknown_due_date` where a person can see the number.

## A countdown needs a date somebody can vouch for

`overdue` and `due_soon` are only computed from `verified` or `calculated` due
dates - Gate 108D's `DATE_CALCULABLE_STATUSES`, imported rather than restated.

```text
verified / calculated   a countdown may be computed
estimated               shown, never counted down - an estimate is not a deadline
unknown / unsupported   shown as undated, never treated as "no deadline"
needs_human_review      shown, routed to a person
```

An estimate presented as a countdown is how a tenant misses the real date while
believing they had a week left.

## Projected burden is not on the compliance calendar

A requirement projected from a notice before the award existed is not something
the tenant owes. It is carried in the item list with
`is_active_obligation: False` and excluded from the obligation counts, so it can
be seen without being owed.

## Confidence is measured, not asserted

`calendar_confidence` is derived from the proportion of active obligations
carrying a date somebody can vouch for. A calendar built entirely from estimates
reports low confidence rather than looking identical to one built from award
documents.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from nativeforge.services.award_requirement_model_service import (
    CLOSED_STATUSES,
    DATE_CALCULABLE_STATUSES,
    SUBMITTED_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirements_calendar_v1"

CALENDAR_PLACEMENTS = frozenset({"dated", "undated", "not_an_obligation"})

CALENDAR_CONFIDENCES = frozenset(
    {"no_obligations", "documented", "mixed", "estimated_only", "unknown"}
)

# Inside this many days a dated obligation is "due soon".
DUE_SOON_DAYS = 30

CALENDAR_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "award_id",
    "calendar_items",
    "items_total",
    "items_verified",
    "items_estimated",
    "items_unknown_due_date",
    "items_needing_human_review",
    "items_overdue",
    "items_due_soon",
    "calendar_confidence",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


def build_requirements_calendar(
    *,
    tenant_id: Any,
    award_id: Any,
    requirements: list[dict[str, Any]] | None = None,
    reference_date: Any = None,
) -> dict[str, Any]:
    """Every requirement, placed honestly. Nothing is hidden for tidiness."""
    requirements = list(requirements or [])
    blocked_reasons: list[str] = []

    if not tenant_id:
        blocked_reasons.append("calendar_without_a_tenant")
    if not award_id:
        blocked_reasons.append("calendar_without_an_award")

    today = _parse_date(reference_date)
    if reference_date and today is None:
        blocked_reasons.append("unparseable_reference_date")
    if today is None:
        # No clock is read implicitly. Without a reference date, nothing is
        # counted down - a calendar that invents "now" produces a different
        # answer every run and cannot be attested.
        blocked_reasons.append("no_reference_date_supplied")

    items: list[dict[str, Any]] = []
    for requirement in requirements:
        # Tenant scoping first, so another tenant's requirement can never land
        # on this calendar.
        if str(requirement.get("tenant_id")) != str(tenant_id):
            continue
        if str(requirement.get("award_id")) != str(award_id):
            continue

        date_status = requirement.get("due_date_status")
        due = _parse_date(requirement.get("due_date"))
        calculable = bool(requirement.get("date_is_calculable")) and due is not None
        active = bool(requirement.get("is_active_obligation"))
        status = requirement.get("requirement_status")

        if not active:
            placement = "not_an_obligation"
            placement_reason = (
                "projected_from_a_notice_before_the_award_existed"
                if requirement.get("extraction_status") == "projected_from_nofo"
                else "provenance_does_not_support_an_active_obligation"
            )
        elif calculable:
            placement = "dated"
            placement_reason = ""
        else:
            placement = "undated"
            placement_reason = {
                "estimated": "date_is_an_estimate_not_a_deadline",
                "unknown": "no_date_established",
                "unsupported": "document_could_not_be_read",
                "needs_human_review": "date_needs_human_review",
            }.get(str(date_status), "date_not_supported")

        overdue = False
        due_soon = False
        days_until_due = None
        if placement == "dated" and today is not None and due is not None:
            days_until_due = (due - today).days
            if status not in CLOSED_STATUSES and status not in SUBMITTED_STATUSES:
                overdue = days_until_due < 0
                due_soon = 0 <= days_until_due <= DUE_SOON_DAYS

        items.append(
            _json_safe(
                {
                    "requirement_id": requirement.get("requirement_id"),
                    "requirement_type": requirement.get("requirement_type"),
                    "requirement_title": requirement.get("requirement_title"),
                    "requirement_status": status,
                    "due_date": requirement.get("due_date"),
                    "due_date_status": date_status,
                    "days_until_due": days_until_due,
                    "calendar_placement": placement,
                    "placement_reason": placement_reason,
                    "is_active_obligation": active,
                    "assigned_owner": requirement.get("assigned_owner"),
                    "proof_of_submission_status": requirement.get(
                        "proof_of_submission_status"
                    ),
                    "overdue": overdue,
                    "due_soon": due_soon,
                    "human_review_required": bool(
                        requirement.get("human_review_required")
                    ),
                }
            )
        )

    active_items = [i for i in items if i["is_active_obligation"]]
    dated = [i for i in items if i["calendar_placement"] == "dated"]
    estimated = [i for i in items if i["due_date_status"] == "estimated"]
    unknown_date = [
        i
        for i in items
        if i["due_date_status"] in {"unknown", "unsupported", "needs_human_review"}
    ]

    if not active_items:
        confidence = "no_obligations"
    elif len(dated) == len(active_items):
        confidence = "documented"
    elif dated:
        confidence = "mixed"
    elif estimated:
        confidence = "estimated_only"
    else:
        confidence = "unknown"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "award_id": award_id,
            "reference_date": reference_date,
            "calendar_items": items,
            "items_total": len(items),
            "items_active_obligations": len(active_items),
            "items_not_an_obligation": len(items) - len(active_items),
            "items_verified": sum(
                1 for i in items if i["due_date_status"] == "verified"
            ),
            "items_estimated": len(estimated),
            "items_unknown_due_date": len(unknown_date),
            "items_needing_human_review": sum(
                1 for i in items if i["human_review_required"]
            ),
            "items_overdue": sum(1 for i in items if i["overdue"]),
            "items_due_soon": sum(1 for i in items if i["due_soon"]),
            "items_unassigned": sum(
                1 for i in active_items if not i["assigned_owner"]
            ),
            "calendar_confidence": confidence,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: nothing here is computed from a default or a guess.
            "dates_inferred": 0,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def calendar_invariant_failures(calendar: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if calendar.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in CALENDAR_FIELDS:
        if field not in calendar:
            fails.append(f"calendar_missing_field:{field}")

    for constant in ("fabricated", "live_fetch_performed"):
        if calendar.get(constant) is not False:
            fails.append(f"calendar_claimed:{constant}")
    if calendar.get("dates_inferred") != 0:
        fails.append("calendar_inferred_a_date")

    if calendar.get("calendar_confidence") not in CALENDAR_CONFIDENCES:
        fails.append("calendar_confidence_out_of_vocabulary")

    items = calendar.get("calendar_items") or []
    for item in items:
        if item.get("calendar_placement") not in CALENDAR_PLACEMENTS:
            fails.append("calendar_placement_out_of_vocabulary")

        # A countdown requires a date somebody can vouch for.
        if (item.get("overdue") or item.get("due_soon")) and item.get(
            "due_date_status"
        ) not in DATE_CALCULABLE_STATUSES:
            fails.append(
                f"countdown_on_an_unsupported_date:{item.get('requirement_id')}"
            )

        # An estimate is never a countdown.
        if item.get("due_date_status") == "estimated" and (
            item.get("overdue") or item.get("due_soon")
        ):
            fails.append(f"estimate_counted_down:{item.get('requirement_id')}")

        # A projection is never an obligation on the calendar.
        if item.get("is_active_obligation") and item.get(
            "calendar_placement"
        ) == "not_an_obligation":
            fails.append("active_obligation_placed_as_not_an_obligation")

        # An undated or excluded item must say why.
        if item.get("calendar_placement") in {
            "undated",
            "not_an_obligation",
        } and not item.get("placement_reason"):
            fails.append("placement_without_a_reason")

    # Nothing is dropped for tidiness: every counted class is inside items.
    if calendar.get("items_total") != len(items):
        fails.append("items_total_disagrees_with_the_item_list")

    unknown_counted = sum(
        1
        for i in items
        if i.get("due_date_status")
        in {"unknown", "unsupported", "needs_human_review"}
    )
    if calendar.get("items_unknown_due_date") != unknown_counted:
        fails.append("unknown_due_dates_hidden_from_the_count")

    # Confidence must agree with the measurements.
    active = [i for i in items if i.get("is_active_obligation")]
    dated = [i for i in items if i.get("calendar_placement") == "dated"]
    if not active and calendar.get("calendar_confidence") != "no_obligations":
        fails.append("confidence_claimed_without_obligations")
    if active and dated and len(dated) == len(active):
        if calendar.get("calendar_confidence") != "documented":
            fails.append("confidence_disagrees_with_the_measurements")

    return fails
