"""178J: twenty ways the commercial model could be wrong, with the answers.

Every case feeds RAW inputs into the REAL services and grades what comes back.

Every case pins its own clock. That is not a style preference in a module
about billing: a licence that expires because a fixture ran on the wrong side
of midnight is exactly the defect 178E names, and a corpus that reads the wall
clock cannot tell you it has not happened.

WHAT THIS CORPUS IS NOT
-----------------------
Twenty cases we thought of, against an approved model. It is not legal
advice, the exact wording of the agreement remains with counsel, and no money
has been charged, refunded or forgiven for any real organisation.
"""

from __future__ import annotations

from typing import Any

from nativeforge.services.commercial_entitlement_service import (
    derive_entitlement,
    entitlement_invariant_failures,
    extension_invariant_failures,
    grant_benefit_extension,
)
from nativeforge.services.commercial_ledger_service import (
    LICENSE_PURCHASED,
    MAINTENANCE_FORGIVEN_EVENT,
    ledger_invariant_failures,
    open_license,
    outstanding_maintenance_cents,
    relicense,
    renew_maintenance,
    replay,
)
from nativeforge.services.commercial_license_model_service import (
    ANNUAL_MAINTENANCE_PRICE_CENTS,
    PERSISTENT_LICENSE_PRICE_CENTS,
    included_maintenance_through,
)

SCHEMA_VERSION = "nf_commercial_gold_corpus_v1"

CORPUS_VERSION = "2026.09.1"

PURCHASED = "2026-03-15"
INCLUDED_THROUGH = "2027-03-15"

#: A licence bought on 2026-03-15 with the first year included.
BASE_LEDGER: dict[str, Any] = {
    "license_purchased_at": PURCHASED,
    "paid_through": INCLUDED_THROUGH,
}

CC = "CONTROLLING_COMPANY_ADMIN"


def _entitlement(as_of: str, ledger: dict[str, Any] | None = None, extensions=None):
    return derive_entitlement(
        organization_id="org-A",
        ledger=ledger or BASE_LEDGER,
        extensions=extensions,
        as_of=as_of,
    )


