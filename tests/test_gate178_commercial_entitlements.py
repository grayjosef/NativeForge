"""Gate 178: the persistent licence, its maintenance, and entitlement.

The approved model, encoded exactly. These tests check the code against the
DECISION rather than against itself: a test asserting "the price is whatever
the constant says" would pass with the wrong price in it.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from nativeforge.services.commercial_consortium_service import (
    COMPLEXITY_BESPOKE,
    COMPLEXITY_ELEVATED,
    COMPLEXITY_STANDARD,
    COMPLEXITY_UNKNOWN,
    ISOLATION_HYBRID,
    ISOLATION_ISOLATED_PER_MEMBER,
    ISOLATION_SHARED_WORKSPACE,
    ISOLATION_UNKNOWN,
    OFFERING_INTERTRIBAL_CONSORTIUM,
    OFFERING_SINGLE_ORGANIZATION,
    build_consortium_quote_request,
    describe_offering_model,
    describe_quote_dimensions,
    quote_invariant_failures,
)
from nativeforge.services.commercial_entitlement_service import (
    ACTION_CORRECT_LEDGER,
    ACTION_FORGIVE_DEBT,
    ACTION_GRANT_EXTENSION,
    ACTION_RELICENSE,
    ACTION_SET_PAID_THROUGH,
    ACTION_VIEW_ENTITLEMENT,
    CONTROLLING_COMPANY_ONLY,
    authorize_commercial_action,
    derive_entitlement,
    entitlement_invariant_failures,
    extension_invariant_failures,
    grant_benefit_extension,
)
from nativeforge.services.commercial_gold_corpus_service import (
    CASES,
    describe_corpus,
    grade_case,
    grade_corpus,
)
from nativeforge.services.commercial_ledger_service import (
    MAINTENANCE_FORGIVEN_EVENT,
    describe_ledger_model,
    ledger_invariant_failures,
    open_license,
    outstanding_maintenance_cents,
    relicense,
    renew_maintenance,
    replay,
)
from nativeforge.services.commercial_license_model_service import (
    ALWAYS_AVAILABLE,
    ANNUAL_MAINTENANCE_PRICE_CENTS,
    DELINQUENCY_DAYS_BEFORE_EXPIRATION,
    EXTENSION_DAYS,
    GRACE_PERIOD_DAYS,
    INCLUDED_MAINTENANCE_MONTHS,
    PERSISTENT_LICENSE_PRICE_CENTS,
    SUBSTANTIVE_WORKFLOWS,
    add_months,
    delinquency_days,
    describe_commercial_model,
    dollars,
    included_maintenance_through,
)
from nativeforge.services.commercial_self_health_service import (
    DETECTORS,
    assess_commercial_health,
    describe_self_health,
    prove_detectors_fire,
)

REPO = Path(__file__).resolve().parents[1]

PURCHASED = "2026-03-15"
INCLUDED_THROUGH = "2027-03-15"
LEDGER = {"license_purchased_at": PURCHASED, "paid_through": INCLUDED_THROUGH}
CC = "CONTROLLING_COMPANY_ADMIN"
CUSTOMER_ROLES = ("ORG_SUPER_ADMIN", "ORG_ADMIN", "ORG_REVIEWER", "ORG_MEMBER")


def _e(as_of: str, ledger=None, extensions=None):
    return derive_entitlement(
        organization_id="org-A",
        ledger=ledger or LEDGER,
        extensions=extensions,
        as_of=as_of,
    )


def _grant(days: int, as_of: str = "2027-06-01", role: str = CC):
    return grant_benefit_extension(
        organization_id="org-A",
        duration_days=days,
        granted_by="cc:staff-1",
        granted_by_role=role,
        reason="purchase order in flight",
        ledger=LEDGER,
        as_of=as_of,
    )


# ==================== 178A: the approved numbers ======================


def test_the_persistent_license_is_34999():
    """Checked against the decision, not against the constant."""
    assert PERSISTENT_LICENSE_PRICE_CENTS == 3_499_900
    assert dollars(PERSISTENT_LICENSE_PRICE_CENTS) == "$34,999.00"


def test_annual_maintenance_is_6999():
    assert ANNUAL_MAINTENANCE_PRICE_CENTS == 699_900
    assert dollars(ANNUAL_MAINTENANCE_PRICE_CENTS) == "$6,999.00"


def test_money_never_becomes_a_float():
    """A rounding error in a licence fee is not a rounding error to the Tribe."""
    for cents in (PERSISTENT_LICENSE_PRICE_CENTS, ANNUAL_MAINTENANCE_PRICE_CENTS, 0):
        assert isinstance(cents, int)
    assert describe_commercial_model()["money_is_integer_cents"] is True
    assert dollars(1) == "$0.01"
    assert dollars(-123_456) == "-$1,234.56"


def test_the_first_twelve_months_are_included_and_free():
    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    assert INCLUDED_MAINTENANCE_MONTHS == 12
    assert str(included_maintenance_through(PURCHASED)) == INCLUDED_THROUGH
    assert replay(events)["paid_through"] == INCLUDED_THROUGH
    # Included means free, not discounted.
    term = next(e for e in events if e["paid_through"])
    assert term["amount_cents"] == 0


def test_a_term_starting_on_the_31st_does_not_overflow():
    """31 January runs to 31 January, not to 3 March."""
    assert str(add_months("2026-01-31", 12)) == "2027-01-31"
    assert str(add_months("2026-01-31", 1)) == "2026-02-28"
    assert str(add_months("2028-01-31", 1)) == "2028-02-29"


def test_renewal_extends_from_the_paid_through_date():
    """A customer who renews late bought a year, not a year minus the delay."""
    renewal = renew_maintenance(
        organization_id="org-A",
        paid_at="2027-04-02",
        recorded_by="cc:staff-1",
        current_paid_through=INCLUDED_THROUGH,
    )
    assert renewal["paid_through"] == "2028-03-15"
    assert renewal["amount_cents"] == ANNUAL_MAINTENANCE_PRICE_CENTS


def test_no_draft_pricing_is_encoded():
    """doc 570's figures are drafts and must not appear as canonical."""
    model = describe_commercial_model()
    assert model["no_draft_pricing_encoded"] is True
    for draft in (2_499_900, 1_499_500, 4_999_900, 899_900):
        assert PERSISTENT_LICENSE_PRICE_CENTS != draft


