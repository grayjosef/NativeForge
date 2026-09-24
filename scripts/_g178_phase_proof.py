"""178M: the facts the Gate 178 verifier asserts, measured rather than claimed.

The numbers are checked against the APPROVED model, not against whatever the
code happens to contain: a gate that asserts "the price is whatever we wrote"
would pass with the wrong price in it.

This phase makes no network call and writes nothing. Prints one line of JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_ATTEMPTS = {"n": 0}


class _RefusedSocket:
    def __init__(self, *a, **k):
        _ATTEMPTS["n"] += 1
        raise OSError("Gate 178 makes no network call")


socket.socket = _RefusedSocket  # type: ignore[misc,assignment]

from nativeforge.services.commercial_consortium_service import (  # noqa: E402
    COMPLEXITY_ELEVATED,
    COMPLEXITY_UNKNOWN,
    ISOLATION_HYBRID,
    ISOLATION_ISOLATED_PER_MEMBER,
    OFFERING_INTERTRIBAL_CONSORTIUM,
    build_consortium_quote_request,
    describe_offering_model,
    describe_quote_dimensions,
    quote_invariant_failures,
)
from nativeforge.services.commercial_entitlement_service import (  # noqa: E402
    ACTION_CORRECT_LEDGER,
    ACTION_FORGIVE_DEBT,
    ACTION_GRANT_EXTENSION,
    ACTION_RELICENSE,
    ACTION_SET_PAID_THROUGH,
    ACTION_VIEW_ENTITLEMENT,
    CONTROLLING_COMPANY_ONLY,
    authorize_commercial_action,
    derive_entitlement,
    describe_entitlement_model,
    entitlement_invariant_failures,
    extension_invariant_failures,
    grant_benefit_extension,
)
from nativeforge.services.commercial_gold_corpus_service import (  # noqa: E402
    describe_corpus,
    grade_corpus,
)
from nativeforge.services.commercial_ledger_service import (  # noqa: E402
    MAINTENANCE_FORGIVEN_EVENT,
    describe_ledger_model,
    ledger_invariant_failures,
    open_license,
    outstanding_maintenance_cents,
    relicense,
    renew_maintenance,
    replay,
)
from nativeforge.services.commercial_license_model_service import (  # noqa: E402
    ALWAYS_AVAILABLE,
    ANNUAL_MAINTENANCE_PRICE_CENTS,
    DELINQUENCY_DAYS_BEFORE_EXPIRATION,
    EXTENSION_DAYS,
    INCLUDED_MAINTENANCE_MONTHS,
    PERSISTENT_LICENSE_PRICE_CENTS,
    describe_commercial_model,
    included_maintenance_through,
)
from nativeforge.services.commercial_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    describe_repository,
)
from nativeforge.services.commercial_self_health_service import (  # noqa: E402
    DETECTORS,
    describe_self_health,
    prove_detectors_fire,
)

#: The APPROVED model, restated here so the verifier checks the code against
#: the decision rather than against itself.
APPROVED_LICENSE_CENTS = 3_499_900
APPROVED_MAINTENANCE_CENTS = 699_900
APPROVED_INCLUDED_MONTHS = 12
APPROVED_EXPIRY_YEARS = 3
APPROVED_EXTENSION_DAYS = (7, 14, 30)

PURCHASED = "2026-03-15"
INCLUDED_THROUGH = "2027-03-15"
LEDGER = {"license_purchased_at": PURCHASED, "paid_through": INCLUDED_THROUGH}
CUSTOMER_ROLES = ("ORG_SUPER_ADMIN", "ORG_ADMIN", "ORG_REVIEWER", "ORG_MEMBER")


def main() -> int:
    out: dict[str, object] = {"phase": "g178_proof"}
    model = describe_commercial_model()

    # ---- 178A: the approved numbers, exactly ------------------------
    out["persistent_license_model_ready"] = bool(
        PERSISTENT_LICENSE_PRICE_CENTS == APPROVED_LICENSE_CENTS
        and model["persistent_license_price"] == "$34,999.00"
        and model["money_is_integer_cents"]
        and model["no_draft_pricing_encoded"]
    )
    out["persistent_license_price_cents"] = PERSISTENT_LICENSE_PRICE_CENTS
    out["annual_maintenance_price_cents"] = ANNUAL_MAINTENANCE_PRICE_CENTS

    events = open_license(
        organization_id="org-A", purchased_at=PURCHASED, recorded_by="cc:staff-1"
    )
    ledger_from_events = replay(events)
    included_event = next(e for e in events if e["paid_through"])
    out["first_year_maintenance_included"] = bool(
        INCLUDED_MAINTENANCE_MONTHS == APPROVED_INCLUDED_MONTHS
        and str(included_maintenance_through(PURCHASED)) == INCLUDED_THROUGH
        and ledger_from_events["paid_through"] == INCLUDED_THROUGH
        # Included means free, not discounted.
        and included_event["amount_cents"] == 0
        and derive_entitlement(
            organization_id="org-A", ledger=ledger_from_events, as_of="2026-09-01"
        )["benefit_access"]
        == "BENEFIT_FULL"
    )

    renewal = renew_maintenance(
        organization_id="org-A",
        paid_at="2027-04-02",
        recorded_by="cc:staff-1",
        current_paid_through=INCLUDED_THROUGH,
    )
    out["annual_maintenance_model_ready"] = bool(
        ANNUAL_MAINTENANCE_PRICE_CENTS == APPROVED_MAINTENANCE_CENTS
        and renewal["amount_cents"] == APPROVED_MAINTENANCE_CENTS
        # Renewed late, still a whole year from the paid-through date.
        and renewal["paid_through"] == "2028-03-15"
        and describe_ledger_model()["renewal_extends_from_the_paid_through_date"]
    )

    # ---- 178A2: the intertribal consortium suite --------------------
    offering = describe_offering_model()
    dimensions = describe_quote_dimensions()

    complete = build_consortium_quote_request(
        consortium_name="Four Rivers Intertribal Consortium",
        member_organization_ids=["org:a", "org:b", "org:c", "org:d"],
        isolation_model=ISOLATION_HYBRID,
        complexity_level=COMPLEXITY_ELEVATED,
        complexity_factors=["CONSORTIUM_LEVEL_REPORTING"],
        seats_requested=28,
        requested_by="cc:sales-1",
        requested_at="2026-09-24",
    )
    isolated = build_consortium_quote_request(
        consortium_name="Two Rivers",
        member_organization_ids=["org:a", "org:b"],
        isolation_model=ISOLATION_ISOLATED_PER_MEMBER,
        complexity_level=COMPLEXITY_ELEVATED,
        seats_requested=10,
        requested_at="2026-09-24",
    )
    incomplete = build_consortium_quote_request(
        consortium_name="Unnamed",
        member_organization_ids=["org:a"],
        complexity_level=COMPLEXITY_UNKNOWN,
        requested_at="2026-09-24",
    )
    priced = dict(complete)
    priced["price_cents"] = 9_999_900

    out["consortium_offering_ready"] = bool(
        OFFERING_INTERTRIBAL_CONSORTIUM in offering["offerings"]
        and offering["every_offering_has_a_meaning"]
        and dimensions["dimensions"] == ["ISOLATION_NEED", "COMPLEXITY", "SEATS"]
        and complete["quotable"]
        and isolated["quotable"]
        and not quote_invariant_failures(complete)
        and not quote_invariant_failures(isolated)
        # An incomplete request says WHAT is missing, individually.
        and not incomplete["quotable"]
        and len(incomplete["blocking_unknowns"]) >= 3
        and not quote_invariant_failures(incomplete)
    )
    out["consortium_price_is_never_computed"] = bool(
        complete["price_cents"] is None
        and complete["requires_human_quote"]
        and offering["consortium_has_no_published_price"]
        and offering["consortium_price_is_never_computed"]
        and complete["reference_is_not_a_formula"]
        # And the refusal must be able to fire.
        and any("computed_price" in f for f in quote_invariant_failures(priced))
    )
    out["consortium_isolation_is_not_a_default"] = bool(
        offering["isolation_unknown_is_an_outcome_not_a_default"]
        and "isolation_model_not_stated" in incomplete["blocking_unknowns"]
    )
    out["consortium_quote_dimensions"] = dimensions["dimensions"]
    out["consortium_blocking_unknowns_example"] = incomplete["blocking_unknowns"]

    # ---- 178D: frozen is not deleted --------------------------------
    frozen = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2027-06-01"
    )
    expired = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2033-01-01"
    )
    out["frozen_not_deleted"] = bool(
        frozen["benefit_access"] == "BENEFIT_FROZEN"
        and frozen["license_held"]
        and not frozen["data_deleted"]
        and not frozen["organization_deleted"]
        and not frozen["history_deleted"]
        and all(a in frozen["available_actions"] for a in ALWAYS_AVAILABLE)
        and "EXPORT_OWN_DATA" in frozen["available_actions"]
        and not entitlement_invariant_failures(frozen)
        # And still true years after expiry.
        and not expired["data_deleted"]
        and "EXPORT_OWN_DATA" in expired["available_actions"]
        and "AUTHENTICATE" in expired["available_actions"]
    )
    out["frozen_available_action_count"] = len(frozen["available_actions"])
    out["frozen_locked_action_count"] = len(frozen["locked_actions"])

    # ---- 178E: three continuous years, and not a day sooner ---------
    at_1094 = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2030-03-13"
    )
    at_1095 = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2030-03-14"
    )
    at_1096 = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2030-03-15"
    )
    out["three_year_license_expiration_ready"] = bool(
        DELINQUENCY_DAYS_BEFORE_EXPIRATION == 1095
        and APPROVED_EXPIRY_YEARS == 3
        and at_1094["delinquency_days"] == 1094
        and at_1094["license_state"] == "LICENSED_FROZEN"
        # At exactly the boundary the licence is still held.
        and at_1095["delinquency_days"] == 1095
        and at_1095["license_state"] == "LICENSED_FROZEN"
        # Past it, and only then.
        and at_1096["license_state"] == "LICENSE_EXPIRED"
        and not at_1096["data_deleted"]
        and not entitlement_invariant_failures(at_1096)
    )

    # ---- 178F: relicensing ------------------------------------------
    owed = outstanding_maintenance_cents(events=events, as_of="2030-05-01")
    relicensed = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
        reason="the Tribe returned",
    )
    after = derive_entitlement(
        organization_id="org-A", ledger=relicensed["ledger"], as_of="2030-06-01"
    )
    by_customer = relicense(
        organization_id="org-A",
        events=events,
        purchased_at="2030-05-01",
        recorded_by="org-super",
        recorded_by_is_controlling_company=False,
    )
    out["relicense_ready"] = bool(
        relicensed["accepted"]
        and relicensed["appended"][0]["amount_cents"] == APPROVED_LICENSE_CENTS
        and after["license_state"] == "LICENSED_ACTIVE"
        and after["maintenance_state"] == "MAINTENANCE_CURRENT"
        and after["benefit_access"] == "BENEFIT_FULL"
        # And a customer cannot do it to themselves.
        and not by_customer["accepted"]
    )

    forgiveness = next(
        e
        for e in relicensed["appended"]
        if e["event_type"] == MAINTENANCE_FORGIVEN_EVENT
    )
    out["historical_maintenance_forgiven_on_relicense"] = bool(
        relicensed["forgiven_cents"] == owed
        and owed == APPROVED_MAINTENANCE_CENTS * 3
        # "Forgiven" with no figure is not a record.
        and forgiveness["amount_cents"] == owed
        and forgiveness["reason"]
        and describe_ledger_model()["forgiveness_does_not_erase_the_debt_record"]
    )
    out["forgiven_cents"] = relicensed["forgiven_cents"]

    # ---- 178I: history preserved ------------------------------------
    prior_ids = {e["event_id"] for e in events}
    after_ids = {e["event_id"] for e in relicensed["events"]}
    out["entitlement_history_preserved"] = bool(
        prior_ids <= after_ids
        and len(relicensed["events"]) > len(events)
        and not relicensed["delinquency_history_rewritten"]
        and not ledger_invariant_failures(before=events, after=relicensed["events"])
        and describe_ledger_model()["ledger_is_append_only"]
        and describe_ledger_model()["corrections_are_events_not_edits"]
        # And the refusal can fail: a ledger that lost an event is caught.
        and ledger_invariant_failures(
            before=events,
            after=[e for e in relicensed["events"] if e["event_id"] not in prior_ids],
        )
    )

    # ---- 178G: extensions -------------------------------------------
    grants = {}
    for days in APPROVED_EXTENSION_DAYS:
        grants[days] = grant_benefit_extension(
            organization_id="org-A",
            duration_days=days,
            granted_by="cc:staff-1",
            granted_by_role="CONTROLLING_COMPANY_ADMIN",
            reason="purchase order in flight",
            ledger=LEDGER,
            as_of="2027-06-01",
        )
    too_long = grant_benefit_extension(
        organization_id="org-A",
        duration_days=60,
        granted_by="cc:staff-1",
        granted_by_role="CONTROLLING_COMPANY_ADMIN",
        reason="r",
        ledger=LEDGER,
        as_of="2027-06-01",
    )
    out["benefit_extensions_7_14_30_ready"] = bool(
        tuple(EXTENSION_DAYS) == APPROVED_EXTENSION_DAYS
        and all(g["accepted"] for g in grants.values())
        and all(
            not extension_invariant_failures(g["extension"]) for g in grants.values()
        )
        and not too_long["accepted"]
        # An extension with no reason is refused.
        and not grant_benefit_extension(
            organization_id="org-A",
            duration_days=7,
            granted_by="cc:staff-1",
            granted_by_role="CONTROLLING_COMPANY_ADMIN",
            reason=None,
            ledger=LEDGER,
            as_of="2027-06-01",
        )["accepted"]
    )

    without = derive_entitlement(
        organization_id="org-A", ledger=LEDGER, as_of="2027-06-05"
    )
    with_ext = derive_entitlement(
        organization_id="org-A",
        ledger=LEDGER,
        extensions=[grants[30]["extension"]],
        as_of="2027-06-05",
    )
    out["extension_does_not_rewrite_billing_truth"] = bool(
        with_ext["benefit_access"] == "BENEFIT_EXTENDED"
        # Everything else is identical.
        and with_ext["delinquency_days"] == without["delinquency_days"]
        and with_ext["paid_through"] == without["paid_through"]
        and with_ext["maintenance_state"] == without["maintenance_state"]
        and with_ext["license_state"] == without["license_state"]
        and with_ext["days_until_license_expiration"]
        == without["days_until_license_expiration"]
        # And the extension recorded the delinquency it did not cure.
        and grants[30]["extension"]["underlying_maintenance_state"]
        == "MAINTENANCE_DELINQUENT"
        and grants[30]["extension"]["underlying_delinquency_days"] > 0
        and grants[30]["billing_truth_unchanged"]
    )

    # ---- 178H: the boundary -----------------------------------------
    customer_attempts = [
        grant_benefit_extension(
            organization_id="org-A",
            duration_days=7,
            granted_by="person-1",
            granted_by_role=role,
            reason="please",
            ledger=LEDGER,
            as_of="2027-06-01",
        )["accepted"]
        for role in CUSTOMER_ROLES
    ]
    out["controlling_company_extension_boundary_ready"] = bool(
        not any(customer_attempts)
        and authorize_commercial_action(
            action=ACTION_GRANT_EXTENSION, actor_role="CONTROLLING_COMPANY_ADMIN"
        )["permitted"]
        and ACTION_GRANT_EXTENSION in CONTROLLING_COMPANY_ONLY
    )

    forbidden = (
        ACTION_FORGIVE_DEBT,
        ACTION_SET_PAID_THROUGH,
        ACTION_RELICENSE,
        ACTION_CORRECT_LEDGER,
        ACTION_GRANT_EXTENSION,
    )
    out["customer_admin_cannot_override_entitlements"] = bool(
        all(
            not authorize_commercial_action(action=action, actor_role=role)["permitted"]
            for action in forbidden
            for role in CUSTOMER_ROLES
        )
        # But a customer may always SEE their own standing.
        and all(
            authorize_commercial_action(
                action=ACTION_VIEW_ENTITLEMENT, actor_role=role
            )["permitted"]
            for role in CUSTOMER_ROLES
        )
        and describe_entitlement_model()["customer_admin_cannot_forgive_debt"]
        and describe_entitlement_model()["customer_admin_cannot_relicense"]
    )

    # ---- 178L: self health ------------------------------------------
    health = prove_detectors_fire()
    out["entitlement_self_health_ready"] = bool(
        health["healthy_population_is_silent"]
        and health["all_detectors_fire"]
        and health["all_detectors_are_specific"]
        and len(DETECTORS) == 9
        and describe_self_health()["every_detector_has_a_meaning"]
        and describe_self_health()["ledger_comparison_uses_two_independent_sources"]
    )
    out["self_health_detector_count"] = len(DETECTORS)

    # ---- 178J: the corpus -------------------------------------------
    corpus = grade_corpus()
    out["corpus_case_count"] = corpus["case_count"]
    out["corpus_passed_count"] = corpus["passed_count"]
    out["corpus_failed_cases"] = [c["case_id"] for c in corpus["failed_cases"]]
    out["corpus_is_world_truth"] = corpus["corpus_is_world_truth"]
    out["money_moved_for_a_real_organization"] = corpus[
        "money_moved_for_a_real_organization"
    ]
    out["is_legal_advice"] = corpus["is_legal_advice"]
    out["every_case_pins_its_own_clock"] = describe_corpus()[
        "every_case_pins_its_own_clock"
    ]

    # ---- 178K: the access paths -------------------------------------
    repo = describe_repository()
    out["critical_query_count"] = repo["critical_query_count"]
    out["critical_queries"] = sorted(CRITICAL_QUERIES)
    out["forbidden_query_shapes"] = repo["forbidden_shapes"]
    out["fleet_questions_read_the_summary_not_the_ledger"] = repo[
        "fleet_questions_read_the_summary_not_the_ledger"
    ]

    # ---- 177 semantics still hold ------------------------------------
    try:
        from nativeforge.services.tenant_administration_service import (
            describe_administration_model,
        )
        from nativeforge.services.tribal_authority_model_service import (
            describe_authority_model,
        )

        authority = describe_authority_model()
        admin = describe_administration_model()
        out["gate177_semantics_preserved"] = bool(
            authority["no_single_verified_boolean"]
            and authority["self_asserted_affiliation_is_never_sufficient"]
            and authority["revocation_preserves_historical_work"]
            and admin["customer_admin_cannot_become_controlling_company"]
            and admin["tenancy_is_checked_before_privilege"]
        )
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        out["gate177_semantics_preserved"] = False
        out["gate177_probe_error"] = str(exc)[:200]

    out["network_requests"] = _ATTEMPTS["n"]
    out["fixture_residue"] = 0
    out["gate178_ready"] = bool(
        out["persistent_license_model_ready"]
        and out["consortium_offering_ready"]
        and out["consortium_price_is_never_computed"]
        and out["consortium_isolation_is_not_a_default"]
        and out["first_year_maintenance_included"]
        and out["annual_maintenance_model_ready"]
        and out["frozen_not_deleted"]
        and out["three_year_license_expiration_ready"]
        and out["relicense_ready"]
        and out["historical_maintenance_forgiven_on_relicense"]
        and out["benefit_extensions_7_14_30_ready"]
        and out["extension_does_not_rewrite_billing_truth"]
        and out["controlling_company_extension_boundary_ready"]
        and out["customer_admin_cannot_override_entitlements"]
        and out["entitlement_history_preserved"]
        and out["entitlement_self_health_ready"]
        and out["gate177_semantics_preserved"]
        and out["corpus_passed_count"] == out["corpus_case_count"]
        and out["network_requests"] == 0
    )
    out["generated_at"] = dt.datetime.now(dt.UTC).isoformat()

    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
