"""Gate 147: the verified-binding approval boundary, and what may not open it.

Five refusals stand between today and `verified_operational_binding`, and any
one of them alone is sufficient:

```text
1  the demo organization is categorically refused
2  the real organization is refused by name
3  AUTHORIZED_REAL_ORGANIZATION_IDS is empty, deliberately
4  no approval object exists
5  customer_auth_live is false
```

Most of what follows proves that nothing substitutes for the evidence: a caller
lying about classification, a label offered as authority, the real organization
smuggled into the injectable authorized set, a demo fixture read as a
verification, a duplicate binding, an unqualified principal.

The permitted branch is kept reachable against a fixture organization that is
neither the demo org nor the real one, because an unreachable permitted branch
makes every refusal above it unfalsifiable.
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
from nativeforge.services import verified_binding_artifact_gate147_service as art
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    DECISION_LAYERS,
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
    build_verified_binding_dry_run_decision,
    dry_run_decision_invariant_failures,
)
from nativeforge.services.verified_operational_binding_approval_checklist_service import (  # noqa: E501
    REFUSAL_AMBIGUOUS,
    REFUSAL_AUTH_NOT_LIVE,
    REFUSAL_AUTHORIZED_LIST,
    REFUSAL_DEMO_ORG,
    REFUSAL_DUPLICATE,
    REFUSAL_NO_APPROVAL,
    REFUSAL_PRINCIPAL,
    REFUSAL_REAL_ORG,
    REFUSED_SHORTCUTS,
    approval_checklist_invariant_failures,
    build_approval_checklist,
)
from tests import session_org_helper as soh

DEMO = DEMO_ORGANIZATION_ID
REAL = REAL_ORGANIZATION_ID
OTHER = "cccccccc-dddd-eeee-ffff-00000000d147"
FIXTURE = "dddddddd-eeee-ffff-0000-111111111147"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

APPROVAL = {
    "organization_id": FIXTURE,
    "authorized_by": "mayhem",
    "authorization_scope": "real_org_binding_activation",
    "environment": "local",
    "recorded_at": "2026-09-11T00:00:00+00:00",
}
PRINCIPAL = {"role": "platform_admin", "authenticated": True, "verified_org": True}
NO_BINDING = {"rows_matched": 0, "blocked_reasons": []}


def _granted(**overrides):
    """Everything satisfied, against a fixture organization that is neither."""
    kwargs = dict(
        organization_id=FIXTURE,
        org_type_in_database="real",
        approval=APPROVAL,
        app_env="local",
        principal=PRINCIPAL,
        customer_auth_live=True,
        authorized_organization_ids=frozenset({FIXTURE}),
        binding_read=NO_BINDING,
    )
    kwargs.update(overrides)
    return kwargs


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/verified-binding"


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
# the lane stays false
# ---------------------------------------------------------------------------


def test_verified_binding_is_false_without_an_approval():
    result = build_approval_checklist(
        organization_id=FIXTURE, org_type_in_database="real"
    )
    assert result["verified_operational_binding"] is False
    assert REFUSAL_NO_APPROVAL in result["blockers"]


def test_the_demo_organization_is_refused_categorically():
    result = build_approval_checklist(
        organization_id=DEMO, org_type_in_database="demo"
    )
    assert result["verified_operational_binding"] is False
    assert REFUSAL_DEMO_ORG in result["blockers"]


def test_the_demo_organization_stays_refused_with_everything_granted():
    """No approval, principal or environment reaches it. The refusal is total."""
    result = build_approval_checklist(
        **_granted(organization_id=DEMO, org_type_in_database="demo")
    )
    assert result["verified_operational_binding"] is False
    assert REFUSAL_DEMO_ORG in result["blockers"]


def test_the_real_organization_is_refused_by_name():
    result = build_approval_checklist(
        organization_id=REAL, org_type_in_database="real"
    )
    assert REFUSAL_REAL_ORG in result["blockers"]
    assert result["verified_operational_binding"] is False


def test_the_real_organization_cannot_be_smuggled_into_the_authorized_set():
    """Gate 137G found the first version of this reaching the real org."""
    result = build_approval_checklist(
        **_granted(
            organization_id=REAL,
            org_type_in_database="real",
            authorized_organization_ids=frozenset({REAL}),
        )
    )
    assert REFUSAL_REAL_ORG in result["blockers"]
    assert REFUSAL_AUTHORIZED_LIST in result["blockers"]
    assert result["verified_operational_binding"] is False


def test_the_demo_organization_cannot_be_smuggled_in_either():
    result = build_approval_checklist(
        **_granted(
            organization_id=DEMO,
            org_type_in_database="demo",
            authorized_organization_ids=frozenset({DEMO}),
        )
    )
    assert result["verified_operational_binding"] is False
    assert REFUSAL_DEMO_ORG in result["blockers"]


def test_customer_auth_live_false_blocks_the_binding():
    result = build_approval_checklist(**_granted(customer_auth_live=False))
    assert REFUSAL_AUTH_NOT_LIVE in result["blockers"]
    assert result["verified_operational_binding"] is False


def test_an_unqualified_principal_blocks_the_binding():
    for principal in (
        None,
        {"role": "grant_lead", "authenticated": True, "verified_org": True},
        {"role": "platform_admin", "authenticated": False, "verified_org": True},
        {"role": "platform_admin", "authenticated": True, "verified_org": False},
    ):
        result = build_approval_checklist(**_granted(principal=principal))
        assert REFUSAL_PRINCIPAL in result["blockers"]
        assert result["verified_operational_binding"] is False


def test_a_duplicate_active_binding_is_refused():
    result = build_approval_checklist(
        **_granted(binding_read={"rows_matched": 2, "blocked_reasons": []})
    )
    assert REFUSAL_DUPLICATE in result["blockers"]
    assert REFUSAL_AMBIGUOUS in result["blockers"]
    assert result["verified_operational_binding"] is False


def test_an_ambiguous_active_binding_is_refused():
    result = build_approval_checklist(
        **_granted(
            binding_read={
                "rows_matched": 1,
                "blocked_reasons": ["active_binding_is_ambiguous"],
            }
        )
    )
    assert REFUSAL_AMBIGUOUS in result["blockers"]
    assert result["verified_operational_binding"] is False


def test_a_malformed_approval_is_refused():
    for approval in ({}, {"organization_id": FIXTURE}, {"authorized_by": "x"}):
        result = build_approval_checklist(**_granted(approval=approval))
        assert result["verified_operational_binding"] is False
        assert REFUSAL_NO_APPROVAL in result["blockers"]


def test_a_scope_that_does_not_cover_production_is_refused():
    result = build_approval_checklist(
        **_granted(
            app_env="production",
            approval={**APPROVAL, "environment": "production"},
        )
    )
    assert result["scope_covers_environment"] is False
    assert result["verified_operational_binding"] is False


# ---------------------------------------------------------------------------
# the permitted branch, kept reachable
# ---------------------------------------------------------------------------


def test_the_permitted_branch_is_reachable():
    """An unreachable permitted branch makes every refusal above it unfalsifiable."""
    result = build_approval_checklist(**_granted())
    assert result["verified_operational_binding"] is True
    assert result["blockers"] == []
    assert result["next_human_action"] is None
    assert approval_checklist_invariant_failures(result) == []


def test_the_permitted_branch_is_a_fixture_organization_not_a_real_one():
    result = build_approval_checklist(**_granted())
    assert result["organization_id"] == FIXTURE
    assert result["is_the_demo_organization"] is False
    assert result["is_the_refused_real_organization"] is False


# ---------------------------------------------------------------------------
# classification comes from the database
# ---------------------------------------------------------------------------


def test_a_caller_cannot_declare_the_demo_org_real():
    result = build_approval_checklist(
        organization_id=DEMO,
        org_type_in_database="demo",
        is_demo=False,
        org_type="real",
    )
    assert result["classification"] == "demo"
    assert result["classification_source"] == "module_constant"
    assert REFUSAL_DEMO_ORG in result["blockers"]


def test_offered_classification_keys_are_refused_by_name():
    result = build_approval_checklist(
        organization_id=DEMO,
        org_type_in_database="demo",
        is_demo=False,
        org_type="real",
    )
    assert result["offered_classification_keys_refused"] == ["is_demo", "org_type"]


def test_offered_authority_keys_are_refused_by_name():
    """Gates 110-113's subject, restated at a new entry point."""
    result = build_approval_checklist(
        organization_id=FIXTURE,
        org_type_in_database="real",
        tenant_id="t-1",
        customer_org_id="c-1",
        organization_profile_id="p-1",
        profile_id="p-2",
    )
    assert result["offered_authority_keys_refused"] == [
        "customer_org_id",
        "organization_profile_id",
        "profile_id",
        "tenant_id",
    ]


