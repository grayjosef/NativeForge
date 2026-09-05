"""Gate 120: identity binding repository and verified binding workflow.

A repository was built and a workflow joined three contracts that had never
spoken to each other. One thing must stay true throughout: **a repository is
somewhere to put a verified binding, and a verified binding is not one.**

The tests are grouped by what they would catch:

```text
anchor       a label treated as an RLS authority
verifier     a verified binding with nobody behind it
revocation   a DELETE where an UPDATE belongs
authorization an approval by a role that may only inspect
readiness    a repository existing being read as persistence going live
```
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import customer_persistence_capability_service as cap_svc
from nativeforge.services import (
    customer_persistence_spine_decision_service as spine_svc,
)
from nativeforge.services import (
    org_scoped_customer_persistence_guard_service as guard_svc,
)
from nativeforge.services import (
    tenant_customer_org_binding_repository_service as repo_svc,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_readiness_service as readiness_svc,
)
from nativeforge.services import tenant_customer_org_binding_store_service as store_svc
from nativeforge.services import verified_binder_authorization_service as auth_svc
from nativeforge.services import verified_binding_workflow_artifact_service as art
from nativeforge.services import (
    verified_binding_workflow_demo_fixture_service as fixtures,
)
from nativeforge.services import verified_binding_workflow_service as flow_svc

ORG = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
VERIFIER = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
VERIFIED_AT = NOW.isoformat()


#: Gate 137D gave `insert_binding` an `is_demo` derived from the organization
#: row, so a *verified* binding now needs one to exist. The fixture builds it.
#:
#: This is not the check being worked around - it is the world the check reads.
#: Without the row the permitted branch below became unreachable, and an
#: unreachable permitted branch makes every refusal above it unfalsifiable,
#: which is the defect this file was written to catch in the first place.
_ORGANIZATIONS = sa.Table(
    "organizations",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


@pytest.fixture
def bindings_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.BINDINGS.create(engine)
    _ORGANIZATIONS.create(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.insert(_ORGANIZATIONS).values(
                id=uuid.UUID(ORG),
                org_type="real",
                seat_cap=5,
                created_at=datetime(2026, 9, 2, tzinfo=UTC),
            )
        )
        yield conn
    engine.dispose()


def _principal(roles, *, demo=False, auth_status="authenticated_verified_org"):
    return {
        "principal_id": VERIFIER,
        "roles": list(roles),
        "auth_status": auth_status,
        "org_claim_verified": True,
        "is_demo_principal": demo,
        "organization_id": ORG,
    }


def _flow_row(**overrides):
    """Row fields the workflow accepts.

    The workflow derives `is_demo` from the principal rather than taking it as a
    parameter — a caller asserting a row is a fixture while the principal is a
    production one is the shape of a bug, and the principal wins.
    """
    kwargs = _demo_row(**overrides)
    kwargs.pop("is_demo", None)
    return kwargs


def _demo_row(**overrides):
    kwargs = {
        "organization_id": ORG,
        "tenant_id": "nf-demo-fixture-tenant",
        "customer_org_id": "nf-demo-fixture-customer-org",
        "binding_status": "demo_fixture",
        "binding_source": "demo_fixture",
        "binding_confidence": "demo_only",
        "is_demo": True,
    }
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- the anchor


def test_the_repository_requires_an_organization_id():
    result = repo_svc.prepare_insert(**_demo_row(organization_id=None))
    assert result["storage_allowed"] is False
    assert "binding_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_the_organization_id_must_be_uuid_shaped():
    """Every RLS policy casts to ::uuid, so anything else cannot be scoped."""
    result = repo_svc.prepare_insert(**_demo_row(organization_id="tenant-acme"))
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_tenant_id_is_a_label_and_is_required_but_never_the_anchor():
    result = repo_svc.prepare_insert(**_demo_row(tenant_id=None))
    assert result["storage_allowed"] is False
    assert "binding_without_a_tenant_label" in result["blocked_reasons"]
    # And it never becomes the anchor.
    assert repo_svc.prepare_insert(**_demo_row())["rls_anchor"] == "organization_id"


def test_customer_org_id_is_a_label_and_is_required():
    result = repo_svc.prepare_insert(**_demo_row(customer_org_id=None))
    assert result["storage_allowed"] is False
    assert "binding_without_a_customer_org_label" in result["blocked_reasons"]


def test_organization_profile_id_is_refused_rather_than_ignored():
    """Gates 110-113: a real value from a real column in the wrong space."""
    result = repo_svc.prepare_insert(**_demo_row(organization_profile_id="profile-123"))
    assert result["storage_allowed"] is False
    assert (
        "organization_profile_id_is_not_an_organization_id_anchor"
        in result["blocked_reasons"]
    )


def test_a_label_cannot_select_a_binding_on_its_own(bindings_db):
    repo_svc.insert_binding(connection=bindings_db, created_at=NOW, **_demo_row())
    result = repo_svc.get_active_binding(
        connection=bindings_db, tenant_id="nf-demo-fixture-tenant"
    )
    assert result["rows_read"] == 0
    assert (
        "read_without_a_uuid_shaped_organization_id_anchor" in result["blocked_reasons"]
    )


def test_a_read_is_scoped_to_one_organization(bindings_db):
    repo_svc.insert_binding(connection=bindings_db, created_at=NOW, **_demo_row())
    other = repo_svc.get_active_binding(
        connection=bindings_db, organization_id=str(uuid.uuid4())
    )
    assert other["rows_read"] == 0
    assert "no_active_binding_for_this_organization" in other["blocked_reasons"]


# ------------------------------------------------- the verifier


def test_a_production_verified_binding_requires_a_verifier_identity():
    result = repo_svc.prepare_insert(
        **_demo_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            binding_confidence="verified",
            is_demo=False,
        )
    )
    assert result["storage_allowed"] is False
    assert "verified_binding_without_a_verifier_identity" in result["blocked_reasons"]


def test_a_production_verified_binding_requires_a_verified_at():
    result = repo_svc.prepare_insert(
        **_demo_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            binding_confidence="verified",
            verified_by_identity_id=VERIFIER,
            is_demo=False,
        )
    )
    assert result["storage_allowed"] is False
    assert "verified_binding_without_a_verified_at" in result["blocked_reasons"]


def test_a_demo_fixture_binding_is_never_production_verified():
    result = repo_svc.prepare_insert(**_demo_row())
    assert result["storage_allowed"] is True
    assert result["demo_fixture"] is True
    assert result["production_verified_binding"] is False
    assert repo_svc.binding_repository_invariant_failures(result) == []


def test_a_demo_fixture_binding_cannot_carry_a_verifier():
    result = repo_svc.prepare_insert(
        **_demo_row(verified_by_identity_id=VERIFIER, verified_at=VERIFIED_AT)
    )
    assert result["storage_allowed"] is False
    assert "demo_fixture_binding_cannot_carry_a_verifier" in result["blocked_reasons"]


def test_the_verified_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    result = repo_svc.prepare_insert(
        **_demo_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            binding_confidence="verified",
            verified_by_identity_id=VERIFIER,
            verified_at=VERIFIED_AT,
            is_demo=False,
        )
    )
    assert result["storage_allowed"] is True
    assert result["production_verified_binding"] is True
    assert result["blocked_reasons"] == []
    assert repo_svc.binding_repository_invariant_failures(result) == []


def test_the_database_refuses_a_verified_binding_with_no_verifier(bindings_db):
    """The CHECK is what catches the case this module gets wrong."""
    with pytest.raises(sa.exc.IntegrityError):
        bindings_db.execute(
            sa.insert(repo_svc.BINDINGS).values(
                id=uuid.uuid4(),
                organization_id=uuid.UUID(ORG),
                tenant_id="t",
                customer_org_id="c",
                binding_status="verified_binding",
                binding_source="admin_verified",
                binding_confidence="verified",
                verified_by_identity_id=None,
                verified_at=None,
                revoked_at=None,
                revoked_by_identity_id=None,
                is_demo=False,
                human_review_required=True,
                blocked_reasons=[],
                created_at=NOW,
                updated_at=NOW,
            )
        )


def test_the_core_table_matches_the_migration_columns():
    migration = Path(
        "alembic/versions/0029_nf_tenant_customer_org_bindings.py"
    ).read_text(encoding="utf-8")
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.BINDINGS.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path(
        "alembic/versions/0029_nf_tenant_customer_org_bindings.py"
    ).read_text(encoding="utf-8")
    declared = set(re.findall(r'name="(ck_nf_binding_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.BINDINGS.constraints
        if c.name and str(c.name).startswith("ck_nf_binding")
    }
    assert mapped == declared


# ------------------------------------------------- revocation


def test_a_revoked_binding_is_retained(bindings_db):
    repo_svc.insert_binding(connection=bindings_db, created_at=NOW, **_demo_row())
    result = repo_svc.revoke_binding(
        connection=bindings_db,
        organization_id=ORG,
        tenant_id="nf-demo-fixture-tenant",
        customer_org_id="nf-demo-fixture-customer-org",
        revoked_by_identity_id=VERIFIER,
        revoked_at=NOW,
    )
    assert result["write_performed"] is True
    assert result["rows_deleted"] == 0

    remaining = bindings_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.BINDINGS)
    ).scalar()
    assert remaining == 1

    listing = repo_svc.list_bindings_for_organization(
        connection=bindings_db, organization_id=ORG
    )
    assert listing["rows_read"] == 1
    assert listing["revoked_count"] == 1


def test_a_revoked_binding_stops_being_the_active_one(bindings_db):
    repo_svc.insert_binding(connection=bindings_db, created_at=NOW, **_demo_row())
    repo_svc.revoke_binding(
        connection=bindings_db,
        organization_id=ORG,
        revoked_by_identity_id=VERIFIER,
        revoked_at=NOW,
    )
    active = repo_svc.get_active_binding(connection=bindings_db, organization_id=ORG)
    assert active["rows_read"] == 0
    assert "no_active_binding_for_this_organization" in active["blocked_reasons"]


def test_revocation_needs_a_revoker_identity():
    result = repo_svc.revoke_binding(organization_id=ORG)
    assert result["storage_allowed"] is False
    assert "revocation_without_a_revoker_identity" in result["blocked_reasons"]


def test_nothing_in_the_repository_deletes():
    source = Path(
        "src/nativeforge/services/tenant_customer_org_binding_repository_service.py"
    ).read_text(encoding="utf-8")
    assert "sa.delete" not in source
    assert ".delete()" not in source


# ------------------------------------------------- conflict


def test_a_conflict_authorizes_no_operational_write():
    result = repo_svc.prepare_insert(
        **_demo_row(binding_status="conflict", binding_source="human_entered")
    )
    assert result["storage_allowed"] is False
    assert (
        "conflict_binding_authorizes_no_operational_write" in result["blocked_reasons"]
    )


def test_marking_a_conflict_clears_the_verifier(bindings_db):
    """Whatever the row asserted is exactly what is in dispute."""
    repo_svc.insert_binding(connection=bindings_db, created_at=NOW, **_demo_row())
    repo_svc.mark_conflict(connection=bindings_db, organization_id=ORG, updated_at=NOW)
    row = bindings_db.execute(sa.select(repo_svc.BINDINGS)).mappings().first()
    assert row["binding_status"] == "conflict"
    assert row["verified_by_identity_id"] is None
    assert row["human_review_required"] is True


# ------------------------------------------------- authorization


def test_the_workflow_checks_authorization_before_anything_else():
    result = flow_svc.run_binding_workflow(
        operation="approve_pending",
        principal=_principal(["grants_manager"]),
        **_flow_row(),
    )
    assert result["authorization_checked"] is True
    assert result["authorization_allowed"] is False
    # The contract was never consulted for an unauthorized caller.
    assert result["binding_contract_valid"] is False
    assert result["repository_write_allowed"] is False


def test_a_grants_manager_may_inspect_but_may_not_approve(bindings_db):
    inspect = flow_svc.run_binding_workflow(
        operation="inspect_pending",
        principal=_principal(["grants_manager"]),
        organization_id=ORG,
        connection=bindings_db,
    )
    assert inspect["authorization_allowed"] is True

    approve = flow_svc.run_binding_workflow(
        operation="approve_pending",
        principal=_principal(["grants_manager"]),
        connection=bindings_db,
        **_flow_row(),
    )
    assert approve["authorization_allowed"] is False
    assert any(
        "role_cannot_verify_a_binding" in reason
        for reason in approve["blocked_reasons"]
    )


def test_an_auditor_may_inspect_but_may_not_approve():
    approve = flow_svc.run_binding_workflow(
        operation="approve_pending",
        principal=_principal(["auditor"]),
        **_flow_row(),
    )
    assert approve["authorization_allowed"] is False


def test_the_role_split_is_gate_111s_and_is_not_widened():
    """A test that fails if a later gate quietly adds a verifier role."""
    assert auth_svc.VERIFIER_ROLES == frozenset({"platform_admin", "tenant_admin"})
    assert auth_svc.INSPECTOR_ROLES == frozenset(
        {"platform_admin", "tenant_admin", "grants_manager", "auditor"}
    )


def test_a_tenant_admin_fixture_can_approve_a_demo_binding(bindings_db):
    result = flow_svc.run_binding_workflow(
        operation="approve_pending",
        principal=_principal(["tenant_admin"], demo=True),
        connection=bindings_db,
        **_flow_row(),
    )
    assert result["authorization_allowed"] is True
    assert result["repository_write_performed"] is True
    # And it binds nobody.
    assert result["verified_operational_binding"] is False
    assert flow_svc.workflow_invariant_failures(result) == []


def test_a_demo_principal_cannot_touch_a_production_binding():
    result = flow_svc.run_binding_workflow(
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"], demo=True),
        **_flow_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            verified_by_identity_id=VERIFIER,
            verified_at=VERIFIED_AT,
        ),
    )
    assert result["authorization_allowed"] is False


# ------------------------------------------------- the liveness boundary


def test_customer_auth_live_is_false_in_the_actual_environment():
    result = flow_svc.run_binding_workflow(
        operation="inspect_pending",
        principal=_principal(["tenant_admin"]),
        organization_id=ORG,
    )
    assert result["customer_auth_live"] is False
    assert result["login_live"] is False


def test_auth_not_live_blocks_an_operational_verified_binding(bindings_db):
    result = flow_svc.run_binding_workflow(
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"]),
        connection=bindings_db,
        **_flow_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            binding_confidence="verified",
            verified_by_identity_id=VERIFIER,
            verified_at=VERIFIED_AT,
        ),
    )
    assert result["authorization_allowed"] is True
    assert result["binding_contract_valid"] is True
    # Authorized and valid, and still no row: a production verified binding
    # written while nobody can be authenticated is an assertion with nothing
    # behind it.
    assert result["repository_write_allowed"] is False
    assert result["repository_write_performed"] is False
    assert result["verified_operational_binding"] is False
    assert (
        "production_verified_binding_requires_live_customer_auth"
        in result["blocked_reasons"]
    )


def test_the_operational_branch_is_reachable_with_auth_injected(bindings_db):
    """Reachable, so every refusal above it is falsifiable."""
    result = flow_svc.run_binding_workflow(
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"]),
        connection=bindings_db,
        customer_auth_live=True,
        login_live=True,
        **_flow_row(
            binding_status="verified_binding",
            binding_source="admin_verified",
            binding_confidence="verified",
            verified_by_identity_id=VERIFIER,
            verified_at=VERIFIED_AT,
        ),
    )
    assert result["repository_write_performed"] is True
    assert result["verified_operational_binding"] is True
    assert result["blocked_reasons"] == []
    assert flow_svc.workflow_invariant_failures(result) == []


def test_a_verified_binding_needs_the_organization_row_to_classify_it():
    """Gate 137D's refusal, reached against a database with no organizations.

    `verified_binding_workflow_service` passes
    `is_demo=bool(principal["is_demo_principal"])` - a principal's
    self-description choosing an organization's RLS partition. For a verified
    binding that is not good enough, and an unclassifiable organization is
    refused rather than admitted on the caller's word.
    """
    engine = sa.create_engine("sqlite://")
    repo_svc.BINDINGS.create(engine)
    with engine.begin() as conn:
        result = flow_svc.run_binding_workflow(
            operation="create_verified_binding",
            principal=_principal(["tenant_admin"]),
            connection=conn,
            customer_auth_live=True,
            login_live=True,
            **_flow_row(
                binding_status="verified_binding",
                binding_source="admin_verified",
                binding_confidence="verified",
                verified_by_identity_id=VERIFIER,
                verified_at=VERIFIED_AT,
            ),
        )
    engine.dispose()

    assert result["repository_write_performed"] is False
    assert result["verified_operational_binding"] is False
    assert (
        f"repository:{repo_svc.VERIFIED_NEEDS_CLASSIFICATION}"
        in result["blocked_reasons"]
    )


def test_a_demo_organization_refuses_a_verified_binding_whatever_the_principal_says():
    """The hole Gate 137A measured, closed at the write path every caller uses.

    The principal says `is_demo_principal: False`; the organization row says
    demo. The row wins, and the row is what pairs with the RLS predicate.
    """
    engine = sa.create_engine("sqlite://")
    repo_svc.BINDINGS.create(engine)
    _ORGANIZATIONS.create(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.insert(_ORGANIZATIONS).values(
                id=uuid.UUID(ORG),
                org_type="demo",
                seat_cap=5,
                created_at=datetime(2026, 9, 2, tzinfo=UTC),
            )
        )
        result = flow_svc.run_binding_workflow(
            operation="create_verified_binding",
            principal=_principal(["tenant_admin"]),
            connection=conn,
            customer_auth_live=True,
            login_live=True,
            **_flow_row(
                binding_status="verified_binding",
                binding_source="admin_verified",
                binding_confidence="verified",
                verified_by_identity_id=VERIFIER,
                verified_at=VERIFIED_AT,
            ),
        )
        written = conn.execute(
            sa.select(sa.func.count()).select_from(repo_svc.BINDINGS)
        ).scalar_one()
    engine.dispose()

    assert result["repository_write_performed"] is False
    assert written == 0
    assert (
        "repository:demo_fixture_cannot_be_a_verified_binding"
        in result["blocked_reasons"]
    )
    assert f"repository:{repo_svc.IS_DEMO_MISMATCH}" in result["blocked_reasons"]


def test_an_operational_binding_claimed_without_auth_is_an_invariant_failure():
    forged = dict(
        flow_svc.run_binding_workflow(
            operation="inspect_pending",
            principal=_principal(["tenant_admin"]),
            organization_id=ORG,
        )
    )
    forged["verified_operational_binding"] = True
    fails = flow_svc.workflow_invariant_failures(forged)
    assert "an_operational_binding_claimed_while_auth_is_not_live" in fails


# ------------------------------------------------- readiness


def test_a_lane_reports_a_repository_only_where_one_can_be_reached():
    """Gate 120's defect, restated so it cannot need editing every gate.

    The original hard-coded the lanes expected to be false, which made it a
    record of which repositories existed in August rather than a check that the
    detector agrees with reality. Gate 124 built the awarded grants repository
    and the list went stale the same week.

    Derived instead: a lane may report a repository exactly when one is
    reachable - a `repositories/<name>.py` file, or a mapped module that
    imports. That still catches the Gate 120 defect in both directions, a
    repository built as a service going undetected and a lane flipping without
    one.
    """
    import importlib.util
    from pathlib import Path

    matrix = cap_svc.build_capability_matrix()
    lanes = {row["capability"]: row for row in matrix["rows"]}

    binding = lanes["identity_binding_persistence"]
    assert binding["repository_available"] is True
    assert binding["write_path_available"] is True
    # And it is still not operational.
    assert binding["operational"] is False

    def reachable(name):
        if Path(
            f"src/nativeforge/repositories/{cap_svc.CAPABILITY_REPOSITORIES[name]}.py"
        ).is_file():
            return True
        module = cap_svc.CAPABILITY_REPOSITORY_MODULES.get(name)
        if not module:
            return False
        try:
            return importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            return False

    for name, lane in lanes.items():
        assert lane["repository_available"] is reachable(name), name


def test_a_repository_does_not_make_customer_persistence_live():
    matrix = cap_svc.build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    assert all(not row["operational"] for row in matrix["rows"])


def test_binding_store_readiness_separates_schema_repository_and_write_path():
    readiness = readiness_svc.build_binding_store_readiness()
    assert readiness["store_schema_available"] is True
    assert readiness["repository_available"] is True
    assert readiness["workflow_available"] is True
    assert readiness["write_path_available"] is True
    # Three facts that are true, and the two that are not.
    assert readiness["store_writable"] is False
    assert readiness["operational_verified_binding"] is False
    assert readiness["operational_binding_storage_ready"] is False
    assert readiness_svc.readiness_invariant_failures(readiness) == []


def test_the_spine_reports_the_repository_without_recommending_past_auth():
    decision = spine_svc.build_persistence_spine_decision()
    assert decision["identity_binding_repository_available"] is True
    assert decision["verified_binding_workflow_available"] is True
    assert decision["verified_operational_binding"] is False
    # Auth still blocks every lane, so it is still the recommendation.
    assert (
        decision["next_gate_recommendation"]["recommendation"]
        == "customer_authentication"
    )
    assert decision["customer_persistence_live"] is False


def test_the_guard_still_refuses_and_now_says_a_repository_exists():
    result = guard_svc.evaluate_persistence_write(
        operation="write_identity_binding",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
    )
    assert result["write_allowed"] is False
    assert result["binding_repository_available"] is True
    # The refusal has moved from "nothing can write one" to "nobody can verify".
    assert "no_repository_can_store_a_verified_binding" not in result["blocked_reasons"]


# ------------------------------------------------- the fixture set


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_workflow_demo_fixture_set()
    assert fixture["case_count"] == 8
    assert fixture["workflow_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.workflow_demo_invariant_failures(fixture) == []


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_workflow_cases(
        [{"case": "inspect_pending_with_grants_manager"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 7


def test_no_fixture_case_produces_an_operational_binding():
    fixture = fixtures.build_workflow_demo_fixture_set()
    assert fixture["operational_binding_count"] == 0
    assert fixture["production_verified_bindings_created"] == 0
    assert fixture["real_customer_rows_written"] == 0
    for row in fixture["cases"]:
        assert row["verified_operational_binding"] is False
        assert row["customer_auth_live"] is False


def test_the_fixture_set_is_deterministic():
    first = fixtures.build_workflow_demo_fixture_set()
    second = fixtures.build_workflow_demo_fixture_set()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------- the artifacts


def _artifact(name: str) -> str:
    return (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_workflow_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_the_written_set_is_four_files_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_workflow_artifacts(repo_root=tmp)
    assert result["file_count"] == 4
    assert result["credential_fields_found"] == []
    assert result["label_anchors_found"] == []
    assert result["configured_secret_values_found"] == []
    assert art.workflow_artifact_invariant_failures(result) == []


def test_the_label_anchor_scanner_can_actually_fail():
    """A scanner that cannot fire proves nothing about the files it passed."""
    planted = {"organization_id": fixtures.FIXTURE_PREFIX + "tenant"}
    assert art.scan_for_label_as_anchor(planted) == ["label_used_as_organization_id"]


def test_no_artifact_carries_customer_data():
    for path in Path(art.ARTIFACT_DIR).iterdir():
        text = path.read_text(encoding="utf-8")
        for forbidden in art.FORBIDDEN_VALUE_FIELDS:
            assert f'"{forbidden}":' not in text, f"{forbidden} in {path.name}"


def test_a_planted_secret_never_reaches_an_artifact(monkeypatch):
    planted = "planted-oidc-secret-that-must-never-be-written-to-a-file"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)
    with tempfile.TemporaryDirectory() as tmp:
        art.write_workflow_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert planted not in path.read_text(encoding="utf-8")


def test_the_writer_refuses_rather_than_writing_a_partial_set(monkeypatch):
    monkeypatch.setattr(
        art, "scan_for_label_as_anchor", lambda payload: ["label_used_as_rls_anchor"]
    )
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="refusing to write"):
            art.write_workflow_artifacts(repo_root=tmp)
        assert not (Path(tmp) / art.ARTIFACT_DIR).exists()


def test_the_declaration_refuses_every_liveness_claim():
    declaration = art.build_workflow_declaration()
    for claim in (
        "verified_operational_binding",
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        assert declaration[claim] is False
    assert declaration["production_verified_bindings_created"] == 0
    assert declaration["real_customer_rows_written"] == 0
    assert declaration["binding_lane_operational"] is False
    assert declaration["missing_auth_gates"]


def test_the_workflow_matrix_has_a_row_per_case():
    import csv as csv_module
    import io as io_module

    text = _artifact("verified_binding_workflow_matrix.csv")
    rows = list(csv_module.DictReader(io_module.StringIO(text)))
    assert len(rows) == 8
    assert list(rows[0]) == list(art.MATRIX_COLUMNS)


def test_no_matrix_row_claims_an_operational_binding():
    """Parsed by column, not by substring — a reader scans the column."""
    import csv as csv_module
    import io as io_module

    text = _artifact("verified_binding_workflow_matrix.csv")
    rows = list(csv_module.DictReader(io_module.StringIO(text)))
    assert rows, "the matrix is empty"
    for row in rows:
        assert row["verified_operational_binding"] == "false", row["case"]
        assert row["customer_auth_live"] == "false", row["case"]
        assert row["authorization_checked"] == "true", row["case"]


# ------------------------------------------------- vocabulary is bridged


def test_the_repository_bridges_gate_109s_vocabulary_rather_than_restating_it():
    source = Path(
        "src/nativeforge/services/tenant_customer_org_binding_repository_service.py"
    ).read_text(encoding="utf-8")
    # Imported, not redefined.
    assert "BINDING_STATUSES = frozenset" not in source
    assert "BINDING_SOURCES = frozenset" not in source
    assert repo_svc.TABLE_NAME == store_svc.STORE_TABLE


def test_alembic_head_is_unchanged_by_this_gate():
    contract = art.build_repository_contract()
    assert contract["alembic_head"] == "0041"
    assert contract["migration_revision"] == "0029"
