"""Gate 155: closing Gates 151-155 without claiming more than they earned.

The overstatement this gate exists to prevent is subtle. Four lanes are true
that were not true before, and the obvious summary - "four lanes went true" -
is wrong: none of them existed at Gate 150, measured across `src/` at commit
4d336d1. They were CREATED and proved. **Nothing that was false became true.**

A reader who takes four green rows for four cleared blockers concludes the
product moved toward a customer. It did not. Every approval Gate 150 recorded
as outstanding is still outstanding.

One defect found while building this gate: the registry check Gate 154 wrote
caught a verifier script added here without a registry entry. That guard had
never been exercised by a gate other than the one that wrote it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    operational_durability_artifact_gate155_service as art,
)
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    build_beta_onboarding_summary,
)
from nativeforge.services.next_activation_decision_service import (
    CANDIDATES,
    ENGINEERING,
    HUMAN,
    NOTHING_BLOCKED,
    WRAPPER_RISK,
    build_next_activation_decision,
    next_activation_decision_invariant_failures,
)
from nativeforge.services.operational_durability_reassessment_service import (
    DURABILITY_LANES,
    GATE_150_BASELINE,
    LIMITED_GO,
    NO_GO,
    UNCHANGED_FALSE_LANES,
    build_durability_reassessment,
    durability_reassessment_invariant_failures,
)
from nativeforge.services.readiness_verifier_registry_service import (
    VERIFIERS,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000155"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

VERIFIER_SCRIPT = (
    REPO_ROOT / "scripts" / "verify_nativeforge_operational_durability_reassessment.sh"
)

PROVED = dict(
    internal_demo_beta="GO",
    controlled_customer_beta=LIMITED_GO,
    tenant_digest_persistence_live=True,
    audit_replay_ready=True,
    operational_backup_restore_ready=True,
    operational_health_ready=True,
    production_backup_ready=False,
    production_monitoring_active=False,
    controlled_customer_pilot=False,
    activation_mechanism_exists=False,
    customer_auth_live=False,
    verified_operational_binding=False,
    consent_boundary_documented=False,
    customer_beta_scope_approved=False,
    source_monitoring_live=False,
    email_delivery=False,
    object_store_configured=False,
)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _reassessment(**overrides):
    return build_durability_reassessment(**{**PROVED, **overrides})


def _decision(**overrides):
    return build_next_activation_decision(
        **{
            "real_customer_org_exists": False,
            "second_identity_available": False,
            "consent_decision_available": False,
            **overrides,
        }
    )


# ------------------------------------------------------- 155B the lane delta


def test_exactly_four_durability_lanes_were_created():
    delta = _reassessment()["lane_delta"]
    assert delta["lanes_created_count"] == 4
    assert len(DURABILITY_LANES) == 4
    assert sorted(delta["lanes_proved"]) == sorted(
        entry["lane"] for entry in DURABILITY_LANES
    )


def test_no_lane_that_was_false_became_true():
    """The overstatement this whole gate exists to prevent."""
    delta = _reassessment()["lane_delta"]
    assert delta["lanes_that_were_false_and_became_true"] == []
    # The claim, not its wording: the explanation must cite the Gate 150
    # measurement and say the lanes were created rather than flipped.
    why = delta["why_that_list_is_empty"].lower()
    assert "gate 150" in why
    assert "4d336d1" in why
    assert "created" in why


def test_every_declared_lane_records_that_it_did_not_exist_at_gate_150():
    for entry in DURABILITY_LANES:
        assert entry["existed_at_gate_150"] == "no", entry["lane"]
        assert entry["gate"] in {"151", "152", "153", "154"}


def test_a_reassessment_claiming_a_false_lane_flipped_is_refused():
    reassessment = _reassessment()
    reassessment["lane_delta"]["lanes_that_were_false_and_became_true"] = [
        "customer_auth_live"
    ]
    assert "claimed_a_false_lane_became_true" in (
        durability_reassessment_invariant_failures(reassessment)
    )


def test_a_lane_not_proved_blocks_the_improvement_claim():
    reassessment = _reassessment(audit_replay_ready=False)
    assert reassessment["operational_durability_improved"] is False
    assert "durability_lane_not_proved:audit_replay_ready" in (
        durability_reassessment_invariant_failures(reassessment)
    )


def test_the_improvement_claim_is_derived_not_supplied():
    assert _reassessment()["operational_durability_improved"] is True
    assert (
        _reassessment(operational_health_ready=False)["operational_durability_improved"]
        is False
    )


# -------------------------------------------------------- the decisions hold


def test_the_customer_beta_decision_is_unchanged():
    assert _reassessment()["customer_beta_decision"] == LIMITED_GO
    assert GATE_150_BASELINE["controlled_customer_beta"] == LIMITED_GO


def test_the_production_decision_is_unchanged():
    assert _reassessment()["production_decision"] == NO_GO


def test_production_rollout_has_no_branch_that_returns_anything_else():
    """Even asked for GO, it returns NO_GO."""
    reassessment = build_durability_reassessment(
        **{**PROVED, "internal_demo_beta": "GO"}
    )
    assert reassessment["production_decision"] == NO_GO
    assert reassessment["decision_delta"]["production_rollout"]["changed"] is False


def test_no_decision_changed():
    reassessment = _reassessment()
    assert reassessment["any_decision_changed"] is False
    for entry in reassessment["decision_delta"].values():
        assert entry["changed"] is False


def test_a_changed_decision_is_refused():
    reassessment = _reassessment(controlled_customer_beta="GO")
    assert "a_decision_changed_without_a_new_approval" in (
        durability_reassessment_invariant_failures(reassessment)
    )


@pytest.mark.parametrize("lane", sorted(UNCHANGED_FALSE_LANES))
def test_each_lane_that_must_stay_false_is_refused_if_true(lane):
    reassessment = _reassessment(**{lane: True})
    assert f"lane_that_must_stay_false_is_true:{lane}" in (
        durability_reassessment_invariant_failures(reassessment)
    )


def test_eight_lanes_remain_false():
    delta = _reassessment()["lane_delta"]
    assert delta["unchanged_false_count"] == len(UNCHANGED_FALSE_LANES)
    assert not any(delta["unchanged_false_lanes"].values())


def test_the_pilot_is_not_activated_and_no_mechanism_exists():
    reassessment = _reassessment()
    assert (
        reassessment["lane_delta"]["unchanged_false_lanes"]["controlled_customer_pilot"]
        is False
    )
    assert reassessment["activation_mechanism_created"] is False
    assert reassessment["anything_activated"] is False


# ---------------------------------------- readiness is not activation


def test_operational_backup_restore_is_not_production_backup():
    pairs = {
        (entry["readiness"], entry["is_not"])
        for entry in _reassessment()["conflations"]
    }
    assert (
        "operational_backup_restore_ready",
        "production_backup_ready",
    ) in pairs


def test_operational_health_is_not_production_monitoring():
    pairs = {
        (entry["readiness"], entry["is_not"])
        for entry in _reassessment()["conflations"]
    }
    assert ("operational_health_ready", "production monitoring") in pairs


def test_removing_the_backup_conflation_warning_is_refused():
    reassessment = _reassessment()
    reassessment["conflations"] = [
        e
        for e in reassessment["conflations"]
        if e["readiness"] != "operational_backup_restore_ready"
    ]
    assert "the_backup_conflation_warning_was_removed" in (
        durability_reassessment_invariant_failures(reassessment)
    )


def test_removing_the_monitoring_conflation_warning_is_refused():
    reassessment = _reassessment()
    reassessment["conflations"] = [
        e
        for e in reassessment["conflations"]
        if e["readiness"] != "operational_health_ready"
    ]
    assert "the_monitoring_conflation_warning_was_removed" in (
        durability_reassessment_invariant_failures(reassessment)
    )


def test_production_durability_is_unchanged_and_constant():
    production = _reassessment()["production_durability"]
    assert production["production_backup_ready"] is False
    assert production["production_monitoring_active"] is False
    assert "procurement" in production["blocked_on"]


def test_a_reassessment_claiming_production_backup_is_refused():
    assert "production_backup_ready_became_true" in (
        durability_reassessment_invariant_failures(
            _reassessment(production_backup_ready=True)
        )
    )


def test_a_reassessment_claiming_production_monitoring_is_refused():
    assert "production_monitoring_became_true" in (
        durability_reassessment_invariant_failures(
            _reassessment(production_monitoring_active=True)
        )
    )


def test_an_activation_mechanism_is_refused():
    assert "an_activation_mechanism_was_created" in (
        durability_reassessment_invariant_failures(
            _reassessment(activation_mechanism_exists=True)
        )
    )


# ------------------------------------------------- the reassessment is clean


def test_the_reassessment_is_deterministic():
    assert _reassessment() == _reassessment()


def test_the_reassessment_has_no_invariant_failures():
    assert durability_reassessment_invariant_failures(_reassessment()) == []


def test_the_reassessment_writes_nothing_and_contacts_nothing():
    reassessment = _reassessment()
    assert reassessment["rows_written"] == 0
    assert reassessment["real_organization_touched"] is False
    assert reassessment["email_sent"] is False
    assert reassessment["live_source_called"] is False
    assert reassessment["object_store_contacted"] is False


def test_the_reassessment_leaks_nothing():
    reassessment = _reassessment()
    assert reassessment["leaked_shapes"] == []
    body = json.dumps(reassessment, default=str)
    assert not ADDRESS_SHAPE.search(body)
    assert not SUBJECT_SHAPE.search(body)
    assert REAL not in body


def test_safe_and_unsafe_claims_are_both_present():
    reassessment = _reassessment()
    assert reassessment["safe_claims"]
    assert reassessment["unsafe_claims"]
    unsafe = " ".join(e["claim"] for e in reassessment["unsafe_claims"]).lower()
    assert "backups" in unsafe
    assert "monitored" in unsafe


def test_every_unsafe_claim_says_what_is_true_instead():
    for entry in _reassessment()["unsafe_claims"]:
        assert entry["why_unsafe"], entry["claim"]
        assert entry["what_is_true"], entry["claim"]


# ------------------------------------------------ 155C the next-block choice


def test_the_next_block_decision_is_deterministic():
    assert _decision() == _decision()


def test_the_next_block_decision_has_no_invariant_failures():
    assert next_activation_decision_invariant_failures(_decision()) == []


def test_the_recommended_block_is_engineering_advancable():
    decision = _decision()
    chosen = next(
        e
        for e in decision["ranked_candidates"]
        if e["candidate"] == decision["recommended_block"]
    )
    assert chosen["engineering_can_advance"] is True
    assert chosen["engineering_blocker_count"] >= 2
    assert chosen["verdict"] != WRAPPER_RISK


def test_the_recommendation_is_source_collection_runtime():
    decision = _decision()
    assert decision["recommended_block"] == "source_collection_runtime"
    assert "scheduler" in decision["first_gate"]


@pytest.mark.parametrize(
    "candidate",
    [
        "customer_activation",
        "email_activation",
        "object_storage_activation",
        "production_infrastructure",
    ],
)
def test_the_human_only_candidates_are_marked_as_wrappers(candidate):
    """The rule: no more readiness around a blocker only a person can clear."""
    entry = next(
        e for e in _decision()["ranked_candidates"] if e["candidate"] == candidate
    )
    assert entry["verdict"] == WRAPPER_RISK
    assert entry["engineering_blocker_count"] == 0


def test_a_candidate_with_nothing_blocked_is_not_recommended():
    entry = next(
        e
        for e in _decision()["ranked_candidates"]
        if e["candidate"] == "additional_durability"
    )
    assert entry["verdict"] == NOTHING_BLOCKED
    assert _decision()["recommended_block"] != "additional_durability"


def test_recommending_a_wrapper_block_is_refused():
    decision = _decision()
    decision["recommended_block"] = "email_activation"
    assert "recommended_a_wrapper_block:email_activation" in (
        next_activation_decision_invariant_failures(decision)
    )


def test_recommending_a_block_with_nothing_blocked_is_refused():
    decision = _decision()
    decision["recommended_block"] = "additional_durability"
    assert "recommended_a_block_with_nothing_blocked:additional_durability" in (
        next_activation_decision_invariant_failures(decision)
    )


def test_the_customer_branch_is_reachable():
    """A branch nobody can reach makes the rule unfalsifiable."""
    decision = _decision(
        real_customer_org_exists=True,
        second_identity_available=True,
        consent_decision_available=True,
    )
    assert decision["recommended_block"] == "customer_activation"
    assert decision["customer_prerequisites_available_now"] is True
    assert next_activation_decision_invariant_failures(decision) == []


@pytest.mark.parametrize(
    "missing",
    [
        "real_customer_org_exists",
        "second_identity_available",
        "consent_decision_available",
    ],
)
def test_every_customer_prerequisite_is_necessary(missing):
    kwargs = {
        "real_customer_org_exists": True,
        "second_identity_available": True,
        "consent_decision_available": True,
        missing: False,
    }
    decision = _decision(**kwargs)
    assert decision["recommended_block"] != "customer_activation"


def test_every_candidate_blocker_is_classified():
    for candidate in CANDIDATES:
        for blocker in candidate["blockers"]:
            assert blocker["kind"] in (HUMAN, ENGINEERING), blocker["blocker"]
            assert blocker["detail"], blocker["blocker"]


def test_the_recommendation_does_not_claim_monitoring_would_go_live():
    decision = _decision()
    joined = " ".join(decision["what_the_recommendation_does_not_mean"])
    assert "source_monitoring_live" in joined
    assert "terms_blocked" in joined


def test_the_decision_activates_nothing():
    decision = _decision()
    assert decision["anything_activated"] is False
    assert decision["activation_mechanism_created"] is False
    assert decision["rows_written"] == 0
    assert decision["external_call_made"] is False


# ----------------------------------------------------------- 155D the routes


ROUTES = ("reassessment", "safe-claims", "unsafe-claims", "next-activation-decision")


@pytest.mark.parametrize("path", ROUTES)
def test_every_route_requires_a_session(client, path):
    response = client.get(f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/{path}")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_a_forged_header_cannot_override_the_org(client, path):
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/{path}",
        headers=soh.forged_header_only(DEMO),
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_another_organization_is_refused(client, path):
    soh.ensure_org(OTHER, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/{path}",
        headers=soh.session_headers(OTHER),
    )
    assert response.status_code in (403, 404)


@pytest.mark.parametrize("path", ROUTES)
def test_no_route_accepts_a_write_method(client, path):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for method in (client.post, client.put, client.patch, client.delete):
        response = method(
            f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/{path}",
            headers=headers,
        )
        assert response.status_code == 405


def test_the_reassessment_route_reports_the_unchanged_decisions(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/reassessment",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["customer_beta_decision"] == LIMITED_GO
    assert body["production_decision"] == NO_GO
    assert body["any_decision_changed"] is False
    assert body["lane_delta"]["lanes_that_were_false_and_became_true"] == []


def test_the_unsafe_claims_route_names_the_likeliest_misreading(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/unsafe-claims",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["unsafe_claim_count"] >= 5
    assert "SKIP" in body["the_one_most_likely"]


def test_the_safe_claims_route_points_at_the_unsafe_one(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/safe-claims",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["safe_claim_count"] >= 5
    assert "unsafe" in body["read_with"]
    assert body["production_backup_ready"] is False


def test_the_next_activation_route_returns_the_recommendation(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/next-activation-decision",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["recommended_block"] == "source_collection_runtime"
    assert body["anything_activated"] is False


def test_no_route_response_carries_an_address_a_subject_or_the_real_org(client):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for path in ROUTES:
        body = client.get(
            f"/v1/nf/demo/orgs/{DEMO}/durability-reassessment/{path}",
            headers=headers,
        ).text
        assert not ADDRESS_SHAPE.search(body), path
        assert not SUBJECT_SHAPE.search(body), path
        assert REAL not in body, path


# ---------------------------------------------------------- 155E the cockpit


def test_the_cockpit_closeout_card_states_the_three_decisions():
    card = build_beta_onboarding_summary()["durability_closeout_card"]
    assert card["internal_demo_beta"] == "GO"
    assert card["controlled_customer_beta"] == LIMITED_GO
    assert card["production_rollout"] == NO_GO
    assert card["decisions_unchanged_since_gate_145"] is True


def test_the_cockpit_closeout_card_makes_no_production_claim():
    card = build_beta_onboarding_summary()["durability_closeout_card"]
    assert card["production_monitoring_active"] is False
    assert card["production_backup_ready"] is False
    assert card["controlled_customer_pilot_active"] is False
    assert card["activation_mechanism_exists"] is False


def test_the_cockpit_closeout_card_claims_no_false_lane_flipped():
    card = build_beta_onboarding_summary()["durability_closeout_card"]
    assert card["lanes_that_were_false_and_became_true"] == []
    assert len(card["lanes_created_by_this_block"]) == 4


def test_the_cockpit_closeout_card_names_the_next_block_and_its_limit():
    card = build_beta_onboarding_summary()["durability_closeout_card"]
    assert card["next_block"] == "source_collection_runtime"
    assert "source_monitoring_live" in card["next_block_does_not_mean"]


def test_the_cockpit_still_has_no_invariant_failures():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        summary_invariant_failures,
    )

    assert summary_invariant_failures(build_beta_onboarding_summary()) == []


# -------------------------------------------------------- 155G the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = art.write_durability_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.durability_artifact_invariant_failures(result) == []
    assert result["file_count"] == 9


def test_the_artifacts_are_deterministic():
    assert art.build_durability_artifacts() == art.build_durability_artifacts()


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_durability_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_no_artifact_carries_an_address_a_subject_or_the_real_org():
    for name, body in art.build_durability_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        assert REAL not in body, name


def test_no_artifact_claims_production_backup_or_monitoring():
    blob = "\n".join(art.build_durability_artifacts().values()).lower()
    assert '"production_backup_ready": true' not in blob
    assert '"production_monitoring_active": true' not in blob


def test_the_closeout_names_both_likely_misreadings():
    body = art.build_durability_artifacts()[art.CLOSEOUT_FILE]
    assert "NativeForge has backups" in body
    assert "NativeForge is monitored" in body
    assert "SKIP" in body


def test_the_survey_records_how_the_lane_delta_was_measured():
    survey = json.loads(art.build_durability_artifacts()[art.SURVEY_FILE])
    assert "4d336d1" in survey["how_the_lane_delta_was_measured"]
    assert "zero files" in survey["how_the_lane_delta_was_measured"]


def test_the_survey_records_the_two_stale_constants():
    survey = json.loads(art.build_durability_artifacts()[art.SURVEY_FILE])
    stale = survey["two_next_step_constants_have_gone_stale_in_this_repository"]
    assert "NEXT_SAFE_ACTION" in " ".join(stale)
    assert "NEXT_BLOCK" in " ".join(stale)


def test_the_production_artifact_says_neither_gate_moved_it():
    production = json.loads(art.build_durability_artifacts()[art.PRODUCTION_FILE])
    assert production["gate_153_did_not_move_this"] is True
    assert production["gate_154_did_not_move_this"] is True
    assert production["production_rollout"] == NO_GO


# --------------------------------------------------------- 155F the verifier


def test_the_verifier_exists_and_is_executable():
    assert VERIFIER_SCRIPT.exists()
    assert VERIFIER_SCRIPT.stat().st_mode & 0o111


def test_the_verifier_runs_the_block_verifiers_rather_than_assuming_them():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    # Each of the four must be named in the loop that actually EXECUTES them,
    # not merely mentioned somewhere in the file. The previous form was
    # `A in body or name in body`, where A is always present - a tautology
    # wearing the costume of a check.
    loop = body.split("for v in ", 1)[1].split("done", 1)[0]
    assert "verify_nativeforge_${v}.sh" in loop
    for name in (
        "tenant_digest_persistence",
        "audit_replay_readiness",
        "backup_restore_readiness",
        "operational_health_runbook",
    ):
        assert name in loop, name


def test_the_verifier_reruns_the_production_backup_harness():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "production_backup_harness_still_skip" in body
    assert "RESULT=SKIP" in body


def test_the_verifier_checks_the_wrapper_rule():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "recommended_block_is_not_a_wrapper" in body
    assert "customer_branch_is_reachable" in body


def test_the_verifier_claims_no_activation():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "NOTHING IS ACTIVATED" in body
    assert "anything_activated=false" in body


def test_this_gates_verifier_is_in_the_registry():
    """Gate 154's registry guard caught this one when it was missing."""
    entry = next(
        e for e in VERIFIERS if e["verifier"] == "operational_durability_reassessment"
    )
    assert entry["gate"] == "155"
    assert entry["expected_result"] == "PASS"
    assert "operational_health_runbook" in entry["depends_on"]


def test_the_production_backup_harness_is_still_untouched():
    body = (REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore.sh").read_text(
        encoding="utf-8"
    )
    assert "operational_durability_improved=true" not in body
