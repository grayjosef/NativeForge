"""Gate 112: OIDC claim to organization_id resolution.

Gate 111 found the claim path terminates at `organization_profile_id` — a
String(128) with no foreign key, on a table with no RLS. Gate 110 established
that `organization_id` is what every policy enforces on.

These tests hold three rules:

```text
a profile id is never promoted to an organization id
an organization claim says which; membership says they belong - both, or no RLS
the dev header is contained today and is still not production-safe
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
from nativeforge.services import (
    customer_auth_principal_contract_service as principals,
)
from nativeforge.services import (
    customer_org_membership_verification_service as membership,
)
from nativeforge.services import dev_org_header_containment_service as containment
from nativeforge.services import (
    oidc_organization_id_resolution_service as resolution,
)
from nativeforge.services import (
    oidc_organization_resolution_artifact_service as art,
)
from nativeforge.services import (
    oidc_organization_resolution_demo_fixture_service as fx,
)
from nativeforge.services import rls_context_claim_guard_service as claims
from nativeforge.services import tenant_beta_readiness_service as beta_readiness
from nativeforge.services import (
    tenant_nofo_digest_readiness_service as digest_readiness,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ORG_UUID = "11111111-2222-3333-4444-555555555555"
PROFILE_ID = "org-profile-123"


def _member(organization_id=ORG_UUID, role="org_admin", **overrides):
    record = {
        "organization_id": organization_id,
        "state": "active",
        "role": role,
    }
    record.update(overrides)
    return [record]


def _resolve(**overrides):
    kwargs = {
        "subject": "subject-1",
        "auth_source": "oidc",
        "claims_verified": True,
        "organization_claim_value": ORG_UUID,
        "membership_records": _member(),
    }
    kwargs.update(overrides)
    return resolution.resolve_organization_id_from_claims(**kwargs)


# ------------------------------------------- a profile id is not an org id


def test_organization_profile_id_alone_cannot_set_rls():
    result = _resolve(
        organization_claim_value=None,
        organization_profile_id=PROFILE_ID,
        membership_records=None,
    )
    assert result["resolution_status"] == "resolved_profile_only"
    assert result["rls_context_allowed"] is False
    assert result["resolved_organization_id"] is None
    assert resolution.resolution_invariant_failures(result) == []


def test_organization_profile_id_is_never_promoted():
    """Carried as evidence, never as the answer."""
    result = _resolve(
        organization_claim_value=None,
        organization_profile_id=PROFILE_ID,
        membership_records=None,
    )
    assert result["organization_profile_id"] == PROFILE_ID
    assert result["resolved_organization_id"] != PROFILE_ID

    forged = json.loads(json.dumps(result))
    forged["resolved_organization_id"] = PROFILE_ID
    assert "organization_profile_id_promoted_to_organization_id" in (
        resolution.resolution_invariant_failures(forged)
    )


def test_an_organization_claim_that_is_really_a_profile_id_is_refused():
    """The shape of what the current mapper actually produces."""
    result = _resolve(
        organization_claim_value=PROFILE_ID,
        organization_profile_id=PROFILE_ID,
        membership_records=None,
    )
    assert result["rls_context_allowed"] is False
    assert result["resolved_organization_id"] is None


def test_organization_id_must_be_uuid_shaped():
    result = _resolve(organization_claim_value="not-a-uuid", membership_records=None)
    assert result["resolution_status"] == "unresolved_invalid_uuid"
    assert result["rls_context_allowed"] is False


def test_an_invalid_uuid_cannot_be_forced_to_resolve():
    forged = _resolve(organization_claim_value="not-a-uuid", membership_records=None)
    forged["resolved_organization_id"] = "not-a-uuid"
    forged["rls_context_allowed"] = True
    failures = resolution.resolution_invariant_failures(forged)
    assert "rls_permitted_under_a_blocking_status" in failures
    assert "rls_permitted_for_a_non_uuid_organization_id" in failures


# ------------------------------------------- verification order


def test_verified_claims_are_required_for_organization_resolution():
    result = _resolve(claims_verified=False)
    assert result["resolution_status"] == "unresolved_unverified_claims"
    assert result["rls_context_allowed"] is False
    assert result["resolved_organization_id"] is None


def test_rls_cannot_be_permitted_on_unverified_claims():
    forged = _resolve(claims_verified=False)
    forged["rls_context_allowed"] = True
    assert "rls_permitted_on_unverified_claims" in (
        resolution.resolution_invariant_failures(forged)
    )


def test_verified_membership_is_required_for_rls_context():
    result = _resolve(membership_records=None)
    assert result["resolution_status"] == "unresolved_membership_missing"
    assert result["membership_verified"] is False
    assert result["rls_context_allowed"] is False


def test_a_membership_for_a_different_organization_does_not_count():
    result = _resolve(
        membership_records=_member(
            organization_id="22222222-2222-4222-8222-222222222222"
        )
    )
    assert result["rls_context_allowed"] is False


def test_a_revoked_membership_blocks_rls():
    result = _resolve(membership_records=_member(revoked_at="2026-01-15"))
    assert result["membership_verified"] is False
    assert result["rls_context_allowed"] is False


def test_conflicting_profile_and_organization_values_block_resolution():
    result = _resolve(
        organization_claim_value=PROFILE_ID,
        organization_profile_id=PROFILE_ID,
        membership_records=None,
    )
    assert result["resolution_status"] == "conflict"
    assert "profile_id_and_organization_claim_conflict" in result["blocked_reasons"]


def test_the_permitted_path_is_reachable():
    """Every other test shows a refusal; this shows the contract can say yes."""
    result = _resolve()
    assert result["resolution_status"] == "resolved_verified_organization_id"
    assert result["resolved_organization_id"] == ORG_UUID
    assert result["membership_verified"] is True
    assert result["rls_context_allowed"] is True
    assert resolution.resolution_invariant_failures(result) == []


def test_a_demo_resolution_does_not_imply_production_auth():
    result = _resolve(auth_source="demo_fixture")
    assert result["resolution_status"] == "resolved_demo_fixture"
    assert result["rls_context_allowed"] is False
    assert result["customer_auth_live"] is False


def test_a_demo_resolution_cannot_be_forced_to_permit_rls():
    forged = _resolve(auth_source="demo_fixture")
    forged["rls_context_allowed"] = True
    failures = resolution.resolution_invariant_failures(forged)
    assert "demo_resolution_permitted_rls" in failures


def test_a_partial_resolution_can_never_carry_rls(monkeypatch):
    """Defence in depth, made observable.

    `rls_context_allowed` checks both the status and the resolved value's shape.
    A partial status never carries a resolved value, so the status conjunct is
    unreachable against real inputs and a mutation widening it survives. Force a
    partial status that does carry one.
    """
    forged = _resolve(
        organization_claim_value=None,
        organization_profile_id=PROFILE_ID,
        membership_records=None,
    )
    assert forged["resolution_status"] == "resolved_profile_only"
    forged["resolved_organization_id"] = ORG_UUID
    forged["rls_context_allowed"] = True
    failures = resolution.resolution_invariant_failures(forged)
    assert "partial_resolution_permitted_rls:resolved_profile_only" in failures
    assert "organization_id_resolved_under_a_blocking_status:resolved_profile_only" in (
        failures
    )


def test_resolution_contacts_no_provider_and_sets_no_context():
    result = _resolve()
    assert result["identity_provider_contacted"] is False
    assert result["current_org_id_set"] is False
    assert result["persisted"] is False


# ------------------------------------------- membership verification


def test_a_verified_member_may_set_rls_but_not_verify_bindings():
    result = membership.verify_membership(
        organization_id=ORG_UUID,
        membership_source="nf_org_memberships",
        membership_records=_member(role="grant_lead"),
    )
    assert result["membership_status"] == "verified_member"
    assert result["can_set_rls_context"] is True
    assert result["can_verify_binding"] is False


def test_a_verified_admin_may_do_both():
    result = membership.verify_membership(
        organization_id=ORG_UUID,
        membership_source="nf_org_memberships",
        membership_records=_member(role="org_admin"),
    )
    assert result["membership_status"] == "verified_admin"
    assert result["can_set_rls_context"] is True
    assert result["can_verify_binding"] is True


def test_binder_authority_cannot_be_claimed_by_a_member():
    forged = membership.verify_membership(
        organization_id=ORG_UUID,
        membership_source="nf_org_memberships",
        membership_records=_member(role="grant_lead"),
    )
    forged["can_verify_binding"] = True
    assert "binder_authority_permitted_under_status:verified_member" in (
        membership.membership_invariant_failures(forged)
    )


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        ([{"organization_id": ORG_UUID, "state": "pending"}], "pending_member"),
        ([], "missing_membership"),
        (
            [
                {
                    "organization_id": ORG_UUID,
                    "state": "active",
                    "revoked_at": "2026-01-15",
                }
            ],
            "revoked",
        ),
    ],
)
def test_blocking_membership_states_permit_nothing(records, expected):
    result = membership.verify_membership(
        organization_id=ORG_UUID,
        membership_source="nf_org_memberships",
        membership_records=records,
    )
    assert result["membership_status"] == expected
    assert result["can_set_rls_context"] is False
    assert result["can_verify_binding"] is False
    assert membership.membership_invariant_failures(result) == []


def test_a_demo_membership_is_not_production_membership():
    result = membership.verify_membership(
        organization_id="nf-demo-org-01",
        membership_source="demo_fixture",
        membership_records=[],
    )
    assert result["membership_status"] == "demo_fixture"
    assert result["is_production_membership"] is False
    assert result["can_set_rls_context"] is False


def test_membership_requires_a_uuid_organization_id():
    result = membership.verify_membership(
        organization_id=PROFILE_ID,
        membership_source="nf_org_memberships",
        membership_records=[],
    )
    assert result["can_set_rls_context"] is False
    assert any(
        "organization_id_is_not_a_uuid" in reason
        for reason in result["blocked_reasons"]
    )


def test_a_matching_record_for_a_non_uuid_organization_still_gets_no_rls():
    """The shape check must hold even when the membership itself is fine.

    With an empty record list the missing-membership branch blocks first, so the
    UUID conjunct is unreachable. Supply a record that matches a profile-shaped
    organization and only the shape check is left standing.
    """
    result = membership.verify_membership(
        organization_id=PROFILE_ID,
        membership_source="nf_org_memberships",
        membership_records=_member(organization_id=PROFILE_ID, role="org_admin"),
    )
    assert result["membership_status"] == "verified_admin"
    assert result["membership_verified"] is True
    assert result["can_set_rls_context"] is False
    assert result["can_verify_binding"] is False


def test_membership_records_for_another_organization_do_not_match():
    """Matched on organization_id, never on 'a record exists'."""
    result = membership.verify_membership(
        organization_id=ORG_UUID,
        membership_source="nf_org_memberships",
        membership_records=_member(
            organization_id="99999999-9999-4999-8999-999999999999",
            role="org_admin",
        ),
    )
    assert result["membership_records_matched"] == 0
    assert result["membership_status"] == "missing_membership"
    assert result["can_set_rls_context"] is False


# ------------------------------------------- integration with Gate 111


def test_authenticated_verified_org_requires_a_resolved_organization_id():
    """A profile-shaped org claim never reaches verified-org."""
    principal = principals.build_principal(
        subject="s-1",
        auth_source="oidc",
        claims_verified=True,
        org_claim_verified=True,
        organization_id=PROFILE_ID,
        roles=["tenant_admin"],
    )
    assert principal["auth_status"] == "authenticated_unverified_org"
    assert principal["rls_context_allowed"] is False


def test_rls_context_requires_verified_membership():
    """Gate 112's tightening of the Gate 111 principal contract."""
    without = principals.build_principal(
        subject="s-2",
        auth_source="oidc",
        claims_verified=True,
        org_claim_verified=True,
        organization_id=ORG_UUID,
        roles=["tenant_admin"],
    )
    assert without["auth_status"] == "authenticated_verified_org"
    assert without["rls_context_allowed"] is False

    with_membership = principals.build_principal(
        subject="s-2",
        auth_source="oidc",
        claims_verified=True,
        org_claim_verified=True,
        organization_id=ORG_UUID,
        roles=["tenant_admin"],
        membership_verified=True,
    )
    assert with_membership["rls_context_allowed"] is True


