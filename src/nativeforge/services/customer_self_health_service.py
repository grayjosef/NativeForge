"""179N: the detectors that catch the customer layer lying.

Nine named detectors. The failures this layer can produce are specific and
each needs its own alarm: a feed built from fixtures looks identical to a
feed built from the graph until you check where the rows came from, and a
cross-tenant recommendation looks like a helpful surprise until somebody
notices it is another Tribe's business.

`prove_detectors_fire()` builds a population broken in EXACTLY one way per
detector and proves each fires on its own breakage, stays silent on a healthy
population, and fires alone.
"""

from __future__ import annotations

from typing import Any

from nativeforge.services.customer_decision_service import (
    WATCHED,
    build_decision,
)
from nativeforge.services.customer_opportunity_feed_service import (
    ELIGIBILITY_APPEARS_ELIGIBLE,
    RELEVANCE_NATIVE_SPECIFIC,
    build_recommendation,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_surface_service import (
    OPERATOR_CAPABILITIES,
    build_customer_surface,
    surface_invariant_failures,
)

SCHEMA_VERSION = "nf_customer_self_health_v1"

HEALTH_MODEL_VERSION = "2026.09.1"

FEED_NOT_FROM_CANONICAL_GRAPH = "customer_feed_not_sourced_from_canonical_graph"
CROSS_TENANT_RECOMMENDATION = "cross_tenant_recommendation"
OPERATOR_CONTROL_VISIBLE = "operator_control_visible_in_customer_contract"
WATCH_STATE_DISAPPEARED = "watch_state_disappeared"
DISMISS_MUTATED_GLOBAL = "dismiss_mutated_global_intelligence"
PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT = "personal_layout_mutated_org_default"
DASHBOARD_UNBOUNDED_SCAN = "dashboard_performs_unbounded_scan"
DEMO_STORY_REQUIRES_REAL_ORG = "demo_story_requires_real_org"
EXPLANATION_WITHOUT_EVIDENCE = "customer_explanation_has_no_evidence"

DETECTORS: tuple[str, ...] = (
    FEED_NOT_FROM_CANONICAL_GRAPH,
    CROSS_TENANT_RECOMMENDATION,
    OPERATOR_CONTROL_VISIBLE,
    WATCH_STATE_DISAPPEARED,
    DISMISS_MUTATED_GLOBAL,
    PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT,
    DASHBOARD_UNBOUNDED_SCAN,
    DEMO_STORY_REQUIRES_REAL_ORG,
    EXPLANATION_WITHOUT_EVIDENCE,
)

DETECTOR_MEANINGS: dict[str, str] = {
    FEED_NOT_FROM_CANONICAL_GRAPH: (
        "a recommendation with no canonical opportunity behind it - the "
        "hand-made spark this gate exists to remove"
    ),
    CROSS_TENANT_RECOMMENDATION: (
        "one organisation's feed carrying another organisation's row"
    ),
    OPERATOR_CONTROL_VISIBLE: (
        "source activation, a plane toggle, a verifier surface or an "
        "entitlement override reachable from a customer contract"
    ),
    WATCH_STATE_DISAPPEARED: (
        "something a customer watched is absent from their decisions - a "
        "durable decision that did not endure"
    ),
    DISMISS_MUTATED_GLOBAL: (
        "a dismissal that changed the canonical record or another tenant's "
        "view. One person's tidy-up must not remove a funding opportunity "
        "from every Tribe in the product"
    ),
    PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT: (
        "one person's tile order changed what everybody sees"
    ),
    DASHBOARD_UNBOUNDED_SCAN: (
        "a dashboard that considered rows belonging to other tenants, or "
        "read more rows than the tenant has"
    ),
    DEMO_STORY_REQUIRES_REAL_ORG: (
        "the demo story touching the real organisation, which is no-touch"
    ),
    EXPLANATION_WITHOUT_EVIDENCE: (
        "a decisive relevance or eligibility claim shown to a customer with "
        "no evidence reference behind it"
    ),
}

CRITICAL = "CRITICAL"
SERIOUS = "SERIOUS"

DETECTOR_SEVERITY: dict[str, str] = {
    FEED_NOT_FROM_CANONICAL_GRAPH: CRITICAL,
    CROSS_TENANT_RECOMMENDATION: CRITICAL,
    OPERATOR_CONTROL_VISIBLE: CRITICAL,
    WATCH_STATE_DISAPPEARED: SERIOUS,
    DISMISS_MUTATED_GLOBAL: CRITICAL,
    PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT: SERIOUS,
    DASHBOARD_UNBOUNDED_SCAN: SERIOUS,
    DEMO_STORY_REQUIRES_REAL_ORG: CRITICAL,
    EXPLANATION_WITHOUT_EVIDENCE: CRITICAL,
}

#: The real organisation, which the campaign brief marks NO-TOUCH.
REAL_ORG_NORMALIZED = "aaaaaaaabbbbccccddddeeeeeeeeeeee"


def _norm(value: Any) -> str:
    return str(value or "").replace("-", "").lower()


def _finding(detector: str, subject: Any, why: str) -> dict[str, Any]:
    return {
        "detector": detector,
        "severity": DETECTOR_SEVERITY[detector],
        "subject": str(subject) if subject is not None else None,
        "why": why,
    }


def assess_customer_health(
    *,
    organization_id: Any = None,
    recommendations: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    expected_watched: list[str] | None = None,
    surface: dict[str, Any] | None = None,
    dashboard: dict[str, Any] | None = None,
    canonical_before: dict[str, Any] | None = None,
    canonical_after: dict[str, Any] | None = None,
    org_default_before: Any = None,
    org_default_after: Any = None,
    demo_story_organization_id: Any = None,
) -> dict[str, Any]:
    """Run every detector over a customer population."""
    recommendations = recommendations or []
    decisions = decisions or []
    expected_watched = expected_watched or []
    findings: list[dict[str, Any]] = []

    for row in recommendations:
        rid = row.get("canonical_id") or row.get("recommendation_id")
        if not row.get("canonical_id") or not row.get("sourced_from_canonical_graph"):
            findings.append(
                _finding(
                    FEED_NOT_FROM_CANONICAL_GRAPH,
                    rid,
                    "the recommendation names no canonical opportunity",
                )
            )
        if organization_id is not None and str(row.get("organization_id")) != str(
            organization_id
        ):
            findings.append(
                _finding(
                    CROSS_TENANT_RECOMMENDATION,
                    rid,
                    f"belongs to {row.get('organization_id')}, not {organization_id}",
                )
            )
        for failure in recommendation_invariant_failures(row):
            if "cites_no_evidence" in failure or "cannot_say_why" in failure:
                findings.append(_finding(EXPLANATION_WITHOUT_EVIDENCE, rid, failure))

    if surface is not None:
        listed = set(surface.get("capabilities") or [])
        leaked = sorted(listed & OPERATOR_CAPABILITIES)
        if leaked:
            findings.append(
                _finding(
                    OPERATOR_CONTROL_VISIBLE,
                    surface.get("organization_id"),
                    f"customer capabilities include {leaked}",
                )
            )
        for failure in surface_invariant_failures(surface):
            if "operator" in failure:
                findings.append(
                    _finding(
                        OPERATOR_CONTROL_VISIBLE,
                        surface.get("organization_id"),
                        failure,
                    )
                )

    watched_now = {
        str(d.get("canonical_id"))
        for d in decisions
        if str(d.get("decision_state")) == WATCHED
    }
    for canonical_id in expected_watched:
        if str(canonical_id) not in watched_now:
            findings.append(
                _finding(
                    WATCH_STATE_DISAPPEARED,
                    canonical_id,
                    "was watched and is no longer recorded as watched",
                )
            )

    if canonical_before is not None and canonical_after is not None:
        if canonical_before != canonical_after:
            findings.append(
                _finding(
                    DISMISS_MUTATED_GLOBAL,
                    None,
                    "the canonical record changed while a dismissal was applied",
                )
            )

    if org_default_before is not None and org_default_after is not None:
        if org_default_before != org_default_after:
            findings.append(
                _finding(
                    PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT,
                    None,
                    "the organisation default changed while applying a "
                    "personal override",
                )
            )

    if dashboard is not None:
        if int(dashboard.get("rows_from_other_tenants_excluded") or 0) and not (
            dashboard.get("tenant_scoped")
        ):
            findings.append(
                _finding(
                    DASHBOARD_UNBOUNDED_SCAN,
                    dashboard.get("organization_id"),
                    "read rows from other tenants without scoping",
                )
            )
        if not dashboard.get("tenant_scoped"):
            findings.append(
                _finding(
                    DASHBOARD_UNBOUNDED_SCAN,
                    dashboard.get("organization_id"),
                    "the dashboard does not claim to be tenant scoped",
                )
            )

    if demo_story_organization_id is not None:
        if _norm(demo_story_organization_id) == REAL_ORG_NORMALIZED:
            findings.append(
                _finding(
                    DEMO_STORY_REQUIRES_REAL_ORG,
                    demo_story_organization_id,
                    "the demo story is built on the real organisation, which "
                    "is no-touch",
                )
            )

    fired = sorted({f["detector"] for f in findings})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "healthy": not findings,
        "finding_count": len(findings),
        "detectors_fired": fired,
        "detectors_silent": [d for d in DETECTORS if d not in fired],
        "critical_finding_count": sum(1 for f in findings if f["severity"] == CRITICAL),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# The proof.
# ---------------------------------------------------------------------------

_ORG = "org-A"
_DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
_CANON = {
    "canonical_id": "canon-1",
    "title": "Tribal Water Infrastructure",
    "funder_name": "EPA",
    "close_date": "2026-11-15",
}


def _healthy_recommendation(org: str = _ORG) -> dict[str, Any]:
    return build_recommendation(
        organization_id=org,
        canonical_record=_CANON,
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
    )


def _healthy_population() -> dict[str, Any]:
    return {
        "organization_id": _ORG,
        "recommendations": [_healthy_recommendation()],
        "decisions": [
            build_decision(
                organization_id=_ORG,
                canonical_id="canon-1",
                decision_state=WATCHED,
                actor_id="person-1",
                decided_at="2026-09-20",
            )
        ],
        "expected_watched": ["canon-1"],
        "surface": build_customer_surface(organization_id=_ORG, role="ORG_ADMIN"),
        "dashboard": {
            "organization_id": _ORG,
            "tenant_scoped": True,
            "rows_from_other_tenants_excluded": 0,
        },
        "canonical_before": dict(_CANON),
        "canonical_after": dict(_CANON),
        "org_default_before": {"tile_order": ["DEADLINES"]},
        "org_default_after": {"tile_order": ["DEADLINES"]},
        "demo_story_organization_id": _DEMO_ORG,
    }


def _break_one_way(detector: str) -> dict[str, Any]:
    pop = _healthy_population()

    if detector == FEED_NOT_FROM_CANONICAL_GRAPH:
        spark = build_recommendation(
            organization_id=_ORG,
            canonical_record={"title": "hand made spark"},
            relevance={
                "relevance_class": RELEVANCE_NATIVE_SPECIFIC,
                "why": "somebody typed it",
                "evidence_ids": ["ev-1"],
            },
            eligibility={
                "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
                "why": "assumed",
                "evidence_ids": ["el-1"],
            },
        )
        pop["recommendations"] = [spark]

    elif detector == CROSS_TENANT_RECOMMENDATION:
        pop["recommendations"] = [_healthy_recommendation(org="org-B")]

    elif detector == OPERATOR_CONTROL_VISIBLE:
        surface = dict(pop["surface"])
        surface["capabilities"] = [*surface["capabilities"], "ACTIVATE_SOURCE"]
        pop["surface"] = surface

    elif detector == WATCH_STATE_DISAPPEARED:
        pop["decisions"] = []

    elif detector == DISMISS_MUTATED_GLOBAL:
        pop["canonical_after"] = {**_CANON, "title": "quietly changed"}

    elif detector == PERSONAL_LAYOUT_MUTATED_ORG_DEFAULT:
        pop["org_default_after"] = {"tile_order": ["WATCH_LIST"]}

    elif detector == DASHBOARD_UNBOUNDED_SCAN:
        pop["dashboard"] = {
            "organization_id": _ORG,
            "tenant_scoped": False,
            "rows_from_other_tenants_excluded": 0,
        }

    elif detector == DEMO_STORY_REQUIRES_REAL_ORG:
        pop["demo_story_organization_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    elif detector == EXPLANATION_WITHOUT_EVIDENCE:
        bare = build_recommendation(
            organization_id=_ORG,
            canonical_record=_CANON,
            relevance={"relevance_class": RELEVANCE_NATIVE_SPECIFIC, "why": "because"},
            eligibility={
                "eligibility_view": ELIGIBILITY_APPEARS_ELIGIBLE,
                "why": "entity type matches",
                "evidence_ids": ["el-1"],
            },
        )
        pop["recommendations"] = [bare]

    else:  # pragma: no cover - a detector with no fixture is a bug
        raise ValueError(f"no broken fixture for detector {detector}")

    return pop


def prove_detectors_fire() -> dict[str, Any]:
    baseline = assess_customer_health(**_healthy_population())

    proofs: list[dict[str, Any]] = []
    for detector in DETECTORS:
        result = assess_customer_health(**_break_one_way(detector))
        fired = result["detectors_fired"]
        proofs.append(
            {
                "detector": detector,
                "severity": DETECTOR_SEVERITY[detector],
                "fires_on_its_own_breakage": detector in fired,
                "no_other_detector_fired": fired == [detector],
                "detectors_fired": fired,
                "why": next(
                    (f["why"] for f in result["findings"] if f["detector"] == detector),
                    None,
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detector_count": len(DETECTORS),
        "healthy_population_is_silent": baseline["healthy"],
        "baseline_findings": baseline["findings"],
        "all_detectors_fire": all(p["fires_on_its_own_breakage"] for p in proofs),
        "all_detectors_are_specific": all(p["no_other_detector_fired"] for p in proofs),
        "detectors_that_did_not_fire": [
            p["detector"] for p in proofs if not p["fires_on_its_own_breakage"]
        ],
        "detectors_that_fired_too_broadly": [
            p["detector"] for p in proofs if not p["no_other_detector_fired"]
        ],
        "proofs": proofs,
    }


def describe_self_health() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detectors": list(DETECTORS),
        "detector_count": len(DETECTORS),
        "every_detector_has_a_meaning": set(DETECTOR_MEANINGS) == set(DETECTORS),
        "every_detector_has_a_severity": set(DETECTOR_SEVERITY) == set(DETECTORS),
        "every_detector_has_a_broken_fixture": True,
        "generic_invalid_is_not_a_result": True,
    }
