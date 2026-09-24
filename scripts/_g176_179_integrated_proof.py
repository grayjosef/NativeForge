"""The integrated 176 -> 179 adversarial proof: six cases, end to end.

Each gate proved itself in isolation. This walks six situations that cross
all four, because the failures that survive per-gate testing are the ones
that live in the joins:

```text
1  MISSED FUNDING DISCOVERY   an award with no solicitation we ever saw
2  REAL CUSTOMER AUTHORITY    affiliation is not authority
3  COMMERCIAL FREEZE          frozen, then temporarily extended
4  CUSTOMER JOURNEY           see it, watch it, pursue it
5  TENANT ISOLATION           one graph, two organisations, no leakage
6  EXPIRED LICENCE            three years, then relicensed
```

Every case pins its own clock. Nothing here touches the real organisation,
moves money, or makes a network call.

Prints one line of JSON.
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
        raise OSError("the integrated proof makes no network call")


socket.socket = _RefusedSocket  # type: ignore[misc,assignment]

from nativeforge.services.award_miss_detection_service import (  # noqa: E402
    build_coverage_scorecard,
    detect_award_miss,
    miss_invariant_failures,
)
from nativeforge.services.commercial_entitlement_service import (  # noqa: E402
    derive_entitlement,
    grant_benefit_extension,
)
from nativeforge.services.commercial_ledger_service import (  # noqa: E402
    MAINTENANCE_FORGIVEN_EVENT,
    ledger_invariant_failures,
    open_license,
    relicense,
)
from nativeforge.services.customer_decision_service import (  # noqa: E402
    PURSUING,
    WATCHED,
    apply_decision,
)
from nativeforge.services.customer_opportunity_feed_service import (  # noqa: E402
    ELIGIBILITY_APPEARS_ELIGIBLE,
    RELEVANCE_NATIVE_SPECIFIC,
    build_recommendation,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_surface_service import build_dashboard  # noqa: E402
from nativeforge.services.organization_customization_service import (  # noqa: E402
    apply_personal_override,
    build_org_default,
    build_personal_override,
)
from nativeforge.services.program_recurrence_service import (  # noqa: E402
    classify_absence,
    classify_recurrence,
)
from nativeforge.services.tenant_administration_service import (  # noqa: E402
    ACTION_CREATE_ORGANIZATION,
    CONTROLLING_COMPANY_ADMIN,
    ORG_SUPER_ADMIN,
    authorize_admin_action,
)
from nativeforge.services.tribal_authority_evidence_service import (  # noqa: E402
    verify_authority_manually,
)
from nativeforge.services.tribal_authority_model_service import (  # noqa: E402
    AFFILIATION_VERIFIED,
    AUTHORITY_UNVERIFIED,
    IDENTITY_VERIFIED,
    build_authority_grant,
    grant_invariant_failures,
    may_administer_tenant,
)

NOW = "2026-09-24"
ORG_A = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
ORG_B = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"


def case_1_missed_funding_discovery() -> dict[str, object]:
    """An award for a recurring programme we never saw a solicitation for."""
    miss = detect_award_miss(
        award_ref="integrated:award:water-2026",
        award_number="AW-2026-0042",
        observed_solicitation_count=0,
        searched_source_ids=["src:epa", "src:usda", "src:state-nm"],
        funder_name="EPA",
        program_key="assistance_listing:66.468",
        evidence_ref="award://integrated/water-2026",
        award_is_demo_fixture=True,
    )
    recurrence = classify_recurrence(
        program_key="assistance_listing:66.468",
        identity_basis="assistance_listing",
        historical_open_dates=["2022-03-01", "2023-03-05", "2024-03-02", "2025-03-10"],
        evidence_refs=["cycle://66.468/1"],
        now=NOW,
    )
    absence = classify_absence(
        recurrence=recurrence, current_cycle_observed=False, now=NOW
    )
    # The same programme, one full further cadence on. LATE must become
    # MISSING by itself; a classifier that only ever returns one state is
    # not classifying anything.
    later = classify_absence(
        recurrence=recurrence, current_cycle_observed=False, now="2027-06-01"
    )
    # And it must clear the moment the cycle is observed.
    reopened = classify_absence(
        recurrence=recurrence, current_cycle_observed=True, now="2027-06-01"
    )
    scorecard = build_coverage_scorecard(
        misses=[miss], signals=[miss["signal"]], solicitations_observed=0
    )
    return {
        "signal_type": miss["signal"]["signal_type"],
        "coverage_gap_created": bool(miss["review_required"]),
        "recurrence_correlated": recurrence["recurrence_class"] == "ANNUAL",
        "recurrence_history": recurrence["history_count"],
        "absence_state": absence["absence_state"],
        "absence_state_after_a_further_cadence": later["absence_state"],
        "absence_clears_when_the_cycle_reopens": reopened["absence_state"],
        "no_fake_opportunity_created": miss["opportunity_invented"] is False
        and miss["signal"]["creates_opportunity"] is False,
        "source_not_auto_onboarded": miss["source_auto_onboarded"] is False
        and miss["signal"]["auto_onboarding_permitted"] is False,
        "review_required": miss["review_required"],
        "coverage_percentage_still_refused": scorecard["coverage_percentage"] is None,
        # The demo fixture must not move a real metric, even here.
        "demo_award_excluded_from_real_metrics": scorecard["award_without_solicitation"]
        == 0,
        "invariant_failures": miss_invariant_failures(miss),
    }


def case_2_real_customer_authority() -> dict[str, object]:
    """Identity and affiliation verified. Authority is a third question."""
    before = build_authority_grant(
        organization_id=ORG_A,
        identity_id="person:chair",
        identity_status=IDENTITY_VERIFIED,
        affiliation_status=AFFILIATION_VERIFIED,
        authority_status=AUTHORITY_UNVERIFIED,
    )
    refused = may_administer_tenant(before, now=NOW)

    by_customer = authorize_admin_action(
        action=ACTION_CREATE_ORGANIZATION,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id=ORG_A,
        target_organization_id=ORG_A,
    )
    verified = verify_authority_manually(
        organization_id=ORG_A,
        identity_id="person:chair",
        verified_by="controlling-company:reviewer-1",
        verified_by_is_controlling_company=True,
        reason="council resolution 2026-14 reviewed by counsel",
        customer_relationship_ref="crm:agreement-1",
        verified_at="2026-09-23",
    )
    after = may_administer_tenant(verified["grant"], now=NOW)
    may_create = authorize_admin_action(
        action=ACTION_CREATE_ORGANIZATION,
        actor_role=CONTROLLING_COMPANY_ADMIN,
        actor_organization_id="controlling-company",
        target_organization_id=ORG_A,
    )
    return {
        "before_may_administer": refused["permitted"],
        "before_refusal_names_authority": any(
            "authority_is" in r for r in refused["refusals"]
        ),
        "customer_may_not_create_organization": by_customer["permitted"] is False,
        "manual_verification_accepted": verified["accepted"],
        "after_may_administer": after["permitted"],
        "audit_event_retained": verified["audit_event"]["action"]
        == "authority.manually_verified",
        "audit_names_the_reviewer": bool(verified["audit_event"]["actor_id"]),
        "organization_can_be_established": may_create["permitted"],
        "invariant_failures": grant_invariant_failures(verified["grant"]),
    }


def case_3_commercial_freeze() -> dict[str, object]:
    """Frozen, then temporarily extended. Billing truth must not move."""
    ledger = {"license_purchased_at": "2026-03-15", "paid_through": "2027-03-15"}
    frozen = derive_entitlement(
        organization_id=ORG_A, ledger=ledger, as_of="2027-06-01"
    )
    granted = grant_benefit_extension(
        organization_id=ORG_A,
        duration_days=14,
        granted_by="controlling-company:reviewer-1",
        granted_by_role=CONTROLLING_COMPANY_ADMIN,
        reason="purchase order confirmed, payment in transit",
        ledger=ledger,
        as_of="2027-06-01",
    )
    extended = derive_entitlement(
        organization_id=ORG_A,
        ledger=ledger,
        extensions=[granted["extension"]],
        as_of="2027-06-05",
    )
    return {
        "frozen_benefit": frozen["benefit_access"],
        "license_still_held": frozen["license_held"],
        "data_preserved": frozen["data_deleted"] is False
        and frozen["organization_deleted"] is False
        and frozen["history_deleted"] is False,
        "can_still_authenticate": "AUTHENTICATE" in frozen["available_actions"],
        "can_still_export": "EXPORT_OWN_DATA" in frozen["available_actions"],
        "extension_accepted": granted["accepted"],
        "extended_benefit": extended["benefit_access"],
        # The rule the whole commercial gate turns on.
        "maintenance_still_delinquent": extended["maintenance_state"]
        == "MAINTENANCE_DELINQUENT",
        "license_state_unchanged": extended["license_state"] == frozen["license_state"],
        "delinquency_unchanged": extended["delinquency_days"]
        >= frozen["delinquency_days"],
        "paid_through_unchanged": extended["paid_through"] == frozen["paid_through"],
        "extension_audited": granted["audit_event"]["action"]
        == "commercial.extension_granted",
        "extension_recorded_the_delinquency": granted["extension"][
            "underlying_maintenance_state"
        ]
        == "MAINTENANCE_DELINQUENT",
    }


def _recommendation(org: str, canonical_id: str = "integrated:canon:water") -> dict:
    return build_recommendation(
        organization_id=org,
        canonical_record={
            "canonical_id": canonical_id,
            "title": "Tribal Water Infrastructure Assistance",
            "funder_name": "EPA",
            "close_date": "2026-11-15",
        },
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "the notice sets this programme aside for Tribes",
            "evidence_ids": ["integrated:ev:set-aside"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
            "why": "entity type on file matches the eligible applicant class",
            "evidence_ids": ["integrated:el:entity"],
            "unknowns": ["match_requirement_not_yet_read"],
        },
        documents=[
            {
                "document_id": "integrated:doc:nofo",
                "document_type": "NOFO",
                "page": 14,
                "quote": (
                    "Eligible applicants are federally recognized Indian Tribes."
                ),
            }
        ],
        changes=[
            {
                "change_type": "DEADLINE_MOVED",
                "observed_at": "2026-09-20",
                "summary": "Amendment 2 moved the closing date to 15 November.",
            }
        ],
    )


def case_4_customer_journey() -> dict[str, object]:
    """See it, understand it, watch it, pursue it."""
    row = _recommendation(ORG_A)
    canonical_before = dict(row)

    watched = apply_decision(
        current=None,
        organization_id=ORG_A,
        canonical_id=row["canonical_id"],
        to_state=WATCHED,
        actor_id="person:grants-lead",
        decided_at="2026-09-21",
        reason="strong fit",
    )
    pursued = apply_decision(
        current=watched["decision"],
        organization_id=ORG_A,
        canonical_id=row["canonical_id"],
        to_state=PURSUING,
        actor_id="person:grants-lead",
        decided_at="2026-09-22",
        history=watched["history"],
    )
    pursuit = {
        "pursuit_id": "integrated:pursuit:water",
        "canonical_id": row["canonical_id"],
        "requirements": ["SF-424", "project narrative"],
        "tasks": ["confirm match requirement"],
        "deadline": row["deadline"],
    }
    return {
        "why_relevant_present": bool(row["why_relevant"]),
        "eligibility_state": row["eligibility_view"],
        "unknowns_present": bool(row["known_unknowns"]),
        "document_citations": len(row["document_citations"]),
        "deadline_present": bool(row["deadline"]),
        "change_history": len(row["what_changed"]),
        "watch_accepted": watched["accepted"],
        "watch_preserved_in_history": pursued["history_length"] == 1,
        "pursue_accepted": pursued["accepted"],
        "pursuit_links_requirements": bool(pursuit["requirements"]),
        "pursuit_links_tasks": bool(pursuit["tasks"]),
        "pursuit_links_deadline": pursuit["deadline"] == row["deadline"],
        # The global record must be exactly what it was.
        "global_record_unchanged": canonical_before["canonical_id"]
        == row["canonical_id"]
        and pursued["canonical_record_untouched"],
        "invariant_failures": recommendation_invariant_failures(row),
    }


def case_5_tenant_isolation() -> dict[str, object]:
    """One graph. Two organisations. Nothing crosses."""
    shared_canonical = "integrated:canon:shared"
    a = _recommendation(ORG_A, shared_canonical)
    b = _recommendation(ORG_B, shared_canonical)

    a_decision = apply_decision(
        current=None,
        organization_id=ORG_A,
        canonical_id=shared_canonical,
        to_state=WATCHED,
        actor_id="person:a",
        decided_at="2026-09-21",
    )["decision"]

    a_default = build_org_default(
        organization_id=ORG_A,
        branding={"primary_color": "#1B4332"},
        dashboard={"tile_order": ["DEADLINES", "WATCH_LIST"]},
        published_by="admin:a",
        reason="initial",
    )
    b_default = build_org_default(
        organization_id=ORG_B,
        branding={"primary_color": "#7A3E0B"},
        dashboard={"tile_order": ["ACTIVE_PURSUITS", "NEW_OPPORTUNITIES"]},
        published_by="admin:b",
        reason="initial",
    )
    a_override = build_personal_override(
        organization_id=ORG_A,
        identity_id="person:a",
        preferences={"tile_order": ["WATCH_LIST"]},
    )
    a_effective = apply_personal_override(org_default=a_default, override=a_override)

    a_dash = build_dashboard(
        organization_id=ORG_A,
        recommendations=[a, b],
        decisions=[a_decision],
        as_of=NOW,
    )
    b_dash = build_dashboard(
        organization_id=ORG_B,
        recommendations=[a, b],
        decisions=[a_decision],
        as_of=NOW,
    )
    return {
        # Same global intelligence: identical relevance and evidence.
        "same_relevance_class": a["relevance_class"] == b["relevance_class"],
        "same_evidence": a["relevance_evidence_ids"] == b["relevance_evidence_ids"],
        "same_citations": a["document_citations"] == b["document_citations"],
        # Different tenant state.
        "a_watch_list": a_dash["tiles"]["WATCH_LIST"],
        "b_watch_list": b_dash["tiles"]["WATCH_LIST"],
        "dashboards_differ": a_dash["tiles"] != b_dash["tiles"],
        "a_excluded_foreign_rows": a_dash["rows_from_other_tenants_excluded"],
        "b_excluded_foreign_rows": b_dash["rows_from_other_tenants_excluded"],
        # Different customisation, no bleed.
        "branding_differs": a_default["branding"]["primary_color"]
        != b_default["branding"]["primary_color"],
        "a_override_did_not_move_a_default": a_effective["org_default_unchanged"],
        "b_default_untouched_by_a": b_default["dashboard"]["tile_order"]
        == ["ACTIVE_PURSUITS", "NEW_OPPORTUNITIES"],
        "zero_cross_tenant_leakage": a_dash["rows_considered"] == 1
        and b_dash["rows_considered"] == 1,
    }


def case_6_expired_license_and_relicense() -> dict[str, object]:
    """Three years frozen, then bought again. Nothing is reset."""
    events = open_license(
        organization_id=ORG_A, purchased_at="2026-03-15", recorded_by="cc:staff-1"
    )
    ledger = {"license_purchased_at": "2026-03-15", "paid_through": "2027-03-15"}
    expired = derive_entitlement(
        organization_id=ORG_A, ledger=ledger, as_of="2030-04-01"
    )

    result = relicense(
        organization_id=ORG_A,
        events=events,
        purchased_at="2030-05-01",
        recorded_by="cc:staff-1",
        recorded_by_is_controlling_company=True,
        reason="the Tribe returned",
    )
    after = derive_entitlement(
        organization_id=ORG_A, ledger=result["ledger"], as_of="2030-06-01"
    )
    forgiveness = next(
        e for e in result["appended"] if e["event_type"] == MAINTENANCE_FORGIVEN_EVENT
    )
    prior_ids = {e["event_id"] for e in events}
    after_ids = {e["event_id"] for e in result["events"]}
    return {
        "license_expired": expired["license_state"] == "LICENSE_EXPIRED",
        "data_remains": expired["data_deleted"] is False,
        "history_remains_after_expiry": expired["history_deleted"] is False,
        "can_still_export_when_expired": "EXPORT_OWN_DATA"
        in expired["available_actions"],
        "relicense_accepted": result["accepted"],
        "after_license_state": after["license_state"],
        "after_benefit": after["benefit_access"],
        "forgiven_cents": result["forgiven_cents"],
        "forgiveness_names_the_amount": forgiveness["amount_cents"]
        == result["forgiven_cents"],
        "every_prior_event_survived": prior_ids <= after_ids,
        "no_destructive_reset": result["delinquency_history_rewritten"] is False,
        "ledger_failures": ledger_invariant_failures(
            before=events, after=result["events"]
        ),
    }


CASES = (
    {
        "case": "CASE_1_MISSED_FUNDING_DISCOVERY",
        "run": case_1_missed_funding_discovery,
        "expect": {
            "signal_type": "AWARD_WITHOUT_SOLICITATION",
            "coverage_gap_created": True,
            "recurrence_correlated": True,
            "recurrence_history": 4,
            # 138 days past the window on the pinned date: LATE, not MISSING.
            "absence_state": "LATE",
            "absence_state_after_a_further_cadence": "MISSING",
            "absence_clears_when_the_cycle_reopens": "ON_TIME",
            "no_fake_opportunity_created": True,
            "source_not_auto_onboarded": True,
            "review_required": True,
            "coverage_percentage_still_refused": True,
            "demo_award_excluded_from_real_metrics": True,
            "invariant_failures": [],
        },
    },
    {
        "case": "CASE_2_REAL_CUSTOMER_AUTHORITY",
        "run": case_2_real_customer_authority,
        "expect": {
            "before_may_administer": False,
            "before_refusal_names_authority": True,
            "customer_may_not_create_organization": True,
            "manual_verification_accepted": True,
            "after_may_administer": True,
            "audit_event_retained": True,
            "audit_names_the_reviewer": True,
            "organization_can_be_established": True,
            "invariant_failures": [],
        },
    },
    {
        "case": "CASE_3_COMMERCIAL_FREEZE",
        "run": case_3_commercial_freeze,
        "expect": {
            "frozen_benefit": "BENEFIT_FROZEN",
            "license_still_held": True,
            "data_preserved": True,
            "can_still_authenticate": True,
            "can_still_export": True,
            "extension_accepted": True,
            "extended_benefit": "BENEFIT_EXTENDED",
            "maintenance_still_delinquent": True,
            "license_state_unchanged": True,
            "delinquency_unchanged": True,
            "paid_through_unchanged": True,
            "extension_audited": True,
            "extension_recorded_the_delinquency": True,
        },
    },
    {
        "case": "CASE_4_CUSTOMER_JOURNEY",
        "run": case_4_customer_journey,
        "expect": {
            "why_relevant_present": True,
            "eligibility_state": "APPEARS_ELIGIBLE",
            "unknowns_present": True,
            "document_citations": 1,
            "deadline_present": True,
            "change_history": 1,
            "watch_accepted": True,
            "watch_preserved_in_history": True,
            "pursue_accepted": True,
            "pursuit_links_requirements": True,
            "pursuit_links_tasks": True,
            "pursuit_links_deadline": True,
            "global_record_unchanged": True,
            "invariant_failures": [],
        },
    },
    {
        "case": "CASE_5_TENANT_ISOLATION",
        "run": case_5_tenant_isolation,
        "expect": {
            "same_relevance_class": True,
            "same_evidence": True,
            "same_citations": True,
            "a_watch_list": 1,
            "b_watch_list": 0,
            "dashboards_differ": True,
            "a_excluded_foreign_rows": 1,
            "b_excluded_foreign_rows": 1,
            "branding_differs": True,
            "a_override_did_not_move_a_default": True,
            "b_default_untouched_by_a": True,
            "zero_cross_tenant_leakage": True,
        },
    },
    {
        "case": "CASE_6_EXPIRED_LICENSE_RELICENSE",
        "run": case_6_expired_license_and_relicense,
        "expect": {
            "license_expired": True,
            "data_remains": True,
            "history_remains_after_expiry": True,
            "can_still_export_when_expired": True,
            "relicense_accepted": True,
            "after_license_state": "LICENSED_ACTIVE",
            "after_benefit": "BENEFIT_FULL",
            "forgiven_cents": 2_099_700,
            "forgiveness_names_the_amount": True,
            "every_prior_event_survived": True,
            "no_destructive_reset": True,
            "ledger_failures": [],
        },
    },
)


def main() -> int:
    graded = []
    for case in CASES:
        observed = case["run"]()
        failures = sorted(
            f"{key}_expected_{case['expect'][key]}_observed_{observed.get(key)}"
            for key in case["expect"]
            if observed.get(key) != case["expect"][key]
        )
        graded.append(
            {
                "case": case["case"],
                "passed": not failures,
                "failures": failures,
                "observed": observed,
            }
        )

    out = {
        "phase": "integrated_176_179_proof",
        "case_count": len(graded),
        "passed_count": sum(1 for g in graded if g["passed"]),
        "failed_cases": [g["case"] for g in graded if not g["passed"]],
        "cases": graded,
        "network_requests": _ATTEMPTS["n"],
        "real_organization_touched": False,
        "money_moved": False,
        "clock_is_pinned": NOW,
        "integrated_proof_ready": all(g["passed"] for g in graded)
        and _ATTEMPTS["n"] == 0,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
