"""Tests: Gates 51-57 tenant isolation, authority proof, RBAC, discovery."""

from __future__ import annotations

from nativeforge.services.authority_proof_workflow_service import (
    authority_proof_invariant_failures,
    build_authority_proof,
    evaluate_authority_sensitive_action,
    transition_authority_proof,
)
from nativeforge.services.continuous_source_discovery_service import (
    build_source_candidate,
    dedupe_candidates,
    evaluate_source_freshness,
    evaluate_source_promotion,
    source_candidate_invariant_failures,
)
from nativeforge.services.opportunity_discovery_quality_service import (
    build_discovery_quality_score,
    build_source_coverage_baseline,
    discovery_quality_invariant_failures,
)
from nativeforge.services.org_tenant_seat_model_service import (
    DEFAULT_SEAT_CAP,
    build_org_tenant,
    evaluate_seat_invite,
    evaluate_tenant_scoped_access,
    org_tenant_invariant_failures,
)
from nativeforge.services.rbac_privilege_matrix_service import (
    build_privilege_matrix,
    evaluate_capability,
    privilege_matrix_invariant_failures,
    record_role_change,
)
from nativeforge.services.sc_federal_discovery_improvement_service import (
    build_improvement_target,
    build_sc_federal_routing,
    evaluate_improvement,
    improvement_invariant_failures,
    sc_federal_routing_invariant_failures,
)

ORG_A = "org-aaaa"
ORG_B = "org-bbbb"


def _full_tenant() -> dict:
    members = [
        {"user_id": f"u{i}", "role": "grant_lead", "state": "active"}
        for i in range(DEFAULT_SEAT_CAP)
    ]
    return build_org_tenant(
        organization_profile_id=ORG_A, display_name="Org A", memberships=members
    )


# ───────────────────────── Gate 51 — tenant + seats ─────────────────────────


def test_default_seat_cap_is_five() -> None:
    t = build_org_tenant(organization_profile_id=ORG_A, display_name="Org A")
    assert t["seat_cap"] == 5
    assert t["seats_used"] == 0
    assert org_tenant_invariant_failures(t) == []


def test_sixth_seat_invite_blocked_by_default() -> None:
    t = _full_tenant()
    assert t["seats_used"] == 5
    assert t["seats_available"] == 0

    r = evaluate_seat_invite(
        tenant=t, invitee_id="u6", role="reviewer", actor_id="owner"
    )
    assert r["allowed"] is False
    assert r["invite_state"] == "blocked_seat_limit"
    assert r["reason"] == "seat_cap_reached_override_required"
    events = [e["event_type"] for e in r["audit_events"]]
    assert "seat_invite_blocked_limit" in events
    assert "seat_limit_override_requested" in events


def test_seat_override_requires_explicit_approval_and_is_audited() -> None:
    t = _full_tenant()
    r = evaluate_seat_invite(
        tenant=t,
        invitee_id="u6",
        role="reviewer",
        actor_id="owner",
        override_approved_by="operator-1",
    )
    assert r["allowed"] is True
    assert r["invite_state"] == "pending_override_approval"
    assert "seat_limit_override_approved" in [
        e["event_type"] for e in r["audit_events"]
    ]


def test_operator_internal_consumes_no_seat_and_carries_no_authority() -> None:
    t = _full_tenant()
    r = evaluate_seat_invite(
        tenant=t, invitee_id="support-1", role="operator_internal", actor_id="ops"
    )
    assert r["allowed"] is True
    assert r["consumes_seat"] is False
    assert r["carries_customer_authority"] is False


def test_cross_org_access_denied_and_audited() -> None:
    for obj in ("workspace", "evidence_intake", "feedback_report"):
        r = evaluate_tenant_scoped_access(
            requesting_org_id=ORG_A,
            resource_org_id=ORG_B,
            object_type=obj,
            action="view",
            actor_id="u1",
            actor_role="org_admin",
        )
        assert r["allowed"] is False, obj
        events = [e["event_type"] for e in r["audit_events"]]
        assert "cross_org_access_attempt" in events
        assert "tenant_access_denied" in events


def test_same_org_access_allowed() -> None:
    r = evaluate_tenant_scoped_access(
        requesting_org_id=ORG_A,
        resource_org_id=ORG_A,
        object_type="workspace",
        action="view",
        actor_id="u1",
    )
    assert r["allowed"] is True
    assert r["audit_events"] == []