def test_tenant_id_still_cannot_set_app_current_org_id():
    principal = principals.build_principal(
        subject="s-3",
        auth_source="oidc",
        claims_verified=True,
        org_claim_verified=True,
        organization_id=ORG_UUID,
        roles=["tenant_admin"],
        membership_verified=True,
    )
    result = claims.evaluate_rls_context_claim(
        principal=principal,
        claimed_identity_name="tenant_id",
        claimed_identity_value=ORG_UUID,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False


def test_customer_org_id_still_cannot_set_the_context_directly():
    principal = principals.build_principal(
        subject="s-4",
        auth_source="oidc",
        claims_verified=True,
        org_claim_verified=True,
        organization_id=ORG_UUID,
        roles=["tenant_admin"],
        membership_verified=True,
    )
    result = claims.evaluate_rls_context_claim(
        principal=principal,
        claimed_identity_name="customer_org_id",
        claimed_identity_value=ORG_UUID,
        claim_source="verified_auth_claim",
    )
    assert result["set_current_org_allowed"] is False


# ------------------------------------------- dev header containment


def test_the_dev_header_is_not_customer_auth():
    result = containment.build_dev_header_containment()
    assert result["dev_header_is_customer_auth"] is False
    assert result["dev_header_name"] == "X-NF-Org-Id"


def test_the_dev_header_is_never_production_safe():
    result = containment.build_dev_header_containment()
    assert result["production_safe"] is False
    assert result["must_disable_before_customer_auth"] is True
    assert result["must_replace_with_auth_claim_guard"] is True
    assert containment.containment_invariant_failures(result) == []


def test_production_safe_cannot_be_claimed():
    forged = containment.build_dev_header_containment()
    forged["production_safe"] = True
    assert "dev_header_claimed_production_safe" in (
        containment.containment_invariant_failures(forged)
    )


def test_containment_is_measured_not_asserted():
    """Containment and production-safety are different questions."""
    result = containment.build_dev_header_containment()
    assert result["backend_unit_active"] is False
    assert result["backend_loopback_only"] is True
    assert result["tunnel_routes_backend"] is False
    assert result["backend_publicly_exposed"] is False
    # Contained today, and still not safe.
    assert result["contained_by_deployment_posture"] is True
    assert result["production_safe"] is False


def test_containment_disagreeing_with_its_measurements_fails():
    forged = containment.build_dev_header_containment()
    forged["contained_by_deployment_posture"] = False
    assert "containment_disagrees_with_the_measurements" in (
        containment.containment_invariant_failures(forged)
    )


def _write_backend_unit(root: Path, host: str) -> None:
    unit = root / "deploy" / "systemd" / "nativeforge-backend.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(
        "[Service]\n"
        f"ExecStart=/usr/bin/uvicorn nativeforge.main:app --host {host} --port 8000\n",
        encoding="utf-8",
    )


