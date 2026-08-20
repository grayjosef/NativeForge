"""Tests: NOFO showcase intelligence packs + application plan skeleton."""

from __future__ import annotations

from nativeforge.services.nofo_showcase_application_plan_service import (
    application_plan_invariant_failures,
    build_application_plan_skeleton,
    build_application_plans_for_pack,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    build_selected_intelligence_pack,
    load_selected_intelligence_pack,
    pack_invariant_failures,
    write_selected_intelligence_pack,
)


def test_selected_pack_has_sc_and_federal() -> None:
    pack = build_selected_intelligence_pack()
    assert pack_invariant_failures(pack) == []
    assert pack["counts"]["sc_state"] >= 1
    assert pack["counts"]["federal"] >= 1
    assert pack["counts"]["total"] == len(SHOWCASE_OPPORTUNITY_IDS)
    assert pack["nofo_pdf_extraction_claimed"] is False
    assert pack["proposal_drafting_claimed"] is False


def test_each_record_marks_unsupported_proposal_and_pdf() -> None:
    pack = build_selected_intelligence_pack()
    for o in pack["opportunities"]:
        assert o["fields"]["proposal_narrative"]["status"] == "not_supported"
        assert o["fields"]["pdf_nofo_full_text"]["status"] == "not_supported"
        assert o["human_review_required"] is True
        assert o["live_ingest_claimed"] is False


def test_write_and_load_pack() -> None:
    path = write_selected_intelligence_pack()
    assert path.is_file()
    loaded = load_selected_intelligence_pack()
    assert pack_invariant_failures(loaded) == []


def test_application_plan_does_not_fabricate_narrative() -> None:
    pack = build_selected_intelligence_pack()
    plan = build_application_plan_skeleton(pack["opportunities"][0])
    assert application_plan_invariant_failures(plan) == []
    assert plan["completeness"]["ready_for_submission"] is False
    assert plan["completeness"]["ready_for_narrative_drafting"] is False
    assert all(
        s.get("content") in (None, "") for s in plan["narrative_section_scaffold"]
    )
    topics = {q["topic"] for q in plan["missing_information_questions"]}
    assert "past_performance" in topics
    assert "budget_basis" in topics


def test_application_plans_bundle() -> None:
    bundle = build_application_plans_for_pack()
    assert bundle["plan_count"] >= 2
    assert bundle["proposal_drafting_claimed"] is False
    for plan in bundle["plans"]:
        assert application_plan_invariant_failures(plan) == []
