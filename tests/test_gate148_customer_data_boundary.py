"""Gate 148: the consent and customer data boundary, and what is not consent.

Every post-award repository gates a production write on `customer_auth_live`
and `verified_operational_binding` and nothing else. Both are identity facts.
On the day Gates 146 and 147 make them true, a production customer write becomes
permitted with no consent recorded anywhere — so the boundary has to exist
before those lanes turn.

Most of what follows proves that nothing substitutes for a consent record: a
login, a membership, an accepted invite, an operator's note, a capability being
activated, or a data class nobody classified.
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
    customer_data_boundary_artifact_gate148_service as art,
)
from nativeforge.services.customer_beta_consent_boundary_service import (
    AUTH_NOT_LIVE,
    BETA_SCOPE_APPROVAL_FIELDS,
    BINDING_ABSENT,
    CLASS_NEVER_STORED,
    CLASS_UNKNOWN,
    CONSENT_ABSENT,
    CONSENT_RECORD_FIELDS,
    DEMO_ORG_NOT_A_CUSTOMER,
    INFERRED_CONSENT_KEYS,
    INFERRED_CONSENT_REFUSED,
    NO_REAL_CUSTOMER_ORG,
    REAL_ORG_REFUSED,
    SCOPE_ABSENT,
    build_consent_boundary,
    consent_boundary_invariant_failures,
)
from nativeforge.services.customer_data_classification_service import (
    CUSTOMER_DATA_CLASSES,
    DATA_CLASSES,
    NEVER_STORED_CLASSES,
    NOT_CONSENT,
    PRE_CONSENT_CLASSES,
    UNKNOWN,
    build_data_class_catalogue,
    classification_invariant_failures,
    classify,
)
from nativeforge.services.customer_data_write_guard_service import (
    CONTROLLED_SCOPE,
    evaluate_write,
    write_guard_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d148"
CUSTOMER = "eeeeeeee-ffff-0000-1111-222222222148"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

CONSENT = {
    "organization_id": CUSTOMER,
    "agreed_by": "a tenant signatory",
    "agreed_at": "2026-01-01T00:00:00+00:00",
    "what_is_collected": "awarded grants",
    "what_is_retained": "the same",
    "retention_period": "award period",
    "what_is_exported": "nothing",
    "how_it_is_deleted": "on request",
    "withdrawal_method": "written notice",
    "document_version": "v1",
}
SCOPE = {
    "organization_id": CUSTOMER,
    "approved_by": "test_fixture",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "scope": "controlled_customer_beta",
    "data_classes_permitted": ["customer_operational_data"],
    "expires_at": "2027-01-01T00:00:00+00:00",
}


def _granted(**overrides):
    """Everything satisfied, for a fixture customer organization."""
    kwargs = dict(
        organization_id=CUSTOMER,
        org_type_in_database="real",
        data_class="customer_operational_data",
        scope="controlled_customer_beta",
        route_context="tests",
        consent_record=CONSENT,
        beta_scope_approval=SCOPE,
        customer_auth_live=True,
        verified_operational_binding=True,
    )
    kwargs.update(overrides)
    return kwargs


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/data-boundary"


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
# the data classes
# ---------------------------------------------------------------------------


def test_nine_data_classes_are_defined():
    assert len(DATA_CLASSES) == 9
    catalogue = build_data_class_catalogue()
    assert set(catalogue["data_classes"]) == set(DATA_CLASSES)
    for name in DATA_CLASSES:
        assert catalogue["definitions"][name]["means"].strip()


def test_every_class_has_a_non_example():
    """The non-examples are where a misclassification actually happens."""
    catalogue = build_data_class_catalogue()
    for name in DATA_CLASSES:
        if name == UNKNOWN:
            continue
        assert catalogue["definitions"][name]["not_examples"], name


def test_an_unclassified_class_is_unknown_and_blocked():
    result = classify(field_name="a_field_nobody_declared")
    assert result["data_class"] == UNKNOWN
    assert result["is_customer_data"] is True
    assert result["is_pre_consent_safe"] is False


def test_nothing_supplied_is_unknown_not_safe():
    result = classify()
    assert result["data_class"] == UNKNOWN
    assert result["is_pre_consent_safe"] is False


def test_a_fixture_row_is_never_customer_data():
    for kwargs in ({"fact_status": "demo_fixture"}, {"is_demo": True}):
        result = classify(**kwargs)
        assert result["data_class"] == "demo_fixture"
        assert result["is_customer_data"] is False
        assert classification_invariant_failures(result) == []


def test_tenant_supplied_is_customer_operational_data():
    result = classify(fact_status="tenant_supplied")
    assert result["data_class"] == "customer_operational_data"
    assert result["is_customer_data"] is True


def test_a_caller_cannot_declare_customer_data_a_fixture():
    result = classify(declared_class="demo_fixture", fact_status="tenant_supplied")
    assert result["data_class"] == "customer_operational_data"
    assert "declared_demo_fixture_without_the_row_agreeing" in result["reasons"]


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("recipient_email", "customer_contact_or_recipient"),
        ("contact_address", "customer_contact_or_recipient"),
        ("document_body", "customer_document_body"),
        ("attachment_bytes", "customer_document_body"),
        ("tribe_name", "customer_identifying_data"),
        ("applicant_legal_name", "customer_identifying_data"),
        ("provider_subject", "provider_identity_secret_or_subject"),
        ("session_token", "provider_identity_secret_or_subject"),
    ],
)
def test_field_names_classify_by_token_not_substring(field, expected):
    """`\\bemail\\b` never matches in `recipient_email`: `_` is a word character.

    The first version used word boundaries and therefore matched nothing at all
    on every underscore-separated field name in this codebase, which is all of
    them - a guard that silently never fired.
    """
    assert classify(field_name=field)["data_class"] == expected


@pytest.mark.parametrize(
    "field",
    ["recipient_fingerprint", "recipient_domain", "email_digest", "organization_id"],
)
def test_the_derived_safe_half_is_not_the_value(field):
    """Gate 142 built the delivery table around exactly this distinction."""
    result = classify(field_name=field)
    assert result["is_customer_data"] is False
    assert result["is_pre_consent_safe"] is True


# ---------------------------------------------------------------------------
# consent, and what is not consent
# ---------------------------------------------------------------------------


def test_no_consent_boundary_is_documented():
    decision = build_consent_boundary(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="customer_operational_data",
    )
    assert decision["consent_boundary_documented"] is False
    assert CONSENT_ABSENT in decision["blockers"]


def test_no_customer_beta_scope_is_approved():
    decision = build_consent_boundary(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="customer_operational_data",
    )
    assert decision["customer_beta_scope_approved"] is False
    assert SCOPE_ABSENT in decision["blockers"]


@pytest.mark.parametrize("key", INFERRED_CONSENT_KEYS)
def test_no_single_signal_is_consent(key):
    decision = build_consent_boundary(
        organization_id=CUSTOMER,
        org_type_in_database="real",
        data_class="customer_operational_data",
        **{key: True},
    )
    assert INFERRED_CONSENT_REFUSED in decision["blockers"]
    assert decision["consent_boundary_documented"] is False
    assert key in decision["inferred_consent_keys_refused"]


def test_login_membership_and_invite_are_each_named_as_not_consent():
    looks_like = {entry["looks_like_consent"] for entry in NOT_CONSENT}
    assert any("login" in s for s in looks_like)
    assert any("membership" in s for s in looks_like)
    assert any("invite" in s for s in looks_like)
    assert any("verbal" in s or "note" in s for s in looks_like)
    for entry in NOT_CONSENT:
        assert entry["actually_says"].strip()
        assert entry["why_not"].strip()


def test_a_partial_consent_record_is_no_record():
    for record in ({}, {"organization_id": CUSTOMER}, {"agreed_by": "x"}):
        decision = build_consent_boundary(
            organization_id=CUSTOMER,
            org_type_in_database="real",
            data_class="customer_operational_data",
            consent_record=record,
        )
        assert decision["consent_boundary_documented"] is False
        assert CONSENT_ABSENT in decision["blockers"]


def test_a_complete_consent_record_is_recognised():
    """The permitted branch has to be reachable or the refusals are unfalsifiable."""
    decision = build_consent_boundary(
        organization_id=CUSTOMER,
        org_type_in_database="real",
        data_class="customer_operational_data",
        consent_record=CONSENT,
        beta_scope_approval=SCOPE,
        customer_auth_live=True,
        verified_operational_binding=True,
    )
    assert decision["consent_boundary_documented"] is True
    assert decision["customer_beta_scope_approved"] is True
    assert decision["blockers"] == []
    assert consent_boundary_invariant_failures(decision) == []


def test_consent_is_not_a_parameter():
    signature = inspect.signature(build_consent_boundary)
    assert "consent_boundary_documented" not in signature.parameters
    assert "customer_beta_scope_approved" not in signature.parameters
    assert "write_permitted" not in signature.parameters


# ---------------------------------------------------------------------------
# the write guard
# ---------------------------------------------------------------------------


def test_demo_fixture_writes_are_still_allowed():
    """This gate must not break the lane every existing route uses."""
    decision = evaluate_write(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="demo_fixture",
        scope=CONTROLLED_SCOPE,
        fact_status="demo_fixture",
        route_context="awarded_grants_routes",
    )
    assert decision["write_allowed"] is True
    assert write_guard_invariant_failures(decision) == []


def test_a_fixture_write_outside_the_demo_scope_is_refused():
    decision = evaluate_write(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="demo_fixture",
        scope="production",
        fact_status="demo_fixture",
        route_context="x",
    )
    assert decision["write_allowed"] is False


def test_a_fixture_label_that_disagrees_with_the_row_is_refused():
    decision = evaluate_write(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="demo_fixture",
        scope=CONTROLLED_SCOPE,
        fact_status="tenant_supplied",
        route_context="x",
    )
    assert decision["write_allowed"] is False


@pytest.mark.parametrize("data_class", sorted(CUSTOMER_DATA_CLASSES))
def test_every_customer_data_class_is_refused_in_the_demo_scope(data_class):
    decision = evaluate_write(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class=data_class,
        scope=CONTROLLED_SCOPE,
        route_context="x",
    )
    assert decision["write_allowed"] is False
    assert write_guard_invariant_failures(decision) == []


def test_customer_identifying_data_is_refused_without_consent():
    decision = evaluate_write(
        **_granted(data_class="customer_identifying_data", consent_record=None)
    )
    assert decision["write_allowed"] is False
    assert CONSENT_ABSENT in decision["blockers"]


def test_customer_operational_data_is_refused_without_consent():
    decision = evaluate_write(**_granted(consent_record=None))
    assert decision["write_allowed"] is False
    assert CONSENT_ABSENT in decision["blockers"]


def test_customer_data_is_refused_without_the_beta_scope():
    decision = evaluate_write(**_granted(beta_scope_approval=None))
    assert decision["write_allowed"] is False
    assert SCOPE_ABSENT in decision["blockers"]


def test_customer_data_is_refused_without_live_customer_auth():
    decision = evaluate_write(**_granted(customer_auth_live=False))
    assert decision["write_allowed"] is False
    assert AUTH_NOT_LIVE in decision["blockers"]


def test_customer_data_is_refused_without_a_verified_binding():
    decision = evaluate_write(**_granted(verified_operational_binding=False))
    assert decision["write_allowed"] is False
    assert BINDING_ABSENT in decision["blockers"]


def test_a_document_body_needs_object_storage_as_well_as_consent():
    decision = evaluate_write(
        **_granted(data_class="customer_document_body", object_store_configured=False)
    )
    assert decision["write_allowed"] is False
    assert "required_capability_not_activated" in decision["blockers"]


def test_a_recipient_needs_email_delivery_as_well_as_consent():
    decision = evaluate_write(
        **_granted(data_class="customer_contact_or_recipient", email_delivery=False)
    )
    assert decision["write_allowed"] is False
    assert "required_capability_not_activated" in decision["blockers"]


def test_a_capability_does_not_substitute_for_consent():
    decision = evaluate_write(
        **_granted(
            data_class="customer_document_body",
            object_store_configured=True,
            consent_record=None,
        )
    )
    assert decision["write_allowed"] is False
    assert CONSENT_ABSENT in decision["blockers"]


@pytest.mark.parametrize("data_class", sorted(NEVER_STORED_CLASSES))
def test_a_provider_subject_is_never_stored(data_class):
    decision = evaluate_write(**_granted(data_class=data_class))
    assert decision["write_allowed"] is False
    assert CLASS_NEVER_STORED in decision["blockers"]


def test_an_unknown_data_class_is_refused():
    decision = evaluate_write(
        **_granted(data_class="a_class_nobody_declared")
    )
    assert decision["write_allowed"] is False
    assert CLASS_UNKNOWN in decision["blockers"]


def test_the_demo_organization_is_not_a_customer_organization():
    decision = evaluate_write(
        **_granted(organization_id=DEMO, org_type_in_database="demo")
    )
    assert decision["write_allowed"] is False
    assert DEMO_ORG_NOT_A_CUSTOMER in decision["blockers"]
    assert NO_REAL_CUSTOMER_ORG in decision["blockers"]


def test_the_real_organization_is_refused_by_name():
    decision = evaluate_write(
        **_granted(organization_id=REAL, org_type_in_database="real")
    )
    assert decision["write_allowed"] is False
    assert REAL_ORG_REFUSED in decision["blockers"]


def test_a_write_with_no_route_context_is_refused():
    """A write nobody can attribute to a route is a write nobody can audit."""
    decision = evaluate_write(**_granted(route_context=None))
    assert decision["write_allowed"] is False
    assert "route_context_not_supplied" in decision["blockers"]


def test_the_permitted_branch_is_reachable_and_writes_nothing():
    decision = evaluate_write(**_granted())
    assert decision["write_allowed"] is True
    assert decision["blockers"] == []
    assert decision["write_performed"] is False
    assert decision["rows_written"] == 0
    assert decision["connection_supplied"] is False
    assert write_guard_invariant_failures(decision) == []


def test_the_guard_never_writes_on_any_branch():
    for kwargs in (
        dict(
            organization_id=DEMO,
            org_type_in_database="demo",
            data_class="demo_fixture",
            scope=CONTROLLED_SCOPE,
            fact_status="demo_fixture",
            route_context="x",
        ),
        _granted(),
        _granted(organization_id=REAL, org_type_in_database="real"),
    ):
        decision = evaluate_write(**kwargs)
        assert decision["write_performed"] is False
        assert decision["rows_written"] == 0
        assert decision["real_organization_touched"] is False
        assert decision["controlled_customer_pilot"] is False
        assert decision["production_rollout"] is False


def test_the_invariants_catch_a_forged_permission():
    decision = evaluate_write(
        organization_id=DEMO,
        org_type_in_database="demo",
        data_class="customer_operational_data",
        scope=CONTROLLED_SCOPE,
        route_context="x",
    )
    decision["write_allowed"] = True
    failures = write_guard_invariant_failures(decision)
    assert "write_allowed_alongside_blockers" in failures
    assert "customer_write_allowed_without_consent" in failures


# ---------------------------------------------------------------------------
# nothing leaks
# ---------------------------------------------------------------------------


def test_no_forbidden_shape_in_any_decision():
    for kwargs in (
        dict(
            organization_id=DEMO,
            org_type_in_database="demo",
            data_class="demo_fixture",
            scope=CONTROLLED_SCOPE,
            route_context="x",
        ),
        _granted(),
        _granted(data_class="customer_contact_or_recipient"),
    ):
        decision = evaluate_write(**kwargs)
        assert decision["leaked_shapes"] == []
        body = json.dumps(decision, default=str)
        assert not ADDRESS_SHAPE.search(body)
        assert not SUBJECT_SHAPE.search(body)


def test_the_leak_scan_actually_fires():
    from nativeforge.services.customer_beta_consent_boundary_service import (
        _leaked_shapes,
    )

    assert _leaked_shapes({"x": "somebody@example.org"}) == ["email_address"]
    assert _leaked_shapes({"x": "112233445566778899001"}) == ["provider_subject"]
    assert _leaked_shapes({"x": "nothing"}) == []


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["readiness", "classes", "consent-blockers"])
def test_every_get_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_the_dry_run_route_refuses_an_unauthenticated_caller(client):
    assert client.post(f"{_base()}/dry-run-write", json={}).status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/readiness",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_both_lanes_false(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    data = body.get("data", body)
    assert data["consent_boundary_documented"] is False
    assert data["customer_beta_scope_approved"] is False
    assert data["customer_data_writes_allowed"] is False
    assert data["demo_fixture_writes_still_allowed"] is True
    assert data["production_rollout"] is False


def test_the_classes_route_lists_all_nine(client, demo_session):
    body = client.get(f"{_base()}/classes", headers=demo_session).json()
    data = body.get("data", body)
    assert len(data["data_classes"]) == 9
    assert data["unknown_is_blocked"] is True


def test_the_blockers_route_names_an_owner_per_blocker(client, demo_session):
    body = client.get(f"{_base()}/consent-blockers", headers=demo_session).json()
    data = body.get("data", body)
    assert data["blockers"]
    for name in data["blockers"]:
        assert data["blocker_owners"][name]["owner"]
    assert data["consent_record_fields_required"] == list(CONSENT_RECORD_FIELDS)
    assert data["beta_scope_fields_required"] == list(BETA_SCOPE_APPROVAL_FIELDS)


def test_the_dry_run_route_records_nothing(client, demo_session):
    response = client.post(
        f"{_base()}/dry-run-write",
        headers=demo_session,
        json={"data_class": "customer_operational_data", "consent_record": CONSENT},
    )
    data = response.json().get("data", response.json())
    assert data["consent_recorded"] is False
    assert data["beta_scope_approved_by_this_call"] is False
    assert data["write_performed"] is False
    assert data["rows_written"] == 0
    assert data["write_allowed"] is False


def test_the_dry_run_route_ignores_caller_supplied_capabilities(client, demo_session):
    """A caller handing the guard its own capability flags hands it the answer."""
    response = client.post(
        f"{_base()}/dry-run-write",
        headers=demo_session,
        json={
            "data_class": "customer_document_body",
            "consent_record": CONSENT,
            "beta_scope_approval": SCOPE,
            "customer_auth_live": True,
            "verified_operational_binding": True,
            "object_store_configured": True,
        },
    )
    data = response.json().get("data", response.json())
    assert data["write_allowed"] is False


def test_a_fixture_dry_run_is_allowed_through_the_route(client, demo_session):
    response = client.post(
        f"{_base()}/dry-run-write",
        headers=demo_session,
        json={
            "data_class": "demo_fixture",
            "scope": CONTROLLED_SCOPE,
            "fact_status": "demo_fixture",
        },
    )
    data = response.json().get("data", response.json())
    assert data["write_allowed"] is True
    assert data["rows_written"] == 0


def test_no_route_leaks_a_shape(client, demo_session):
    for path in ("readiness", "classes", "consent-blockers"):
        raw = client.get(f"{_base()}/{path}", headers=demo_session).text
        assert not ADDRESS_SHAPE.search(raw)
        assert not SUBJECT_SHAPE.search(raw)
        assert "nf_session=" not in raw


def test_another_organization_is_refused(client, demo_session):
    response = client.get(f"{_base(OTHER)}/readiness", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_no_real_organization_route_was_built():
    from nativeforge.api import customer_data_boundary_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    assert "/v1/nf/real" not in Path(routes.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# cockpit
# ---------------------------------------------------------------------------


def test_the_cockpit_has_a_consent_lane():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    lane = next(
        entry
        for entry in summary["lanes"]
        if entry["lane"] == "consent_and_data_boundary"
    )
    assert lane["value"] is False
    assert lane["status"] != "operational"
    assert "consent_boundary_not_documented" in lane["blockers"]


def test_the_cockpit_has_a_beta_scope_lane():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    lane = next(
        entry for entry in summary["lanes"] if entry["lane"] == "customer_beta_scope"
    )
    assert lane["value"] is False
    assert "customer_beta_scope_not_approved" in lane["blockers"]


def test_the_cockpit_never_claims_the_beta_is_approved():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        build_beta_onboarding_summary,
    )

    summary = build_beta_onboarding_summary()
    assert summary["consent_boundary_documented"] is False
    assert summary["customer_beta_scope_approved"] is False
    assert summary["controlled_customer_pilot"] is False
    assert summary["customer_data_writes_allowed"] is False
    assert summary["demo_fixture_writes_still_allowed"] is True


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_customer_data_boundary_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.customer_data_boundary_artifact_invariant_failures(result) == []


def test_the_artifact_is_deterministic():
    built = art.build_customer_data_boundary_artifacts()
    assert built == art.build_customer_data_boundary_artifacts()


def test_the_artifact_reads_no_database():
    builder = art.build_customer_data_boundary_artifacts
    assert inspect.signature(builder).parameters == {}


def test_the_artifacts_record_the_finding():
    files = art.build_customer_data_boundary_artifacts()
    survey = json.loads(files[art.SURVEY_FILE])
    assert survey["consent_table_in_any_migration"] is False
    assert "Neither is consent" in survey["the_finding"]


def test_the_artifacts_record_what_is_not_consent():
    files = art.build_customer_data_boundary_artifacts()
    consent = json.loads(files[art.CONSENT_FILE])
    assert len(consent["not_consent"]) >= 4
    assert consent["inferred_consent_keys_refused_by_name"]
    assert consent["consent_boundary_documented"] is False


def test_the_artifacts_record_the_class_catalogue():
    files = art.build_customer_data_boundary_artifacts()
    classes = json.loads(files[art.CLASSES_FILE])
    assert len(classes["data_classes"]) == 9
    assert sorted(classes["customer_data_classes"]) == sorted(CUSTOMER_DATA_CLASSES)
    assert sorted(classes["pre_consent_classes"]) == sorted(PRE_CONSENT_CLASSES)


def test_the_artifacts_record_what_stays_false():
    files = art.build_customer_data_boundary_artifacts()
    readiness = json.loads(files[art.READINESS_FILE])
    for name in (
        "consent_boundary_documented",
        "customer_beta_scope_approved",
        "controlled_customer_pilot",
        "production_rollout",
    ):
        assert name in readiness["stays_false_after_this_gate"]
    assert readiness["rows_written"] == 0


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_customer_data_boundary_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_customer_data_boundary_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# the live database
# ---------------------------------------------------------------------------


def test_no_customer_data_row_exists():
    """A regression that wrote one would show up here. Read-only, counts only."""
    import sqlalchemy as sa

    from nativeforge.lib.settings import get_settings

    try:
        engine = sa.create_engine(get_settings().database_url)
        with engine.connect() as connection:
            inspector = sa.inspect(engine)
            tables = [
                name
                for name in inspector.get_table_names()
                if name.startswith("nf_award")
            ]
            counts = {}
            for table in tables:
                columns = {c["name"] for c in inspector.get_columns(table)}
                if "fact_status" not in columns:
                    continue
                counts[table] = connection.execute(
                    sa.text(
                        f"SELECT count(*) FROM {table} "
                        "WHERE fact_status = 'tenant_supplied'"
                    )
                ).scalar()
    except Exception:  # noqa: BLE001
        pytest.skip("no database reachable in this environment")

    assert all(count == 0 for count in counts.values()), counts