def test_the_loopback_detector_can_answer_no(tmp_path):
    """The detector must fire on a unit that does not bind loopback.

    The real unit does, so a detector hardcoded to True would pass every other
    assertion here.
    """
    _write_backend_unit(tmp_path, "0.0.0.0")
    result = containment.build_dev_header_containment(detect_root=tmp_path)
    assert result["backend_loopback_only"] is False
    assert result["contained_by_deployment_posture"] is False
    assert "backend_unit_does_not_bind_loopback_only" in result["blocked_reasons"]
    assert containment.containment_invariant_failures(result) == []


def test_the_loopback_detector_answers_yes_for_a_loopback_unit(tmp_path):
    _write_backend_unit(tmp_path, "127.0.0.1")
    result = containment.build_dev_header_containment(detect_root=tmp_path)
    assert result["backend_loopback_only"] is True


def test_containment_turns_false_when_the_tunnel_routes_the_backend(tmp_path):
    """Containment is computed from exposure, not assumed."""
    _write_backend_unit(tmp_path, "127.0.0.1")
    config = tmp_path / "ops" / "cloudflared" / "config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "ingress:\n  - hostname: nf.example.invalid\n    service: http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    result = containment.build_dev_header_containment(detect_root=tmp_path)
    assert result["tunnel_routes_backend"] is True
    assert result["backend_publicly_exposed"] is True
    assert result["contained_by_deployment_posture"] is False
    assert result["production_safe"] is False
    assert "backend_reachable_from_outside_loopback" in result["blocked_reasons"]
    assert containment.containment_invariant_failures(result) == []