def test_tenant_never_claims_production_storage_or_persistence() -> None:
    t = _full_tenant()
    assert t["production_storage_claimed"] is False
    assert t["customer_persistence_claimed"] is False
    assert t["login_live_claimed"] is False


# ───────────────────────── Gate 52 — authority proof ─────────────────────────


def test_submitted_proof_is_not_verified() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="submitted",
        proof_types_submitted=["tribal_resolution_or_authorization_letter"],
    )
    assert p["state"] == "submitted"
    assert p["unlocks_authority_sensitive_actions"] is False
    assert authority_proof_invariant_failures(p) == []

    d = evaluate_authority_sensitive_action(
        action="official_package_approval", proof=p
    )
    assert d["allowed"] is False
    assert "authority_proof_state_blocks:submitted" in d["blocked_reasons"]


def test_verified_without_verifier_is_not_verified() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
    )
    assert p["state"] == "under_review"
    assert p["unlocks_authority_sensitive_actions"] is False


def test_rejected_expired_revoked_block_final_approval() -> None:
    for state in ("rejected", "expired", "revoked"):
        p = build_authority_proof(
            person_id="p1",
            organization_profile_id=ORG_A,
            role="authorized_representative",
            state=state,
            verified_by="ops",
        )
        d = evaluate_authority_sensitive_action(
            action="final_application_package_signoff", proof=p
        )
        assert d["allowed"] is False, state
        assert f"authority_proof_state_blocks:{state}" in d["blocked_reasons"]


def test_verified_proof_expires_against_now() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
        verified_by="ops",
        expires_at="2026-01-01",
        now="2026-08-23",
    )
    assert p["state"] == "expired"
    assert p["unlocks_authority_sensitive_actions"] is False


def test_unknown_authority_blocks_submission_readiness() -> None:
    p = build_authority_proof(
        person_id="p1", organization_profile_id=ORG_A, role="grant_lead"
    )
    d = evaluate_authority_sensitive_action(
        action="official_submission_readiness", proof=p
    )
    assert d["allowed"] is False
    assert d["submission_ready_claimed"] is False


def test_authorized_representative_cannot_bypass_missing_evidence() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
        verified_by="ops",
    )
    assert p["unlocks_authority_sensitive_actions"] is True

    ok = evaluate_authority_sensitive_action(
        action="official_package_approval", proof=p
    )
    assert ok["allowed"] is True

    blocked = evaluate_authority_sensitive_action(
        action="official_package_approval",
        proof=p,
        missing_evidence=["tribal_resolution"],
    )
    assert blocked["allowed"] is False
    assert "missing_evidence_present" in blocked["blocked_reasons"]
    assert blocked["audit_event"]["event_type"] == "authority_sensitive_action_blocked"


def test_reviewer_role_can_never_hold_authority() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="reviewer",
        state="verified",
        verified_by="ops",
    )
    assert p["role_is_authority_capable"] is False
    assert p["unlocks_authority_sensitive_actions"] is False


def test_revocation_removes_unlock_and_audits() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
        verified_by="ops",
    )
    t = transition_authority_proof(
        proof=p, new_state="revoked", actor_id="ops", reason="left_organization"
    )
    assert t["proof"]["unlocks_authority_sensitive_actions"] is False
    assert t["audit_event"]["event_type"] == "authority_proof_revoked"


def test_authority_proof_never_asserts_external_status() -> None:
    p = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="org_owner",
        state="verified",
        verified_by="ops",
        proof_types_submitted=["sam_uei_ebiz_aor_evidence"],
    )
    assert p["sam_uei_status_claimed"] is False
    assert p["aor_status_claimed"] is False
    assert p["portal_access_claimed"] is False
    assert p["tribal_facts_asserted"] is False
    assert authority_proof_invariant_failures(p) == []


# ───────────────────────── Gate 53 — RBAC matrix ─────────────────────────


def test_privilege_matrix_is_deny_by_default_and_valid() -> None:
    m = build_privilege_matrix()
    assert m["default"] == "deny"
    assert privilege_matrix_invariant_failures(m) == []
    assert m["controlled_customer_pilot_status"] == "NO_GO"
    assert m["production_rollout_status"] == "NO_GO"


