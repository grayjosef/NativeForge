"""Gate 137: the real-org verified binding path exists and is not activated.

Gate 137A measured what this closes, and the finding was not the one the brief
expected. The refusal everyone credited Gate 113 with — *a demo organization
cannot be a verified binding* — was a refusal of the caller's **label**, not of
the organization. A verified binding written onto the demo org with
`is_demo=False` produced `production_verified_binding: True`, no blockers, and
no invariant failures.

And with `customer_auth_live` injected true, a **real-org** production verified
binding was fully writable, with no approval of any kind anywhere in the chain.

Everything below is about whether either can still happen.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import (
    tenant_customer_org_binding_repository_service as repo,
)
from nativeforge.services import (
    verified_operational_binding_artifact_gate137_service as art,
)
from nativeforge.services.customer_auth_activation_gate_service import (
    REQUIRED_AUTH_GATES,
    activation_gate_invariant_failures,
    build_customer_auth_activation_gate,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    APPROVAL_FIELDS,
    AUTHORIZED_REAL_ORGANIZATION_IDS,
    DEMO_ORGANIZATION_ID,
    FORBIDDEN_AUTHORITY_KEYS,
    PRODUCTION_SCOPE,
    REAL_ORG_SCOPE,
    REAL_ORGANIZATION_ID,
    REVOCATION_ENV,
    activation_boundary_invariant_failures,
    build_real_org_binding_activation_decision,
)
from nativeforge.services.verified_operational_binding_preparation_service import (
    CLASSIFICATION_SOURCE,
    preparation_invariant_failures,
    prepare_verified_operational_binding,
    write_invariant_failures,
    write_verified_operational_binding,
)

DEMO = DEMO_ORGANIZATION_ID
REAL = REAL_ORGANIZATION_ID
#: Neither the demo org nor the real one. Both refusals stay reachable.
FIXTURE = "cccccccc-dddd-eeee-ffff-000000000001"
OTHER_FIXTURE = "cccccccc-dddd-eeee-ffff-000000000002"
VERIFIER = "dddddddd-eeee-ffff-0000-111111111111"
NOW = datetime(2026, 9, 2, tzinfo=UTC)

ORGANIZATIONS = sa.Table(
    "organizations",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def approval(organization_id, *, scope=REAL_ORG_SCOPE, environment="dev"):
    return {
        "organization_id": organization_id,
        "authorized_by": "mayhem",
        "authorization_scope": scope,
        "environment": environment,
        "recorded_at": NOW.isoformat(),
    }


@pytest.fixture
def binding_db():
    """Organizations and bindings, for one test. Never the dev database."""
    engine = sa.create_engine("sqlite://")
    ORGANIZATIONS.create(engine)
    repo.BINDINGS.create(engine)
    with engine.begin() as conn:
        for organization_id, org_type in (
            (REAL, "real"),
            (DEMO, "demo"),
            (FIXTURE, "real"),
            (OTHER_FIXTURE, "real"),
        ):
            conn.execute(
                sa.insert(ORGANIZATIONS).values(
                    id=uuid.UUID(organization_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=NOW,
                )
            )
        yield conn
    engine.dispose()


def _write(conn, organization_id, **overrides):
    fields = {
        "organization_id": organization_id,
        "tenant_id": "t-fix",
        "customer_org_id": "c-fix",
        "verified_by_identity_id": VERIFIER,
        "verified_at": NOW.isoformat(),
        "approval": approval(organization_id),
        "app_env": "dev",
        "authorized_organization_ids": frozenset({organization_id}),
    }
    fields.update(overrides)
    return write_verified_operational_binding(connection=conn, created_at=NOW, **fields)


# ---------------------------------------------------------------------------
# the demo organization
# ---------------------------------------------------------------------------


def test_the_demo_org_cannot_satisfy_a_verified_operational_binding(binding_db):
    """Even listed as authorized, even with a well-formed approval."""
    result = _write(binding_db, DEMO)
    assert result["write_performed"] is False
    assert result["verified_operational_binding"] is False
    assert result["is_demo_derived"] is True
    assert (
        "boundary:demo_organization_is_never_a_verified_operational_binding"
        in result["blocked_reasons"]
    )
    assert write_invariant_failures(result) == []


def test_the_demo_refusal_is_derived_from_the_row_not_from_the_caller(binding_db):
    """The defect Gate 137A measured, and the exact input that produced it.

    `is_demo=False` against the demo organization used to write a row with
    `production_verified_binding: True` and no blockers.
    """
    result = _write(binding_db, DEMO, is_demo=False)
    assert result["write_performed"] is False
    assert result["is_demo_derived"] is True
    assert result["is_demo_supplied_by_caller"] is False
    assert result["is_demo_authority"] == CLASSIFICATION_SOURCE
    assert (
        "supplied_is_demo_disagrees_with_the_organization_row"
        in result["blocked_reasons"]
    )
    rows = binding_db.execute(sa.select(sa.func.count()).select_from(repo.BINDINGS))
    assert rows.scalar_one() == 0


def test_a_demo_fixture_binding_cannot_carry_a_verifier(binding_db):
    """Gate 113's original refusal, still standing and not weakened."""
    result = repo.insert_binding(
        connection=binding_db,
        organization_id=DEMO,
        tenant_id="t",
        customer_org_id="c",
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        binding_confidence="demo_only",
        verified_by_identity_id=VERIFIER,
        verified_at=NOW.isoformat(),
        is_demo=True,
        created_at=NOW,
    )
    assert result["rows_written"] == 0
    assert "demo_fixture_binding_cannot_carry_a_verifier" in result["blocked_reasons"]


