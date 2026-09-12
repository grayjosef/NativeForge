"""Gate 149: the pilot activation package, and why the pilot stays off.

`controlled_customer_pilot` is not a value that is false. It is not a value at
all: no table records a pilot approval, no environment flag exists, and no code
path sets it true. This gate states what must be true and builds no switch.

Most of what follows proves two things. That every prerequisite is required —
none of the nine can be skipped. And that a pilot activation may never carry
another capability with it: email, live source monitoring, object storage and
production are refused as a bundle even when every prerequisite is satisfied.
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
    controlled_customer_pilot_artifact_gate149_service as art,
)
from nativeforge.services.controlled_customer_pilot_activation_boundary_service import (  # noqa: E501
    ACTIVATION_APPROVAL_FIELDS,
    BUNDLE_TARGETS,
    UNSAFE_BUNDLE_KEYS,
    activation_decision_invariant_failures,
    build_pilot_activation_decision,
)
from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    GO,
    LIMITED_GO,
    NO_GO,
    PREREQUISITE_OWNERS,
    PREREQUISITES,
    SEPARATELY_GATED,
    WOULD_NOT_UNLOCK,
    WOULD_UNLOCK,
    build_pilot_activation_checklist,
    checklist_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d149"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

OWNER = {"support_contact": "the operator", "rollback_owner": "the owner"}
APPROVAL = {
    "organization_id": "eeeeeeee-ffff-0000-1111-222222222149",
    "approved_by": "test_fixture",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "pilot_scope": "one organization",
    "support_contact": "the operator",
    "rollback_owner": "the owner",
    "expires_at": "2027-01-01T00:00:00+00:00",
}

SCOPES = {"internal_demo_beta": GO, "controlled_customer_beta": LIMITED_GO}


def _all_satisfied(**overrides):
    kwargs = dict(
        real_customer_organization_exists=True,
        second_person_event_complete=True,
        customer_auth_live=True,
        verified_operational_binding=True,
        consent_boundary_documented=True,
        customer_beta_scope_approved=True,
        customer_data_write_guard_ready=True,
        support_and_rollback_owner=OWNER,
        pilot_scope_limitations_documented=True,
        **SCOPES,
    )
    kwargs.update(overrides)
    return kwargs


#: Maps each prerequisite to the keyword that satisfies it, so a test can
#: remove exactly one and assert the pilot stays false.
_PREREQ_KWARG = {
    "real_customer_organization_exists": ("real_customer_organization_exists", False),
    "second_person_event_complete": ("second_person_event_complete", False),
    "customer_auth_live": ("customer_auth_live", False),
    "verified_operational_binding": ("verified_operational_binding", False),
    "consent_boundary_documented": ("consent_boundary_documented", False),
    "customer_beta_scope_approved": ("customer_beta_scope_approved", False),
    "customer_data_write_guard_ready": ("customer_data_write_guard_ready", False),
    "support_and_rollback_owner_named": ("support_and_rollback_owner", None),
    "pilot_scope_limitations_documented": (
        "pilot_scope_limitations_documented",
        False,
    ),
}


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/pilot-activation"


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
# the pilot stays off
# ---------------------------------------------------------------------------


def test_the_pilot_is_false_today():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert checklist["controlled_customer_pilot"] is False
    assert checklist_invariant_failures(checklist) == []


def test_the_package_is_ready_while_the_pilot_is_not():
    """activation_package_ready is not controlled_customer_pilot."""
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert checklist["activation_package_ready"] is True
    assert checklist["controlled_customer_pilot"] is False
    assert checklist["package_ready_is_not_an_activated_pilot"]


def test_production_is_always_no_go():
    for kwargs in (
        dict(customer_data_write_guard_ready=True, **SCOPES),
        _all_satisfied(),
    ):
        checklist = build_pilot_activation_checklist(**kwargs)
        assert checklist["production_rollout"] == NO_GO
        assert checklist["production_is_never_computed"] is True


def test_internal_demo_and_customer_beta_are_reported_not_computed():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert checklist["internal_demo_beta"] == GO
    assert checklist["controlled_customer_beta"] == LIMITED_GO


def test_controlled_customer_pilot_is_not_a_parameter():
    signature = inspect.signature(build_pilot_activation_checklist)
    assert "controlled_customer_pilot" not in signature.parameters
    assert "activation_package_ready" not in signature.parameters


# ---------------------------------------------------------------------------
# every prerequisite is required
# ---------------------------------------------------------------------------


def test_nine_prerequisites_are_declared():
    assert len(PREREQUISITES) == 9
    for name in PREREQUISITES:
        owner = PREREQUISITE_OWNERS[name]
        assert owner["kind"]
        assert owner["owner"]
        assert owner["gate"]
        assert owner["satisfied_by"]


@pytest.mark.parametrize("prerequisite", sorted(_PREREQ_KWARG))
def test_removing_any_single_prerequisite_blocks_the_pilot(prerequisite):
    keyword, value = _PREREQ_KWARG[prerequisite]
    checklist = build_pilot_activation_checklist(**_all_satisfied(**{keyword: value}))
    assert checklist["controlled_customer_pilot"] is False
    assert prerequisite in checklist["prerequisites_missing"]
    assert checklist_invariant_failures(checklist) == []


def test_the_missing_real_customer_org_is_the_front_of_the_queue():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert (
        checklist["next_human_action"]["prerequisite"]
        == "real_customer_organization_exists"
    )
    assert checklist["next_human_action"]["owner"] == "nobody in this repository"


def test_a_partial_support_owner_does_not_count():
    for owner in (None, {}, {"support_contact": "x"}, {"rollback_owner": "y"}):
        checklist = build_pilot_activation_checklist(
            **_all_satisfied(support_and_rollback_owner=owner)
        )
        assert checklist["controlled_customer_pilot"] is False
        assert "support_and_rollback_owner_named" in checklist["prerequisites_missing"]


def test_the_permitted_branch_is_reachable():
    """An unreachable permitted branch makes every refusal above it unfalsifiable."""
    checklist = build_pilot_activation_checklist(**_all_satisfied())
    assert checklist["controlled_customer_pilot"] is True
    assert checklist["prerequisites_missing"] == []
    assert checklist["next_human_action"] is None
    assert checklist_invariant_failures(checklist) == []


def test_the_write_guard_is_the_one_already_satisfied():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert checklist["prerequisites_satisfied"]["customer_data_write_guard_ready"]
    assert checklist["prerequisites_satisfied_count"] == 1


# ---------------------------------------------------------------------------
# what is not a prerequisite
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capability", sorted(SEPARATELY_GATED))
def test_separately_gated_capabilities_are_not_prerequisites(capability):
    assert capability not in PREREQUISITES
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert capability in checklist["separately_gated"]
    assert capability not in checklist["prerequisites_missing"]


def test_every_separately_gated_capability_says_why():
    for name, entry in SEPARATELY_GATED.items():
        assert entry["why_separate"].strip(), name
        assert entry["gate"].strip(), name


def test_the_invariants_catch_a_capability_listed_as_a_prerequisite():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    checklist["prerequisites"] = [*checklist["prerequisites"], "email_delivery"]
    failures = checklist_invariant_failures(checklist)
    marker = "separately_gated_capability_listed_as_prerequisite"
    assert any(marker in failure for failure in failures)


def test_the_pilot_would_and_would_not_unlock_are_both_stated():
    checklist = build_pilot_activation_checklist(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert list(checklist["would_unlock"]) == list(WOULD_UNLOCK)
    assert list(checklist["would_not_unlock"]) == list(WOULD_NOT_UNLOCK)
    joined = " ".join(checklist["would_not_unlock"]).lower()
    assert "email" in joined
    assert "source" in joined
    assert "production" in joined


# ---------------------------------------------------------------------------
# the activation boundary
# ---------------------------------------------------------------------------


def test_the_boundary_activates_nothing_on_any_branch():
    for kwargs in (
        dict(customer_data_write_guard_ready=True, **SCOPES),
        _all_satisfied(),
        _all_satisfied(activation_approval=APPROVAL),
    ):
        decision = build_pilot_activation_decision(**kwargs)
        assert decision["dry_run"] is True
        assert decision["may_activate"] is False
        assert decision["mutation_enabled"] is False
        assert decision["mutation_performed"] is False
        assert decision["rows_written"] == 0
        assert decision["connection_supplied"] is False
        assert decision["real_organization_touched"] is False
        assert activation_decision_invariant_failures(decision) == []


def test_may_activate_is_false_even_with_everything_granted():
    """There is nothing to act on it: no table, no flag, no code path."""
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL)
    )
    assert decision["may_activate"] is False
    assert decision["activation_mechanism_exists"] is False
    assert decision["why_may_activate_is_always_false"]


def test_prerequisites_would_permit_is_the_question_worth_asking():
    blocked = build_pilot_activation_decision(
        customer_data_write_guard_ready=True, **SCOPES
    )
    assert blocked["prerequisites_would_permit"] is False

    permitted = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL)
    )
    assert permitted["prerequisites_would_permit"] is True


def test_an_activation_without_an_approval_is_refused():
    decision = build_pilot_activation_decision(**_all_satisfied())
    assert decision["prerequisites_would_permit"] is False
    assert "no_pilot_activation_approval_supplied" in decision["blockers"]
    assert "pilot_activation_approval" in decision["approvals_required"]


def test_a_partial_activation_approval_is_refused():
    for approval in ({}, {"organization_id": "x"}, {"approved_by": "y"}):
        decision = build_pilot_activation_decision(
            **_all_satisfied(activation_approval=approval)
        )
        assert decision["prerequisites_would_permit"] is False


def test_the_approval_shape_is_declared():
    assert len(ACTIVATION_APPROVAL_FIELDS) >= 7
    for field in ("support_contact", "rollback_owner", "pilot_scope", "expires_at"):
        assert field in ACTIVATION_APPROVAL_FIELDS


# ---------------------------------------------------------------------------
# bundling is refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(UNSAFE_BUNDLE_KEYS))
def test_no_capability_can_be_bundled_with_a_pilot(key):
    """Refused even when every prerequisite and the approval are satisfied."""
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL), **{key: True}
    )
    assert decision["prerequisites_would_permit"] is False
    assert key in decision["unsafe_bundled_requests"]
    assert BUNDLE_TARGETS[key] in decision["unsafe_bundled_targets"]
    assert "activation_request_bundled_other_capabilities" in decision["blockers"]


def test_bundling_email_is_refused():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL), activate_email=True
    )
    assert "email_delivery" in decision["unsafe_bundled_targets"]
    assert decision["prerequisites_would_permit"] is False


def test_bundling_source_monitoring_is_refused():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL),
        activate_source_monitoring=True,
    )
    assert "source_monitoring_live" in decision["unsafe_bundled_targets"]
    assert decision["prerequisites_would_permit"] is False


def test_bundling_object_storage_is_refused():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL),
        activate_object_storage=True,
    )
    assert "object_store_configured" in decision["unsafe_bundled_targets"]
    assert decision["prerequisites_would_permit"] is False


def test_bundling_production_is_refused_by_its_own_name():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL), go_live=True
    )
    assert "production_requested_alongside_a_pilot" in decision["blockers"]
    assert decision["production_rollout"] == NO_GO


def test_every_bundled_request_names_its_target():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL),
        activate_email=True,
        source_monitoring_live=True,
    )
    assert len(decision["unsafe_bundled_targets"]) == 2
    assert activation_decision_invariant_failures(decision) == []


def test_the_invariants_catch_a_bundled_request_that_was_permitted():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL), activate_email=True
    )
    decision["prerequisites_would_permit"] = True
    assert "would_permit_a_bundled_request" in activation_decision_invariant_failures(
        decision
    )


def test_the_invariants_catch_a_mutation():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL)
    )
    decision["mutation_performed"] = True
    decision["rows_written"] = 1
    failures = activation_decision_invariant_failures(decision)
    assert "dry_run_performed_a_mutation" in failures
    assert "dry_run_wrote_rows" in failures


def test_the_invariants_catch_a_forged_may_activate():
    decision = build_pilot_activation_decision(
        **_all_satisfied(activation_approval=APPROVAL)
    )
    decision["may_activate"] = True
    assert (
        "may_activate_became_true_with_no_mechanism_to_act_on_it"
        in activation_decision_invariant_failures(decision)
    )


# ---------------------------------------------------------------------------
# nothing leaks
# ---------------------------------------------------------------------------


def test_no_forbidden_shape_in_any_decision():
    for kwargs in (
        dict(customer_data_write_guard_ready=True, **SCOPES),
        _all_satisfied(activation_approval=APPROVAL),
    ):
        decision = build_pilot_activation_decision(**kwargs)
        assert decision["leaked_shapes"] == []
        body = json.dumps(decision, default=str)
        assert not ADDRESS_SHAPE.search(body)
        assert not SUBJECT_SHAPE.search(body)


def test_the_leak_scan_actually_fires():
    from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
        _leaked_shapes,
    )

    assert _leaked_shapes({"x": "somebody@example.org"}) == ["email_address"]
    assert _leaked_shapes({"x": "112233445566778899001"}) == ["provider_subject"]
    assert _leaked_shapes({"x": "nothing"}) == []


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["checklist", "blockers", "unsafe-bundled-requests"]
)
def test_every_get_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_the_dry_run_route_refuses_an_unauthenticated_caller(client):
    assert client.post(f"{_base()}/dry-run-decision", json={}).status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/checklist",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_checklist_route_reports_the_pilot_false(client, demo_session):
    body = client.get(f"{_base()}/checklist", headers=demo_session).json()
    data = body.get("data", body)
    assert data["controlled_customer_pilot"] is False
    assert data["activation_package_ready"] is True
    assert data["production_rollout"] == NO_GO
    assert data["activation_mechanism_exists"] is False
    assert data["prerequisites_missing"]


def test_the_blockers_route_names_an_owner_per_prerequisite(client, demo_session):
    body = client.get(f"{_base()}/blockers", headers=demo_session).json()
    data = body.get("data", body)
    assert data["prerequisites_missing"]
    for name in data["prerequisites_missing"]:
        assert data["prerequisite_owners"][name]["owner"]
    assert data["controlled_customer_pilot"] is False


def test_the_bundled_route_lists_every_key(client, demo_session):
    body = client.get(
        f"{_base()}/unsafe-bundled-requests", headers=demo_session
    ).json()
    data = body.get("data", body)
    assert sorted(data["unsafe_bundle_keys"]) == sorted(UNSAFE_BUNDLE_KEYS)
    assert data["refused_even_when_prerequisites_are_met"] is True


def test_the_dry_run_route_activates_nothing(client, demo_session):
    response = client.post(
        f"{_base()}/dry-run-decision",
        headers=demo_session,
        json={"activation_approval": APPROVAL},
    )
    data = response.json().get("data", response.json())
    assert data["pilot_activated"] is False
    assert data["approval_recorded"] is False
    assert data["mutation_performed"] is False
    assert data["rows_written"] == 0
    assert data["may_activate"] is False


def test_the_dry_run_route_refuses_a_bundled_request(client, demo_session):
    response = client.post(
        f"{_base()}/dry-run-decision",
        headers=demo_session,
        json={"activation_approval": APPROVAL, "activate_email": True},
    )
    data = response.json().get("data", response.json())
    assert "email_delivery" in data["unsafe_bundled_targets"]
    assert data["prerequisites_would_permit"] is False


def test_the_dry_run_route_ignores_caller_supplied_prerequisites(
    client, demo_session
):
    """A caller supplying customer_auth_live would be supplying the answer."""
    response = client.post(
        f"{_base()}/dry-run-decision",
        headers=demo_session,
        json={
            "activation_approval": APPROVAL,
            "customer_auth_live": True,
            "verified_operational_binding": True,
            "real_customer_organization_exists": True,
            "consent_boundary_documented": True,
        },
    )
    data = response.json().get("data", response.json())
    assert data["prerequisites_would_permit"] is False
    assert "customer_auth_live" in data["prerequisites_missing"]


def test_no_route_leaks_a_shape(client, demo_session):
    for path in ("checklist", "blockers", "unsafe-bundled-requests"):
        raw = client.get(f"{_base()}/{path}", headers=demo_session).text
        assert not ADDRESS_SHAPE.search(raw)
        assert not SUBJECT_SHAPE.search(raw)
        assert "nf_session=" not in raw


def test_another_organization_is_refused(client, demo_session):
    response = client.get(f"{_base(OTHER)}/checklist", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_no_real_organization_route_was_built():
    from nativeforge.api import controlled_customer_pilot_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    assert "/v1/nf/real" not in Path(routes.__file__).read_text(encoding="utf-8")


def test_no_route_anywhere_sets_the_pilot_true():
    """Every occurrence in api/ must be a constant False."""
    api = REPO_ROOT / "src" / "nativeforge" / "api"
    for path in api.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if "controlled_customer_pilot" not in stripped:
                continue
            if stripped.startswith("#"):
                continue
            assert "True" not in stripped, f"{path.name}: {stripped}"


# ---------------------------------------------------------------------------
# cockpit
# ---------------------------------------------------------------------------


def test_the_cockpit_does_not_claim_the_pilot_is_active():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    assert summary["controlled_customer_pilot"] is False
    lane = next(
        entry
        for entry in summary["lanes"]
        if entry["lane"] == "controlled_customer_pilot"
    )
    assert lane["value"] is False
    assert lane["status"] != "operational"


def test_the_cockpit_lane_names_the_missing_mechanism():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    lane = next(
        entry
        for entry in summary["lanes"]
        if entry["lane"] == "controlled_customer_pilot"
    )
    assert "no_activation_mechanism_exists" in lane["blockers"]
    assert "real_customer_organization_missing" in lane["blockers"]


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_pilot_activation_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.pilot_activation_artifact_invariant_failures(result) == []


def test_the_artifact_is_deterministic():
    built = art.build_pilot_activation_artifacts()
    assert built == art.build_pilot_activation_artifacts()


def test_the_artifact_reads_no_database():
    builder = art.build_pilot_activation_artifacts
    assert inspect.signature(builder).parameters == {}


def test_the_artifacts_record_the_missing_mechanism():
    files = art.build_pilot_activation_artifacts()
    survey = json.loads(files[art.SURVEY_FILE])
    assert survey["no_table_records_a_pilot_approval"] is True
    assert survey["no_environment_flag_exists"] is True
    assert survey["no_route_can_activate_a_pilot"] is True


def test_the_artifacts_record_every_prerequisite():
    files = art.build_pilot_activation_artifacts()
    checklist = json.loads(files[art.CHECKLIST_FILE])
    assert [entry["prerequisite"] for entry in checklist["prerequisites"]] == list(
        PREREQUISITES
    )


def test_the_artifacts_record_the_bundled_refusals():
    files = art.build_pilot_activation_artifacts()
    bundled = json.loads(files[art.BUNDLED_FILE])
    assert sorted(bundled["unsafe_bundle_keys"]) == sorted(UNSAFE_BUNDLE_KEYS)
    assert bundled["refused_even_when_every_prerequisite_is_met"] is True


def test_the_artifacts_record_what_stays_false():
    files = art.build_pilot_activation_artifacts()
    readiness = json.loads(files[art.READINESS_FILE])
    for name in (
        "controlled_customer_pilot",
        "production_rollout",
        "email_delivery",
        "source_monitoring_live",
        "object_store_configured",
    ):
        assert name in readiness["stays_false_after_this_gate"]
    assert readiness["rows_written"] == 0


def test_no_artifact_claims_the_pilot_is_active():
    files = art.build_pilot_activation_artifacts()
    cockpit = json.loads(files[art.COCKPIT_FILE])
    assert cockpit["pilot_active"] is False
    assert cockpit["production_ready"] is False
    assert cockpit["email_included"] is False
    assert cockpit["source_monitoring_included"] is False
    assert cockpit["object_storage_included"] is False


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_pilot_activation_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_pilot_activation_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# nothing anywhere activates a pilot
# ---------------------------------------------------------------------------


def test_no_migration_creates_a_pilot_approval_table():
    versions = REPO_ROOT / "alembic" / "versions"
    for path in versions.glob("*.py"):
        body = path.read_text(encoding="utf-8").lower()
        assert "pilot_approval" not in body, path.name
        assert "controlled_customer_pilot" not in body, path.name


def test_no_environment_flag_activates_a_pilot():
    settings = REPO_ROOT / "src" / "nativeforge" / "lib" / "settings.py"
    body = settings.read_text(encoding="utf-8").lower()
    assert "pilot" not in body
