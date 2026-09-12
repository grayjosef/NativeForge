"""Gate 150: the customer beta reassessment, and the one way it could lie.

Gates 146-149 were boundary gates. They made refusals exact and moved no lane,
which is the correct outcome — a block of four gates that moved a lane without a
new external approval would mean one of them had granted itself something.

The single failure mode this gate has is reporting `controlled_customer_beta:
GO` without the four approvals behind it. Most of what follows exists to prove
that cannot happen, and that the honest GO branch is still reachable so the
refusal stays falsifiable.
"""

from __future__ import annotations

import inspect
import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    customer_beta_reassessment_artifact_gate150_service as art,
)
from nativeforge.services.customer_beta_reassessment_service import (
    CLARIFICATIONS,
    CONFLATIONS,
    CUSTOMER_BETA_APPROVALS,
    GATE_145_BASELINE,
    GO,
    LIMITED_GO,
    NEXT_BLOCK,
    NO_GO,
    SAFE_CLAIMS,
    THE_THROUGHLINE,
    UNSAFE_CLAIMS,
    build_reassessment,
    reassessment_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d150"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _measured(**overrides):
    """The state as Gates 146-149 measured it."""
    kwargs = dict(
        internal_demo_beta=GO,
        controlled_customer_beta=LIMITED_GO,
        customer_auth_live=False,
        verified_operational_binding=False,
        consent_boundary_documented=False,
        customer_beta_scope_approved=False,
        controlled_customer_pilot=False,
        activation_mechanism_exists=False,
        second_person_readiness_passed=True,
        approval_boundary_ready=True,
        customer_data_write_guard_ready=True,
        activation_package_ready=True,
    )
    kwargs.update(overrides)
    return kwargs


def _every_approval_granted(**overrides):
    """All four approvals, then any override — merged, not passed twice."""
    granted = {
        "controlled_customer_beta": GO,
        "customer_auth_live": True,
        "verified_operational_binding": True,
        "consent_boundary_documented": True,
        "customer_beta_scope_approved": True,
    }
    granted.update(overrides)
    return _measured(**granted)


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/beta-reassessment"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    return soh.session_headers(uuid.UUID(DEMO))


# ---------------------------------------------------------------------------
# the decision is compared, not recomputed
# ---------------------------------------------------------------------------


def test_gate_145_is_the_baseline():
    assert GATE_145_BASELINE == {
        "internal_demo_beta": GO,
        "controlled_customer_beta": LIMITED_GO,
        "production_rollout": NO_GO,
    }


def test_the_delta_compares_every_scope():
    result = build_reassessment(**_measured())
    assert set(result["decision_delta"]) == set(GATE_145_BASELINE)
    for scope, entry in result["decision_delta"].items():
        assert entry["gate_145"] == GATE_145_BASELINE[scope]


def test_no_decision_changed():
    result = build_reassessment(**_measured())
    assert result["any_decision_changed"] is False
    assert result["lanes_moved_by_this_block"] == 0
    assert reassessment_invariant_failures(result) == []


def test_internal_demo_remains_go():
    result = build_reassessment(**_measured())
    assert result["current_decision"]["internal_demo_beta"] == GO
    assert result["decision_delta"]["internal_demo_beta"]["changed"] is False


def test_controlled_customer_beta_remains_limited_go():
    result = build_reassessment(**_measured())
    assert result["current_decision"]["controlled_customer_beta"] == LIMITED_GO
    assert result["decision_delta"]["controlled_customer_beta"]["changed"] is False
    assert len(result["customer_beta_approvals_outstanding"]) == 4


def test_production_remains_no_go_whatever_is_supplied():
    for kwargs in (_measured(), _every_approval_granted()):
        result = build_reassessment(**kwargs)
        assert result["current_decision"]["production_rollout"] == NO_GO


def test_production_cannot_be_supplied_as_anything_else():
    result = build_reassessment(**_measured(production_rollout=GO))
    assert result["current_decision"]["production_rollout"] == NO_GO


# ---------------------------------------------------------------------------
# the one failure mode
# ---------------------------------------------------------------------------


def test_a_customer_go_without_approvals_is_refused():
    forged = build_reassessment(**_measured(controlled_customer_beta=GO))
    failures = reassessment_invariant_failures(forged)
    assert any("customer_go_with_outstanding_approvals" in f for f in failures)


@pytest.mark.parametrize("approval", sorted(CUSTOMER_BETA_APPROVALS))
def test_a_customer_go_missing_any_single_approval_is_refused(approval):
    keyword = {
        "customer_auth_live": "customer_auth_live",
        "verified_operational_binding": "verified_operational_binding",
        "consent_and_data_boundary_documented": "consent_boundary_documented",
        "customer_beta_scope_approved": "customer_beta_scope_approved",
    }[approval]
    forged = build_reassessment(**_every_approval_granted(**{keyword: False}))
    failures = reassessment_invariant_failures(forged)
    assert any("customer_go_with_outstanding_approvals" in f for f in failures)
    assert approval in forged["customer_beta_approvals_outstanding"]


def test_the_honest_customer_go_branch_is_reachable():
    """An unreachable permitted branch makes the refusal above it unfalsifiable."""
    honest = build_reassessment(**_every_approval_granted())
    assert honest["current_decision"]["controlled_customer_beta"] == GO
    assert honest["customer_beta_approvals_outstanding"] == []
    assert honest["decision_delta"]["controlled_customer_beta"]["changed"] is True
    assert reassessment_invariant_failures(honest) == []


def test_a_forged_delta_baseline_is_refused():
    result = build_reassessment(**_measured())
    result["decision_delta"]["controlled_customer_beta"]["gate_145"] = GO
    assert any(
        "delta_baseline_disagrees" in f
        for f in reassessment_invariant_failures(result)
    )


def test_a_forged_changed_flag_is_refused():
    result = build_reassessment(**_measured())
    result["decision_delta"]["internal_demo_beta"]["changed"] = True
    assert any(
        "delta_changed_flag_disagrees" in f
        for f in reassessment_invariant_failures(result)
    )


# ---------------------------------------------------------------------------
# readiness is not the capability beside it
# ---------------------------------------------------------------------------


def test_six_conflations_are_named():
    assert len(CONFLATIONS) == 6
    for entry in CONFLATIONS:
        assert entry["readiness"]
        assert entry["capability"]
        assert entry["difference"]
        assert entry["gate"]


def test_readiness_passing_alongside_a_false_capability_is_correct():
    """This is today's state, and it must not be an invariant failure."""
    result = build_reassessment(**_measured())
    assert result["readiness_facts"]["second_person_readiness_passed"] is True
    assert result["customer_beta_approvals"]["customer_auth_live"] is False
    assert reassessment_invariant_failures(result) == []


def test_a_capability_reported_true_without_its_readiness_is_refused():
    forged = build_reassessment(
        **_measured(customer_auth_live=True, second_person_readiness_passed=False)
    )
    assert (
        "customer_auth_live_without_the_readiness_behind_it"
        in reassessment_invariant_failures(forged)
    )


def test_activation_package_readiness_is_not_an_activated_pilot():
    result = build_reassessment(**_measured())
    assert result["readiness_facts"]["activation_package_ready"] is True
    assert result["controlled_customer_pilot"] is False
    assert result["activation_mechanism_exists"] is False


def test_the_pilot_stays_false_and_no_mechanism_appears():
    for kwargs in (_measured(), _every_approval_granted()):
        result = build_reassessment(**kwargs)
        assert result["controlled_customer_pilot"] is False
        assert result["activation_mechanism_exists"] is False
        assert result["activation_mechanism_created_by_this_module"] is False


def test_a_reported_pilot_activation_is_refused():
    forged = build_reassessment(**_measured(controlled_customer_pilot=True))
    assert "pilot_reported_as_activated" in reassessment_invariant_failures(forged)


def test_a_reported_activation_mechanism_is_refused():
    forged = build_reassessment(**_measured(activation_mechanism_exists=True))
    assert "an_activation_mechanism_appeared" in reassessment_invariant_failures(
        forged
    )


# ---------------------------------------------------------------------------
# what the block established
# ---------------------------------------------------------------------------


def test_four_gates_are_recorded_and_none_moved_a_lane():
    assert len(CLARIFICATIONS) == 4
    assert {entry["gate"] for entry in CLARIFICATIONS} == {"146", "147", "148", "149"}
    for entry in CLARIFICATIONS:
        assert entry["lane_moved"] == "no"
        assert entry["was_reported_as"]
        assert entry["is_actually"]


def test_the_throughline_names_the_missing_customer():
    assert "customer organization" in THE_THROUGHLINE["finding"]
    assert set(THE_THROUGHLINE["found_by"]) == {"147", "148", "149"}


def test_no_outstanding_customer_blocker_is_technical():
    result = build_reassessment(**_measured())
    assert result["no_outstanding_customer_blocker_is_technical"] is True


# ---------------------------------------------------------------------------
# claims
# ---------------------------------------------------------------------------


def test_safe_claims_are_constrained():
    assert 4 <= len(SAFE_CLAIMS) <= 12
    joined = " ".join(SAFE_CLAIMS).lower()
    assert "demo" in joined
    for forbidden in ("we monitor", "by email", "your data is in"):
        assert forbidden not in joined


def test_no_safe_claim_asserts_a_false_capability():
    joined = " ".join(SAFE_CLAIMS).lower()
    assert "none is being monitored" in joined or "not being monitored" in joined
    assert "not sent" in joined


def test_ten_unsafe_claims_each_with_a_true_alternative():
    assert len(UNSAFE_CLAIMS) >= 10
    for entry in UNSAFE_CLAIMS:
        assert entry["claim"].strip()
        assert entry["why_unsafe"].strip()
        assert entry["true_statement"].strip()


@pytest.mark.parametrize(
    "fragment",
    [
        "monitor grant sources",
        "weekly digest by email",
        "data is in our system",
        "verified your organization",
        "turn email on",
        "guarantee your eligib",
        "guarantee these deadlines",
        "65%",
    ],
)
def test_the_unsafe_inventory_covers_the_known_traps(fragment):
    joined = " ".join(entry["claim"] for entry in UNSAFE_CLAIMS).lower()
    assert fragment.lower() in joined


def test_the_nearly_true_claim_is_named():
    """The approval is not what is missing - a customer organization is."""
    claims = {entry["claim"] for entry in UNSAFE_CLAIMS}
    assert any("we just need an approval" in claim for claim in claims)


def test_the_unsafe_inventory_does_not_trip_the_leak_scan():
    """An inventory of what may not be said is not a saying of it.

    Gate 145 needed an exemption for this; this scan looks for value shapes and
    the inventory contains none, so it scans clean with no exemption at all.
    """
    result = build_reassessment(**_measured())
    assert result["leaked_shapes"] == []
    body = json.dumps(result["unsafe_claims"], default=str)
    assert not ADDRESS_SHAPE.search(body)
    assert not SUBJECT_SHAPE.search(body)


# ---------------------------------------------------------------------------
# next block
# ---------------------------------------------------------------------------


def test_the_next_block_is_recommended_with_a_reason():
    assert NEXT_BLOCK["block"]
    assert NEXT_BLOCK["first_gate"]
    assert NEXT_BLOCK["why"]
    assert len(NEXT_BLOCK["gates"]) == 5


def test_the_next_block_does_not_wait_on_humans():
    assert "idle" in NEXT_BLOCK["why"] or "waiting" in NEXT_BLOCK["why"]


# ---------------------------------------------------------------------------
# nothing leaks, nothing is written
# ---------------------------------------------------------------------------


def test_nothing_is_written_on_any_branch():
    for kwargs in (_measured(), _every_approval_granted()):
        result = build_reassessment(**kwargs)
        assert result["rows_written"] == 0
        assert result["real_organization_touched"] is False
        assert result["approval_granted_by_this_module"] is False
        assert result["pilot_activated_by_this_module"] is False


def test_the_leak_scan_actually_fires():
    from nativeforge.services.customer_beta_reassessment_service import (
        _leaked_shapes,
    )

    assert _leaked_shapes({"x": "somebody@example.org"}) == ["email_address"]
    assert _leaked_shapes({"x": "112233445566778899001"}) == ["provider_subject"]
    assert _leaked_shapes({"x": "nothing"}) == []


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["decision", "safe-claims", "unsafe-claims", "next-block"]
)
def test_every_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/decision",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_decision_route_reports_the_honest_result(client, demo_session):
    body = client.get(f"{_base()}/decision", headers=demo_session).json()
    data = body.get("data", body)
    assert data["current_decision"]["internal_demo_beta"] == GO
    assert data["current_decision"]["controlled_customer_beta"] == LIMITED_GO
    assert data["current_decision"]["production_rollout"] == NO_GO
    assert data["any_decision_changed"] is False
    assert data["lanes_moved_by_this_block"] == 0
    assert data["controlled_customer_pilot"] is False
    assert data["activation_mechanism_exists"] is False