# ==================== 178B/C: three states, never one =================


def test_the_three_states_are_separate():
    model = describe_commercial_model()
    assert model["three_states_are_separate"] is True
    assert len(model["license_states"]) == 5
    assert len(model["maintenance_states"]) == 5
    assert len(model["benefit_states"]) == 4


def test_a_delinquent_org_with_an_extension_holds_all_three_at_once():
    """The case a single is_active flag cannot express."""
    granted = _grant(14)
    e = _e("2027-06-05", extensions=[granted["extension"]])
    assert e["license_state"] == "LICENSED_FROZEN"
    assert e["maintenance_state"] == "MAINTENANCE_DELINQUENT"
    assert e["benefit_access"] == "BENEFIT_EXTENDED"
    assert entitlement_invariant_failures(e) == []


def test_one_day_late_does_not_freeze_a_tribe():
    """An invoice a fortnight late is an accounts department."""
    day_one = _e("2027-03-16")
    assert day_one["benefit_access"] == "BENEFIT_FULL"
    assert day_one["license_state"] == "LICENSED_GRACE"
    last_grace_day = _e(
        str(dt.date(2027, 3, 15) + dt.timedelta(days=GRACE_PERIOD_DAYS))
    )
    assert last_grace_day["benefit_access"] == "BENEFIT_FULL"
    past_grace = _e(
        str(dt.date(2027, 3, 15) + dt.timedelta(days=GRACE_PERIOD_DAYS + 1))
    )
    assert past_grace["benefit_access"] == "BENEFIT_FROZEN"