def _extension(days: int, as_of: str, ledger: dict[str, Any] | None = None):
    return grant_benefit_extension(
        organization_id="org-A",
        duration_days=days,
        granted_by="cc:staff-1",
        granted_by_role=CC,
        reason="purchase order in flight",
        ledger=ledger or BASE_LEDGER,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# The twenty cases.
# ---------------------------------------------------------------------------


def case_01_new_license() -> dict[str, Any]:
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    purchase = next(e for e in events if e["event_type"] == LICENSE_PURCHASED)
    return {
        "price_cents": purchase["amount_cents"],
        "ledger_failures": ledger_invariant_failures(before=[], after=events),
    }


def case_02_first_year_included() -> dict[str, Any]:
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    ledger = replay(events)
    e = _entitlement("2026-09-01", ledger)
    return {
        "paid_through": ledger["paid_through"],
        "included_cost_cents": next(
            x["amount_cents"] for x in events if x["paid_through"]
        ),
        "benefit_access": e["benefit_access"],
    }


def case_03_annual_renewal() -> dict[str, Any]:
    renewal = renew_maintenance(
        organization_id="org-A",
        paid_at="2027-04-02",
        recorded_by="cc:staff-1",
        current_paid_through=INCLUDED_THROUGH,
    )
    return {
        # Renewed a fortnight late, and still bought a whole year.
        "paid_through": renewal["paid_through"],
        "price_cents": renewal["amount_cents"],
    }


def case_04_maintenance_just_expired() -> dict[str, Any]:
    day_one = _entitlement("2027-03-16")
    day_thirty = _entitlement("2027-04-14")
    return {
        "day_one_benefit": day_one["benefit_access"],
        "day_one_license": day_one["license_state"],
        "day_thirty_benefit": day_thirty["benefit_access"],
        "maintenance_state": day_one["maintenance_state"],
    }


def case_05_frozen_preserves_data() -> dict[str, Any]:
    e = _entitlement("2027-06-01")
    return {
        "benefit_access": e["benefit_access"],
        "license_held": e["license_held"],
        "data_deleted": e["data_deleted"],
        "organization_deleted": e["organization_deleted"],
        "history_deleted": e["history_deleted"],
        "can_export": "EXPORT_OWN_DATA" in e["available_actions"],
        "can_authenticate": "AUTHENTICATE" in e["available_actions"],
        "can_see_renewal_path": "VIEW_RENEWAL_PATH" in e["available_actions"],
        "invariant_failures": entitlement_invariant_failures(e),
    }


def case_06_payment_restores_benefits() -> dict[str, Any]:
    frozen = _entitlement("2027-06-01")
    paid = _entitlement("2027-06-01", {**BASE_LEDGER, "paid_through": "2028-03-15"})
    return {
        "before_benefit": frozen["benefit_access"],
        "after_benefit": paid["benefit_access"],
        "after_license": paid["license_state"],
        "after_maintenance": paid["maintenance_state"],
    }


def _extension_case(days: int) -> dict[str, Any]:
    granted = _extension(days, "2027-06-01")
    during = _entitlement("2027-06-02", extensions=[granted["extension"]])
    return {
        "accepted": granted["accepted"],
        "benefit_access": during["benefit_access"],
        "license_state": during["license_state"],
        "maintenance_state": during["maintenance_state"],
        "extension_failures": extension_invariant_failures(granted["extension"]),
        "billing_truth_unchanged": granted["billing_truth_unchanged"],
    }


def case_07_seven_day_extension() -> dict[str, Any]:
    return _extension_case(7)


def case_08_fourteen_day_extension() -> dict[str, Any]:
    return _extension_case(14)


def case_09_thirty_day_extension() -> dict[str, Any]:
    return _extension_case(30)


def case_10_extension_expires() -> dict[str, Any]:
    granted = _extension(7, "2027-06-01")
    inside = _entitlement("2027-06-05", extensions=[granted["extension"]])
    on_the_day = _entitlement("2027-06-08", extensions=[granted["extension"]])
    after = _entitlement("2027-06-20", extensions=[granted["extension"]])
    return {
        "inside_benefit": inside["benefit_access"],
        # The window is exclusive at the end: a 7-day grant from the 1st runs
        # through the 7th, and the 8th is over.
        "on_expiry_benefit": on_the_day["benefit_access"],
        "after_benefit": after["benefit_access"],
    }


def case_11_org_admin_attempts_extension() -> dict[str, Any]:
    results = {}
    for role in ("ORG_SUPER_ADMIN", "ORG_ADMIN", "ORG_REVIEWER", "ORG_MEMBER"):
        outcome = grant_benefit_extension(
            organization_id="org-A",
            duration_days=7,
            granted_by="person-1",
            granted_by_role=role,
            reason="we are waiting on the council",
            ledger=BASE_LEDGER,
            as_of="2027-06-01",
        )
        results[role] = outcome["accepted"]
    return {
        "any_customer_role_succeeded": any(results.values()),
        "extension_created": any(results.values()),
    }


def case_12_two_years_364_days_does_not_expire() -> dict[str, Any]:
    # Paid through 2027-03-15; 1094 days later is 2030-03-13.
    almost = _entitlement("2030-03-13")
    exactly = _entitlement("2030-03-14")
    return {
        "at_1094_days_license": almost["license_state"],
        "at_1094_days_delinquency": almost["delinquency_days"],
        "at_1095_days_license": exactly["license_state"],
        "at_1095_days_delinquency": exactly["delinquency_days"],
    }


def case_13_three_years_expires() -> dict[str, Any]:
    e = _entitlement("2030-03-15")
    return {
        "license_state": e["license_state"],
        "delinquency_days": e["delinquency_days"],
        "data_deleted": e["data_deleted"],
        "organization_deleted": e["organization_deleted"],
        "can_export": "EXPORT_OWN_DATA" in e["available_actions"],
        "invariant_failures": entitlement_invariant_failures(e),
    }


def case_14_relicensing_restores_active() -> dict[str, Any]:
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
        reason="the Tribe returned",
    )
    e = derive_entitlement(
        organization_id="org-A", ledger=result["ledger"], as_of="2030-06-01"
    )
    return {
        "accepted": result["accepted"],
        "license_state": e["license_state"],
        "maintenance_state": e["maintenance_state"],
        "benefit_access": e["benefit_access"],
        "price_cents": result["appended"][0]["amount_cents"],
    }