def test_a_tunnel_routed_backend_must_be_reported_as_exposed():
    forged = containment.build_dev_header_containment()
    forged["tunnel_routes_backend"] = True
    forged["backend_publicly_exposed"] = False
    assert "tunnel_routed_backend_not_reported_as_exposed" in (
        containment.containment_invariant_failures(forged)
    )


# ------------------------------------------- readiness


def test_customer_auth_and_login_remain_false():
    declaration = art.build_resolution_declaration()
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


# ------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_resolution_case():
    fixture = fx.build_resolution_demo_fixture_set()
    assert fixture["resolution_cases_missing"] == []
    assert set(fixture["resolution_cases_covered"]) == fx.REQUIRED_RESOLUTION_CASES


def test_exactly_one_fixture_case_reaches_an_rls_context():
    fixture = fx.build_resolution_demo_fixture_set()
    permitted = [
        row for row in fixture["resolution_rows"] if row["rls_context_allowed"]
    ]
    assert len(permitted) == 1
    assert permitted[0]["case"] == "verified_uuid_org_with_membership"


def test_the_fixture_creates_no_users_sessions_or_provider_calls():
    fixture = fx.build_resolution_demo_fixture_set()
    for constant in (
        "customer_auth_live",
        "login_live",
        "real_user_data",
        "real_sessions_created",
        "identity_provider_contacted",
        "secrets_stored",
        "current_org_id_set",
    ):
        assert fixture[constant] is False
    assert fx.resolution_demo_invariant_failures(fixture) == []


