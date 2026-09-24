"""Gate 179: customer experience, tenant customisation, industrial scale.

The finding this gate exists to fix, from its own survey:

    buyer_feed_depends_on_hand_made_sparks = true
    api_imports_canonical_intelligence     = false

Nine gates of intelligence that never reached a buyer.
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

from nativeforge.services.customer_decision_service import (
    DECISION_STATES,
    DISMISSED,
    NEW,
    PURSUING,
    WATCHED,
    apply_decision,
    build_decision,
    decision_invariant_failures,
    describe_decision_model,
    summarize_decisions,
    visible_to_other_tenant,
)
from nativeforge.services.customer_demo_story_service import (
    DEMO_ORGANIZATION_ID,
    NOT_YET_WALKED,
    build_demo_story,
    build_ux_smoke_checklist,
    describe_demo_story,
    render_ux_checklist_markdown,
)
from nativeforge.services.customer_opportunity_feed_service import (
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_APPEARS_INELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    ELIGIBILITY_NOT_ASSESSED,
    ELIGIBILITY_UNCERTAIN,
    ORDER_DEADLINE_SOONEST,
    ORDER_RELEVANCE_STRENGTH,
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_UNCERTAIN,
    build_feed,
    build_recommendation,
    describe_feed_model,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_repository_service import (
    CRITICAL_QUERIES,
    describe_repository,
    plan_is_a_table_scan,
)
from nativeforge.services.customer_self_health_service import (
    DETECTORS,
    describe_self_health,
    prove_detectors_fire,
)
from nativeforge.services.customer_surface_service import (
    CUSTOMER_CAPABILITIES,
    OPERATOR_CAPABILITIES,
    build_customer_surface,
    build_dashboard,
    build_trust_panel,
    capabilities_for,
    describe_surface_model,
    surface_invariant_failures,
)

REPO = Path(__file__).resolve().parents[1]

NOW = "2026-09-24"
ORG = "org-A"
CANON = {
    "canonical_id": "canon-1",
    "title": "Tribal Water Infrastructure",
    "funder_name": "EPA",
    "close_date": "2026-11-15",
}


def _rec(**over):
    base = dict(
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
    )
    base.update(over)
    return build_recommendation(**base)


# ==================== 179B: from the graph, not from fixtures =========


def test_a_recommendation_must_come_from_the_canonical_graph():
    """The hand-made spark this gate exists to remove."""
    spark = _rec(canonical_record={"title": "hand made spark"})
    failures = recommendation_invariant_failures(spark)
    assert "recommendation_has_no_canonical_opportunity" in failures
    assert "recommendation_not_sourced_from_the_canonical_graph" in failures


def test_a_real_recommendation_passes():
    row = _rec()
    assert recommendation_invariant_failures(row) == []
    assert row["sourced_from_canonical_graph"] is True


def test_the_feed_reports_where_it_came_from():
    feed = build_feed(organization_id=ORG, recommendations=[_rec()], as_of=NOW)
    assert feed["sourced_from_canonical_graph"] is True
    assert describe_feed_model()["no_hand_made_sparks"] is True


# ==================== 179C: it explains itself ========================


def test_a_decisive_relevance_claim_needs_evidence():
    bare = _rec(relevance={"relevance_class": RELEVANCE_NATIVE_SPECIFIC, "why": "x"})
    assert any(
        "cites_no_evidence" in f for f in recommendation_invariant_failures(bare)
    )


def test_conditional_eligibility_must_name_its_condition():
    row = _rec(
        eligibility={
            "eligibility_view": ELIGIBILITY_CONDITIONAL,
            "why": "needs a match",
            "conditions": ["25% non-federal match"],
            "evidence_ids": ["el"],
        }
    )
    assert recommendation_invariant_failures(row) == []
    nameless = {**row, "eligibility_conditions": []}
    assert any(
        "names_no_condition" in f for f in recommendation_invariant_failures(nameless)
    )


def test_ineligibility_must_name_its_blocker():
    row = _rec(
        eligibility={
            "eligibility_view": ELIGIBILITY_APPEARS_INELIGIBLE,
            "why": "applicant class excludes Tribes",
            "blockers": ["must be a public port authority"],
            "evidence_ids": ["el"],
        }
    )
    assert recommendation_invariant_failures(row) == []
    assert any(
        "names_no_blocker" in f
        for f in recommendation_invariant_failures({**row, "eligibility_blockers": []})
    )


def test_uncertainty_reaches_the_customer():
    """A system that hides uncertainty is more confident about wrong things."""
    row = _rec(
        canonical_record={**CANON, "close_date": None},
        relevance={"relevance_class": RELEVANCE_UNCERTAIN},
        eligibility={"eligibility_view": ELIGIBILITY_UNCERTAIN, "why": "unclear"},
    )
    assert "native_relevance_undecided" in row["known_unknowns"]
    assert "eligibility_undecided" in row["known_unknowns"]
    assert "no_published_deadline" in row["known_unknowns"]
    assert recommendation_invariant_failures(row) == []


def test_not_assessed_is_not_uncertain():
    assert ELIGIBILITY_NOT_ASSESSED != ELIGIBILITY_UNCERTAIN
    assert describe_feed_model()["not_assessed_is_distinct_from_uncertain"] is True


def test_a_citation_without_a_quote_is_dropped():
    """A reference nobody can check is not a citation."""
    row = _rec(
        documents=[
            {"document_id": "doc-1", "document_type": "NOFO", "page": 4, "quote": ""},
            {
                "document_id": "doc-2",
                "document_type": "NOFO",
                "page": 14,
                "quote": "Eligible applicants are federally recognized Tribes.",
            },
        ]
    )
    assert len(row["document_citations"]) == 1
    assert row["document_citations"][0]["document_id"] == "doc-2"


def test_ordering_is_named_not_scored():
    rows = [
        _rec(
            canonical_record={**CANON, "canonical_id": "a", "close_date": "2026-12-01"}
        ),
        _rec(
            canonical_record={**CANON, "canonical_id": "b", "close_date": "2026-10-01"},
            relevance={"relevance_class": RELEVANCE_UNCERTAIN},
        ),
    ]
    by_deadline = build_feed(
        organization_id=ORG,
        recommendations=rows,
        ordering=ORDER_DEADLINE_SOONEST,
        as_of=NOW,
    )
    by_relevance = build_feed(
        organization_id=ORG,
        recommendations=rows,
        ordering=ORDER_RELEVANCE_STRENGTH,
        as_of=NOW,
    )
    assert by_deadline["recommendations"][0]["canonical_id"] == "b"
    assert by_relevance["recommendations"][0]["canonical_id"] == "a"
    assert describe_feed_model()["no_opaque_score"] is True

    with pytest.raises(ValueError):
        build_feed(
            organization_id=ORG, recommendations=rows, ordering="SECRET", as_of=NOW
        )


# ==================== 179D: durable decisions =========================


def test_every_human_decision_names_an_actor():
    """The survey found 457 watchlist rows recording none."""
    assert (
        apply_decision(
            current=None,
            organization_id=ORG,
            canonical_id="c",
            to_state=DISMISSED,
            actor_id=None,
            decided_at=NOW,
        )["accepted"]
        is False
    )
    orphan = build_decision(
        organization_id=ORG, canonical_id="c", decision_state=DISMISSED
    )
    assert any("names_no_actor" in f for f in decision_invariant_failures(orphan))


def test_history_is_appended_not_overwritten():
    first = apply_decision(
        current=None,
        organization_id=ORG,
        canonical_id="c",
        to_state=WATCHED,
        actor_id="p1",
        decided_at="2026-09-20",
    )
    second = apply_decision(
        current=first["decision"],
        organization_id=ORG,
        canonical_id="c",
        to_state=PURSUING,
        actor_id="p2",
        decided_at="2026-09-22",
        history=first["history"],
    )
    assert second["history_length"] == 1
    assert second["decision"]["previous_state"] == WATCHED


def test_dismiss_does_not_delete_intelligence():
    """One person's tidy-up must not remove funding from every Tribe."""
    result = apply_decision(
        current=None,
        organization_id=ORG,
        canonical_id="c",
        to_state=DISMISSED,
        actor_id="p1",
        decided_at=NOW,
        reason="not our area",
    )
    assert result["global_intelligence_unchanged"] is True
    assert result["canonical_record_untouched"] is True
    assert result["other_tenants_unaffected"] is True
    assert (
        visible_to_other_tenant(
            decision=result["decision"], other_organization_id="org-B"
        )
        is False
    )