def case_15_unpaid_maintenance_forgiven() -> dict[str, Any]:
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    owed = outstanding_maintenance_cents(events=events, as_of="2030-05-01")
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
    )
    forgiveness = next(
        e for e in result["appended"] if e["event_type"] == MAINTENANCE_FORGIVEN_EVENT
    )
    return {
        "owed_before_cents": owed,
        "forgiven_cents": result["forgiven_cents"],
        "forgiveness_names_the_amount": forgiveness["amount_cents"] == owed,
        "forgiveness_states_a_reason": bool(forgiveness["reason"]),
    }


def case_16_history_remains() -> dict[str, Any]:
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
    )
    after_ids = {e["event_id"] for e in result["events"]}
    return {
        "every_prior_event_survived": all(e["event_id"] in after_ids for e in events),
        "event_count_grew": len(result["events"]) > len(events),
        "delinquency_history_rewritten": result["delinquency_history_rewritten"],
        "ledger_failures": ledger_invariant_failures(
            before=events, after=result["events"]
        ),
    }


def case_17_clock_edge() -> dict[str, Any]:
    """A datetime, a date string, and an ISO timestamp must agree.

    178E names "clock fixture ambiguity" as a reason a licence must never
    expire. The three spellings below are the same instant written three
    ways, and a model that read them differently would expire somebody's
    licence depending on which caller asked.
    """
    import datetime as dt

    plain = _entitlement("2030-03-13")
    with_time = derive_entitlement(
        organization_id="org-A",
        ledger=BASE_LEDGER,
        as_of="2030-03-13T23:59:59+00:00",
        extensions=None,
    )
    as_datetime = derive_entitlement(
        organization_id="org-A",
        ledger=BASE_LEDGER,
        as_of=dt.datetime(2030, 3, 13, 23, 59, 59, tzinfo=dt.UTC),
        extensions=None,
    )
    return {
        "all_three_agree": (
            plain["license_state"]
            == with_time["license_state"]
            == as_datetime["license_state"]
        ),
        "all_three_same_delinquency": (
            plain["delinquency_days"]
            == with_time["delinquency_days"]
            == as_datetime["delinquency_days"]
        ),
        "license_state": plain["license_state"],
    }


def case_18_extension_does_not_falsify_delinquency() -> dict[str, Any]:
    """The case this gate exists for."""
    without = _entitlement("2027-06-05")
    granted = _extension(30, "2027-06-01")
    with_ext = _entitlement("2027-06-05", extensions=[granted["extension"]])
    return {
        "delinquency_unchanged": with_ext["delinquency_days"]
        == without["delinquency_days"],
        "paid_through_unchanged": with_ext["paid_through"] == without["paid_through"],
        "maintenance_state_unchanged": with_ext["maintenance_state"]
        == without["maintenance_state"],
        "license_state_unchanged": with_ext["license_state"]
        == without["license_state"],
        # Only this moved.
        "benefit_access_changed": with_ext["benefit_access"]
        != without["benefit_access"],
        # And the extension itself recorded what it did not cure.
        "extension_recorded_delinquency": granted["extension"][
            "underlying_delinquency_days"
        ]
        > 0,
        "extension_recorded_maintenance_state": granted["extension"][
            "underlying_maintenance_state"
        ],
    }