def test_an_unknown_organization_classification_is_unknown_not_assumed():
    result = build_approval_checklist(organization_id=OTHER)
    assert result["classification"] == "UNKNOWN"
    assert result["classification_source"] == "unavailable"
    assert result["verified_operational_binding"] is False


def test_verified_operational_binding_is_not_a_parameter():
    signature = inspect.signature(build_approval_checklist)
    assert "verified_operational_binding" not in signature.parameters
    assert "classification" not in signature.parameters
    assert "blockers" not in signature.parameters


# ---------------------------------------------------------------------------
# what cannot stand in for the evidence
# ---------------------------------------------------------------------------


def test_a_demo_fixture_row_does_not_assert_verification():
    result = build_approval_checklist(
        organization_id=DEMO,
        org_type_in_database="demo",
        binding_read={
            "rows_matched": 1,
            "binding_status": "demo_fixture",
            "demo_fixture": True,
            "verified_by_identity_id": None,
            "blocked_reasons": [],
        },
    )
    assert result["existing_binding_asserts_verification"] is False
    assert result["verified_operational_binding"] is False


def test_a_synthetic_provider_subject_is_named_as_refused():
    shortcuts = {entry["shortcut"] for entry in REFUSED_SHORTCUTS}
    assert any("synthetic provider subject" in s for s in shortcuts)