def test_delinquency_is_never_negative():
    """A negative duration flows into the expiry arithmetic."""
    assert delinquency_days(paid_through="2030-01-01", as_of="2026-01-01") == 0
    e = _e("2026-06-01")
    assert e["delinquency_days"] == 0


def test_entitlement_never_reads_the_clock():
    with pytest.raises(ValueError):
        derive_entitlement(organization_id="org-A", ledger=LEDGER, as_of=None)


def test_entitlement_is_deterministic():
    granted = _grant(14)
    runs = {
        json.dumps(
            _e("2027-06-05", extensions=[granted["extension"]]),
            sort_keys=True,
            default=str,
        )
        for _ in range(10)
    }
    assert len(runs) == 1


# ==================== 178D: frozen is not deleted =====================


@pytest.mark.parametrize(
    "as_of",
    [
        "2026-06-01",
        "2027-03-20",
        "2027-06-01",
        "2029-01-01",
        "2030-03-15",
        "2033-01-01",
    ],
)
def test_nothing_is_ever_deleted(as_of):
    """Six points from active to expired-for-years."""
    e = _e(as_of)
    assert e["data_deleted"] is False
    assert e["organization_deleted"] is False
    assert e["history_deleted"] is False
    assert entitlement_invariant_failures(e) == []


@pytest.mark.parametrize("action", list(ALWAYS_AVAILABLE))
def test_always_available_actions_survive_expiry(action):
    """Including EXPORT_OWN_DATA, years after the licence is gone."""
    assert action in _e("2033-01-01")["available_actions"]


def test_frozen_locks_workflows_and_only_workflows():
    e = _e("2027-06-01")
    assert e["benefit_access"] == "BENEFIT_FROZEN"
    assert e["license_held"] is True
    assert set(e["locked_actions"]) == set(SUBSTANTIVE_WORKFLOWS)
    assert set(ALWAYS_AVAILABLE) <= set(e["available_actions"])


def test_payment_restores_benefits_immediately():
    assert _e("2027-06-01")["benefit_access"] == "BENEFIT_FROZEN"
    paid = _e("2027-06-01", {**LEDGER, "paid_through": "2028-03-15"})
    assert paid["benefit_access"] == "BENEFIT_FULL"
    assert paid["license_state"] == "LICENSED_ACTIVE"


# ==================== 178E: three continuous years ====================


def test_the_licence_survives_the_boundary_day():
    """The most expensive arithmetic error this system can make."""
    assert DELINQUENCY_DAYS_BEFORE_EXPIRATION == 1095
    at_1094 = _e("2030-03-13")
    at_1095 = _e("2030-03-14")
    at_1096 = _e("2030-03-15")
    assert at_1094["delinquency_days"] == 1094
    assert at_1094["license_state"] == "LICENSED_FROZEN"
    # Exactly three years: still held.
    assert at_1095["delinquency_days"] == 1095
    assert at_1095["license_state"] == "LICENSED_FROZEN"
    # Past three years, and only then.
    assert at_1096["license_state"] == "LICENSE_EXPIRED"


def test_expiry_does_not_delete_anything():
    e = _e("2030-03-15")
    assert e["data_deleted"] is False
    assert "EXPORT_OWN_DATA" in e["available_actions"]
    assert entitlement_invariant_failures(e) == []


def test_the_same_instant_written_three_ways_agrees():
    """178E names clock fixture ambiguity as a reason not to expire."""
    plain = _e("2030-03-13")
    iso = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2030-03-13T23:59:59+00:00"
    )
    stamped = derive_entitlement(
        organization_id="org-A",
        ledger=LEDGER,
        as_of=dt.datetime(2030, 3, 13, 23, 59, 59, tzinfo=dt.UTC),
    )
    assert plain["license_state"] == iso["license_state"] == stamped["license_state"]
    assert (
        plain["delinquency_days"]
        == iso["delinquency_days"]
        == stamped["delinquency_days"]
    )


