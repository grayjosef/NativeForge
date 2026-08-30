"""Awarded grants persistence validation (Gate 124D).

Is a stored award fit to drive obligation tracking — without turning an
uncertain award fact into an obligation somebody is held to.

## The distinction the whole service exists for

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
```

Gate 91 built `pursuit_reporting_burden_projection_service`, in which every
field is prefixed `projected_` and every result carries
`is_active_obligation: False`. That refusal is one-directional and this service
is the other end of it: nothing here promotes a projection, and
`projected_burden_considered` is a constant `False` with an invariant behind it.

## Obligations need established facts

```text
active_obligation_status = obligations_established
  requires fact_status in {verified, tenant_supplied}
```

An award nobody has established cannot oblige anybody. The database enforces
this too (`ck_nf_awarded_grants_obligations_need_established_facts`), because a
row asserting an obligation on an unverified award is a compliance calendar
built on a guess.

`demo_fixture` is deliberately excluded from the established set — Gate 103's
rule, and the reason the status vocabulary exists.

## A claim is not a derivation

Two fields, because they answer two questions:

```text
obligations_claimed      the row says `obligations_established`
obligations_established  and every condition for that actually holds
```

The first is what somebody wrote down. The second is a conjunction — the claim,
established facts, a capable extraction, and a live award — and it is `False`
whenever any of them is missing.

Collapsing the two is the defect this campaign keeps finding: a field named for
a capability that reports a *declaration*. Kept apart, the invariants below
become statements this service can never violate, rather than validation rules
that fire on ordinary bad input.

## An amount is money, and unknown money stays unknown

```text
award_amount   None      -> fact_status must be unestablished
award_amount   250000.00 -> a currency is required alongside
```

Nothing infers an amount. An award whose value nobody has confirmed is recorded
as unknown and flagged for human review, rather than defaulting to zero — a zero
in a funding column reads as a real number to everything downstream.

## A period that ends before it starts is refused

Not clamped, not swapped, not warned about. A reversed period is a data-entry
error, and the two plausible corrections (swap them, or trust one) are both
guesses about which end was mistyped.

## Lineage is lineage

`source_pursuit_id` and `source_opportunity_id` say where an award came from.
They are validated for shape and nothing else: an award is never created because
a pursuit exists, and `award_created_from_lineage` is a constant `False`.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from nativeforge.services.awarded_grant_record_service import (
    AWARD_STATUSES,
    LIVE_AWARD_STATUSES,
    OBLIGATION_CAPABLE_EXTRACTION,
    REQUIREMENTS_EXTRACTION_STATUSES,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
    UNESTABLISHED_FACT_STATUSES,
)

SCHEMA_VERSION = "nf_awarded_grants_persistence_validation_v1"

# What this award obliges the tenant to do, now. Never derived from a pursuit.
ACTIVE_OBLIGATION_STATUSES = frozenset(
    {
        "no_obligations_established",
        "obligations_established",
        "obligations_closed",
        "needs_human_review",
        "unknown",
    }
)

# The one obligation status that asserts a live duty. It needs established
# facts behind it, and the database agrees.
OBLIGATING_STATUSES = frozenset({"obligations_established"})

# ISO 4217 is three letters. Anything else is a symbol somebody typed.
CURRENCY_LENGTH = 3

VALIDATION_FIELDS: tuple[str, ...] = (
    "award_title_present",
    "award_status_valid",
    "active_obligation_status_valid",
    "period_dates_valid",
    "award_amount_valid_or_unknown",
    "fact_status_valid",
    "lineage_only_fields_valid",
    "human_review_required",
    "unknowns_labelled",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def validate_awarded_grant(
    *,
    award_title: Any = None,
    award_status: Any = None,
    active_obligation_status: Any = None,
    fact_status: Any = None,
    award_amount: Any = None,
    award_currency: Any = None,
    period_start: Any = None,
    period_end: Any = None,
    source_pursuit_id: Any = None,
    source_opportunity_id: Any = None,
    requirements_extraction_status: Any = None,
) -> dict[str, Any]:
    """Is this award fit to be stored and acted on? Deny by default.

    Nothing here infers. An award status is not derived from a pursuit, an
    amount is not derived from anything, and an obligation is not derived from a
    projection.
    """
    blocked_reasons: list[str] = []
    unknown_fields: list[str] = []

    # -- the title, the one thing that cannot be unknown ---------------------
    title = str(award_title or "").strip()
    award_title_present = bool(title)
    if not award_title_present:
        blocked_reasons.append("award_without_a_title")

    # -- the award's own status ----------------------------------------------
    status = str(award_status or "unknown").strip().lower()
    award_status_valid = status in AWARD_STATUSES
    if not award_status_valid:
        blocked_reasons.append(f"award_status_not_recognised:{status}")
    if status == "unknown":
        unknown_fields.append("award_status")
        # Not inferred from a pursuit reaching "submitted", or from anything
        # else. Named so the refusal is inspectable.
        blocked_reasons.append("award_status_unestablished_and_never_inferred")

    # -- the fact status behind all of it ------------------------------------
    fact = str(fact_status or "unknown").strip().lower()
    fact_status_valid = fact in FACT_STATUSES
    if not fact_status_valid:
        blocked_reasons.append(f"fact_status_not_recognised:{fact}")
    facts_established = fact in ACTIONABLE_FACT_STATUSES

    # -- the obligation, which is separate from the status -------------------
    obligation = str(active_obligation_status or "unknown").strip().lower()
    active_obligation_status_valid = obligation in ACTIVE_OBLIGATION_STATUSES
    if not active_obligation_status_valid:
        blocked_reasons.append(f"active_obligation_status_not_recognised:{obligation}")
    if obligation == "unknown":
        unknown_fields.append("active_obligation_status")

    obligations_claimed = obligation in OBLIGATING_STATUSES

    if obligations_claimed and not facts_established:
        # The constraint the database also enforces. A compliance calendar
        # built on a guess is worse than no calendar.
        blocked_reasons.append(
            "obligations_established_requires_verified_or_tenant_supplied_facts"
        )

    # An obligation on an award that is not live is a contradiction: a closed or
    # cancelled award obliges nobody.
    if obligations_claimed and status not in LIVE_AWARD_STATUSES:
        blocked_reasons.append(f"obligations_established_on_a_non_live_award:{status}")

    # -- how the requirements got there, if they did -------------------------
    extraction = str(requirements_extraction_status or "not_attempted").strip()
    if extraction not in REQUIREMENTS_EXTRACTION_STATUSES:
        blocked_reasons.append(
            f"requirements_extraction_status_not_recognised:{extraction}"
        )
    obligation_capable = extraction in OBLIGATION_CAPABLE_EXTRACTION
    if obligations_claimed and not obligation_capable:
        # Gate 108's rule: only a human entry or an evidence extraction can
        # produce an obligation. `not_attempted` and `unsupported_document_type`
        # cannot.
        blocked_reasons.append(
            f"obligations_established_without_a_capable_extraction:{extraction}"
        )

    # -- the money -----------------------------------------------------------
    amount = _as_amount(award_amount)
    currency = str(award_currency or "").strip().upper()
    amount_supplied = award_amount not in (None, "")

    if amount_supplied and amount is None:
        blocked_reasons.append("award_amount_is_not_a_number")
    if amount is not None and amount < 0:
        blocked_reasons.append("award_amount_is_negative")
    if (amount is not None) != bool(currency):
        # Money without a currency is a number; a currency without money is a
        # preference. Both or neither.
        blocked_reasons.append("award_amount_and_currency_must_both_be_present")
    if currency and len(currency) != CURRENCY_LENGTH:
        blocked_reasons.append(f"award_currency_is_not_a_three_letter_code:{currency}")

    if amount is None:
        unknown_fields.append("award_amount")
        if fact not in UNESTABLISHED_FACT_STATUSES and fact != "demo_fixture":
            # An unknown amount cannot sit on an award claiming settled facts.
            blocked_reasons.append(
                "unknown_award_amount_cannot_carry_an_established_fact_status"
            )

    award_amount_valid_or_unknown = bool(
        (amount is None and "award_amount" in unknown_fields)
        or (amount is not None and amount >= 0 and len(currency) == CURRENCY_LENGTH)
    )

    # -- the period ----------------------------------------------------------
    start = _as_date(period_start)
    end = _as_date(period_end)
    if period_start not in (None, "") and start is None:
        blocked_reasons.append("period_start_is_not_an_iso_date")
    if period_end not in (None, "") and end is None:
        blocked_reasons.append("period_end_is_not_an_iso_date")

    reversed_period = bool(start and end and end < start)
    if reversed_period:
        # Refused, not clamped and not swapped: both plausible corrections are
        # guesses about which end was mistyped.
        blocked_reasons.append("period_end_is_before_period_start")

    period_dates_valid = bool(
        not reversed_period
        and (period_start in (None, "") or start is not None)
        and (period_end in (None, "") or end is not None)
    )
    if start is None and end is None:
        unknown_fields.append("period")

    # -- lineage, which is lineage -------------------------------------------
    pursuit_id = str(source_pursuit_id or "").strip()
    opportunity_id = str(source_opportunity_id or "").strip()
    lineage_only_fields_valid = True
    if len(pursuit_id) > 255 or len(opportunity_id) > 255:
        lineage_only_fields_valid = False
        blocked_reasons.append("lineage_identifier_is_implausibly_long")

    # -- the derived obligation ----------------------------------------------
    # Every conjunct, or False. A claim on its own establishes nothing.
    obligations_established = bool(
        obligations_claimed
        and active_obligation_status_valid
        and facts_established
        and obligation_capable
        and award_status_valid
        and status in LIVE_AWARD_STATUSES
    )

    # -- what none of it settles ---------------------------------------------
    unknowns_labelled = True
    human_review_required = bool(
        unknown_fields or blocked_reasons or not facts_established
    )

    award_ready_for_obligation_tracking = bool(
        award_title_present
        and award_status_valid
        and status in LIVE_AWARD_STATUSES
        and active_obligation_status_valid
        and obligations_established
        and period_dates_valid
        and award_amount_valid_or_unknown
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "award_title_present": award_title_present,
            "award_status": status,
            "award_status_valid": award_status_valid,
            "award_is_live": status in LIVE_AWARD_STATUSES,
            "active_obligation_status": obligation,
            "active_obligation_status_valid": active_obligation_status_valid,
            "obligations_claimed": obligations_claimed,
            "obligations_established": obligations_established,
            "requirements_extraction_status": extraction,
            "obligation_capable_extraction": obligation_capable,
            "period_dates_valid": period_dates_valid,
            "period_start": start.isoformat() if start else None,
            "period_end": end.isoformat() if end else None,
            "award_amount_valid_or_unknown": award_amount_valid_or_unknown,
            "award_amount_known": amount is not None,
            "award_currency": currency or None,
            "fact_status": fact,
            "fact_status_valid": fact_status_valid,
            "facts_established": facts_established,
            "lineage_only_fields_valid": lineage_only_fields_valid,
            "source_pursuit_id": pursuit_id or None,
            "source_opportunity_id": opportunity_id or None,
            "unknowns_labelled": unknowns_labelled,
            "unknown_fields": sorted(set(unknown_fields)),
            "human_review_required": human_review_required,
            "award_ready_for_obligation_tracking": (
                award_ready_for_obligation_tracking
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants. Nothing here promotes a projection or invents a fact.
            "projected_burden_considered": False,
            "award_created_from_lineage": False,
            "award_status_inferred_from_pursuit": False,
            "award_amount_inferred": False,
            "obligations_inferred": False,
            "fabricated": False,
        }
    )


def validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this validation must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in (
        "projected_burden_considered",
        "award_created_from_lineage",
        "award_status_inferred_from_pursuit",
        "award_amount_inferred",
        "obligations_inferred",
        "fabricated",
    ):
        if result.get(field):
            failures.append(f"validation_claimed_{field}")

    # The rule Gate 91 exists to protect.
    if result.get("obligations_established") and not result.get("facts_established"):
        failures.append("obligations_established_without_established_facts")

    if result.get("obligations_established") and not result.get(
        "obligation_capable_extraction"
    ):
        failures.append("obligations_established_without_a_capable_extraction")

    if result.get("obligations_established") and not result.get("award_is_live"):
        failures.append("obligations_established_on_a_non_live_award")

    if result.get("award_amount_known") and not result.get("award_currency"):
        failures.append("an_amount_was_reported_without_a_currency")

    if result.get("award_ready_for_obligation_tracking"):
        for conjunct in (
            "award_title_present",
            "award_status_valid",
            "award_is_live",
            "obligations_established",
            "facts_established",
            "obligation_capable_extraction",
            "period_dates_valid",
        ):
            if not result.get(conjunct):
                failures.append(f"ready_for_obligation_tracking_without:{conjunct}")
        if result.get("blocked_reasons"):
            failures.append("ready_for_obligation_tracking_with_blocked_reasons")
        if result.get("human_review_required"):
            failures.append("ready_for_obligation_tracking_while_review_required")

    # A claim this service refused must say why, or the refusal is invisible to
    # the caller that made it.
    if (
        result.get("obligations_claimed")
        and not result.get("obligations_established")
        and not result.get("blocked_reasons")
    ):
        failures.append("an_obligation_claim_was_refused_without_a_reason")

    if result.get("unknown_fields") and not result.get("human_review_required"):
        failures.append("unknown_fields_without_human_review")

    if not result.get("unknowns_labelled"):
        failures.append("an_unknown_was_not_labelled")

    return sorted(set(failures))


def build_validation_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them established."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = validate_awarded_grant(**case["award"])
        rows.append(
            {
                "case": case["case"],
                "award_title_present": result["award_title_present"],
                "award_status": result["award_status"],
                "award_status_valid": result["award_status_valid"],
                "award_is_live": result["award_is_live"],
                "active_obligation_status": result["active_obligation_status"],
                "active_obligation_status_valid": result[
                    "active_obligation_status_valid"
                ],
                # Both, never one. A matrix reporting only the derived value
                # could not show a claim being refused, which is most of what
                # these cases demonstrate.
                "obligations_claimed": result["obligations_claimed"],
                "obligations_established": result["obligations_established"],
                "requirements_extraction_status": result[
                    "requirements_extraction_status"
                ],
                "obligation_capable_extraction": result[
                    "obligation_capable_extraction"
                ],
                "fact_status": result["fact_status"],
                "facts_established": result["facts_established"],
                "award_amount_known": result["award_amount_known"],
                "period_dates_valid": result["period_dates_valid"],
                "award_amount_valid_or_unknown": result[
                    "award_amount_valid_or_unknown"
                ],
                "fact_status_valid": result["fact_status_valid"],
                "award_ready_for_obligation_tracking": result[
                    "award_ready_for_obligation_tracking"
                ],
                "human_review_required": result["human_review_required"],
                "unknown_fields": result["unknown_fields"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": validation_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "ready_count": sum(
                1 for r in rows if r["award_ready_for_obligation_tracking"]
            ),
            "obligating_count": sum(1 for r in rows if r["obligations_established"]),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            "projected_burden_considered": False,
        }
    )