def test_the_boundary_refuses_the_demo_org_even_when_it_is_listed():
    decision = build_real_org_binding_activation_decision(
        organization_id=DEMO,
        approval=approval(DEMO),
        app_env="dev",
        org_type_in_database="demo",
        authorized_organization_ids=frozenset({DEMO}),
    )
    assert decision["approves_real_org_binding_activation"] is False
    assert decision["organization_is_demo"] is True
    assert (
        "demo_organization_is_never_a_verified_operational_binding"
        in decision["blocked_reasons"]
    )
    assert activation_boundary_invariant_failures(decision) == []


# ---------------------------------------------------------------------------
# the real organization
# ---------------------------------------------------------------------------


def test_the_real_org_cannot_be_touched_without_approval(binding_db):
    result = _write(binding_db, REAL, approval=None, authorized_organization_ids=None)
    assert result["write_performed"] is False
    assert "boundary:no_approval_object_supplied" in result["blocked_reasons"]


def test_the_real_org_is_refused_by_name_even_with_an_approval(binding_db):
    """The authorized list is empty, and an approval alone does not add to it."""
    result = _write(binding_db, REAL, authorized_organization_ids=None)
    assert result["write_performed"] is False
    assert (
        "boundary:organization_is_the_explicitly_refused_real_org"
        in result["blocked_reasons"]
    )


def test_the_authorized_real_org_list_is_empty():
    """Empty is the decision, not an oversight."""
    assert AUTHORIZED_REAL_ORGANIZATION_IDS == frozenset()
    assert REAL not in AUTHORIZED_REAL_ORGANIZATION_IDS


def test_an_approval_object_is_required_and_must_be_complete():
    for missing in APPROVAL_FIELDS:
        incomplete = approval(FIXTURE)
        incomplete.pop(missing)
        decision = build_real_org_binding_activation_decision(
            organization_id=FIXTURE,
            approval=incomplete,
            app_env="dev",
            org_type_in_database="real",
            authorized_organization_ids=frozenset({FIXTURE}),
        )
        assert decision["approves_real_org_binding_activation"] is False, missing
        assert f"approval_missing_field:{missing}" in decision["blocked_reasons"]