# ==================== 178G: extensions ================================


@pytest.mark.parametrize("days", list(EXTENSION_DAYS))
def test_the_three_allowed_durations_work(days):
    granted = _grant(days)
    assert granted["accepted"] is True
    assert extension_invariant_failures(granted["extension"]) == []


@pytest.mark.parametrize("days", [1, 6, 8, 15, 31, 60, 90, 365])
def test_no_other_duration_is_allowed(days):
    assert _grant(days)["accepted"] is False


def test_an_extension_changes_benefit_access_and_nothing_else():
    """The whole gate in one test."""
    without = _e("2027-06-05")
    granted = _grant(30)
    with_ext = _e("2027-06-05", extensions=[granted["extension"]])

    assert with_ext["benefit_access"] != without["benefit_access"]
    # Everything else is identical.
    assert with_ext["delinquency_days"] == without["delinquency_days"]
    assert with_ext["paid_through"] == without["paid_through"]
    assert with_ext["maintenance_state"] == without["maintenance_state"]
    assert with_ext["license_state"] == without["license_state"]
    assert (
        with_ext["days_until_license_expiration"]
        == without["days_until_license_expiration"]
    )
    assert granted["billing_truth_unchanged"] is True


def test_an_extension_records_the_delinquency_it_did_not_cure():
    """An extension claiming the customer was current is a lie with a timestamp."""
    granted = _grant(14)
    extension = granted["extension"]
    assert extension["underlying_maintenance_state"] == "MAINTENANCE_DELINQUENT"
    assert extension["underlying_license_state"] == "LICENSED_FROZEN"
    assert extension["underlying_delinquency_days"] > 0


def test_an_extension_expires_by_itself():
    granted = _grant(7)
    assert (
        _e("2027-06-05", extensions=[granted["extension"]])["benefit_access"]
        == "BENEFIT_EXTENDED"
    )
    # A 7-day grant from the 1st runs through the 7th; the 8th is over.
    assert (
        _e("2027-06-08", extensions=[granted["extension"]])["benefit_access"]
        == "BENEFIT_FROZEN"
    )


def test_an_extension_needs_a_reason_and_a_grantor():
    assert (
        grant_benefit_extension(
            organization_id="org-A",
            duration_days=7,
            granted_by="cc:staff-1",
            granted_by_role=CC,
            reason=None,
            ledger=LEDGER,
            as_of="2027-06-01",
        )["accepted"]
        is False
    )
    assert (
        grant_benefit_extension(
            organization_id="org-A",
            duration_days=7,
            granted_by=None,
            granted_by_role=CC,
            reason="r",
            ledger=LEDGER,
            as_of="2027-06-01",
        )["accepted"]
        is False
    )


# ==================== 178H: the boundary ==============================


@pytest.mark.parametrize("role", list(CUSTOMER_ROLES))
def test_no_customer_role_may_grant_an_extension(role):
    assert _grant(7, role=role)["accepted"] is False


@pytest.mark.parametrize("role", list(CUSTOMER_ROLES))
@pytest.mark.parametrize(
    "action",
    [
        ACTION_FORGIVE_DEBT,
        ACTION_SET_PAID_THROUGH,
        ACTION_RELICENSE,
        ACTION_CORRECT_LEDGER,
        ACTION_GRANT_EXTENSION,
    ],
)
def test_no_customer_role_may_alter_commercial_truth(role, action):
    assert (
        authorize_commercial_action(action=action, actor_role=role)["permitted"]
        is False
    )


@pytest.mark.parametrize("role", list(CUSTOMER_ROLES))
def test_every_customer_role_may_see_its_own_standing(role):
    """A refusal a customer cannot even read would be its own failure."""
    assert (
        authorize_commercial_action(action=ACTION_VIEW_ENTITLEMENT, actor_role=role)[
            "permitted"
        ]
        is True
    )