@pytest.mark.parametrize("state", list(DECISION_STATES))
def test_every_state_is_reversible(state):
    """A dead end in a workflow about money is a support ticket."""
    assert describe_decision_model()["every_state_is_reversible"] is True
    model = describe_decision_model()
    assert state in model["decision_states"]


def test_a_summary_never_counts_another_tenant():
    summary = summarize_decisions(
        decisions=[
            build_decision(
                organization_id=ORG,
                canonical_id="c1",
                decision_state=WATCHED,
                actor_id="p",
                decided_at=NOW,
            ),
            build_decision(
                organization_id="org-B",
                canonical_id="c2",
                decision_state=WATCHED,
                actor_id="p",
                decided_at=NOW,
            ),
        ],
        organization_id=ORG,
    )
    assert summary["watching"] == 1
    assert summary["rows_from_other_tenants"] == 1


# ==================== 179E/G/H: dashboard, surfaces, trust ============


def test_the_dashboard_excludes_other_tenants():
    dash = build_dashboard(
        organization_id=ORG,
        recommendations=[
            _rec(),
            _rec(
                organization_id="org-B", canonical_record={**CANON, "canonical_id": "x"}
            ),
        ],
        decisions=[],
        as_of=NOW,
    )
    assert dash["rows_considered"] == 1
    assert dash["rows_from_other_tenants_excluded"] == 1
    assert dash["tenant_scoped"] is True