def test_blocked_capabilities_cannot_be_granted_to_any_role() -> None:
    for role in (
        "org_owner",
        "org_admin",
        "authorized_representative",
        "operator_internal",
    ):
        for cap in (
            "controlled_customer_pilot_go",
            "production_rollout_go",
            "enable_login_live",
            "enable_production_storage",
            "declare_pen_test_passed",
            "final_submit_to_portal",
        ):
            r = evaluate_capability(role=role, capability=cap)
            assert r["allowed"] is False, (role, cap)


def test_viewer_and_reviewer_cannot_approve_or_certify() -> None:
    for role in ("viewer", "reviewer", "grant_lead"):
        for cap in ("certify_org_facts", "approve_package_readiness"):
            r = evaluate_capability(role=role, capability=cap)
            assert r["allowed"] is False, (role, cap)


def test_operator_internal_never_holds_customer_authority() -> None:
    r = evaluate_capability(role="operator_internal", capability="certify_org_facts")
    assert r["allowed"] is False
    assert r["carries_customer_authority"] is False

    support = evaluate_capability(
        role="operator_internal", capability="support_review_access"
    )
    assert support["allowed"] is True
    assert support["carries_customer_authority"] is False


def test_authority_gated_capability_requires_verified_proof() -> None:
    without = evaluate_capability(
        role="authorized_representative", capability="approve_package_readiness"
    )
    assert without["allowed"] is False
    assert "authority_proof_required" in without["blocked_reasons"]

    verified = build_authority_proof(
        person_id="p1",
        organization_profile_id=ORG_A,
        role="authorized_representative",
        state="verified",
        verified_by="ops",
    )
    with_proof = evaluate_capability(
        role="authorized_representative",
        capability="approve_package_readiness",
        authority_proof=verified,
    )
    assert with_proof["allowed"] is True

    still_blocked = evaluate_capability(
        role="authorized_representative",
        capability="approve_package_readiness",
        authority_proof=verified,
        missing_evidence=["board_resolution"],
    )
    assert still_blocked["allowed"] is False


def test_role_change_is_audited_and_grants_nothing_immediately() -> None:
    e = record_role_change(
        organization_profile_id=ORG_A,
        actor_id="owner",
        subject_id="u2",
        old_role="reviewer",
        new_role="authorized_representative",
    )
    assert e["event_type"] == "role_changed"
    assert e["is_privilege_escalation"] is True
    assert e["grants_customer_authority_immediately"] is False


# ───────────────────────── Gate 54 — discovery quality ─────────────────────


def _opp(**kw) -> dict:
    base = {
        "source_id": "src_1",
        "source_url": "https://example.gov/x",
        "extraction_timestamp": "2026-08-01",
        "native_relevance_evidence": ["set_aside_language"],
        "eligibility_evidence": ["recognition_tier_match"],
        "eligibility_state": "possibly_eligible",
        "recognition_tier": "federally_recognized",
        "authority_requirements": ["AOR"],
        "funding_geography": "federal",
        "category": "education",
    }
    base.update(kw)
    return base


def test_duplicate_heavy_set_scores_lower_than_unique_set() -> None:
    coverage = build_source_coverage_baseline(
        sources=[{"source_type": "grants_gov", "freshness_state": "fresh"}]
    )
    unique = [_opp() for _ in range(10)]
    dup_heavy = [_opp() for _ in range(10)] + [
        _opp(duplicate_of="o1") for _ in range(10)
    ]

    a = build_discovery_quality_score(opportunities=unique, coverage=coverage)
    b = build_discovery_quality_score(opportunities=dup_heavy, coverage=coverage)

    assert b["opportunity_count_raw"] > a["opportunity_count_raw"]
    assert b["discovery_quality_score"] < a["discovery_quality_score"]
    assert discovery_quality_invariant_failures(a) == []


def test_missing_provenance_and_evidence_reduce_score() -> None:
    coverage = build_source_coverage_baseline(
        sources=[{"source_type": "grants_gov", "freshness_state": "fresh"}]
    )
    good = [_opp() for _ in range(5)]
    bad = [
        _opp(
            source_url=None,
            extraction_timestamp=None,
            native_relevance_evidence=None,
            eligibility_evidence=None,
        )
        for _ in range(5)
    ]
    a = build_discovery_quality_score(opportunities=good, coverage=coverage)
    b = build_discovery_quality_score(opportunities=bad, coverage=coverage)
    assert b["discovery_quality_score"] < a["discovery_quality_score"]
    assert b["missing_metadata_rate"] > 0