def test_the_controlling_company_may_act():
    """The boundary must be able to say yes, or it is just a ban."""
    for action in CONTROLLING_COMPANY_ONLY:
        assert authorize_commercial_action(action=action, actor_role=CC)["permitted"]


# ==================== 178F/I: relicensing and history =================


def _opened():
    return open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )


def test_relicensing_restores_active_at_the_current_price():
    events = _opened()
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
        reason="the Tribe returned",
    )
    assert result["accepted"] is True
    assert result["appended"][0]["amount_cents"] == PERSISTENT_LICENSE_PRICE_CENTS
    after = derive_entitlement(
        organization_id="org-A", ledger=result["ledger"], as_of="2030-06-01"
    )
    assert after["license_state"] == "LICENSED_ACTIVE"
    assert after["benefit_access"] == "BENEFIT_FULL"


def test_forgiveness_names_its_amount():
    """'Forgiven' with no figure is not a record, it is a shrug."""
    events = _opened()
    owed = outstanding_maintenance_cents(events=events, as_of="2030-05-01")
    assert owed == ANNUAL_MAINTENANCE_PRICE_CENTS * 3
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
    assert forgiveness["amount_cents"] == owed
    assert forgiveness["reason"]


def test_relicensing_appends_and_removes_nothing():
    """The debt is forgiven. The record that it was owed is not."""
    events = _opened()
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
    )
    after_ids = {e["event_id"] for e in result["events"]}
    assert all(e["event_id"] in after_ids for e in events)
    assert len(result["events"]) > len(events)
    assert result["delinquency_history_rewritten"] is False
    assert ledger_invariant_failures(before=events, after=result["events"]) == []


def test_a_ledger_that_lost_an_event_is_refused():
    """Compared by id: removing one and adding two passes a length check."""
    events = _opened()
    result = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
    )
    tampered = [e for e in result["events"] if e["event_id"] != events[0]["event_id"]]
    failures = ledger_invariant_failures(before=events, after=tampered)
    assert any("lost" in f for f in failures)


def test_a_customer_cannot_relicense_itself():
    assert (
        relicense(
            organization_id="org-A",
            events=_opened(),
            purchased_at="2030-05-01",
            recorded_by="org-super",
            recorded_by_is_controlling_company=False,
        )["accepted"]
        is False
    )


def test_the_ledger_model_states_its_refusals():
    model = describe_ledger_model()
    assert model["ledger_is_append_only"] is True
    assert model["forgiveness_does_not_erase_the_debt_record"] is True
    assert model["delinquency_history_is_never_rewritten"] is True
    assert model["corrections_are_events_not_edits"] is True


# ==================== 178L: self health ===============================


def test_specific_self_health_detectors_fire():
    proof = prove_detectors_fire()
    assert proof["healthy_population_is_silent"] is True, proof["baseline_findings"]
    assert proof["all_detectors_fire"] is True, proof["detectors_that_did_not_fire"]
    assert proof["all_detectors_are_specific"] is True, proof[
        "detectors_that_fired_too_broadly"
    ]
    assert proof["detector_count"] == len(DETECTORS) == 9
    assert describe_self_health()["every_detector_has_a_meaning"] is True


def test_the_ledger_detector_compares_two_independent_sources():
    """A stale cache is how somebody sees ACTIVE after their licence expired."""
    served = _e("2027-06-05", {**LEDGER, "paid_through": "2028-03-15"})
    health = assess_commercial_health(
        entitlements=[served],
        ledgers={"org-A": LEDGER},
        as_of="2027-06-05",
    )
    assert "current_entitlement_disagrees_with_ledger" in health["detectors_fired"]
    # Agreeing sources must stay silent.
    agreeing = assess_commercial_health(
        entitlements=[_e("2027-06-05")],
        ledgers={"org-A": LEDGER},
        as_of="2027-06-05",
    )
    assert (
        "current_entitlement_disagrees_with_ledger" not in agreeing["detectors_fired"]
    )