def test_the_dashboard_needs_a_date():
    with pytest.raises(ValueError):
        build_dashboard(
            organization_id=ORG, recommendations=[], decisions=[], as_of=None
        )


def test_customer_and_operator_capabilities_are_disjoint():
    assert not (CUSTOMER_CAPABILITIES & OPERATOR_CAPABILITIES)
    model = describe_surface_model()
    assert model["source_activation_is_operator_only"] is True
    assert model["plane_toggle_is_operator_only"] is True
    assert model["entitlement_override_is_operator_only"] is True
    assert model["verifier_surface_is_operator_only"] is True


def test_a_customer_session_carries_no_operator_power():
    surface = build_customer_surface(organization_id=ORG, role="ORG_ADMIN")
    assert surface_invariant_failures(surface) == []
    assert not (set(surface["capabilities"]) & OPERATOR_CAPABILITIES)
    assert (
        capabilities_for(role="ORG_ADMIN", is_controlling_company=False)[
            "operator_capabilities_withheld"
        ]
        is True
    )


@pytest.mark.parametrize(
    "power",
    [
        "ACTIVATE_SOURCE",
        "TOGGLE_DEMO_REAL_PLANE",
        "FORGIVE_MAINTENANCE_DEBT",
        "VIEW_VERIFIER_OUTPUT",
    ],
)
def test_leaking_an_operator_power_is_refused(power):
    surface = build_customer_surface(organization_id=ORG, role="ORG_ADMIN")
    leaked = {**surface, "capabilities": [*surface["capabilities"], power]}
    assert any("operator_powers" in f for f in surface_invariant_failures(leaked))


def test_nested_internal_fields_are_refused():
    """A filter that checks only the top level is one a serialiser walks past."""
    surface = build_customer_surface(organization_id=ORG, role="ORG_ADMIN")
    nested = {
        **surface,
        "dashboard": {"deadlines": [{"canonical_id": "c", "lease_id": "abc"}]},
    }
    failures = surface_invariant_failures(nested)
    assert any("internal_field" in f for f in failures)


def test_the_trust_panel_excludes_plumbing():
    panel = build_trust_panel(
        recommendation=_rec(),
        source_records=[
            {
                "source_name": "EPA Grants",
                "publisher": "EPA",
                "last_observed_at": "2026-09-23",
                "authorization_status": "AUTHORIZED",
                "lease_id": "internal",
                "worker_id": "internal",
            }
        ],
    )
    assert set(panel["sources"][0]) == {
        "source_name",
        "publisher",
        "last_observed_at",
        "authorization_status",
    }


# ==================== 179L/M: the demo story and the checklist ========


def test_the_demo_story_runs_only_on_the_demo_organization():
    story = build_demo_story()
    assert story["organization_id"] == DEMO_ORGANIZATION_ID
    assert describe_demo_story()["refuses_the_real_organization"] is True


@pytest.mark.parametrize(
    "bad",
    [
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "aaaaaaaabbbbccccddddeeeeeeeeeeee",
        "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        "some-other-org",
    ],
)
def test_the_demo_story_refuses_any_other_organization(bad):
    with pytest.raises(ValueError):
        build_demo_story(organization_id=bad)


def test_the_demo_story_is_deterministic():
    assert build_demo_story()["content_digest"] == build_demo_story()["content_digest"]