def test_the_safe_claims_route_lists_them(client, demo_session):
    body = client.get(f"{_base()}/safe-claims", headers=demo_session).json()
    data = body.get("data", body)
    assert data["safe_claim_count"] == len(SAFE_CLAIMS)


def test_the_unsafe_claims_route_pairs_each_with_a_true_statement(
    client, demo_session
):
    body = client.get(f"{_base()}/unsafe-claims", headers=demo_session).json()
    data = body.get("data", body)
    assert data["unsafe_claim_count"] >= 10
    for entry in data["unsafe_claims"]:
        assert entry["true_statement"]


def test_the_next_block_route_names_the_first_gate(client, demo_session):
    body = client.get(f"{_base()}/next-block", headers=demo_session).json()
    data = body.get("data", body)
    assert data["first_gate"]
    assert data["why"]


def test_no_route_leaks_a_shape(client, demo_session):
    for path in ("decision", "safe-claims", "unsafe-claims", "next-block"):
        raw = client.get(f"{_base()}/{path}", headers=demo_session).text
        assert not ADDRESS_SHAPE.search(raw)
        assert not SUBJECT_SHAPE.search(raw)
        assert "nf_session=" not in raw


def test_another_organization_is_refused(client, demo_session):
    response = client.get(f"{_base(OTHER)}/decision", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_the_routes_are_get_only():
    from nativeforge.api import customer_beta_reassessment_routes as routes

    methods = set()
    for route in routes.router.routes:
        methods |= set(getattr(route, "methods", set()))
    assert methods == {"GET"}


def test_no_real_organization_route_was_built():
    from nativeforge.api import customer_beta_reassessment_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    assert "/v1/nf/real" not in Path(routes.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# cockpit
# ---------------------------------------------------------------------------


def test_the_cockpit_does_not_claim_customer_beta_full_go():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    assert summary["customer_beta_full_go"] is False
    assert summary["pilot_active"] is False
    assert summary["production_ready"] is False


def test_the_cockpit_records_the_block_reading():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    assert summary["gate_145_baseline_decision"] == GATE_145_BASELINE
    assert summary["customer_beta_decision_changed_since_gate_145"] is False
    assert summary["lanes_moved_by_gates_146_to_149"] == 0
    assert summary["customer_beta_approvals_outstanding"] == 4


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_reassessment_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.reassessment_artifact_invariant_failures(result) == []


def test_the_artifact_is_deterministic():
    built = art.build_reassessment_artifacts()
    assert built == art.build_reassessment_artifacts()


def test_the_artifact_reads_no_database():
    builder = art.build_reassessment_artifacts
    assert inspect.signature(builder).parameters == {}


def test_the_artifacts_record_the_unchanged_decision():
    files = art.build_reassessment_artifacts()
    decision = json.loads(files[art.DECISION_FILE])
    assert decision["internal_demo_beta"] == GO
    assert decision["controlled_customer_beta"] == LIMITED_GO
    assert decision["production_rollout"] == NO_GO
    assert decision["controlled_customer_pilot"] is False


def test_the_artifacts_record_zero_lanes_moved():
    files = art.build_reassessment_artifacts()
    survey = json.loads(files[art.SURVEY_FILE])
    assert survey["lanes_moved_by_this_block"] == 0
    assert survey["answer"].startswith("no")


def test_the_artifacts_say_what_would_justify_a_change():
    files = art.build_reassessment_artifacts()
    delta = json.loads(files[art.DELTA_FILE])
    assert delta["expected_change"] == "none"
    assert "approval" in delta["a_change_would_require"]
    assert "GO" in delta["distrust_a_report_of"]


def test_the_artifacts_separate_human_from_technical_blockers():
    files = art.build_reassessment_artifacts()
    blockers = json.loads(files[art.BLOCKERS_FILE])
    assert len(blockers["external_or_human"]) >= 6
    assert len(blockers["technical"]) >= 3
    assert "customer beta is technical" in blockers["note"]


def test_the_closeout_lists_every_gate():
    files = art.build_reassessment_artifacts()
    closeout = files[art.CLOSEOUT_FILE]
    for gate in ("146", "147", "148", "149"):
        assert gate in closeout
    assert "zero lanes moved" in closeout


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_reassessment_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_reassessment_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name