def test_stale_sources_penalise_freshness_and_unknown_is_not_fresh() -> None:
    cov = build_source_coverage_baseline(
        sources=[
            {"source_type": "grants_gov", "freshness_state": "stale"},
            {"source_type": "state_grant_portal", "freshness_state": "unknown"},
        ]
    )
    assert cov["source_freshness_score"] == 0.0
    assert cov["unknown_counted_as_fresh"] is False
    assert cov["stale_source_rate"] == 0.5


def test_unknown_eligibility_never_counts_as_eligible() -> None:
    coverage = build_source_coverage_baseline(
        sources=[{"source_type": "grants_gov", "freshness_state": "fresh"}]
    )
    unknown = [
        _opp(eligibility_state="unknown", eligibility_evidence=None) for _ in range(4)
    ]
    s = build_discovery_quality_score(opportunities=unknown, coverage=coverage)
    assert s["eligibility_evidence_score"] == 0.0
    assert s["unknown_eligibility_counted_as_eligible"] is False


# ───────────────────────── Gate 55 — source discovery ─────────────────────


def test_unknown_source_cannot_be_promoted_without_review() -> None:
    c = build_source_candidate(
        source_url="https://example.org/feed",
        source_type="unknown",
        state="unknown",
    )
    r = evaluate_source_promotion(candidate=c)
    assert r["allowed"] is False
    assert "unknown_source_requires_review" in r["blocked_reasons"]
    assert "human_review_approval_required" in r["blocked_reasons"]
    assert r["audit_event"]["event_type"] == "source_candidate_blocked"


def test_terms_prohibited_source_is_blocked() -> None:
    c = build_source_candidate(
        source_url="https://example.org/x",
        source_type="local_or_regional",
        terms_review_state="prohibited",
    )
    assert c["state"] == "blocked_terms"
    r = evaluate_source_promotion(candidate=c, approver_id="ops")
    assert r["allowed"] is False
    assert source_candidate_invariant_failures(c) == []


def test_robots_disallow_blocks_promotion() -> None:
    c = build_source_candidate(
        source_url="https://example.org/y",
        source_type="local_or_regional",
        robots_allows=False,
    )
    assert c["state"] == "blocked_terms"
    r = evaluate_source_promotion(candidate=c, approver_id="ops")
    assert r["allowed"] is False


def test_promotion_requires_approver_and_complete_provenance() -> None:
    base = dict(
        source_url="https://example.gov/rss",
        source_type="federal_agency_native_relevant",
        access_method="rss",
        terms_review_state="permitted",
        robots_allows=True,
        state="triaged",
        extraction_timestamp="2026-08-01",
    )
    no_prov = build_source_candidate(**base)
    r1 = evaluate_source_promotion(candidate=no_prov, approver_id="ops")
    assert r1["allowed"] is False
    assert "provenance_incomplete" in r1["blocked_reasons"]

    ok = build_source_candidate(**base, provenance={"publisher": "US Agency"})
    r2 = evaluate_source_promotion(candidate=ok, approver_id=None)
    assert r2["allowed"] is False
    assert "human_review_approval_required" in r2["blocked_reasons"]

    r3 = evaluate_source_promotion(candidate=ok, approver_id="ops")
    assert r3["allowed"] is True
    assert r3["resulting_state"] == "monitoring"
    assert r3["audit_event"]["event_type"] == "source_candidate_promoted"
    assert r3["live_ingest_claimed"] is False


def test_stale_source_stays_stale_and_freshness_is_never_inferred() -> None:
    c = build_source_candidate(
        source_url="https://example.gov/z", source_type="grants_gov"
    )
    stale = evaluate_source_freshness(
        candidate=c, now_days_since_epoch=100, last_seen_days_since_epoch=40
    )
    assert stale["freshness_state"] == "stale"
    assert stale["counted_as_fresh"] is False
    assert stale["audit_event"]["event_type"] == "opportunity_source_stale"

    unknown = evaluate_source_freshness(candidate=c)
    assert unknown["freshness_state"] == "unknown"
    assert unknown["counted_as_fresh"] is False
    assert unknown["freshness_inferred"] is False


def test_duplicate_candidates_are_flagged_not_dropped_silently() -> None:
    d = dedupe_candidates(
        candidates=[
            {"title": "Program A", "source_url": "https://x.gov/a"},
            {"title": "program a", "source_url": "https://X.gov/A"},
            {"title": "Program B", "source_url": "https://x.gov/b"},
        ]
    )
    assert d["unique_count"] == 2
    assert d["duplicate_count"] == 1
    assert (
        d["duplicates_flagged"][0]["audit_event"]["event_type"]
        == "opportunity_duplicate_flagged"
    )