def case_19_deletion_is_impossible() -> dict[str, Any]:
    """No state, at any point on the timeline, reports deleted data."""
    dates = [
        "2026-06-01",  # active
        "2027-03-20",  # grace
        "2027-06-01",  # frozen
        "2029-01-01",  # long delinquent
        "2030-03-15",  # expired
        "2033-01-01",  # expired for years
    ]
    states = [_entitlement(d) for d in dates]
    return {
        "any_data_deleted": any(s["data_deleted"] for s in states),
        "any_organization_deleted": any(s["organization_deleted"] for s in states),
        "any_history_deleted": any(s["history_deleted"] for s in states),
        "export_always_available": all(
            "EXPORT_OWN_DATA" in s["available_actions"] for s in states
        ),
        "authenticate_always_available": all(
            "AUTHENTICATE" in s["available_actions"] for s in states
        ),
        "invariant_failures": sorted(
            {f for s in states for f in entitlement_invariant_failures(s)}
        ),
    }


def case_20_recalculation_is_deterministic() -> dict[str, Any]:
    """The same inputs, ten times, must produce byte-identical answers."""
    import json

    granted = _extension(14, "2027-06-01")
    runs = [
        json.dumps(
            _entitlement("2027-06-05", extensions=[granted["extension"]]),
            sort_keys=True,
            default=str,
        )
        for _ in range(10)
    ]
    return {
        "all_runs_identical": len(set(runs)) == 1,
        "distinct_results": len(set(runs)),
    }


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "G178J-01",
        "name": "new_persistent_license",
        "narrative": "The approved price, recorded exactly.",
        "run": case_01_new_license,
        "expect": {
            "price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
            "ledger_failures": [],
        },
    },
    {
        "case_id": "G178J-02",
        "name": "first_year_maintenance_included",
        "narrative": "Twelve months, at no additional charge.",
        "run": case_02_first_year_included,
        "expect": {
            "paid_through": INCLUDED_THROUGH,
            "included_cost_cents": 0,
            "benefit_access": "BENEFIT_FULL",
        },
    },
    {
        "case_id": "G178J-03",
        "name": "annual_maintenance_renewal",
        "narrative": (
            "Renewed a fortnight late. They bought a year, not a year minus "
            "a fortnight."
        ),
        "run": case_03_annual_renewal,
        "expect": {
            "paid_through": "2028-03-15",
            "price_cents": ANNUAL_MAINTENANCE_PRICE_CENTS,
        },
    },
    {
        "case_id": "G178J-04",
        "name": "maintenance_just_expired",
        "narrative": (
            "One day late is an accounts department, not a lapsed customer. "
            "Freezing a Tribe's grant pipeline over it loses them."
        ),
        "run": case_04_maintenance_just_expired,
        "expect": {
            "day_one_benefit": "BENEFIT_FULL",
            "day_one_license": "LICENSED_GRACE",
            "day_thirty_benefit": "BENEFIT_FULL",
            "maintenance_state": "MAINTENANCE_LAPSED",
        },
    },
    {
        "case_id": "G178J-05",
        "name": "frozen_account_preserves_data",
        "narrative": "Workflows pause. Nothing is taken.",
        "run": case_05_frozen_preserves_data,
        "expect": {
            "benefit_access": "BENEFIT_FROZEN",
            "license_held": True,
            "data_deleted": False,
            "organization_deleted": False,
            "history_deleted": False,
            "can_export": True,
            "can_authenticate": True,
            "can_see_renewal_path": True,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G178J-06",
        "name": "payment_restores_active_benefits",
        "narrative": "Paying should work, immediately and completely.",
        "run": case_06_payment_restores_benefits,
        "expect": {
            "before_benefit": "BENEFIT_FROZEN",
            "after_benefit": "BENEFIT_FULL",
            "after_license": "LICENSED_ACTIVE",
            "after_maintenance": "MAINTENANCE_CURRENT",
        },
    },
    {
        "case_id": "G178J-07",
        "name": "seven_day_extension_while_delinquent",
        "narrative": "Benefits return; the debt does not move.",
        "run": case_07_seven_day_extension,
        "expect": {
            "accepted": True,
            "benefit_access": "BENEFIT_EXTENDED",
            "license_state": "LICENSED_FROZEN",
            "maintenance_state": "MAINTENANCE_DELINQUENT",
            "extension_failures": [],
            "billing_truth_unchanged": True,
        },
    },
    {
        "case_id": "G178J-08",
        "name": "fourteen_day_extension",
        "narrative": "Same rule, longer window.",
        "run": case_08_fourteen_day_extension,
        "expect": {
            "accepted": True,
            "benefit_access": "BENEFIT_EXTENDED",
            "license_state": "LICENSED_FROZEN",
            "maintenance_state": "MAINTENANCE_DELINQUENT",
            "extension_failures": [],
            "billing_truth_unchanged": True,
        },
    },
    {
        "case_id": "G178J-09",
        "name": "thirty_day_extension",
        "narrative": "The longest the approved model allows.",
        "run": case_09_thirty_day_extension,
        "expect": {
            "accepted": True,
            "benefit_access": "BENEFIT_EXTENDED",
            "license_state": "LICENSED_FROZEN",
            "maintenance_state": "MAINTENANCE_DELINQUENT",
            "extension_failures": [],
            "billing_truth_unchanged": True,
        },
    },
    {
        "case_id": "G178J-10",
        "name": "extension_expires",
        "narrative": "It ends by itself. Nobody has to remember to end it.",
        "run": case_10_extension_expires,
        "expect": {
            "inside_benefit": "BENEFIT_EXTENDED",
            "on_expiry_benefit": "BENEFIT_FROZEN",
            "after_benefit": "BENEFIT_FROZEN",
        },
    },
    {
        "case_id": "G178J-11",
        "name": "org_admin_attempts_extension",
        "narrative": "A customer cannot extend their own benefits.",
        "run": case_11_org_admin_attempts_extension,
        "expect": {"any_customer_role_succeeded": False, "extension_created": False},
    },
    {
        "case_id": "G178J-12",
        "name": "two_years_364_days_does_not_expire",
        "narrative": (
            "The day before the boundary, and the boundary itself. Neither "
            "costs them the licence."
        ),
        "run": case_12_two_years_364_days_does_not_expire,
        "expect": {
            "at_1094_days_license": "LICENSED_FROZEN",
            "at_1094_days_delinquency": 1094,
            "at_1095_days_license": "LICENSED_FROZEN",
            "at_1095_days_delinquency": 1095,
        },
    },
    {
        "case_id": "G178J-13",
        "name": "three_years_expires_license",
        "narrative": (
            "Past three continuous years. The licence is lost; the data is not."
        ),
        "run": case_13_three_years_expires,
        "expect": {
            "license_state": "LICENSE_EXPIRED",
            "delinquency_days": 1096,
            "data_deleted": False,
            "organization_deleted": False,
            "can_export": True,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G178J-14",
        "name": "relicensing_restores_active",
        "narrative": "Current full price, and they are back.",
        "run": case_14_relicensing_restores_active,
        "expect": {
            "accepted": True,
            "license_state": "LICENSED_ACTIVE",
            "maintenance_state": "MAINTENANCE_CURRENT",
            "benefit_access": "BENEFIT_FULL",
            "price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
        },
    },
    {
        "case_id": "G178J-15",
        "name": "unpaid_maintenance_forgiven_on_relicense",
        "narrative": (
            "Forgiven, with the amount named. 'Forgiven' and no figure is not "
            "a record, it is a shrug."
        ),
        "run": case_15_unpaid_maintenance_forgiven,
        "expect": {
            "owed_before_cents": ANNUAL_MAINTENANCE_PRICE_CENTS * 3,
            "forgiven_cents": ANNUAL_MAINTENANCE_PRICE_CENTS * 3,
            "forgiveness_names_the_amount": True,
            "forgiveness_states_a_reason": True,
        },
    },
    {
        "case_id": "G178J-16",
        "name": "history_remains_after_relicense",
        "narrative": (
            "The debt is forgiven. The record that it was owed stays exactly "
            "where it is."
        ),
        "run": case_16_history_remains,
        "expect": {
            "every_prior_event_survived": True,
            "event_count_grew": True,
            "delinquency_history_rewritten": False,
            "ledger_failures": [],
        },
    },
    {
        "case_id": "G178J-17",
        "name": "clock_and_timezone_edge",
        "narrative": (
            "The same instant written three ways. A model that read them "
            "differently would expire a licence depending on who asked."
        ),
        "run": case_17_clock_edge,
        "expect": {
            "all_three_agree": True,
            "all_three_same_delinquency": True,
            "license_state": "LICENSED_FROZEN",
        },
    },
    {
        "case_id": "G178J-18",
        "name": "extension_does_not_falsify_delinquency",
        "narrative": (
            "The whole gate in one case. Benefits move; billing truth does "
            "not, and the extension records the delinquency it did not cure."
        ),
        "run": case_18_extension_does_not_falsify_delinquency,
        "expect": {
            "delinquency_unchanged": True,
            "paid_through_unchanged": True,
            "maintenance_state_unchanged": True,
            "license_state_unchanged": True,
            "benefit_access_changed": True,
            "extension_recorded_delinquency": True,
            "extension_recorded_maintenance_state": "MAINTENANCE_DELINQUENT",
        },
    },
    {
        "case_id": "G178J-19",
        "name": "deletion_is_an_impossible_side_effect",
        "narrative": (
            "Six points on the timeline, from active to expired for years. "
            "None of them reports deleted anything."
        ),
        "run": case_19_deletion_is_impossible,
        "expect": {
            "any_data_deleted": False,
            "any_organization_deleted": False,
            "any_history_deleted": False,
            "export_always_available": True,
            "authenticate_always_available": True,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G178J-20",
        "name": "recalculation_is_deterministic",
        "narrative": "Ten runs, one answer.",
        "run": case_20_recalculation_is_deterministic,
        "expect": {"all_runs_identical": True, "distinct_results": 1},
    },
)

_CAVEAT: dict[str, Any] = {
    "measured_against": "this corpus only",
    "corpus_is_world_truth": False,
    "money_moved_for_a_real_organization": False,
    "is_legal_advice": False,
    "why": (
        "Twenty cases we thought of, against an approved commercial model. "
        "The exact wording of the agreement remains with counsel, and no "
        "money has been charged, refunded or forgiven for any real "
        "organisation."
    ),
}


def grade_case(case: dict[str, Any]) -> dict[str, Any]:
    observed = case["run"]()
    failures = sorted(
        f"{key}_expected_{case['expect'][key]}_observed_{observed.get(key)}"
        for key in case["expect"]
        if observed.get(key) != case["expect"][key]
    )
    return {
        "case_id": case["case_id"],
        "name": case["name"],
        "passed": not failures,
        "failures": failures,
        "observed": observed,
    }


def grade_corpus(cases: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any]:
    cases = cases if cases is not None else CASES
    graded = [grade_case(case) for case in cases]
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(graded),
        "passed_count": sum(1 for g in graded if g["passed"]),
        "failed_cases": [
            {"case_id": g["case_id"], "name": g["name"], "failures": g["failures"]}
            for g in graded
            if not g["passed"]
        ],
        "cases": graded,
        **_CAVEAT,
    }


def describe_corpus() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(CASES),
        "case_ids": [c["case_id"] for c in CASES],
        "every_case_has_a_narrative": all(c.get("narrative") for c in CASES),
        "every_case_has_expectations": all(c.get("expect") for c in CASES),
        "exercises_the_real_services": True,
        "every_case_pins_its_own_clock": True,
        "canonical_license_price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
        "canonical_maintenance_price_cents": ANNUAL_MAINTENANCE_PRICE_CENTS,
        "included_through_for_the_base_ledger": str(
            included_maintenance_through(PURCHASED)
        ),
        **_CAVEAT,
    }