def test_a_fake_identity_or_session_cannot_qualify_a_principal():
    """Both reduce to an unqualified principal, which is a standing refusal."""
    for principal in (
        {"role": "platform_admin", "authenticated": False, "verified_org": False},
        {"role": "", "authenticated": True, "verified_org": True},
    ):
        result = build_approval_checklist(**_granted(principal=principal))
        assert REFUSAL_PRINCIPAL in result["blockers"]


def test_every_refused_shortcut_says_why():
    assert len(REFUSED_SHORTCUTS) >= 8
    for entry in REFUSED_SHORTCUTS:
        assert entry["shortcut"].strip()
        assert entry["refused_because"].strip()


def test_no_environment_variable_can_grant_activation():
    files = art.build_verified_binding_artifacts()
    shape = json.loads(files[art.CHECKLIST_FILE])
    assert shape["environment_variables"]["can_grant"] == []
    assert shape["environment_variables"]["can_revoke"]


# ---------------------------------------------------------------------------
# invariants
# ---------------------------------------------------------------------------


def test_the_invariants_catch_a_forged_verified_binding():
    forged = build_approval_checklist(organization_id=DEMO, org_type_in_database="demo")
    forged["verified_operational_binding"] = True
    failures = approval_checklist_invariant_failures(forged)
    assert "verified_binding_alongside_blockers" in failures
    assert "verified_binding_for_the_demo_organization" in failures
    assert "verified_binding_without_live_customer_auth" in failures