# ==================== 178J: the corpus ================================


def test_the_corpus_passes_every_case():
    report = grade_corpus()
    assert report["case_count"] == 20
    assert report["failed_cases"] == [], report["failed_cases"]


def test_the_corpus_can_fail():
    case = dict(
        next(c for c in CASES if c["name"] == "extension_does_not_falsify_delinquency")
    )
    case["expect"] = dict(case["expect"], delinquency_unchanged=False)
    graded = grade_case(case)
    assert graded["passed"] is False


def test_the_corpus_claims_nothing_about_the_world():
    for payload in (describe_corpus(), grade_corpus()):
        assert payload["corpus_is_world_truth"] is False
        assert payload["money_moved_for_a_real_organization"] is False
        assert payload["is_legal_advice"] is False
    assert describe_corpus()["every_case_pins_its_own_clock"] is True


# ==================== 0064: the constraints are real ==================

NOW_DT = dt.datetime(2027, 6, 5, tzinfo=dt.UTC)

_EXT_ROW = {
    "organization_id": "org-A",
    "granted_by": "cc:staff-1",
    "granted_by_role": CC,
    "granted_at": dt.date(2027, 6, 1),
    "duration_days": 14,
    "expires_at": dt.date(2027, 6, 15),
    "reason": "purchase order in flight",
    "underlying_license_state": "LICENSED_FROZEN",
    "underlying_maintenance_state": "MAINTENANCE_DELINQUENT",
    "underlying_delinquency_days": 78,
    "revoked_at": None,
    "revoked_by": None,
    "policy_version": "2026.09-approved-v1",
    "is_demo": False,
}

_STATE_ROW = {
    "license_state": "LICENSED_ACTIVE",
    "maintenance_state": "MAINTENANCE_CURRENT",
    "benefit_access": "BENEFIT_FULL",
    "paid_through": dt.date(2028, 3, 15),
    "delinquency_days": 0,
    "days_until_license_expiration": 1095,
    "active_extension_id": None,
    "extension_expires_at": None,
    "maintenance_forgiven": False,
    "policy_version": "2026.09-approved-v1",
    "computed_at": NOW_DT,
    "is_demo": False,
}


def _insert(session, table, key_column, key, defaults, override):
    row = {key_column: key, **defaults, **override}
    columns = ", ".join(row)
    values = ", ".join(f":{name}" for name in row)
    session.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), row)


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("60 days", {"duration_days": 60, "expires_at": dt.date(2027, 7, 31)}),
        ("31 days", {"duration_days": 31, "expires_at": dt.date(2027, 7, 2)}),
        ("granted by a customer admin", {"granted_by_role": "ORG_SUPER_ADMIN"}),
        (
            "records the customer as current",
            {"underlying_maintenance_state": "MAINTENANCE_CURRENT"},
        ),
        ("negative delinquency", {"underlying_delinquency_days": -5}),
        ("expires before it begins", {"expires_at": dt.date(2027, 5, 1)}),
    ],
)
def test_the_database_refuses_an_impossible_extension(label, override):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(
                session,
                "nf_commercial_benefit_extensions",
                "extension_id",
                f"bad-{label}",
                _EXT_ROW,
                override,
            )
            session.commit()
        session.rollback()


@pytest.mark.parametrize(
    ("label", "override"),
    [
        (
            "full benefits while frozen",
            {"license_state": "LICENSED_FROZEN", "delinquency_days": 90},
        ),
        (
            "expired at exactly 1095 days",
            {
                "license_state": "LICENSE_EXPIRED",
                "benefit_access": "BENEFIT_FROZEN",
                "delinquency_days": 1095,
            },
        ),
        (
            "expired at 400 days",
            {
                "license_state": "LICENSE_EXPIRED",
                "benefit_access": "BENEFIT_FROZEN",
                "delinquency_days": 400,
            },
        ),
        ("negative delinquency", {"delinquency_days": -3}),
    ],
)
def test_the_database_refuses_an_unjustifiable_state(label, override):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(
                session,
                "nf_commercial_entitlement_state",
                "organization_id",
                f"bad-{label}",
                _STATE_ROW,
                override,
            )
            session.commit()
        session.rollback()


