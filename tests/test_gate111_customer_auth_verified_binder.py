"""Gate 111: customer auth boundary and verified binder authorization.

Gate 110 named customer auth as the first blocked reason on the binding store:
a verified binding needs a verifier, and nobody can be one until a person can
authenticate.

These tests hold three rules:

```text
authenticated is not verified-org, because the claim path does not produce one
a demo principal verifies demo bindings and nothing else
only the RLS authority, verified, may set app.current_org_id
```
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import (
    awarded_grants_requirements_readiness_service as awarded_readiness,
)
from nativeforge.services import customer_auth_boundary_artifact_service as art
from nativeforge.services import customer_auth_demo_fixture_service as fx
from nativeforge.services import (
    customer_auth_principal_contract_service as principals,
)
from nativeforge.services import rls_context_claim_guard_service as claims
from nativeforge.services import tenant_beta_readiness_service as beta_readiness
from nativeforge.services import (
    tenant_nofo_digest_readiness_service as digest_readiness,
)
from nativeforge.services import verified_binder_authorization_service as binder

REPO_ROOT = Path(__file__).resolve().parents[1]

UUID_VALUE = "11111111-2222-3333-4444-555555555555"


def _oidc(role: str, **overrides):
    kwargs = {
        "subject": f"subject-{role}",
        "auth_source": "oidc",
        "claims_verified": True,
        "org_claim_verified": True,
        "organization_id": UUID_VALUE,
        "roles": [role],
    }
    kwargs.update(overrides)
    return principals.build_principal(**kwargs)


def _demo(role: str = "tenant_admin"):
    return principals.build_principal(
        subject=f"nf-demo-{role}",
        auth_source="demo_fixture",
        roles=[role],
        demo_label="demo_fixture",
    )


# ------------------------------------------------- what auth establishes


def test_demo_auth_is_not_production_auth():
    principal = _demo()
    assert principal["auth_status"] == "authenticated_demo"
    assert principal["is_production_authenticated"] is False
    assert principal["rls_context_allowed"] is False
    assert principals.principal_invariant_failures(principal) == []


def test_a_demo_principal_cannot_claim_production_authentication():
    forged = _demo()
    forged["is_production_authenticated"] = True
    forged["rls_context_allowed"] = True
    failures = principals.principal_invariant_failures(forged)
    assert "demo_principal_claimed_production_authentication" in failures
    assert "demo_principal_permitted_rls_context" in failures


def test_cloudflare_access_is_not_customer_app_auth():
    """Edge access controls who reaches the host, not who they may act for."""
    principal = principals.build_principal(
        subject="cf-subject",
        auth_source="cloudflare_access",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    assert principal["auth_status"] != "authenticated_verified_org"
    assert principal["rls_context_allowed"] is False
    assert "cloudflare_access_is_edge_access_not_app_auth" in (
        principal["blocked_reasons"]
    )


def test_edge_access_cannot_be_treated_as_verified_org_auth():
    forged = principals.build_principal(
        subject="cf-subject",
        auth_source="cloudflare_access",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    forged["auth_status"] = "authenticated_verified_org"
    assert "edge_access_treated_as_verified_org_auth" in (
        principals.principal_invariant_failures(forged)
    )


def test_authenticated_does_not_imply_verified_organization_membership():
    """The distinction the whole gate turns on."""
    principal = principals.build_principal(
        subject="oidc-subject",
        auth_source="oidc",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    assert principal["claims_verified"] is True
    assert principal["org_claim_verified"] is False
    assert principal["auth_status"] == "authenticated_unverified_org"
    assert principal["organization_membership_status"] == "unknown"


def test_an_org_claim_resolving_to_a_profile_string_is_not_verified():
    """The real shape of today's claim path.

    oidc_identity_mapper_service resolves to organization_profile_id - a
    String(128) with no foreign key on a table with no RLS. It is not the UUID
    the policies enforce on, so it cannot verify an organization.
    """
    principal = _oidc("tenant_admin", organization_id="org-profile-123")
    assert principal["auth_status"] == "authenticated_unverified_org"
    assert principal["org_claim_verified"] is False
    assert any(
        "org_claim_is_not_a_uuid_organization_id" in reason
        for reason in principal["blocked_reasons"]
    )


def test_organization_id_must_be_uuid_shaped_for_rls():
    """Gate 112 added membership as a second requirement, so it is supplied here.

    An organization claim says *which* organization was asserted; membership
    says the person belongs to it. Both are needed for an RLS context, and this
    test is about the shape half.
    """
    verified = _oidc("tenant_admin", membership_verified=True)
    assert verified["rls_context_allowed"] is True

    non_uuid = _oidc(
        "tenant_admin", organization_id="not-a-uuid", membership_verified=True
    )
    assert non_uuid["rls_context_allowed"] is False


def test_a_verified_org_claim_without_membership_gets_no_rls_context():
    """Gate 112: verified-org auth alone is not enough."""
    without = _oidc("tenant_admin")
    assert without["auth_status"] == "authenticated_verified_org"
    assert without["membership_verified"] is False
    assert without["rls_context_allowed"] is False
    assert "organization_membership_not_verified_for_rls" in (
        without["blocked_reasons"]
    )


def test_rls_cannot_be_claimed_without_verified_membership():
    forged = _oidc("tenant_admin")
    forged["rls_context_allowed"] = True
    assert "rls_context_permitted_without_verified_membership" in (
        principals.principal_invariant_failures(forged)
    )


def test_an_unverified_org_principal_holds_no_operational_permission():
    principal = principals.build_principal(
        subject="oidc-subject",
        auth_source="oidc",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    assert "verify_binding" not in principal["permissions"]
    assert "write_operational" not in principal["permissions"]
    assert "read_operational" not in principal["permissions"]


def test_a_revoked_principal_holds_nothing():
    principal = _oidc("platform_admin", revoked=True)
    assert principal["auth_status"] == "revoked"
    assert principal["permissions"] == []
    assert principal["rls_context_allowed"] is False


def test_role_mappings_cover_the_existing_vocabularies():
    """Bridged, not forked. If either source grows a role, this fails."""
    assert principals.role_mappings_are_complete()


def test_the_principal_contract_logs_nobody_in():
    principal = _oidc("tenant_admin")
    assert principal["customer_auth_live"] is False
    assert principal["login_live"] is False
    assert principal["session_created"] is False
    assert principal["identity_provider_contacted"] is False


# ------------------------------------------------- binder authorization


@pytest.mark.parametrize("role", ["platform_admin", "tenant_admin"])
def test_admins_can_verify_a_binding_when_org_is_verified(role):
    result = binder.authorize_binding_operation(
        principal=_oidc(role), binding_operation="create_verified_binding"
    )
    assert result["binding_authorized"] is True
    assert result["verifier_role"] == role
    assert binder.binder_authorization_invariant_failures(result) == []


def test_grants_manager_can_inspect_but_not_verify():
    principal = _oidc("grants_manager")
    inspect = binder.authorize_binding_operation(
        principal=principal, binding_operation="inspect_pending_binding"
    )
    verify = binder.authorize_binding_operation(
        principal=principal, binding_operation="create_verified_binding"
    )
    assert inspect["binding_authorized"] is True
    assert verify["binding_authorized"] is False
    assert "role_cannot_verify_a_binding" in verify["blocked_reasons"]


@pytest.mark.parametrize("role", ["grants_viewer", "auditor"])
def test_read_only_roles_cannot_verify(role):
    result = binder.authorize_binding_operation(
        principal=_oidc(role), binding_operation="create_verified_binding"
    )
    assert result["binding_authorized"] is False


def test_grants_viewer_cannot_even_inspect():
    result = binder.authorize_binding_operation(
        principal=_oidc("grants_viewer"), binding_operation="inspect_pending_binding"
    )
    assert result["binding_authorized"] is False


def test_an_unauthenticated_principal_cannot_verify():
    result = binder.authorize_binding_operation(
        principal=principals.build_principal(),
        binding_operation="create_verified_binding",
    )
    assert result["binding_authorized"] is False
    assert any("principal_not_usable" in r for r in result["blocked_reasons"])


def test_a_revoked_principal_cannot_verify():
    result = binder.authorize_binding_operation(
        principal=_oidc("platform_admin", revoked=True),
        binding_operation="create_verified_binding",
    )
    assert result["binding_authorized"] is False


def test_an_unverified_org_principal_cannot_verify():
    principal = principals.build_principal(
        subject="oidc-subject",
        auth_source="oidc",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    result = binder.authorize_binding_operation(
        principal=principal, binding_operation="create_verified_binding"
    )
    assert result["binding_authorized"] is False
    assert "production_verification_requires_authenticated_verified_org" in (
        result["blocked_reasons"]
    )


def test_a_demo_principal_may_verify_a_demo_binding_only():
    principal = _demo("tenant_admin")

    against_demo = binder.authorize_binding_operation(
        principal=principal,
        binding_operation="create_verified_binding",
        target_binding_status="demo_fixture",
    )
    against_production = binder.authorize_binding_operation(
        principal=principal, binding_operation="create_verified_binding"
    )

    assert against_demo["binding_authorized"] is True
    assert against_production["binding_authorized"] is False
    assert "demo_principal_cannot_touch_a_production_binding" in (
        against_production["blocked_reasons"]
    )


def test_a_demo_authorization_against_production_fails_its_invariants():
    forged = binder.authorize_binding_operation(
        principal=_demo("tenant_admin"),
        binding_operation="create_verified_binding",
        target_binding_status="demo_fixture",
    )
    forged["target_binding_status"] = None
    assert "demo_principal_authorized_against_a_production_binding" in (
        binder.binder_authorization_invariant_failures(forged)
    )


def test_production_verification_cannot_be_forged_without_verified_org():
    forged = binder.authorize_binding_operation(
        principal=_oidc("tenant_admin"), binding_operation="create_verified_binding"
    )
    forged["auth_status"] = "authenticated_unverified_org"
    forged["org_membership_verified"] = False
    failures = binder.binder_authorization_invariant_failures(forged)
    assert "production_verification_without_verified_org_auth" in failures
    assert "production_verification_without_verified_membership" in failures


def test_binder_authorization_does_not_create_a_binding():
    result = binder.authorize_binding_operation(
        principal=_oidc("platform_admin"),
        binding_operation="create_verified_binding",
    )
    assert result["binding_created"] is False
    assert result["binding_modified"] is False
    assert result["persisted"] is False


def test_an_unknown_binding_operation_is_refused():
    result = binder.authorize_binding_operation(
        principal=_oidc("platform_admin"), binding_operation="whatever"
    )
    assert result["binding_operation"] == "unknown"
    assert result["binding_authorized"] is False


# ------------------------------------------------- the RLS claim guard


def _verified_principal():
    return _oidc("tenant_admin")


def test_a_verified_organization_id_claim_may_set_the_context():
    """The permission path must be reachable, or the refusals prove nothing."""
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="organization_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is True
    assert claims.claim_guard_invariant_failures(result) == []


def test_tenant_id_can_never_set_app_current_org_id():
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="tenant_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False
    assert result["rls_context_allowed"] is False
    assert "tenant_id_can_never_set_app_current_org_id" in result["blocked_reasons"]


def test_a_forged_tenant_id_claim_fails_its_invariants():
    forged = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="tenant_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    forged["set_current_org_allowed"] = True
    assert "tenant_id_permitted_to_set_app_current_org_id" in (
        claims.claim_guard_invariant_failures(forged)
    )


def test_customer_org_id_cannot_set_the_context_directly():
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="customer_org_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False
    assert "customer_org_id_can_never_set_app_current_org_id" in (
        result["blocked_reasons"]
    )


def test_an_unverified_claim_cannot_set_the_context():
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="organization_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="unverified_claim",
    )
    assert result["set_current_org_allowed"] is False


def test_the_dev_request_header_is_not_an_authenticated_claim():
    """The one path in the tree that sets the context today.

    api/deps_db.py takes X-NF-Org-Id, an unauthenticated header, and calls
    apply_org_rls_gucs. Any future auth-driven path must not inherit that.
    """
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="organization_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="dev_request_header",
    )
    assert result["set_current_org_allowed"] is False
    assert "dev_request_header_is_not_an_authenticated_claim" in (
        result["blocked_reasons"]
    )


def test_a_claim_that_cannot_survive_a_uuid_cast_is_blocked():
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="organization_id",
        claimed_identity_value="org-profile-123",
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False
    assert any(
        "cannot_survive_a_uuid_cast" in reason for reason in result["blocked_reasons"]
    )


def test_a_demo_claim_cannot_set_a_production_context():
    result = claims.evaluate_rls_context_claim(
        principal=_demo(),
        claimed_identity_name="organization_id",
        claimed_identity_value="nf-demo-org-01",
        claim_source="demo_fixture",
    )
    assert result["set_current_org_allowed"] is False


def test_a_principal_without_a_verified_org_claim_cannot_set_the_context():
    unverified = principals.build_principal(
        subject="oidc-subject",
        auth_source="oidc",
        claims_verified=True,
        roles=["tenant_admin"],
    )
    result = claims.evaluate_rls_context_claim(
        principal=unverified,
        claimed_identity_name="organization_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False
    assert "principal_org_claim_not_verified" in result["blocked_reasons"]


def test_the_claim_guard_sets_nothing():
    result = claims.evaluate_rls_context_claim(
        principal=_verified_principal(),
        claimed_identity_name="organization_id",
        claimed_identity_value=UUID_VALUE,
        claim_source="verified_auth_claim",
    )
    assert result["current_org_id_set"] is False
    assert result["session_variable_written"] is False
    assert result["identity_derived"] is False


# ------------------------------------------------- readiness


def test_customer_auth_is_not_live():
    """Read from the existing promotion gate, not asserted here."""
    declaration = art.build_auth_boundary_declaration()
    assert declaration["customer_auth_live"] is False
    assert declaration["login_live"] is False
    assert declaration["login_promotion_gates_missing"]


def test_operational_awarded_tracking_remains_false():
    result = awarded_readiness.build_awarded_requirements_readiness()
    assert result["ready_for_operational_awarded_tracking"] is False


def test_operational_digest_remains_false():
    result = digest_readiness.build_digest_readiness()
    assert result["ready_for_operational_digest"] is False


def test_beta_onboarding_remains_false():
    result = beta_readiness.build_tenant_beta_readiness()
    assert result["ready_for_beta_onboarding"] is False
    assert result["customer_auth_live"] is False


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_principal_case():
    fixture = fx.build_demo_auth_fixture_set()
    assert fixture["principal_cases_missing"] == []
    assert set(fixture["principal_cases_covered"]) == fx.REQUIRED_PRINCIPAL_CASES


def test_every_demo_principal_is_labelled():
    fixture = fx.build_demo_auth_fixture_set()
    for principal in fixture["principals"]:
        assert principal["fixture_label"] == fx.FIXTURE_LABEL


def test_the_fixture_creates_no_users_sessions_or_provider_calls():
    fixture = fx.build_demo_auth_fixture_set()
    for constant in (
        "customer_auth_live",
        "login_live",
        "real_user_data",
        "real_sessions_created",
        "identity_provider_contacted",
        "credentials_stored",
    ):
        assert fixture[constant] is False
    assert fx.demo_auth_invariant_failures(fixture) == []


def test_no_demo_sourced_principal_is_authorized_against_production():
    fixture = fx.build_demo_auth_fixture_set()
    for row in fixture["production_binder_matrix"]["rows"]:
        if row["is_demo_principal"]:
            assert row["binding_authorized"] is False


def test_principal_case_coverage_is_measured_not_asserted():
    """Feed it a short set and it must notice."""
    assert fx.measure_principal_cases([]) == set()
    partial = fx.measure_principal_cases(
        [{"case": "revoked"}, {"case": "auditor"}]
    )
    assert partial == {"revoked", "auditor"}
    assert "verified_org_tenant_admin" not in partial


# ------------------------------------------------- artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    art.write_auth_boundary_artifacts(repo_root=tmp_path / "a")
    art.write_auth_boundary_artifacts(repo_root=tmp_path / "b")
    for name in (
        "customer_auth_principal_contract.json",
        "verified_binder_authorization_matrix.csv",
        "rls_context_claim_guard_matrix.csv",
        "customer_auth_demo_principals.json",
        "customer_auth_readiness_summary.md",
    ):
        first = (tmp_path / "a" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        second = (tmp_path / "b" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert first == second


def test_committed_artifacts_match_fresh_generation(tmp_path):
    art.write_auth_boundary_artifacts(repo_root=tmp_path)
    for name in (
        "customer_auth_principal_contract.json",
        "verified_binder_authorization_matrix.csv",
        "rls_context_claim_guard_matrix.csv",
        "customer_auth_demo_principals.json",
        "customer_auth_readiness_summary.md",
    ):
        fresh = (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_the_contract_artifact_states_the_required_facts():
    payload = json.loads(
        (
            REPO_ROOT / art.ARTIFACT_DIR / "customer_auth_principal_contract.json"
        ).read_text(encoding="utf-8")
    )
    for key in (
        "customer_auth_contract_available",
        "verified_binder_authorization_available",
        "rls_context_claim_guard_available",
    ):
        assert payload[key] is True
    for key in (
        "customer_auth_live",
        "login_live",
        "binding_store_built",
        "verified_operational_binding",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        assert payload[key] is False


def test_the_binder_matrix_artifact_never_authorizes_a_demo_verification(tmp_path):
    path = REPO_ROOT / art.ARTIFACT_DIR / "verified_binder_authorization_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["target_binding_status"] == "production" and row["auth_status"] == (
            "authenticated_demo"
        ):
            assert row["binding_authorized"] == "false"


def test_the_claim_matrix_artifact_permits_only_verified_uuid_authority():
    path = REPO_ROOT / art.ARTIFACT_DIR / "rls_context_claim_guard_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["set_current_org_allowed"] == "true":
            assert row["claimed_identity_name"] in {"organization_id", "org_id"}
            assert row["claimed_identity_shape"] == "uuid"
            assert row["claim_verified"] == "true"


def test_the_summary_states_what_is_not_live():
    text = (
        REPO_ROOT / art.ARTIFACT_DIR / "customer_auth_readiness_summary.md"
    ).read_text(encoding="utf-8")
    for line in (
        "customer_auth_live",
        "login_live",
        "tenant_id_can_set_current_org_id",
        "cloudflare_access_is_app_auth",
        "beta_onboarding_ready",
    ):
        assert line in text


def test_artifact_invariants_pass():
    declaration = art.build_auth_boundary_declaration()
    assert art.auth_artifact_invariant_failures(declaration) == []