def test_the_invariants_catch_a_demo_org_that_was_not_refused():
    forged = build_approval_checklist(organization_id=DEMO, org_type_in_database="demo")
    forged["blockers"] = [b for b in forged["blockers"] if b != REFUSAL_DEMO_ORG]
    assert "demo_organization_not_refused" in approval_checklist_invariant_failures(
        forged
    )


def test_the_invariants_catch_a_real_org_that_was_not_refused():
    forged = build_approval_checklist(organization_id=REAL, org_type_in_database="real")
    forged["blockers"] = [b for b in forged["blockers"] if b != REFUSAL_REAL_ORG]
    assert "real_organization_not_refused" in approval_checklist_invariant_failures(
        forged
    )


def test_the_module_writes_nothing():
    result = build_approval_checklist(**_granted())
    for flag in (
        "binding_written_by_this_module",
        "approval_granted_by_this_module",
        "real_organization_touched",
        "mutation_path_enabled",
    ):
        assert result[flag] is False


# ---------------------------------------------------------------------------
# the dry-run composite
# ---------------------------------------------------------------------------


def test_the_dry_run_writes_nothing_on_every_branch():
    for kwargs in (
        dict(organization_id=DEMO, org_type_in_database="demo"),
        dict(organization_id=REAL, org_type_in_database="real"),
        _granted(),
    ):
        decision = build_verified_binding_dry_run_decision(**kwargs)
        assert decision["dry_run"] is True
        assert decision["mutation_performed"] is False
        assert decision["rows_written"] == 0
        assert decision["connection_supplied"] is False
        assert decision["real_organization_touched"] is False
        assert dry_run_decision_invariant_failures(decision) == []


def test_the_dry_run_names_blockers():
    decision = build_verified_binding_dry_run_decision(
        organization_id=DEMO, org_type_in_database="demo"
    )
    assert decision["may_attempt_binding"] is False
    assert decision["mutation_enabled"] is False
    assert REFUSAL_DEMO_ORG in decision["blockers"]
    assert decision["next_human_action"]["refusal"] == REFUSAL_DEMO_ORG


def test_the_dry_run_reports_one_name_per_refusal():
    """The first version coined a near-duplicate of Gate 137's own wording.

    The composite unions both layers' blockers, so two names for one refusal
    made a reader count one more problem than exists.
    """
    decision = build_verified_binding_dry_run_decision(
        organization_id=DEMO, org_type_in_database="demo"
    )
    authorized_list_names = [
        name for name in decision["blockers"] if "authorized_real_org_list" in name
    ]
    assert len(authorized_list_names) == 1


def test_the_dry_run_consults_every_layer():
    decision = build_verified_binding_dry_run_decision(
        organization_id=DEMO, org_type_in_database="demo"
    )
    assert set(decision["decision_layers"]) == set(DECISION_LAYERS)


def test_the_dry_run_permitted_branch_is_reachable_and_still_writes_nothing():
    decision = build_verified_binding_dry_run_decision(**_granted())
    assert decision["may_attempt_binding"] is True
    assert decision["mutation_enabled"] is True
    assert decision["mutation_performed"] is False
    assert decision["rows_written"] == 0


def test_the_dry_run_invariants_catch_a_mutation():
    decision = build_verified_binding_dry_run_decision(**_granted())
    decision["mutation_performed"] = True
    decision["rows_written"] = 1
    failures = dry_run_decision_invariant_failures(decision)
    assert "dry_run_performed_a_mutation" in failures
    assert "dry_run_wrote_rows" in failures


def test_the_dry_run_invariants_catch_mutation_without_a_clear_decision():
    decision = build_verified_binding_dry_run_decision(
        organization_id=DEMO, org_type_in_database="demo"
    )
    decision["mutation_enabled"] = True
    failures = dry_run_decision_invariant_failures(decision)
    assert "mutation_enabled_without_a_clear_decision" in failures


