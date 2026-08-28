"""Gate 108: Awarded Grants requirements tracking.

Pursuit asks whether to chase an opportunity. Awarded Grants asks what a Tribe is
now responsible for. These tests hold the boundary between them, and the three
refusals the awarded lane turns on:

```text
a projection is not an obligation
an unreadable document produces no verified requirement
an unknown due date stays unknown, and stays visible
```
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import award_requirement_model_service as model
from nativeforge.services import award_requirement_proof_audit_service as proof
from nativeforge.services import award_requirements_calendar_service as calendar
from nativeforge.services import awarded_grant_record_service as record
from nativeforge.services import awarded_grants_demo_fixture_service as fixtures
from nativeforge.services import awarded_grants_requirements_artifact_service as art
from nativeforge.services import (
    awarded_grants_requirements_readiness_service as readiness,
)
from nativeforge.services.award_transition_service import (
    AwardTransitionError,
    mark_awarded_for_tenant,
    tenant_transition_invariant_failures,
    undo_mark_awarded_for_tenant,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

TENANT = "t-gate108"
ORG = "org-gate108"


def _award_details():
    return {
        "award_number": "AW-108",
        "award_start_date": "2026-01-01",
        "award_end_date": "2026-12-31",
        "award_amount": 250000,
    }


def _transition(**overrides):
    kwargs = {
        "tenant_id": TENANT,
        "customer_org_id": ORG,
        "source_opportunity_id": "opp-108",
        "pursuit_record_id": "pur-108",
        "user_action": True,
        "at": "2026-02-01",
        "award_details": _award_details(),
        "requirements_extraction_status": "human_entered",
        "grant_title": "Gate 108 award",
    }
    kwargs.update(overrides)
    return mark_awarded_for_tenant(**kwargs)


# ------------------------------------------------- 108B: the award record


def test_an_awarded_record_is_not_a_pursuit_record():
    result = record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        pursuit_record_id="pur-1",
    )
    assert result["is_pursuit_record"] is False
    assert result["pursuit_record_id"] == "pur-1"
    assert result["source_opportunity_id"] == "opp-1"
    assert result["award_id"] != result["pursuit_record_id"]


def test_an_award_record_preserves_pursuit_and_source_history():
    result = record.build_awarded_grant_record(
        tenant_id=TENANT, customer_org_id=ORG, source_opportunity_id="opp-1"
    )
    assert result["pursuit_history_preserved"] is True
    assert result["source_history_preserved"] is True
    assert result["pursuit_record_deleted"] is False
    assert result["source_opportunity_deleted"] is False


def test_an_award_may_exist_before_anyone_knows_what_it_obliges():
    """The letter arrived; nobody has read the terms. That is a valid record."""
    result = record.build_awarded_grant_record(
        tenant_id=TENANT, customer_org_id=ORG, source_opportunity_id="opp-1"
    )
    assert result["requirements_extraction_status"] == "not_attempted"
    assert result["active_obligations_supported"] is False
    assert result["missing_award_details"]
    assert record.award_record_invariant_failures(result) == []


def test_an_award_record_is_tenant_specific():
    result = record.build_awarded_grant_record(
        tenant_id="", customer_org_id=ORG, source_opportunity_id="opp-1"
    )
    assert "award_without_a_tenant" in result["blocked_reasons"]
    assert "award_record_without_a_tenant" in (
        record.award_record_invariant_failures(result)
    )


def test_the_two_identity_spaces_are_not_merged():
    """tenant_id and customer_org_id are carried, never derived from each other.

    Gate 109 replaced the old {caller_supplied, unknown} pair: two strings
    arriving together is not a statement that they belong to each other, so
    both ids with no verification is `pending_review`, not a binding.
    """
    with_both = record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        binding_source="human_entered",
    )
    assert with_both["tenant_org_binding_status"] == "pending_review"
    assert with_both["operational_identity_binding_verified"] is False

    without_org = record.build_awarded_grant_record(
        tenant_id=TENANT, source_opportunity_id="opp-1"
    )
    assert without_org["tenant_org_binding_status"] == "unbound"
    assert without_org["customer_org_id"] is None
    assert "no_customer_org_id_supplied_for_the_gate91_lane" in (
        without_org["blocked_reasons"]
    )


def test_a_binding_cannot_be_claimed_without_both_identities():
    forged = record.build_awarded_grant_record(
        tenant_id=TENANT, source_opportunity_id="opp-1"
    )
    forged["tenant_org_binding_status"] = "verified_binding"
    assert "binding_claimed_without_both_identities" in (
        record.award_record_invariant_failures(forged)
    )


def test_an_unsupported_award_package_supports_no_obligations():
    result = record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        requirements_extraction_status="unsupported_document_type",
    )
    assert result["active_obligations_supported"] is False
    assert result["evidence_status"] == "unsupported_document_type"
    assert result["human_review_required"] is True


def test_no_performance_period_is_invented_from_one_date():
    result = record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        award_start_date="2026-01-01",
    )
    assert result["performance_period"]["derived_from"] == "incomplete_award_dates"
    assert result["dates_inferred"] is False


def test_gate91_lifecycle_statuses_are_fully_mapped():
    """Bridged, not forked. If Gate 91 grows a status, this fails."""
    assert record.portfolio_lifecycle_is_fully_mapped()


# ------------------------------------------------ 108C: the transition


def test_marking_awarded_creates_a_record_and_preserves_history():
    result = _transition()
    assert result["awarded_record_created"] is True
    assert result["pursuit_history_preserved"] is True
    assert result["source_history_preserved"] is True
    assert result["pursuit_record_deleted"] is False
    assert result["evidence_deleted"] is False
    assert tenant_transition_invariant_failures(result) == []


def test_a_transition_never_creates_active_obligations():
    """The rule the awarded workspace turns on."""
    result = _transition()
    assert result["active_obligations_created"] is False


def test_a_transition_cannot_claim_it_created_obligations():
    forged = dict(_transition())
    forged["active_obligations_created"] = True
    assert "transition_created_active_obligations" in (
        tenant_transition_invariant_failures(forged)
    )


def test_marking_awarded_requires_a_tenant():
    with pytest.raises(AwardTransitionError):
        _transition(tenant_id="")


def test_marking_awarded_requires_an_explicit_user_action():
    """Inherited from Gate 91: a backend may not infer an award."""
    with pytest.raises(AwardTransitionError):
        _transition(user_action=False)


def test_undo_is_idempotent():
    first = undo_mark_awarded_for_tenant(transition=_transition())
    second = undo_mark_awarded_for_tenant(transition=first)
    third = undo_mark_awarded_for_tenant(transition=second)
    assert first["undo_status"] == "undone"
    assert second["undo_status"] == "already_undone"
    assert third["undo_status"] == "already_undone"


def test_undo_preserves_everything_and_claims_no_record():
    undone = undo_mark_awarded_for_tenant(transition=_transition())
    assert undone["awarded_record_created"] is False
    assert undone["active_obligations_created"] is False
    assert undone["pursuit_history_preserved"] is True
    assert undone["source_history_preserved"] is True
    assert undone["evidence_deleted"] is False
    assert set(undone["preserved_on_undo"]) >= {
        "documents",
        "extracted_requirements",
        "award_details",
        "audit_events",
    }
    assert tenant_transition_invariant_failures(undone) == []


def test_an_undone_transition_cannot_still_claim_a_record():
    forged = dict(undo_mark_awarded_for_tenant(transition=_transition()))
    forged["awarded_record_created"] = True
    assert "undone_transition_still_claims_an_awarded_record" in (
        tenant_transition_invariant_failures(forged)
    )


def test_the_default_from_lane_is_in_the_real_vocabulary():
    """A plausible-looking lane string is not a lane."""
    from nativeforge.services.award_transition_service import (
        DEFAULT_TRANSITIONABLE_FROM_LANE,
    )
    from nativeforge.services.grant_lane_separation_service import PURSUIT_LANES

    assert DEFAULT_TRANSITIONABLE_FROM_LANE in PURSUIT_LANES


# ------------------------------------------- 108D: the requirement model


def test_every_required_requirement_type_is_supported():
    expected = {
        "narrative_report",
        "financial_report",
        "audit",
        "reimbursement",
        "drawdown",
        "match_documentation",
        "budget_revision",
        "performance_measure",
        "board_or_council_resolution",
        "subrecipient_report",
        "vendor_documentation",
        "closeout",
        "document_retention",
        "other",
        "unknown",
    }
    assert expected <= model.REQUIREMENT_TYPES


def test_gate91_requirement_categories_are_fully_mapped():
    assert model.portfolio_categories_are_fully_mapped()


def test_a_projected_burden_is_not_an_active_obligation():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="financial_report",
        requirement_title="Projected quarterly reporting",
        extraction_status="projected_from_nofo",
    )
    assert result["is_active_obligation"] is False
    assert "projected_burden_is_not_an_active_obligation" in result["blocked_reasons"]
    assert model.requirement_invariant_failures(result) == []


def test_a_projection_cannot_be_marked_active():
    forged = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="Projected audit",
        extraction_status="projected_from_nofo",
    )
    forged["is_active_obligation"] = True
    failures = model.requirement_invariant_failures(forged)
    assert "projected_burden_treated_as_active_obligation" in failures


def test_an_active_obligation_needs_supporting_provenance():
    forged = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="Unknown provenance",
        extraction_status="unknown",
    )
    forged["is_active_obligation"] = True
    assert "active_obligation_without_supporting_provenance" in (
        model.requirement_invariant_failures(forged)
    )


def test_an_unsupported_document_produces_no_verified_due_date():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="financial_report",
        requirement_title="From an unreadable package",
        extraction_status="unsupported_document_type",
        due_date="2026-06-30",
        due_date_status="verified",
    )
    assert result["due_date_status"] == "unsupported"
    assert result["date_is_calculable"] is False
    assert "unsupported_document_claimed_a_supported_date" in result["blocked_reasons"]


def test_an_unsupported_document_cannot_claim_a_supported_date():
    forged = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="Unreadable",
        extraction_status="unsupported_document_type",
    )
    forged["due_date_status"] = "verified"
    assert "unsupported_document_produced_a_supported_date" in (
        model.requirement_invariant_failures(forged)
    )


def test_an_unknown_due_date_remains_unknown():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="Single audit if threshold met",
        extraction_status="human_entered",
    )
    assert result["due_date"] is None
    assert result["due_date_status"] == "unknown"
    assert result["date_is_calculable"] is False
    assert result["due_date_inferred"] is False


def test_an_estimated_due_date_stays_labelled_estimated():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="performance_measure",
        requirement_title="Mid-year measures",
        due_date="2026-08-01",
        due_date_status="estimated",
        extraction_status="human_entered",
    )
    assert result["due_date_status"] == "estimated"
    assert result["date_is_calculable"] is False


def test_a_date_status_cannot_claim_support_without_a_date():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="No date",
        due_date_status="verified",
        extraction_status="human_entered",
    )
    assert result["due_date_status"] == "unknown"
    assert "date_status_claims_support_without_a_date" in result["blocked_reasons"]


def test_evidence_extracted_without_a_reference_is_flagged():
    result = model.build_award_requirement(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_type="narrative_report",
        requirement_title="Claimed but unreferenced",
        extraction_status="evidence_extracted",
    )
    assert result["evidence_status"] == "evidence_claimed_without_reference"
    assert "evidence_extracted_without_a_reference" in result["blocked_reasons"]


def test_a_requirement_is_tenant_and_award_specific():
    result = model.build_award_requirement(
        tenant_id="", award_id="", requirement_type="audit", requirement_title="x"
    )
    failures = model.requirement_invariant_failures(result)
    assert "requirement_without_a_tenant" in failures
    assert "requirement_without_an_award" in failures


def test_requirement_summary_counts_what_is_uncertain():
    requirements = [
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="audit",
            requirement_title="Unknown date",
            extraction_status="human_entered",
        ),
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="financial_report",
            requirement_title="Projected",
            extraction_status="projected_from_nofo",
        ),
    ]
    summary = model.summarise_requirements(requirements)
    assert summary["requirements_total"] == 2
    assert summary["active_obligations"] == 1
    assert summary["projected_not_active"] == 1
    assert summary["unknown_due_dates"] == 2


# ---------------------------------------------------- 108E: the calendar


def _calendar_requirements():
    return [
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="narrative_report",
            requirement_title="Overdue",
            requirement_status="not_started",
            due_date="2026-01-15",
            due_date_status="verified",
            extraction_status="evidence_extracted",
            source_evidence_ref="d1",
        ),
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="financial_report",
            requirement_title="Due soon",
            requirement_status="in_progress",
            due_date="2026-03-10",
            due_date_status="verified",
            extraction_status="evidence_extracted",
            source_evidence_ref="d1",
        ),
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="audit",
            requirement_title="Estimated",
            due_date="2026-02-25",
            due_date_status="estimated",
            extraction_status="human_entered",
        ),
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="closeout",
            requirement_title="Unknown date",
            due_date_status="unknown",
            extraction_status="human_entered",
        ),
        model.build_award_requirement(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_type="match_documentation",
            requirement_title="Projected",
            extraction_status="projected_from_nofo",
        ),
    ]


def test_the_calendar_does_not_hide_unknown_due_dates():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    titles = {i["requirement_title"] for i in result["calendar_items"]}
    assert "Unknown date" in titles
    assert result["items_unknown_due_date"] >= 1
    assert result["items_total"] == 5


def test_an_unknown_due_date_is_not_treated_as_no_deadline():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    unknown = next(
        i for i in result["calendar_items"] if i["requirement_title"] == "Unknown date"
    )
    assert unknown["calendar_placement"] == "undated"
    assert unknown["placement_reason"] == "no_date_established"
    assert unknown["overdue"] is False
    assert unknown["due_soon"] is False


def test_an_estimate_is_never_counted_down():
    """An estimate presented as a countdown is how a real date gets missed."""
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    estimated = next(
        i for i in result["calendar_items"] if i["requirement_title"] == "Estimated"
    )
    assert estimated["overdue"] is False
    assert estimated["due_soon"] is False
    assert estimated["calendar_placement"] == "undated"


def test_a_countdown_on_an_unsupported_date_is_caught():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    forged = json.loads(json.dumps(result))
    target = next(
        i for i in forged["calendar_items"] if i["requirement_title"] == "Estimated"
    )
    target["overdue"] = True
    failures = calendar.calendar_invariant_failures(forged)
    assert any(f.startswith("countdown_on_an_unsupported_date") for f in failures)
    assert any(f.startswith("estimate_counted_down") for f in failures)


def test_overdue_and_due_soon_require_a_supported_date():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    assert result["items_overdue"] == 1
    assert result["items_due_soon"] == 1
    for item in result["calendar_items"]:
        if item["overdue"] or item["due_soon"]:
            assert item["due_date_status"] in model.DATE_CALCULABLE_STATUSES


def test_a_projected_burden_is_not_on_the_compliance_calendar():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    projected = next(
        i for i in result["calendar_items"] if i["requirement_title"] == "Projected"
    )
    assert projected["calendar_placement"] == "not_an_obligation"
    assert projected["is_active_obligation"] is False
    assert projected["placement_reason"]


def test_the_calendar_is_tenant_and_award_scoped():
    other = model.build_award_requirement(
        tenant_id="other-tenant",
        award_id="aw-1",
        requirement_type="audit",
        requirement_title="Another tenant",
        extraction_status="human_entered",
    )
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=[*_calendar_requirements(), other],
        reference_date="2026-02-20",
    )
    titles = {i["requirement_title"] for i in result["calendar_items"]}
    assert "Another tenant" not in titles


def test_the_calendar_reads_no_implicit_clock():
    """Without a reference date nothing is counted down, and it says why."""
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT, award_id="aw-1", requirements=_calendar_requirements()
    )
    assert "no_reference_date_supplied" in result["blocked_reasons"]
    assert result["items_overdue"] == 0
    assert result["items_due_soon"] == 0


def test_calendar_confidence_is_derived():
    documented = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements()[:2],
        reference_date="2026-02-20",
    )
    assert documented["calendar_confidence"] == "documented"

    forged = json.loads(json.dumps(documented))
    forged["calendar_confidence"] = "estimated_only"
    assert "confidence_disagrees_with_the_measurements" in (
        calendar.calendar_invariant_failures(forged)
    )


def test_the_calendar_infers_no_dates():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    assert result["dates_inferred"] == 0
    assert calendar.calendar_invariant_failures(result) == []


def test_hidden_unknown_due_dates_are_caught():
    result = calendar.build_requirements_calendar(
        tenant_id=TENANT,
        award_id="aw-1",
        requirements=_calendar_requirements(),
        reference_date="2026-02-20",
    )
    forged = json.loads(json.dumps(result))
    forged["items_unknown_due_date"] = 0
    assert "unknown_due_dates_hidden_from_the_count" in (
        calendar.calendar_invariant_failures(forged)
    )


# ------------------------------------------------ 108F: proof and audit


def test_proof_is_never_fabricated():
    result = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_submitted",
        status_before="in_progress",
        at="2026-02-01",
    )
    assert result["proof_ref"] is None
    assert result["proof_of_submission_status"] == "proof_missing"
    assert result["proof_fabricated"] is False
    assert "mark_submitted_without_a_proof_reference" in result["blocked_reasons"]


def test_proof_cannot_be_claimed_without_a_reference():
    forged = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_submitted",
        at="2026-02-01",
    )
    forged["proof_of_submission_status"] = "proof_attached"
    assert "proof_claimed_without_a_reference" in (
        proof.proof_audit_invariant_failures(forged)
    )


def test_a_demo_proof_reference_is_labelled():
    result = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_submitted",
        proof_ref="demo-proof-0001",
        proof_label=proof.DEMO_PROOF_LABEL,
        at="2026-02-01",
    )
    assert result["proof_is_demo_fixture"] is True
    assert result["proof_label"] == proof.DEMO_PROOF_LABEL
    assert proof.proof_audit_invariant_failures(result) == []


def test_a_demo_proof_cannot_drop_its_label():
    forged = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_submitted",
        proof_ref="demo-proof-0001",
        proof_label=proof.DEMO_PROOF_LABEL,
        at="2026-02-01",
    )
    forged["proof_label"] = None
    assert "demo_proof_without_its_label" in (
        proof.proof_audit_invariant_failures(forged)
    )


def test_rejection_preserves_the_proof_history():
    result = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_rejected",
        status_before="submitted",
        prior_proof_refs=["receipt-001"],
        at="2026-02-05",
    )
    assert result["proof_ref_history"] == ["receipt-001"]
    assert result["proof_preserved"] is True
    assert result["proof_deleted"] is False
    assert result["source_evidence_preserved"] is True


def test_no_status_change_deletes_anything():
    for action in ("mark_submitted", "mark_accepted", "mark_rejected", "mark_waived"):
        result = proof.record_proof_action(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_id="r-1",
            action=action,
            proof_ref="receipt-001",
            at="2026-02-05",
        )
        assert result["proof_deleted"] is False
        assert result["audit_record_deleted"] is False
        assert result["source_evidence_preserved"] is True


def test_proof_actions_never_contact_external_storage():
    result = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="attach_proof",
        proof_ref="receipt-001",
        at="2026-02-05",
    )
    assert result["external_storage_contacted"] is False
    assert result["live_fetch_performed"] is False


def test_an_audit_event_id_is_derivable_from_its_own_fields():
    result = proof.record_proof_action(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_accepted",
        proof_ref="receipt-001",
        at="2026-02-05",
    )
    assert result["audit_event_id"] == proof.build_audit_event_id(
        tenant_id=TENANT,
        award_id="aw-1",
        requirement_id="r-1",
        action="mark_accepted",
        at="2026-02-05",
    )
    assert proof.proof_audit_invariant_failures(result) == []


def test_an_audit_trail_deletes_nothing():
    events = [
        proof.record_proof_action(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_id="r-1",
            action="mark_submitted",
            proof_ref="receipt-001",
            at="2026-02-01",
        ),
        proof.record_proof_action(
            tenant_id=TENANT,
            award_id="aw-1",
            requirement_id="r-1",
            action="mark_rejected",
            prior_proof_refs=["receipt-001"],
            at="2026-02-05",
        ),
    ]
    trail = proof.build_audit_trail(events)
    assert trail["event_count"] == 2
    assert trail["proof_deleted"] == 0
    assert trail["audit_records_deleted"] == 0
    assert trail["proof_fabricated"] is False


# ------------------------------------------------------ 108G: readiness


def test_demo_contract_readiness_is_true():
    result = readiness.build_awarded_requirements_readiness()
    assert result["ready_for_demo_contract"] is True
    assert result["missing_contract_components"] == []


def test_operational_awarded_tracking_remains_false():
    result = readiness.build_awarded_requirements_readiness()
    assert result["ready_for_operational_awarded_tracking"] is False
    assert result["blocked_reasons"]


def test_ui_customer_persistence_and_document_storage_remain_false():
    result = readiness.build_awarded_requirements_readiness()
    assert result["ui_available"] is False
    assert result["customer_persistence_live"] is False
    assert result["document_storage_live"] is False
    assert result["requirement_extraction_live"] is False


def test_readiness_claims_no_collection_or_coverage():
    result = readiness.build_awarded_requirements_readiness()
    for constant in (
        "live_source_collection_available",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        assert result[constant] is False


def test_operational_readiness_cannot_be_declared():
    result = readiness.build_awarded_requirements_readiness()
    forged = json.loads(json.dumps(result))
    forged["ready_for_operational_awarded_tracking"] = True
    failures = readiness.readiness_invariant_failures(forged)
    assert "operational_readiness_claimed_with_missing_components" in failures


def test_readiness_invariants_pass():
    result = readiness.build_awarded_requirements_readiness()
    assert readiness.readiness_invariant_failures(result) == []


def test_the_ui_detector_can_find_a_surface(tmp_path):
    """Detected on disk, so ui_available False means looked-for-and-absent."""
    src = tmp_path / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "AwardedGrantsPage.tsx").write_text(
        "export const Page = () => <div>Awarded Grants</div>", encoding="utf-8"
    )
    assert readiness._detect_awarded_ui(tmp_path) is True
    assert readiness._detect_awarded_ui(tmp_path / "nowhere") is False


# ------------------------------------------------- 108H: demo fixtures


def test_the_fixture_set_covers_every_required_case():
    result = fixtures.build_demo_fixture_set()
    assert result["demo_cases_missing"] == []
    assert set(result["demo_cases_covered"]) == fixtures.REQUIRED_DEMO_CASES


def test_every_demo_record_is_labelled():
    result = fixtures.build_demo_fixture_set()
    assert result["fixture_label"] == fixtures.FIXTURE_LABEL
    for group in ("awards", "requirements", "proof_events", "calendars"):
        for entry in result[group]:
            assert entry["fixture_label"] == fixtures.FIXTURE_LABEL


def test_the_fixture_projection_is_not_an_obligation():
    result = fixtures.build_demo_fixture_set()
    projected = [
        r
        for r in result["requirements"]
        if r["extraction_status"] == "projected_from_nofo"
    ]
    assert projected
    for requirement in projected:
        assert requirement["is_active_obligation"] is False


def test_the_fixture_unsupported_document_stays_unsupported():
    result = fixtures.build_demo_fixture_set()
    unsupported = [
        r
        for r in result["requirements"]
        if r["extraction_status"] == "unsupported_document_type"
    ]
    assert unsupported
    for requirement in unsupported:
        assert requirement["due_date_status"] == "unsupported"
        assert requirement["is_active_obligation"] is False


def test_the_fixture_uses_a_fixed_clock():
    """A demo that reads the wall clock stops demonstrating overdue."""
    assert fixtures.REFERENCE_NOW == "2026-03-01"
    first = fixtures.build_demo_fixture_set()
    second = fixtures.build_demo_fixture_set()
    assert first == second


def test_the_fixture_claims_no_real_customer_data():
    result = fixtures.build_demo_fixture_set()
    assert result["real_customer_data"] is False
    assert result["real_award_numbers"] is False
    assert result["fabricated_requirements"] is False
    assert fixtures.demo_fixture_invariant_failures(result) == []


def test_case_coverage_is_measured_not_asserted():
    """Feed it data missing a case and it must notice.

    The real fixture covers everything, so a function returning the full set
    would pass every other assertion here.
    """
    empty = fixtures.measure_demo_cases(
        awards=[], requirements=[], proof_events=[], calendars=[]
    )
    assert empty == set()

    partial = fixtures.measure_demo_cases(
        awards=[{"requirements_extraction_status": "evidence_extracted"}],
        requirements=[{"requirement_type": "closeout"}],
        proof_events=[],
        calendars=[],
    )
    assert partial == {"documented_award", "closeout_requirement"}
    assert "overdue_requirement" not in partial
    assert "proof_of_submission" not in partial


def test_case_coverage_detects_each_case_individually():
    assert fixtures.measure_demo_cases(
        awards=[],
        requirements=[{"extraction_status": "projected_from_nofo"}],
        proof_events=[],
        calendars=[],
    ) == {"projected_burden_only"}
    assert fixtures.measure_demo_cases(
        awards=[],
        requirements=[],
        proof_events=[],
        calendars=[{"calendar_items": [{"overdue": True}]}],
    ) == {"overdue_requirement"}
    assert fixtures.measure_demo_cases(
        awards=[],
        requirements=[],
        proof_events=[{"proof_is_demo_fixture": True}],
        calendars=[],
    ) == {"proof_of_submission"}


def test_a_fixture_missing_a_case_fails_its_invariants():
    result = fixtures.build_demo_fixture_set()
    forged = json.loads(json.dumps(result))
    forged["demo_cases_missing"] = ["overdue_requirement"]
    assert "demo_case_not_covered:overdue_requirement" in (
        fixtures.demo_fixture_invariant_failures(forged)
    )


# ------------------------------------------------------ 108I: artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    art.write_awarded_requirements_artifacts(repo_root=tmp_path / "a")
    art.write_awarded_requirements_artifacts(repo_root=tmp_path / "b")
    for name in (
        "awarded_grants_requirements_contract.json",
        "awarded_grants_demo_awards.json",
        "awarded_grants_requirements_matrix.csv",
        "awarded_grants_calendar_preview.csv",
        "awarded_grants_transition_matrix.csv",
        "awarded_grants_readiness_summary.md",
    ):
        first = (tmp_path / "a" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        second = (tmp_path / "b" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert first == second


def test_committed_artifacts_match_fresh_generation(tmp_path):
    art.write_awarded_requirements_artifacts(repo_root=tmp_path)
    for name in (
        "awarded_grants_requirements_contract.json",
        "awarded_grants_demo_awards.json",
        "awarded_grants_requirements_matrix.csv",
        "awarded_grants_calendar_preview.csv",
        "awarded_grants_transition_matrix.csv",
        "awarded_grants_readiness_summary.md",
    ):
        fresh = (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_the_artifact_writer_inspects_the_real_tree(tmp_path):
    written = art.write_awarded_requirements_artifacts(repo_root=tmp_path)
    assert written["declaration"]["ready_for_demo_contract"] is True
    assert written["fixture"]["award_count"] == 4


def test_the_contract_artifact_states_the_required_facts():
    payload = json.loads(
        (
            REPO_ROOT / art.ARTIFACT_DIR / "awarded_grants_requirements_contract.json"
        ).read_text(encoding="utf-8")
    )
    for key in (
        "awarded_grant_record_contract_available",
        "award_transition_contract_available",
        "requirement_model_available",
        "requirements_calendar_available",
        "proof_audit_contract_available",
        "ready_for_demo_contract",
    ):
        assert payload[key] is True
    for key in (
        "ready_for_operational_awarded_tracking",
        "customer_persistence_live",
        "document_storage_live",
        "requirement_extraction_live",
        "live_source_collection_available",
    ):
        assert payload[key] is False


def test_the_requirements_matrix_never_marks_a_projection_active():
    path = REPO_ROOT / art.ARTIFACT_DIR / "awarded_grants_requirements_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["extraction_status"] == "projected_from_nofo":
            assert row["is_active_obligation"] == "false"
        if row["extraction_status"] == "unsupported_document_type":
            assert row["due_date_status"] == "unsupported"


def test_the_calendar_artifact_never_counts_down_an_estimate():
    path = REPO_ROOT / art.ARTIFACT_DIR / "awarded_grants_calendar_preview.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["overdue"] == "true" or row["due_soon"] == "true":
            assert row["due_date_status"] in {"verified", "calculated"}


def test_the_transition_artifact_preserves_history_on_every_row():
    path = REPO_ROOT / art.ARTIFACT_DIR / "awarded_grants_transition_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        assert row["pursuit_history_preserved"] == "true"
        assert row["source_history_preserved"] == "true"


def test_the_summary_states_the_boundaries():
    text = (
        REPO_ROOT / art.ARTIFACT_DIR / "awarded_grants_readiness_summary.md"
    ).read_text(encoding="utf-8")
    for line in (
        "ready_for_operational_awarded_tracking",
        "customer_persistence_live",
        "document_storage_live",
        "requirement_extraction_live",
        "source_monitoring_live",
        "requirements_fabricated",
    ):
        assert line in text


def test_artifact_invariants_pass():
    declaration = art.build_contract_declaration()
    assert art.artifact_invariant_failures(declaration) == []