def test_the_database_accepts_the_honest_states():
    """The rules are not a ban on writing."""
    from nativeforge.db.session import SessionLocal

    honest = [
        (
            "org-frozen",
            {
                "license_state": "LICENSED_FROZEN",
                "maintenance_state": "MAINTENANCE_DELINQUENT",
                "benefit_access": "BENEFIT_FROZEN",
                "delinquency_days": 90,
            },
        ),
        (
            "org-extended",
            {
                "license_state": "LICENSED_FROZEN",
                "maintenance_state": "MAINTENANCE_DELINQUENT",
                "benefit_access": "BENEFIT_EXTENDED",
                "delinquency_days": 90,
                "active_extension_id": "ext-1",
            },
        ),
        (
            "org-expired",
            {
                "license_state": "LICENSE_EXPIRED",
                "maintenance_state": "MAINTENANCE_DELINQUENT",
                "benefit_access": "BENEFIT_FROZEN",
                "delinquency_days": 1096,
            },
        ),
    ]
    with SessionLocal() as session:
        try:
            for key, override in honest:
                _insert(
                    session,
                    "nf_commercial_entitlement_state",
                    "organization_id",
                    key,
                    _STATE_ROW,
                    override,
                )
            session.commit()
        finally:
            session.execute(text("DELETE FROM nf_commercial_entitlement_state"))
            session.commit()


# ==================== the instruments =================================


def test_network_zero_and_the_gate_is_ready():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g178_phase_proof.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["network_requests"] == 0
    assert report["fixture_residue"] == 0
    assert report["gate178_ready"] is True
    assert report["money_moved_for_a_real_organization"] is False


def test_the_scale_paths_are_indexed_without_zero_row_proofs():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g178_phase_scale.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["target_is_scratch"] is True
    assert report["zero_row_queries"] == []
    assert report["unindexed_queries"] == []
    assert report["scan_detector_still_fires"] is True
    assert report["critical_entitlement_queries_indexed"] is True
    assert report["network_requests"] == 0


def test_the_survey_found_no_draft_pricing_in_the_code():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g178_survey_commercial.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["draft_figures_are_not_in_code"] is True
    assert report["doc570_labels_its_figures_as_drafts"] is True
    assert report["nothing_can_delete_a_delinquent_organization"] is True
    assert report["feature_and_commercial_entitlement_are_distinct"] is True
    assert report["network_requests"] == 0


# ==================== 178A2: the consortium suite =====================


def _quote(**over):
    base = dict(
        consortium_name="Four Rivers Intertribal Consortium",
        member_organization_ids=["org:a", "org:b", "org:c", "org:d"],
        isolation_model=ISOLATION_HYBRID,
        complexity_level=COMPLEXITY_ELEVATED,
        complexity_factors=["CONSORTIUM_LEVEL_REPORTING"],
        seats_requested=28,
        requested_by="cc:sales-1",
        requested_at="2026-09-24",
    )
    base.update(over)
    return build_consortium_quote_request(**base)


def test_there_are_two_offerings_and_only_one_has_a_published_price():
    model = describe_offering_model()
    assert set(model["offerings"]) == {
        OFFERING_SINGLE_ORGANIZATION,
        OFFERING_INTERTRIBAL_CONSORTIUM,
    }
    assert model["offerings_with_a_published_price"] == [OFFERING_SINGLE_ORGANIZATION]
    assert model["consortium_has_no_published_price"] is True
    assert model["single_organization_price"] == "$34,999.00"


