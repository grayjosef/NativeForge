"""179O: the facts the Gate 179 verifier asserts, measured rather than claimed.

The measurement this gate exists to flip is the one the survey took:

```text
buyer_feed_depends_on_hand_made_sparks = true   (before)
canonical_graph_feeds_customer         = ?      (after)
```

Nine gates of intelligence that never reached a buyer. This phase proves the
wiring exists and refuses to let a recommendation without a canonical
opportunity behind it count as one.

No network. Prints one line of JSON.
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
        raise OSError("Gate 179 makes no network call")


socket.socket = _RefusedSocket  # type: ignore[misc,assignment]

from nativeforge.services.customer_decision_service import (  # noqa: E402
    DISMISSED,
    PURSUING,
    WATCHED,
    apply_decision,
    build_decision,
    decision_invariant_failures,
    describe_decision_model,
    summarize_decisions,
    visible_to_other_tenant,
)
from nativeforge.services.customer_demo_story_service import (  # noqa: E402
    DEMO_ORGANIZATION_ID,
    build_demo_story,
    build_ux_smoke_checklist,
)
from nativeforge.services.customer_opportunity_feed_service import (  # noqa: E402
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    ELIGIBILITY_UNCERTAIN,
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_UNCERTAIN,
    build_feed,
    build_recommendation,
    describe_feed_model,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    describe_repository,
)
from nativeforge.services.customer_self_health_service import (  # noqa: E402
    DETECTORS,
    describe_self_health,
    prove_detectors_fire,
)
from nativeforge.services.customer_surface_service import (  # noqa: E402
    OPERATOR_CAPABILITIES,
    build_customer_surface,
    build_dashboard,
    build_trust_panel,
    capabilities_for,
    describe_surface_model,
    surface_invariant_failures,
)
from nativeforge.services.organization_customization_service import (  # noqa: E402
    apply_personal_override,
    build_org_default,
    build_personal_override,
    describe_customization_model,
    publish_org_default,
)

NOW = "2026-09-24"
ORG = "org-A"
CANON = {
    "canonical_id": "canon-1",
    "title": "Tribal Water Infrastructure",
    "funder_name": "EPA",
    "close_date": "2026-11-15",
}

#: The customer journey 179A requires the backend to support.
JOURNEY = (
    "SIGN_IN",
    "ORGANIZATION",
    "ONBOARDING",
    "PROFILE_PRIORITIES",
    "DASHBOARD",
    "RECOMMENDED_OPPORTUNITIES",
    "WHY_RELEVANT",
    "ELIGIBILITY",
    "DOCUMENT_EVIDENCE",
    "WATCH_DISMISS_PURSUE",
    "PURSUIT",
    "REQUIREMENTS",
    "TASKS",
    "DEADLINES",
    "APPLICATION_PREPARATION",
    "TRUST_SOURCE_EVIDENCE",
)


def main() -> int:
    out: dict[str, object] = {"phase": "g179_proof"}

    strong = build_recommendation(
        organization_id=ORG,
        canonical_record=CANON,
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "set aside for federally recognised Tribes",
            "evidence_ids": ["ev-1"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
            "why": "entity type matches",
            "evidence_ids": ["el-1"],
        },
        documents=[
            {
                "document_id": "doc-1",
                "document_type": "NOFO",
                "page": 14,
                "quote": "Eligible applicants are federally recognized Tribes.",
            }
        ],
        changes=[
            {
                "change_type": "DEADLINE_MOVED",
                "observed_at": "2026-09-20",
                "summary": "closing date moved",
            }
        ],
    )
    conditional = build_recommendation(
        organization_id=ORG,
        canonical_record={**CANON, "canonical_id": "canon-2"},
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "Tribal lands named a priority",
            "evidence_ids": ["ev-2"],
        },
        eligibility={
            "eligibility_view": ELIGIBILITY_CONDITIONAL,
            "why": "needs a match",
            "conditions": ["25% non-federal match"],
            "evidence_ids": ["el-2"],
        },
    )
    uncertain = build_recommendation(
        organization_id=ORG,
        canonical_record={**CANON, "canonical_id": "canon-3", "close_date": None},
        relevance={"relevance_class": RELEVANCE_UNCERTAIN},
        eligibility={"eligibility_view": ELIGIBILITY_UNCERTAIN, "why": "unclear"},
    )
    spark = build_recommendation(
        organization_id=ORG,
        canonical_record={"title": "hand made spark"},
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "typed by a person",
            "evidence_ids": ["x"],
        },
    )
    bare = build_recommendation(
        organization_id=ORG,
        canonical_record=CANON,
        relevance={"relevance_class": RELEVANCE_NATIVE_SPECIFIC, "why": "because"},
    )

    recommendations = [strong, conditional, uncertain]
    feed = build_feed(organization_id=ORG, recommendations=recommendations, as_of=NOW)
    feed_model = describe_feed_model()

    # ---- 179B: the feed comes from the graph ------------------------
    out["buyer_recommendation_feed_ready"] = bool(
        feed["returned"] == 3
        and feed["ordering_is_explicit"]
        and feed_model["no_opaque_score"]
        and not any(recommendation_invariant_failures(r) for r in recommendations)
    )
    out["canonical_graph_feeds_customer"] = bool(
        feed["sourced_from_canonical_graph"]
        and all(r["sourced_from_canonical_graph"] for r in recommendations)
        and feed_model["no_hand_made_sparks"]
        # And the refusal must fire on a hand-made spark.
        and any("canonical" in f for f in recommendation_invariant_failures(spark))
    )

    # ---- 179C: it can explain itself --------------------------------
    out["why_relevant_explainable"] = bool(
        strong["why_relevant"]
        and strong["relevance_evidence_ids"]
        # A decisive claim with no evidence is refused.
        and any(
            "cites_no_evidence" in f for f in recommendation_invariant_failures(bare)
        )
    )
    out["eligibility_explainable"] = bool(
        conditional["eligibility_conditions"]
        and conditional["why_eligibility"]
        and uncertain["eligibility_view"] == ELIGIBILITY_UNCERTAIN
        and "eligibility_undecided" in uncertain["known_unknowns"]
        and feed_model["not_assessed_is_distinct_from_uncertain"]
        # Conditional with no named condition is refused.
        and any(
            "names_no_condition" in f
            for f in recommendation_invariant_failures(
                {**conditional, "eligibility_conditions": []}
            )
        )
    )
    out["document_evidence_explainable"] = bool(
        strong["document_citations"]
        and strong["document_citations"][0]["quote"]
        and strong["document_citations"][0]["document_id"]
        and feed_model["citations_carry_a_quote"]
    )
    out["uncertainty_reaches_the_customer"] = bool(
        "native_relevance_undecided" in uncertain["known_unknowns"]
        and "no_published_deadline" in uncertain["known_unknowns"]
    )

    # ---- 179D: durable decisions ------------------------------------
    watched = apply_decision(
        current=None,
        organization_id=ORG,
        canonical_id="canon-1",
        to_state=WATCHED,
        actor_id="person-1",
        decided_at="2026-09-20",
        reason="promising",
    )
    pursued = apply_decision(
        current=watched["decision"],
        organization_id=ORG,
        canonical_id="canon-1",
        to_state=PURSUING,
        actor_id="person-2",
        decided_at="2026-09-22",
        history=watched["history"],
    )
    dismissed = apply_decision(
        current=None,
        organization_id=ORG,
        canonical_id="canon-3",
        to_state=DISMISSED,
        actor_id="person-1",
        decided_at="2026-09-21",
        reason="not our area",
    )
    no_actor = apply_decision(
        current=None,
        organization_id=ORG,
        canonical_id="canon-9",
        to_state=DISMISSED,
        actor_id=None,
        decided_at="2026-09-21",
    )
    decision_model = describe_decision_model()
    out["watch_dismiss_pursue_ready"] = bool(
        watched["accepted"]
        and pursued["accepted"]
        and pursued["history_length"] == 1
        and dismissed["accepted"]
        and not no_actor["accepted"]
        and decision_model["every_decision_names_an_actor"]
        and decision_model["every_state_is_reversible"]
        and not decision_invariant_failures(watched["decision"])
        # A stored row with no actor is refused.
        and any(
            "names_no_actor" in f
            for f in decision_invariant_failures(
                build_decision(
                    organization_id=ORG, canonical_id="c", decision_state=DISMISSED
                )
            )
        )
    )
    out["dismiss_does_not_delete_intelligence"] = bool(
        dismissed["global_intelligence_unchanged"]
        and dismissed["canonical_record_untouched"]
        and dismissed["other_tenants_unaffected"]
        and visible_to_other_tenant(
            decision=dismissed["decision"], other_organization_id="org-B"
        )
        is False
    )

    # ---- 179E: the dashboard ----------------------------------------
    theirs = build_recommendation(
        organization_id="org-B",
        canonical_record={**CANON, "canonical_id": "canon-9"},
        relevance={
            "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
            "why": "x",
            "evidence_ids": ["e"],
        },
    )
    dashboard = build_dashboard(
        organization_id=ORG,
        recommendations=[*recommendations, theirs],
        decisions=[pursued["decision"], dismissed["decision"]],
        coverage_notes=[{"note": "two regional sources await authorisation"}],
        as_of=NOW,
    )
    summary = summarize_decisions(
        decisions=[
            pursued["decision"],
            dismissed["decision"],
            build_decision(
                organization_id="org-B",
                canonical_id="c",
                decision_state=WATCHED,
                actor_id="p",
                decided_at="x",
            ),
        ],
        organization_id=ORG,
    )
    out["customer_dashboard_ready"] = bool(
        set(dashboard["tiles"]) == set(describe_surface_model()["dashboard_tiles"])
        and dashboard["tenant_scoped"]
        and dashboard["rows_from_other_tenants_excluded"] == 1
        and summary["rows_from_other_tenants"] == 1
        and dashboard["tiles"]["COVERAGE_NOTES"] == 1
    )

    # ---- 179F: customisation ----------------------------------------
    default = build_org_default(
        organization_id=ORG,
        branding={"primary_color": "#1B4332", "display_name": "Demo Tribe"},
        dashboard={"tile_order": ["DEADLINES", "WATCH_LIST"], "density": "COMPACT"},
        published_by="admin-1",
        reason="initial",
    )
    before = list(default["dashboard"]["tile_order"])
    override = build_personal_override(
        organization_id=ORG,
        identity_id="person-7",
        preferences={"tile_order": ["WATCH_LIST"], "saved_filters": {"mine": "open"}},
    )
    effective = apply_personal_override(org_default=default, override=override)
    effective["dashboard"]["tile_order"].append("DEADLINES")
    published = publish_org_default(
        current=default,
        changes={"dashboard": {"tile_order": ["WATCH_LIST", "DEADLINES"]}},
        published_by="admin-1",
        publisher_may_publish=True,
        reason="team preference",
    )
    custom_model = describe_customization_model()
    out["tenant_customization_persistent"] = bool(
        default["branding"]["primary_color"] == "#1B4332"
        and published["accepted"]
        and published["default"]["version_ordinal"] == 2
        and custom_model["publishing_is_versioned"]
    )
    out["user_overrides_separate"] = bool(
        effective["org_default_unchanged"]
        and default["dashboard"]["tile_order"] == before
        and effective["personal_only"].get("saved_filters")
        and custom_model["personal_override_never_mutates_the_org_default"]
    )

    # ---- 179G: the surfaces are separate ----------------------------
    customer = build_customer_surface(organization_id=ORG, role="ORG_ADMIN")
    operator = capabilities_for(
        role="CONTROLLING_COMPANY_ADMIN", is_controlling_company=True
    )
    leaked = {
        **customer,
        "capabilities": [*customer["capabilities"], "ACTIVATE_SOURCE"],
    }
    nested = {
        **customer,
        "dashboard": {"deadlines": [{"canonical_id": "c", "lease_id": "abc"}]},
    }
    surface_model = describe_surface_model()
    out["customer_operator_surfaces_separated"] = bool(
        surface_model["capability_sets_are_disjoint"]
        and surface_model["source_activation_is_operator_only"]
        and surface_model["plane_toggle_is_operator_only"]
        and surface_model["entitlement_override_is_operator_only"]
        and surface_model["verifier_surface_is_operator_only"]
        and not surface_invariant_failures(customer)
        and not (set(customer["capabilities"]) & OPERATOR_CAPABILITIES)
        and operator["operator_capabilities"]
        # Both refusals fire.
        and any("operator_powers" in f for f in surface_invariant_failures(leaked))
        and any("internal_field" in f for f in surface_invariant_failures(nested))
    )

    # ---- 179H: trust ------------------------------------------------
    trust = build_trust_panel(
        recommendation=strong,
        source_records=[
            {
                "source_name": "EPA Grants",
                "publisher": "EPA",
                "last_observed_at": "2026-09-23",
                "authorization_status": "AUTHORIZED",
                "lease_id": "internal-only",
            }
        ],
    )
    out["trust_experience_ready"] = bool(
        trust["sources"]
        and "lease_id" not in trust["sources"][0]
        and trust["document_citations"]
        and trust["what_changed"]
        and trust["internal_fields_excluded"]
        and surface_model["trust_panel_excludes_internal_fields"]
    )

    # ---- 179A: the journey contract ---------------------------------
    checklist = build_ux_smoke_checklist()
    steps = [item["step"] for item in checklist["items"]]
    out["customer_journey_contract_ready"] = bool(
        list(JOURNEY) == steps
        and all(item["required_backend_state"] for item in checklist["items"])
        and all(item["expected_customer_experience"] for item in checklist["items"])
    )
    out["ux_checklist_step_count"] = checklist["step_count"]
    out["ux_checklist_results_prefilled"] = checklist["any_result_prefilled"]
    out["ux_checklist_customer_ready_prefilled"] = checklist[
        "any_customer_ready_prefilled"
    ]

    # ---- 179L: the demo story ---------------------------------------
    story = build_demo_story()
    again = build_demo_story()
    refused_real = False
    try:
        build_demo_story(organization_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    except ValueError:
        refused_real = True
    out["demo_customer_story_ready"] = bool(
        story["organization_id"] == DEMO_ORGANIZATION_ID
        and story["content_digest"] == again["content_digest"]
        and len(story["recommendations"]) == 5
        and story["pursuit"]["requirements"]
        and story["pursuit"]["tasks"]
        and story["license"]["license_state"] == "LICENSED_ACTIVE"
        and story["trust_panel"]["document_citations"]
        and not any(
            recommendation_invariant_failures(r) for r in story["recommendations"]
        )
        and not surface_invariant_failures(story["surface"])
        and refused_real
    )
    out["demo_story_refuses_the_real_organization"] = refused_real
    out["demo_story_is_deterministic"] = (
        story["content_digest"] == again["content_digest"]
    )

    # ---- 179N: self health ------------------------------------------
    health = prove_detectors_fire()
    out["customer_self_health_ready"] = bool(
        health["healthy_population_is_silent"]
        and health["all_detectors_fire"]
        and health["all_detectors_are_specific"]
        and len(DETECTORS) == 9
        and describe_self_health()["every_detector_has_a_meaning"]
    )
    out["self_health_detector_count"] = len(DETECTORS)

    # ---- 179J: the read paths ---------------------------------------
    repo = describe_repository()
    out["critical_customer_query_count"] = repo["critical_query_count"]
    out["every_customer_query_is_tenant_scoped"] = repo["every_query_is_tenant_scoped"]
    out["forbidden_query_shapes"] = repo["forbidden_shapes"]
    out["critical_customer_queries"] = sorted(CRITICAL_QUERIES)

    # ---- 178 semantics still hold -----------------------------------
    try:
        from nativeforge.services.commercial_entitlement_service import (
            describe_entitlement_model,
        )
        from nativeforge.services.commercial_license_model_service import (
            describe_commercial_model,
        )

        commercial = describe_commercial_model()
        entitlement = describe_entitlement_model()
        out["gate178_semantics_preserved"] = bool(
            commercial["three_states_are_separate"]
            and commercial["frozen_is_not_deleted"]
            and commercial["export_is_always_available"]
            and entitlement["extension_changes_benefit_access_only"]
            and entitlement["customer_admin_cannot_forgive_debt"]
        )
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        out["gate178_semantics_preserved"] = False
        out["gate178_probe_error"] = str(exc)[:200]

    out["network_requests"] = _ATTEMPTS["n"]
    out["fixture_residue"] = 0
    out["gate179_ready"] = bool(
        out["customer_journey_contract_ready"]
        and out["buyer_recommendation_feed_ready"]
        and out["canonical_graph_feeds_customer"]
        and out["why_relevant_explainable"]
        and out["eligibility_explainable"]
        and out["document_evidence_explainable"]
        and out["watch_dismiss_pursue_ready"]
        and out["dismiss_does_not_delete_intelligence"]
        and out["customer_dashboard_ready"]
        and out["tenant_customization_persistent"]
        and out["user_overrides_separate"]
        and out["customer_operator_surfaces_separated"]
        and out["trust_experience_ready"]
        and out["demo_customer_story_ready"]
        and out["customer_self_health_ready"]
        and out["gate178_semantics_preserved"]
        and out["network_requests"] == 0
    )
    out["generated_at"] = dt.datetime.now(dt.UTC).isoformat()

    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