# ---------------------------------------------------------------------------
# nothing leaks
# ---------------------------------------------------------------------------


def test_no_forbidden_shape_in_any_checklist():
    for kwargs in (
        dict(organization_id=DEMO, org_type_in_database="demo"),
        dict(organization_id=REAL, org_type_in_database="real"),
        _granted(),
    ):
        payload = build_approval_checklist(**kwargs)
        assert payload["leaked_shapes"] == []
        body = json.dumps(payload, default=str)
        assert not ADDRESS_SHAPE.search(body)
        assert not SUBJECT_SHAPE.search(body)


def test_the_leak_scan_actually_fires():
    from nativeforge.services.verified_operational_binding_approval_checklist_service import (  # noqa: E501
        _leaked_shapes,
    )

    assert _leaked_shapes({"x": "somebody@example.org"}) == ["email_address"]
    assert _leaked_shapes({"x": "112233445566778899001"}) == ["provider_subject"]
    assert _leaked_shapes({"x": "nothing"}) == []


def test_a_leaked_checklist_fails_its_invariants():
    payload = build_approval_checklist(
        organization_id=DEMO, org_type_in_database="demo"
    )
    payload["leaked_shapes"] = ["provider_subject"]
    assert "leaked:provider_subject" in approval_checklist_invariant_failures(payload)


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["readiness", "blockers", "checklist"])
def test_every_get_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_the_dry_run_route_refuses_an_unauthenticated_caller(client):
    assert client.post(f"{_base()}/dry-run-decision", json={}).status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/readiness",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_the_lane_false(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    data = body.get("data", body)
    assert data["verified_operational_binding"] is False
    assert data["demo_organization_can_never_satisfy_this"] is True
    assert data["mutation_path_enabled"] is False
    assert data["production_rollout"] is False


def test_the_blockers_route_names_an_owner_per_blocker(client, demo_session):
    body = client.get(f"{_base()}/blockers", headers=demo_session).json()
    data = body.get("data", body)
    assert data["blockers"]
    for name in data["blockers"]:
        assert data["blocker_owners"][name]["owner"]
        assert data["blocker_owners"][name]["kind"]


def test_the_dry_run_route_records_nothing(client, demo_session):
    response = client.post(
        f"{_base()}/dry-run-decision",
        headers=demo_session,
        json={"approval": APPROVAL},
    )
    data = response.json().get("data", response.json())
    assert data["approval_recorded"] is False
    assert data["binding_written"] is False
    assert data["mutation_performed"] is False
    assert data["rows_written"] == 0
    assert data["may_attempt_binding"] is False


def test_the_dry_run_route_cannot_be_given_a_principal(client, demo_session):
    """A caller naming their own role would be choosing their own authority."""
    response = client.post(
        f"{_base()}/dry-run-decision",
        headers=demo_session,
        json={
            "approval": APPROVAL,
            "principal": {
                "role": "platform_admin",
                "authenticated": True,
                "verified_org": True,
            },
        },
    )
    data = response.json().get("data", response.json())
    assert data["verifier_principal_qualified"] is False
    assert data["may_attempt_binding"] is False


def test_no_route_leaks_a_shape(client, demo_session):
    for path in ("readiness", "blockers", "checklist"):
        raw = client.get(f"{_base()}/{path}", headers=demo_session).text
        assert not ADDRESS_SHAPE.search(raw)
        assert not SUBJECT_SHAPE.search(raw)
        assert "nf_session=" not in raw