# ───────────────────────── Gate 56 — 65% target ─────────────────────────


def _quality(dup_rate: float, miss_rate: float, prov: float) -> dict:
    return {
        "duplicate_rate": dup_rate,
        "missing_metadata_rate": miss_rate,
        "components": {"provenance_completeness": prov},
    }


def test_target_is_baseline_times_1_65() -> None:
    t = build_improvement_target(
        baseline_score=0.40,
        baseline_window="2026-08-01..2026-08-23",
        baseline_measured_at="2026-08-23",
    )
    assert t["target_score"] == 0.66
    assert t["achieved"] is False
    assert t["improvement_claimed"] is False


def test_improvement_requires_measurement() -> None:
    t = build_improvement_target(
        baseline_score=0.40, baseline_window="w", baseline_measured_at="2026-08-23"
    )
    r = evaluate_improvement(target=t, current_score=None, current_quality=None)
    assert r["measured"] is False
    assert r["achieved"] is False
    assert "no_measurement_available" in r["blocked_reasons"]
    assert improvement_invariant_failures(r) == []


def test_score_below_target_is_not_achieved() -> None:
    t = build_improvement_target(
        baseline_score=0.40, baseline_window="w", baseline_measured_at="2026-08-23"
    )
    r = evaluate_improvement(
        target=t, current_score=0.50, current_quality=_quality(0.0, 0.0, 1.0)
    )
    assert r["achieved"] is False
    assert "current_score_below_target" in r["blocked_reasons"]


def test_duplicate_heavy_increase_does_not_count_as_improvement() -> None:
    t = build_improvement_target(
        baseline_score=0.40, baseline_window="w", baseline_measured_at="2026-08-23"
    )
    r = evaluate_improvement(
        target=t, current_score=0.90, current_quality=_quality(0.55, 0.0, 1.0)
    )
    assert r["achieved"] is False
    assert "duplicate_rate_exceeds_limit" in r["blocked_reasons"]
    assert r["raw_count_counted_as_improvement"] is False


def test_stale_and_missing_metadata_block_improvement() -> None:
    t = build_improvement_target(
        baseline_score=0.40, baseline_window="w", baseline_measured_at="2026-08-23"
    )
    r = evaluate_improvement(
        target=t,
        current_score=0.90,
        current_quality=_quality(0.0, 0.5, 0.2),
        coverage={"stale_source_rate": 0.9},
    )
    assert r["achieved"] is False
    for reason in (
        "missing_metadata_rate_exceeds_limit",
        "provenance_completeness_below_minimum",
        "stale_source_rate_exceeds_limit",
    ):
        assert reason in r["blocked_reasons"]


def test_clean_measurement_above_target_is_achieved() -> None:
    t = build_improvement_target(
        baseline_score=0.40, baseline_window="w", baseline_measured_at="2026-08-23"
    )
    r = evaluate_improvement(
        target=t,
        current_score=0.70,
        current_quality=_quality(0.02, 0.01, 0.95),
        coverage={"stale_source_rate": 0.05},
    )
    assert r["achieved"] is True
    assert r["improvement_claimed"] is True
    assert improvement_invariant_failures(r) == []


def test_sc_and_federal_lanes_are_separated_not_collapsed() -> None:
    routing = build_sc_federal_routing(
        opportunities=[
            _opp(
                funding_geography="south_carolina",
                recognition_tier="state_recognized",
            ),
            _opp(funding_geography="federal", recognition_tier="federally_recognized"),
            _opp(funding_geography="federal", recognition_tier="unknown"),
        ]
    )
    assert routing["sc_state_count"] == 1
    assert routing["federal_count"] == 2
    assert routing["single_workflow"] is True
    assert routing["lanes_merged"] is False
    assert routing["state_and_federal_recognition_collapsed"] is False
    assert routing["by_recognition_route"]["state_recognized"] == 1
    assert routing["by_recognition_route"]["federally_recognized"] == 1
    assert routing["unknown_recognition_count"] == 1
    assert routing["unknown_recognition_treated_as_eligible"] is False
    assert sc_federal_routing_invariant_failures(routing) == []