def test_an_approval_for_another_organization_is_not_an_approval_for_this_one():
    decision = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(OTHER_FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert decision["approves_real_org_binding_activation"] is False
    assert "approval_names_a_different_organization" in decision["blocked_reasons"]


def test_production_approval_is_separate_from_the_dev_approval():
    """The narrow scope does not reach production."""
    narrow = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(FIXTURE, environment="production"),
        app_env="production",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert narrow["approves_real_org_binding_activation"] is False
    assert "approval_scope_does_not_cover_production" in narrow["blocked_reasons"]

    broad = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(FIXTURE, scope=PRODUCTION_SCOPE, environment="production"),
        app_env="production",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert broad["approves_real_org_binding_activation"] is True
    assert broad["approves_production_binding_activation"] is True
    assert broad["approves_production_rollout"] is False
    assert activation_boundary_invariant_failures(broad) == []


def test_no_environment_variable_can_approve_and_one_can_revoke(monkeypatch):
    decision = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert decision["approves_real_org_binding_activation"] is True
    assert decision["grant_environment_variable"] is None

    monkeypatch.setenv(REVOCATION_ENV, "true")
    revoked = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert revoked["revoked"] is True
    assert revoked["approves_real_org_binding_activation"] is False


def test_the_decision_never_approves_rollout_or_a_pilot():
    for environment in ("local", "dev", "test", "production"):
        decision = build_real_org_binding_activation_decision(
            organization_id=FIXTURE,
            approval=approval(FIXTURE, scope=PRODUCTION_SCOPE, environment=environment),
            app_env=environment,
            org_type_in_database="real",
            authorized_organization_ids=frozenset({FIXTURE}),
        )
        assert decision["approves_production_rollout"] is False
        assert decision["approves_controlled_customer_pilot"] is False

    forged = dict(
        build_real_org_binding_activation_decision(
            organization_id=FIXTURE,
            approval=approval(FIXTURE),
            app_env="dev",
            org_type_in_database="real",
            authorized_organization_ids=frozenset({FIXTURE}),
        )
    )
    forged["approves_production_rollout"] = True
    assert (
        "decision_approved_production_rollout"
        in activation_boundary_invariant_failures(forged)
    )


# ---------------------------------------------------------------------------
# organization_id is the only authority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", FORBIDDEN_AUTHORITY_KEYS)
def test_no_label_can_authorize_a_binding(key):
    decision = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=approval(FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
        **{key: "some-label"},
    )
    assert decision["approves_real_org_binding_activation"] is False
    assert f"not_an_authority_for_a_binding:{key}" in decision["blocked_reasons"]


@pytest.mark.parametrize("key", FORBIDDEN_AUTHORITY_KEYS)
def test_an_approval_cannot_name_a_label_as_its_subject(key):
    carrying = approval(FIXTURE)
    carrying[key] = "some-label"
    decision = build_real_org_binding_activation_decision(
        organization_id=FIXTURE,
        approval=carrying,
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert decision["approves_real_org_binding_activation"] is False
    assert (
        f"approval_carries_a_non_authority_subject:{key}" in decision["blocked_reasons"]
    )


def test_a_binding_cannot_be_resolved_by_tenant_id_alone(binding_db):
    _write(binding_db, FIXTURE)
    by_label = repo.get_active_binding(connection=binding_db, tenant_id="t-fix")
    assert by_label["read_performed"] is False
    assert (
        "read_without_a_uuid_shaped_organization_id_anchor"
        in by_label["blocked_reasons"]
    )


def test_an_organization_profile_id_is_refused_rather_than_ignored(binding_db):
    result = _write(binding_db, FIXTURE, organization_profile_id="profile-1")
    assert result["write_performed"] is False
    assert any(
        "organization_profile_id" in reason for reason in result["blocked_reasons"]
    )


# ---------------------------------------------------------------------------
# the hermetic real-org path
# ---------------------------------------------------------------------------


def test_a_hermetic_real_org_binding_can_be_written_with_approval(binding_db):
    """The permitted branch is reachable, which is what makes every refusal
    above a measurement rather than a constant."""
    result = _write(binding_db, FIXTURE)
    assert result["write_performed"] is True
    assert result["verified_operational_binding"] is True
    assert result["rows_written"] == 1
    assert result["is_demo_derived"] is False
    assert result["readback_performed"] is True
    assert result["readback_is_demo"] is False
    assert result["blocked_reasons"] == []
    assert write_invariant_failures(result) == []


def test_the_written_row_lands_in_the_real_partition(binding_db):
    _write(binding_db, FIXTURE)
    row = (
        binding_db.execute(
            sa.select(repo.BINDINGS).where(
                repo.BINDINGS.c.organization_id == uuid.UUID(FIXTURE)
            )
        )
        .mappings()
        .one()
    )
    assert row["is_demo"] is False
    assert row["binding_status"] == "verified_binding"
    assert row["verified_by_identity_id"] is not None
    assert row["verified_at"] is not None


def test_the_binding_can_be_read_back_by_organization_id(binding_db):
    _write(binding_db, FIXTURE)
    got = repo.get_active_binding(connection=binding_db, organization_id=FIXTURE)
    assert got["read_performed"] is True
    assert got["rows_matched"] == 1
    assert got["production_verified_binding"] is True
    assert got["demo_fixture"] is False


def test_a_second_binding_with_the_same_labels_is_refused(binding_db):
    _write(binding_db, FIXTURE)
    again = _write(binding_db, FIXTURE)
    assert again["write_performed"] is False
    assert f"repository:{repo.DUPLICATE_ACTIVE}" in again["blocked_reasons"]


def test_a_second_verified_binding_with_other_labels_is_refused_too(binding_db):
    """Found because Gate 137F's artifact measured the first rule and disagreed
    with the claim printed beside it.

    Two verified bindings for one organization are two statements that it is
    verifiably bound to different tenant and customer-org pairs. They
    contradict each other at the level the RLS anchor cares about, so the label
    scoping that is right for the general case is too loose for this one.
    """
    _write(binding_db, FIXTURE)
    other = _write(binding_db, FIXTURE, tenant_id="t-other", customer_org_id="c-other")
    assert other["write_performed"] is False
    assert f"repository:{repo.VERIFIED_ALREADY_EXISTS}" in other["blocked_reasons"]

    count = binding_db.execute(
        sa.select(sa.func.count()).select_from(repo.BINDINGS)
    ).scalar_one()
    assert count == 1


def test_an_ambiguous_read_refuses_to_pick(binding_db):
    """Two rows past the repository, so the branch is reachable."""
    for _ in range(2):
        binding_db.execute(
            sa.insert(repo.BINDINGS).values(
                id=uuid.uuid4(),
                organization_id=uuid.UUID(FIXTURE),
                tenant_id="t",
                customer_org_id="c",
                binding_status="verified_binding",
                binding_source="admin_verified",
                binding_confidence="verified",
                verified_by_identity_id=uuid.UUID(VERIFIER),
                verified_at=NOW,
                revoked_at=None,
                revoked_by_identity_id=None,
                is_demo=False,
                human_review_required=False,
                blocked_reasons=[],
                created_at=NOW,
                updated_at=NOW,
            )
        )
    got = repo.get_active_binding(connection=binding_db, organization_id=FIXTURE)
    assert got["read_performed"] is False
    assert got["rows_matched"] == 2
    assert got["production_verified_binding"] is False
    assert repo.AMBIGUOUS_ACTIVE in got["blocked_reasons"]


def test_the_runtime_real_org_is_never_written_to(binding_db):
    """Every attempt in this file, and then a count."""
    for organization_id in (DEMO, REAL, FIXTURE):
        _write(binding_db, organization_id)
    for organization_id in (DEMO, REAL):
        count = binding_db.execute(
            sa.select(sa.func.count())
            .select_from(repo.BINDINGS)
            .where(repo.BINDINGS.c.organization_id == uuid.UUID(organization_id))
        ).scalar_one()
        assert count == 0, organization_id


def test_the_declared_result_fields_are_all_present(binding_db):
    """`RESULT_FIELDS` was declared in Gate 120B and consumed by nothing."""
    _write(binding_db, FIXTURE)
    got = repo.get_active_binding(connection=binding_db, organization_id=FIXTURE)
    missing = [field for field in repo.RESULT_FIELDS if field not in got]
    assert missing == []


# ---------------------------------------------------------------------------
# preparation reports nothing it should not
# ---------------------------------------------------------------------------


def test_the_prepared_result_carries_no_secret_or_subject():
    result = prepare_verified_operational_binding(
        organization_id=FIXTURE,
        tenant_id="t",
        customer_org_id="c",
        verified_by_identity_id=VERIFIER,
        verified_at=NOW.isoformat(),
        approval=approval(FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert result["binding_ready_to_write"] is True
    assert preparation_invariant_failures(result) == []
    blob = json.dumps(result).lower()
    for forbidden in ("id_token", "access_token", "code_verifier", "@gmail.com"):
        assert forbidden not in blob, forbidden
    for key in ("subject", "provider_subject", "email", "client_secret"):
        assert key not in result, key


def test_preparation_writes_nothing():
    result = prepare_verified_operational_binding(
        organization_id=FIXTURE,
        tenant_id="t",
        customer_org_id="c",
        verified_by_identity_id=VERIFIER,
        verified_at=NOW.isoformat(),
        approval=approval(FIXTURE),
        app_env="dev",
        org_type_in_database="real",
        authorized_organization_ids=frozenset({FIXTURE}),
    )
    assert result["write_performed"] is False
    assert result["rows_written"] == 0
    assert result["real_organization_touched"] is False
    assert result["real_customer_rows_written"] == 0


# ---------------------------------------------------------------------------
# the activation gate
# ---------------------------------------------------------------------------

_FACTS = {
    "preflight": {
        "validation_possible": True,
        "client_secret_present": True,
        "issuer_url_present": True,
        "audience_present": True,
        "jwks_reachable": None,
    },
    "route_readiness": {
        "callback_route_available": True,
        "session_cookie_policy_available": True,
    },
    "signing_key_readiness": {"can_sign_production_session": True},
    "binding_evidence": {
        "org_binding_passed": True,
        "callback_session_validated": True,
    },
    "jwks_validation_evidence": {
        "issuer_jwks_validated": True,
        "provider_called": True,
    },
    "role_mapping_evidence": {"role_mapping_passed": True},
    "login_activation_decision": {"approves_login_live": True},
    "invite_binding_evidence": {"invite_binding_passed": True},
    "customer_auth_activation_decision": {"approves_customer_auth_live": True},
    "dev_header_exposure": {"route_total": 217, "dev_header_route_count": 0},
}


def _gate(**overrides):
    return build_customer_auth_activation_gate(**{**_FACTS, **overrides})


def test_verified_operational_binding_is_not_a_required_auth_gate():
    """Adding it would close the cycle Gate 134F spent a gate opening."""
    assert "verified_operational_binding" not in REQUIRED_AUTH_GATES


def test_verified_operational_binding_is_false_without_a_readback():
    gate = _gate()
    assert gate["customer_auth_live"] is True
    assert gate["verified_operational_binding"] is False
    assert gate["production_write_readiness"] is False
    assert gate["production_write_blockers"]
    assert activation_gate_invariant_failures(gate) == []


def test_customer_auth_live_does_not_pretend_to_be_production_readiness():
    gate = _gate()
    assert gate["customer_auth_live"] is True
    assert gate["customer_auth_live_scope"] == "controlled_dev_demo_org_only"
    assert gate["production_write_readiness"] is False
    assert gate["production_write_readiness_requires"] == [
        "customer_auth_live",
        "verified_operational_binding",
    ]


def test_a_real_org_readback_makes_production_write_readiness_true():
    gate = _gate(
        verified_binding_readback={
            "read_performed": True,
            "production_verified_binding": True,
            "demo_fixture": False,
            "organization_id": FIXTURE,
        }
    )
    assert gate["verified_operational_binding"] is True
    assert gate["production_write_readiness"] is True
    assert gate["production_write_blockers"] == []
    assert activation_gate_invariant_failures(gate) == []


def test_a_demo_org_readback_does_not(binding_db):
    """The boolean, not only the blocker list.

    Written the other way round first: the reason was named and the flag still
    said true, which is the shape this gate exists to catch.
    """
    gate = _gate(
        verified_binding_readback={
            "read_performed": True,
            "production_verified_binding": True,
            "demo_fixture": False,
            "organization_id": DEMO,
        }
    )
    assert gate["verified_operational_binding"] is False
    assert gate["verified_binding_is_for_the_demo_organization"] is True
    assert (
        "verified_binding_readback_is_for_the_demo_organization"
        in gate["production_write_blockers"]
    )
    assert activation_gate_invariant_failures(gate) == []


def test_a_forged_demo_org_binding_claim_fails_an_invariant():
    gate = dict(
        _gate(
            verified_binding_readback={
                "read_performed": True,
                "production_verified_binding": True,
                "demo_fixture": False,
                "organization_id": DEMO,
            }
        )
    )
    gate["verified_operational_binding"] = True
    assert (
        "verified_operational_binding_claimed_for_the_demo_org"
        in activation_gate_invariant_failures(gate)
    )


def test_customer_auth_live_stays_false_when_the_invite_is_missing():
    """Unchanged by this gate, and asserted so it stays that way."""
    gate = _gate(invite_binding_evidence={"invite_binding_passed": False})
    assert gate["customer_auth_live"] is False
    assert "invite_binding_passed" in gate["missing_auth_gates"]


def test_the_gate_never_claims_rollout_or_a_pilot():
    for readback in (
        None,
        {
            "read_performed": True,
            "production_verified_binding": True,
            "demo_fixture": False,
            "organization_id": FIXTURE,
        },
    ):
        gate = _gate(verified_binding_readback=readback)
        assert gate["production_rollout"] is False
        assert gate["controlled_customer_pilot"] is False


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifacts_regenerate_deterministically(tmp_path):
    art.write_binding_artifacts(repo_root=tmp_path)
    written = {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / art.ARTIFACT_DIR).iterdir()
    }
    assert set(written) == set(art.ARTIFACT_FILES)

    again = art.build_binding_artifacts()
    for name, body in written.items():
        assert body == again[name], name

    committed = Path(art.ARTIFACT_DIR)
    for name, body in written.items():
        assert (committed / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_carry_no_secret_or_provider_subject():
    files = art.build_binding_artifacts()
    blob = "\n".join(files.values()).lower()
    for forbidden in ("gocspx-", "set-cookie:", "eyj", "@gmail.com"):
        assert forbidden not in blob, forbidden

    import re

    for field in art.CREDENTIAL_FIELDS:
        assert not re.search(rf'"{re.escape(field)}"\s*:\s*"', blob), field


def test_the_artifacts_record_the_real_org_as_untouched():
    files = art.build_binding_artifacts()
    untouched = json.loads(files["runtime_real_org_untouched.json"])
    assert untouched["bindings_written_for_the_real_organization"] == 0
    assert untouched["bindings_written_for_the_demo_organization"] == 0
    assert untouched["runtime_database_opened_by_this_gate"] is False
    assert untouched["real_customer_data_written"] is False
    assert untouched["production_bindings_created"] == 0


def test_the_artifacts_do_not_claim_a_verified_binding_exists():
    files = art.build_binding_artifacts()
    readiness = json.loads(files["customer_auth_readiness_after_gate137.json"])
    deterministic = readiness["deterministic_gate_no_evidence_supplied"]
    assert deterministic["verified_operational_binding"] is False
    assert deterministic["customer_auth_live"] is False
    assert deterministic["production_write_readiness"] is False
    assert readiness["production_rollout"] is False
    assert readiness["controlled_customer_pilot"] is False


def test_the_hermetic_artifact_measures_rather_than_describes():
    files = art.build_binding_artifacts()
    hermetic = json.loads(files["hermetic_real_org_binding_result.json"])
    assert hermetic["first_write"]["write_performed"] is True
    assert hermetic["second_write_same_labels"]["write_performed"] is False
    assert hermetic["second_write_other_labels"]["write_performed"] is False
    assert len(hermetic["stored_rows"]) == 1
    assert hermetic["stored_rows"][0]["organization_id"] == art.FIXTURE_ORGANIZATION_ID
    assert hermetic["fixture_organization_id"] not in {DEMO, REAL}


def test_the_artifact_invariants_hold(tmp_path):
    result = art.write_binding_artifacts(repo_root=tmp_path)
    assert art.binding_artifact_invariant_failures(result) == []
    assert result["file_count"] == len(art.ARTIFACT_FILES)