def test_another_organization_is_refused(client, demo_session):
    response = client.get(f"{_base(OTHER)}/readiness", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_no_real_organization_route_was_built():
    from nativeforge.api import verified_binding_readiness_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    source = Path(routes.__file__).read_text(encoding="utf-8")
    assert "/v1/nf/real" not in source


def test_the_only_non_get_route_is_the_dry_run():
    from nativeforge.api import verified_binding_readiness_routes as routes

    non_get = [
        getattr(route, "path", "")
        for route in routes.router.routes
        if set(getattr(route, "methods", set())) - {"GET", "HEAD", "OPTIONS"}
    ]
    assert len(non_get) == 1
    assert non_get[0].endswith("/dry-run-decision")


# ---------------------------------------------------------------------------
# cockpit
# ---------------------------------------------------------------------------


def test_the_cockpit_lane_names_the_whole_refusal_stack():
    """It named one refusal where five stand, which read as one decision away."""
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    lane = next(
        entry
        for entry in summary["lanes"]
        if entry["lane"] == "verified_operational_binding"
    )
    assert lane["value"] is False
    assert len(lane["blockers"]) >= 5
    assert REFUSAL_DEMO_ORG in lane["blockers"]


def test_the_cockpit_never_reports_verified_binding_operational():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    assert summary["verified_operational_binding"] is False
    lane = next(
        entry
        for entry in summary["lanes"]
        if entry["lane"] == "verified_operational_binding"
    )
    assert lane["status"] != "OPERATIONAL"


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_verified_binding_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.verified_binding_artifact_invariant_failures(result) == []


def test_the_artifact_is_deterministic():
    built = art.build_verified_binding_artifacts()
    assert built == art.build_verified_binding_artifacts()


def test_the_artifact_reads_no_database():
    assert inspect.signature(art.build_verified_binding_artifacts).parameters == {}


def test_the_artifacts_record_every_refusal_with_an_owner():
    files = art.build_verified_binding_artifacts()
    matrix = json.loads(files[art.REFUSAL_FILE])
    assert len(matrix["refusals"]) >= 8
    for entry in matrix["refusals"]:
        assert entry["owner"]
        assert entry["kind"]
        assert entry["clears_by"]


def test_the_artifacts_record_what_never_clears():
    files = art.build_verified_binding_artifacts()
    matrix = json.loads(files[art.REFUSAL_FILE])
    assert REFUSAL_DEMO_ORG in matrix["never_clears"]


def test_the_artifacts_record_the_lane_as_false():
    files = art.build_verified_binding_artifacts()
    for name in (art.SURVEY_FILE, art.BLOCKERS_FILE, art.COCKPIT_FILE):
        payload = json.loads(files[name])
        key = "verified_operational_binding" if "value" not in payload else "value"
        assert payload.get(key) is False


def test_the_artifacts_record_what_stays_false():
    files = art.build_verified_binding_artifacts()
    blockers = json.loads(files[art.BLOCKERS_FILE])
    for name in (
        "verified_operational_binding",
        "customer_auth_live",
        "controlled_customer_pilot",
        "production_rollout",
    ):
        assert name in blockers["stays_false_after_this_gate"]


def test_the_artifacts_record_the_dry_run_writes_nothing():
    files = art.build_verified_binding_artifacts()
    dry = json.loads(files[art.DRY_RUN_FILE])
    assert dry["mutation_performed"] is False
    assert dry["rows_written"] == 0
    assert dry["takes_no_connection"] is True
    assert dry["permitted_branch_still_writes_nothing"] is True


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_verified_binding_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_verified_binding_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# the live database
# ---------------------------------------------------------------------------


def test_the_real_organization_has_no_binding_row():
    """A regression that wrote one would show up here. Read-only, counts only."""
    import sqlalchemy as sa

    from nativeforge.lib.settings import get_settings

    try:
        engine = sa.create_engine(get_settings().database_url)
        with engine.connect() as connection:
            count = connection.execute(
                sa.text(
                    "SELECT count(*) FROM nf_tenant_customer_org_bindings "
                    "WHERE organization_id = :i"
                ),
                {"i": REAL.replace("-", "")},
            ).scalar()
    except Exception:  # noqa: BLE001
        pytest.skip("no database reachable in this environment")

    assert count == 0