def test_the_consortium_is_priced_on_three_named_dimensions():
    """Isolation need, complexity, seats — the operator's three."""
    assert describe_quote_dimensions()["dimensions"] == [
        "ISOLATION_NEED",
        "COMPLEXITY",
        "SEATS",
    ]


def test_a_consortium_quote_never_carries_a_price():
    """A computed suite price would be a wrong number, confidently.

    Three factors multiplied together look like arithmetic rather than like
    a guess, which is what makes the wrongness invisible.
    """
    quote = _quote()
    assert quote["price_cents"] is None
    assert quote["requires_human_quote"] is True
    assert quote_invariant_failures(quote) == []


def test_a_quote_that_priced_itself_is_refused():
    priced = {**_quote(), "price_cents": 9_999_900}
    assert any("computed_price" in f for f in quote_invariant_failures(priced))


def test_the_reference_price_is_not_a_formula():
    """Context for the person quoting, not a multiplier."""
    quote = _quote()
    assert quote["reference_single_license_price"] == "$34,999.00"
    assert quote["reference_is_not_a_formula"] is True


@pytest.mark.parametrize(
    "isolation",
    [ISOLATION_SHARED_WORKSPACE, ISOLATION_ISOLATED_PER_MEMBER, ISOLATION_HYBRID],
)
def test_every_stated_isolation_model_is_quotable(isolation):
    quote = _quote(isolation_model=isolation)
    assert quote["quotable"] is True
    assert quote_invariant_failures(quote) == []


def test_unstated_isolation_is_an_outcome_not_a_default():
    """A consortium that has not decided this is not quotable."""
    quote = _quote(isolation_model=ISOLATION_UNKNOWN)
    assert quote["quotable"] is False
    assert "isolation_model_not_stated" in quote["blocking_unknowns"]
    assert (
        describe_offering_model()["isolation_unknown_is_an_outcome_not_a_default"]
        is True
    )


@pytest.mark.parametrize(
    "level", [COMPLEXITY_STANDARD, COMPLEXITY_ELEVATED, COMPLEXITY_BESPOKE]
)
def test_every_assessed_complexity_is_quotable(level):
    assert _quote(complexity_level=level)["quotable"] is True


def test_an_incomplete_request_names_what_is_missing_individually():
    """ "Incomplete" tells nobody what to chase."""
    quote = build_consortium_quote_request(
        consortium_name="Unnamed",
        member_organization_ids=["org:a"],
        complexity_level=COMPLEXITY_UNKNOWN,
        requested_at="2026-09-24",
    )
    assert quote["quotable"] is False
    assert set(quote["blocking_unknowns"]) == {
        "isolation_model_not_stated",
        "complexity_not_assessed",
        "seats_not_stated",
        "fewer_than_two_member_organizations",
    }
    assert quote_invariant_failures(quote) == []


def test_a_consortium_needs_at_least_two_members():
    assert (
        "fewer_than_two_member_organizations"
        in _quote(member_organization_ids=["org:a"])["blocking_unknowns"]
    )


def test_seats_per_member_cannot_exceed_seats_requested():
    over = _quote(seats_requested=10, seats_per_member={"org:a": 40})
    assert any("exceeds" in f for f in quote_invariant_failures(over))


def test_isolated_per_member_is_the_isolation_gate_179_proves():
    """The commercial dimension and the architectural one are the same thing."""
    model = describe_offering_model()
    assert model["isolated_per_member_is_the_tenant_isolation_gate_179_proved"] is True
    dimensions = describe_quote_dimensions()
    assert (
        "invisible to the others"
        in dimensions["isolation_meanings"][ISOLATION_ISOLATED_PER_MEMBER]
    )


def test_an_unrecognised_complexity_factor_is_reported_not_dropped():
    quote = _quote(complexity_factors=["CONSORTIUM_LEVEL_REPORTING", "VIBES"])
    assert quote["complexity_factors"] == ["CONSORTIUM_LEVEL_REPORTING"]
    assert quote["unrecognised_complexity_factors"] == ["VIBES"]