def test_resolution_case_coverage_is_measured_not_asserted():
    assert fx.measure_resolution_cases([]) == set()
    partial = fx.measure_resolution_cases(
        [{"case": "verified_profile_only"}, {"case": "revoked_membership"}]
    )
    assert partial == {"verified_profile_only", "revoked_membership"}
    assert "verified_uuid_org_with_membership" not in partial


# ------------------------------------------- artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    art.write_resolution_artifacts(repo_root=tmp_path / "a")
    art.write_resolution_artifacts(repo_root=tmp_path / "b")
    for name in (
        "oidc_organization_id_resolution_contract.json",
        "oidc_organization_id_resolution_matrix.csv",
        "customer_org_membership_verification_matrix.csv",
        "dev_org_header_containment_summary.json",
        "oidc_organization_resolution_demo_fixtures.json",
        "oidc_organization_id_resolution_readiness_summary.md",
    ):
        first = (tmp_path / "a" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        second = (tmp_path / "b" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert first == second


def test_committed_artifacts_match_fresh_generation(tmp_path):
    art.write_resolution_artifacts(repo_root=tmp_path)
    for name in (
        "oidc_organization_id_resolution_contract.json",
        "oidc_organization_id_resolution_matrix.csv",
        "customer_org_membership_verification_matrix.csv",
        "dev_org_header_containment_summary.json",
        "oidc_organization_resolution_demo_fixtures.json",
        "oidc_organization_id_resolution_readiness_summary.md",
    ):
        fresh = (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_the_contract_artifact_states_the_required_facts():
    payload = json.loads(
        (
            REPO_ROOT
            / art.ARTIFACT_DIR
            / "oidc_organization_id_resolution_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["oidc_organization_id_resolution_contract_available"] is True
    assert payload["organization_id_required_for_rls"] is True
    for key in (
        "organization_profile_id_is_rls_authority",
        "customer_auth_live",
        "login_live",
        "dev_header_production_safe",
        "binding_store_built",
        "verified_operational_binding",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        assert payload[key] is False


def test_the_resolution_matrix_artifact_permits_only_a_resolved_uuid():
    path = (
        REPO_ROOT / art.ARTIFACT_DIR / "oidc_organization_id_resolution_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["rls_context_allowed"] == "true":
            assert row["resolution_status"] == "resolved_verified_organization_id"
            assert row["organization_id_shape"] == "uuid"
            assert row["membership_verified"] == "true"
            assert row["claims_verified"] == "true"


def test_the_membership_matrix_artifact_separates_member_from_admin():
    path = (
        REPO_ROOT
        / art.ARTIFACT_DIR
        / "customer_org_membership_verification_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["can_verify_binding"] == "true":
            assert row["membership_status"] == "verified_admin"


def test_the_dev_header_artifact_states_it_is_not_production_safe():
    payload = json.loads(
        (
            REPO_ROOT / art.ARTIFACT_DIR / "dev_org_header_containment_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["production_safe"] is False
    assert payload["dev_header_is_customer_auth"] is False
    assert payload["must_replace_with_auth_claim_guard"] is True


def test_the_summary_states_the_refusals():
    text = (
        REPO_ROOT
        / art.ARTIFACT_DIR
        / "oidc_organization_id_resolution_readiness_summary.md"
    ).read_text(encoding="utf-8")
    for line in (
        "organization_profile_id_is_rls_authority",
        "organization_id_required_for_rls",
        "dev_header_production_safe",
        "customer_auth_live",
        "beta_onboarding_ready",
    ):
        assert line in text


def test_artifact_invariants_pass():
    declaration = art.build_resolution_declaration()
    assert art.resolution_artifact_invariant_failures(declaration) == []