def test_the_demo_story_covers_every_required_case():
    story = build_demo_story()
    relevance = {r["relevance_class"] for r in story["recommendations"]}
    eligibility = {r["eligibility_view"] for r in story["recommendations"]}
    states = {d["decision_state"] for d in story["decisions"]}
    assert RELEVANCE_NATIVE_SPECIFIC in relevance
    assert "NOT_RELEVANT" in relevance
    assert ELIGIBILITY_CONDITIONAL in eligibility
    assert {WATCHED, PURSUING} <= states
    assert story["pursuit"]["requirements"] and story["pursuit"]["tasks"]
    assert story["license"]["license_state"] == "LICENSED_ACTIVE"
    assert story["trust_panel"]["document_citations"]
    assert not any(
        recommendation_invariant_failures(r) for r in story["recommendations"]
    )


def test_the_checklist_arrives_unwalked():
    """A checklist pre-marked PASS answers the question it exists to ask."""
    checklist = build_ux_smoke_checklist()
    assert checklist["step_count"] == 16
    assert checklist["any_result_prefilled"] is False
    assert checklist["any_customer_ready_prefilled"] is False
    assert all(i["actual_result"] == NOT_YET_WALKED for i in checklist["items"])
    assert all(i["customer_ready"] is None for i in checklist["items"])
    assert all(i["evidence_screenshot_needed"] for i in checklist["items"])


def test_the_checklist_renders_for_a_human():
    markdown = render_ux_checklist_markdown(build_ux_smoke_checklist())
    assert "NOT_YET_WALKED" in markdown
    assert markdown.count("## ") == 16


# ==================== 179N: self health ===============================


def test_specific_self_health_detectors_fire():
    proof = prove_detectors_fire()
    assert proof["healthy_population_is_silent"] is True, proof["baseline_findings"]
    assert proof["all_detectors_fire"] is True, proof["detectors_that_did_not_fire"]
    assert proof["all_detectors_are_specific"] is True, proof[
        "detectors_that_fired_too_broadly"
    ]
    assert proof["detector_count"] == len(DETECTORS) == 9
    assert describe_self_health()["every_detector_has_a_meaning"] is True


# ==================== 0065: the constraints are real ==================

NOW_DT = dt.datetime(2026, 9, 24, tzinfo=dt.UTC)

_ROW = {
    "decision_state": WATCHED,
    "previous_state": NEW,
    "actor_id": "person-1",
    "decided_at": NOW_DT,
    "reason": "promising",
    "is_demo": False,
    "model_version": "test",
}


def _insert(session, org, canonical, **over):
    row = {
        "organization_id": org,
        "canonical_id": canonical,
        **_ROW,
        **over,
    }
    columns = ", ".join(row)
    values = ", ".join(f":{name}" for name in row)
    session.execute(
        text(
            f"INSERT INTO nf_customer_opportunity_decisions ({columns}) "
            f"VALUES ({values})"
        ),
        row,
    )


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("watched with no actor", {"actor_id": None}),
        ("dismissed with no time", {"decision_state": DISMISSED, "decided_at": None}),
        ("pursuing with no actor", {"decision_state": PURSUING, "actor_id": None}),
        ("state outside the vocabulary", {"decision_state": "ARCHIVED"}),
    ],
)
def test_the_database_refuses_a_decision_nobody_made(label, override):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(session, ORG, f"canon-{label}", **override)
            session.commit()
        session.rollback()


def test_the_database_accepts_an_honest_decision():
    """NEW needs no actor; a human state does."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            _insert(session, ORG, "canon-ok")
            _insert(
                session,
                ORG,
                "canon-new",
                decision_state=NEW,
                previous_state=None,
                actor_id=None,
                decided_at=None,
            )
            session.commit()
        finally:
            session.execute(text("DELETE FROM nf_customer_opportunity_decisions"))
            session.commit()


def test_one_current_decision_per_organization_and_opportunity():
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            _insert(session, ORG, "canon-dup")
            session.commit()
            with pytest.raises(sa.exc.IntegrityError):
                _insert(session, ORG, "canon-dup", decision_state=DISMISSED)
                session.commit()
            session.rollback()
        finally:
            session.execute(text("DELETE FROM nf_customer_opportunity_decisions"))
            session.commit()


def test_the_customer_read_paths_are_indexed():
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        session.execute(text("DELETE FROM nf_customer_opportunity_decisions"))
        rows = [
            {
                "organization_id": f"org:{i % 50:06d}",
                "canonical_id": f"canon:{i:06d}",
                **_ROW,
                "decision_state": [WATCHED, DISMISSED, PURSUING][i % 3],
            }
            for i in range(2000)
        ]
        columns = ", ".join(rows[0])
        values = ", ".join(f":{name}" for name in rows[0])
        session.execute(
            text(
                f"INSERT INTO nf_customer_opportunity_decisions ({columns}) "
                f"VALUES ({values})"
            ),
            rows,
        )
        session.execute(text("ANALYZE"))
        session.commit()
        try:
            for name, spec in CRITICAL_QUERIES.items():
                sql, params = spec["builder"](**spec["sample_kwargs"])
                plan_rows = session.execute(
                    text(f"EXPLAIN QUERY PLAN {sql}"), params
                ).fetchall()
                plan = " | ".join(str(r[-1]) for r in plan_rows)
                assert not plan_is_a_table_scan(plan, spec["table"]), f"{name}: {plan}"
        finally:
            session.execute(text("DELETE FROM nf_customer_opportunity_decisions"))
            session.commit()


def test_the_scan_detector_can_still_fire():
    assert plan_is_a_table_scan(
        "SCAN nf_customer_opportunity_decisions", "nf_customer_opportunity_decisions"
    )
    assert not plan_is_a_table_scan(
        "SCAN nf_customer_opportunity_decisions USING INDEX ix_x",
        "nf_customer_opportunity_decisions",
    )


def test_the_repository_states_its_forbidden_shapes():
    repo = describe_repository()
    assert repo["every_query_is_tenant_scoped"] is True
    assert repo["current_state_is_not_derived_from_history"] is True
    assert "opportunity_by_tenant_by_document_cartesian" in repo["forbidden_shapes"]


# ==================== the instruments =================================


def test_network_zero_and_the_gate_is_ready():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g179_phase_proof.py"],
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
    assert report["gate179_ready"] is True
    assert report["canonical_graph_feeds_customer"] is True
    assert report["demo_story_refuses_the_real_organization"] is True


def test_the_rehearsal_is_honest_about_what_it_proves():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g179_phase_rehearsal.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["source_count"] >= 1000
    assert report["every_kind_represented"] is True
    assert report["every_health_state_represented"] is True
    assert report["no_cartesian_catastrophe"] is True
    assert report["global_intelligence_not_recomputed_per_tenant"] is True
    assert report["critical_customer_queries_indexed"] is True
    assert report["customer_zero_row_queries"] == []
    # The two honest refusals.
    assert report["claims_real_thousand_source_coverage"] is False
    assert report["postgres_concurrency_status"] == "UNKNOWN_NOT_MEASURED"
    assert report["network_requests"] == 0


def test_the_survey_recorded_the_gap_this_gate_closes():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g179_survey_customer.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["wrote_nothing"] is True
    assert report["network_requests"] == 0
    assert report["postgres_concurrency_status"] == "UNKNOWN_NOT_MEASURED"


# ==================== the integrated 176 -> 179 proof =================


def test_the_integrated_176_to_179_proof_holds():
    """Six situations that cross all four gates.

    Each gate proved itself in isolation. The failures that survive per-gate
    testing are the ones that live in the joins.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g176_179_integrated_proof.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["case_count"] == 6
    assert report["failed_cases"] == [], report["failed_cases"]
    assert report["integrated_proof_ready"] is True
    assert report["network_requests"] == 0
    assert report["real_organization_touched"] is False
    assert report["money_moved"] is False


def test_the_integrated_proof_case_names_match_the_block():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g176_179_integrated_proof.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert [c["case"] for c in report["cases"]] == [
        "CASE_1_MISSED_FUNDING_DISCOVERY",
        "CASE_2_REAL_CUSTOMER_AUTHORITY",
        "CASE_3_COMMERCIAL_FREEZE",
        "CASE_4_CUSTOMER_JOURNEY",
        "CASE_5_TENANT_ISOLATION",
        "CASE_6_EXPIRED_LICENSE_RELICENSE",
    ]


def test_the_absence_classifier_moves_rather_than_sits():
    """LATE becomes MISSING by itself, and clears when the cycle reopens.

    The first run of the integrated proof expected MISSING and got LATE. The
    model was right: 138 days past the window is late, not missing. A
    classifier that only ever returns one state is not classifying anything,
    so the case now asserts the progression.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g176_179_integrated_proof.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    observed = report["cases"][0]["observed"]
    assert observed["absence_state"] == "LATE"
    assert observed["absence_state_after_a_further_cadence"] == "MISSING"
    assert observed["absence_clears_when_the_cycle_reopens"] == "ON_TIME"
