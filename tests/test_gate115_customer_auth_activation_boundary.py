"""Gate 115: the customer authentication activation boundary.

Five services and one recurring question: **may customer auth be turned on?**

The answer is no, for twelve of fifteen gates. The hard part of testing that is
the same as in Gate 114 and inverted: a boundary that only ever refuses is
indistinguishable from a constant. So several tests forge the inputs and assert
the *permitted* branch is reachable — not as a claim that a provider exists, but
so the twelve refusals mean something.

Secrets get their own attention. `secret_present` is a boolean everywhere, three
independent leak scans run in the chain, and a test asserts that a value planted
in the environment never reaches an artifact.
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

from nativeforge.services import customer_auth_activation_artifact_service as art
from nativeforge.services import (
    customer_auth_activation_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import customer_auth_role_mapping_service as roles_svc
from nativeforge.services import customer_auth_route_readiness_service as routes_svc
from nativeforge.services import dev_org_header_shutdown_readiness_service as header

REPO_ROOT = Path(__file__).resolve().parents[1]

MAPPING = {
    "nf-platform-admins": "platform_admin",
    "nf-tenant-admins": "tenant_admin",
    "nf-grants-managers": "grants_manager",
    "nf-grants-viewers": "grants_viewer",
    "nf-auditors": "auditor",
}

SECURED_OPENAPI = {
    "paths": {
        "/v1/auth/login": {"get": {}},
        "/v1/auth/logout": {"post": {}},
        "/v1/auth/callback": {"get": {}},
        "/v1/auth/session": {"get": {"security": [{"nf_session": []}]}},
        "/v1/auth/me": {"get": {"security": [{"nf_session": []}]}},
    },
    "components": {"securitySchemes": {"nf_session": {"type": "apiKey"}}},
}

FULL_PREFLIGHT = {
    "validation_possible": True,
    "client_secret_present": True,
    "issuer_url_present": True,
    "audience_present": True,
    "jwks_reachable": True,
}
FULL_VALIDATION = {
    "provider_validated": True,
    "callback_session_validated": True,
    "invite_binding_passed": True,
    "org_binding_passed": True,
    "role_mapping_passed": True,
}


def _secured_routes():
    """A forged application that authenticates people.

    `customer_auth_live=True` is forged alongside the route table because Gate
    117 made organization-resolution enforcement depend on a principal being
    possible. Without it `ready_for_live_login: True` would be unreachable, and
    an unreachable branch makes every "not ready" claim unfalsifiable.
    """
    return routes_svc.build_route_readiness(
        openapi=SECURED_OPENAPI,
        cloudflare_access_in_front=False,
        customer_auth_live=True,
        # Gate 118 added a session signing key to the conjuncts. Forged here for
        # the same reason as customer_auth_live: the permitted branch has to be
        # reachable or the refusals prove nothing.
        session_signing_key_present=True,
    )


def _activated(**overrides):
    """A gate with everything satisfied. Forged; nothing here is configured."""
    kwargs = {
        "preflight": dict(FULL_PREFLIGHT),
        "validation": dict(FULL_VALIDATION),
        "route_readiness": _secured_routes(),
        "dev_header_disabled_for_production": True,
        "owner_approval": True,
        # Gate 119B added a sixteenth gate. Forged readiness, booleans only -
        # no key material appears in this file.
        "signing_key_readiness": fixtures.SIGNING_READY,
    }
    kwargs.update(overrides)
    return gate_svc.build_customer_auth_activation_gate(**kwargs)


# ------------------------------------------------- secrets


def test_secret_detection_is_boolean_only():
    result = gate_svc.build_customer_auth_activation_gate()
    assert isinstance(result["secret_present"], bool)
    assert result["secret_value_emitted"] is False
    assert result["secrets_stored"] is False


def test_a_planted_secret_never_reaches_the_gate_output(monkeypatch):
    """The check that matters most, exercised rather than asserted."""
    planted = "super-secret-value-that-must-never-appear-anywhere"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    result = gate_svc.build_customer_auth_activation_gate()
    blob = json.dumps(result)
    assert planted not in blob
    # Presence is still reported, as a boolean.
    assert isinstance(result["secret_present"], bool)


def test_a_planted_secret_never_reaches_an_artifact(monkeypatch, tmp_path):
    planted = "another-secret-value-nobody-should-ever-see-in-a-file"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    art.write_activation_artifacts(repo_root=tmp_path)
    for path in (tmp_path / art.ARTIFACT_DIR).iterdir():
        assert planted not in path.read_text(encoding="utf-8"), path.name


def test_the_leak_scanner_reports_key_names_not_values(monkeypatch):
    planted = "yet-another-secret-value-for-the-scanner-to-find"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    leaked = art.scan_for_secret_values({"oops": planted})
    assert leaked == ["OIDC_CLIENT_SECRET"]
    assert planted not in json.dumps(leaked)


def test_a_leak_invalidates_every_claim():
    forged = dict(_activated())
    forged["secret_value_emitted"] = True
    fails = gate_svc.activation_gate_invariant_failures(forged)
    assert "activation_gate_emitted_a_secret_value" in fails
    assert "claim_survived_a_secret_leak:customer_auth_live" in fails


# ------------------------------------------------- the activation gate


def test_the_actual_environment_is_not_auth_live():
    result = gate_svc.build_customer_auth_activation_gate()
    assert result["customer_auth_live"] is False
    assert result["login_live"] is False
    assert result["activation_allowed"] is False
    assert result["missing_auth_gates"]
    assert gate_svc.activation_gate_invariant_failures(result) == []


def test_a_missing_provider_blocks_activation():
    result = _activated(preflight={**FULL_PREFLIGHT, "validation_possible": False})
    assert result["provider_configured"] is False
    assert result["customer_auth_live"] is False
    assert "auth_gate_not_satisfied:provider_configured" in result["blocked_reasons"]


def test_a_missing_secret_blocks_activation():
    result = _activated(preflight={**FULL_PREFLIGHT, "client_secret_present": False})
    assert result["secret_present"] is False
    assert result["customer_auth_live"] is False
    assert "auth_gate_not_satisfied:secret_present" in result["blocked_reasons"]


def test_missing_jwks_validation_blocks_activation_and_says_it_was_unchecked():
    """Unvalidated is not the same fact as validated-and-failed."""
    result = _activated(
        preflight={**FULL_PREFLIGHT, "jwks_reachable": None},
        validation={**FULL_VALIDATION, "provider_validated": False},
    )
    assert result["issuer_jwks_validated"] is False
    assert result["customer_auth_live"] is False
    assert (
        "issuer_jwks_unvalidated_no_network_check_performed"
        in result["blocked_reasons"]
    )
    assert result["issuer_jwks_network_check_performed"] is False


def test_missing_callback_or_session_validation_blocks_login_live():
    result = _activated(
        validation={**FULL_VALIDATION, "callback_session_validated": False}
    )
    assert result["login_live"] is False
    assert result["customer_auth_live"] is False


def test_missing_org_binding_blocks_activation():
    result = _activated(validation={**FULL_VALIDATION, "org_binding_passed": False})
    assert result["customer_auth_live"] is False
    assert "auth_gate_not_satisfied:org_binding_passed" in result["blocked_reasons"]


def test_missing_role_mapping_blocks_activation():
    result = _activated(validation={**FULL_VALIDATION, "role_mapping_passed": False})
    assert result["customer_auth_live"] is False
    assert "auth_gate_not_satisfied:role_mapping_passed" in result["blocked_reasons"]


def test_organization_id_resolution_is_required():
    result = gate_svc.build_customer_auth_activation_gate()
    assert "organization_id_resolution_available" in gate_svc.REQUIRED_AUTH_GATES
    assert result["organization_id_resolution_available"] is True

    forged = dict(_activated())
    forged["organization_id_resolution_available"] = False
    assert (
        "customer_auth_live_without:organization_id_resolution_available"
        in gate_svc.activation_gate_invariant_failures(forged)
    )


def test_membership_verification_is_required():
    assert "membership_verification_available" in gate_svc.REQUIRED_AUTH_GATES
    forged = dict(_activated())
    forged["membership_verification_available"] = False
    assert (
        "customer_auth_live_without:membership_verification_available"
        in gate_svc.activation_gate_invariant_failures(forged)
    )


def test_the_dev_header_blocks_auth_activation_but_not_login():
    """The pair that separates two easily-confused facts."""
    result = _activated(dev_header_disabled_for_production=False)
    assert result["login_live"] is True, "a login flow could still run"
    assert result["customer_auth_live"] is False, (
        "auth is not live while an unauthenticated header can set the RLS context"
    )
    assert gate_svc.activation_gate_invariant_failures(result) == []


def test_owner_approval_is_required_even_with_every_gate_satisfied():
    result = _activated(owner_approval=False)
    assert result["customer_auth_live"] is False
    assert (
        "owner_has_not_authorized_customer_auth_activation" in result["blocked_reasons"]
    )


def test_the_activated_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    result = _activated()
    assert result["customer_auth_live"] is True
    assert result["login_live"] is True
    assert result["activation_allowed"] is True
    assert result["blocked_reasons"] == []
    assert gate_svc.activation_gate_invariant_failures(result) == []


def test_every_unmet_gate_points_somewhere():
    result = gate_svc.build_customer_auth_activation_gate()
    pointed = {entry["gate"] for entry in result["next_required_actions"]}
    for name in result["missing_auth_gates"]:
        assert name in pointed, name


# ------------------------------------------------- route readiness


def test_the_applications_auth_routes_enforce_nothing():
    """Gate 115 asserted these routes did not exist. Gate 116 added them.

    The point of the original test was that readiness reflects reality rather
    than a constant, and that point survives the change: the five routes now
    exist, a security scheme is now declared, and **still** nothing is enforced
    and login is not ready. Deleting the test would have lost the assertion
    that matters; keeping the old assertion would have pinned reality to a
    state this gate deliberately moved past.
    """
    readiness = routes_svc.build_route_readiness()
    assert readiness["application_route_count"] > 100
    for field in routes_svc.REQUIRED_ROUTES:
        assert readiness[field] is True, field
    assert readiness["security_scheme_declared"] is True
    # Gate 117 attached the scheme to /current-user, which now refuses.
    assert readiness["secured_route_count"] == 1
    assert readiness["route_auth_enforced"] is True
    # And still nothing resolves an organization, so login is not ready.
    assert readiness["route_org_resolution_enforced"] is False
    assert readiness["ready_for_live_login"] is False


def test_route_existence_does_not_imply_enforcement():
    """Five auth routes that declare no security scheme enforce nothing."""
    unsecured = {
        "paths": {
            "/v1/auth/login": {"get": {}},
            "/v1/auth/logout": {"post": {}},
            "/v1/auth/callback": {"get": {}},
            "/v1/auth/session": {"get": {}},
            "/v1/auth/me": {"get": {}},
        },
        "components": {},
    }
    readiness = routes_svc.build_route_readiness(
        openapi=unsecured, cloudflare_access_in_front=False
    )
    assert all(readiness[f] for f in routes_svc.REQUIRED_ROUTES)
    assert readiness["route_auth_enforced"] is False
    assert readiness["ready_for_live_login"] is False
    assert "no_security_scheme_is_declared_anywhere" in readiness["blocked_reasons"]


def test_cloudflare_access_is_not_customer_app_auth():
    readiness = routes_svc.build_route_readiness()
    assert readiness["cloudflare_access_is_customer_auth"] is False
    assert "cloudflare_access_is_not_customer_app_auth" in readiness["blocked_reasons"]

    forged = dict(readiness)
    forged["cloudflare_access_is_customer_auth"] = True
    assert (
        "route_readiness_claimed:cloudflare_access_is_customer_auth"
        in routes_svc.route_readiness_invariant_failures(forged)
    )


def test_the_frontend_preview_is_not_backend_login():
    readiness = routes_svc.build_route_readiness()
    assert readiness["frontend_preview_is_backend_login"] is False
    assert readiness["dev_header_is_customer_auth"] is False


def test_the_swagger_oauth_helper_is_not_a_callback_route():
    """It is FastAPI's own, and counting it would make the gate lie."""
    readiness = routes_svc.build_route_readiness(
        openapi={"paths": {"/docs/oauth2-redirect": {"get": {}}}, "components": {}},
        cloudflare_access_in_front=False,
    )
    assert readiness["callback_route_available"] is False


def test_the_ready_for_login_branch_is_reachable():
    readiness = _secured_routes()
    assert readiness["ready_for_live_login"] is True
    assert routes_svc.route_readiness_invariant_failures(readiness) == []


# ------------------------------------------------- role mapping


def test_an_unknown_provider_role_grants_no_privilege():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["some-group-nobody-configured"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
    )
    assert result["least_privilege_role"] == "unknown"
    assert result["can_view_grants"] is False
    assert result["can_edit_grants"] is False
    assert result["can_verify_binding"] is False
    assert result["can_manage_persistence"] is False
    assert roles_svc.role_mapping_invariant_failures(result) == []


def test_a_claim_literally_named_platform_admin_grants_nothing_unmapped():
    """The provider controls that string. It is an assertion, not a grant."""
    result = roles_svc.map_provider_roles(
        provider_role_claims=["platform_admin"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
    )
    assert result["least_privilege_role"] == "unknown"
    assert result["mapping_status"] == "all_claims_unmapped"


def test_platform_admin_requires_an_explicit_configured_mapping():
    without = roles_svc.map_provider_roles(
        provider_role_claims=["nf-platform-admins"],
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert without["least_privilege_role"] == "unknown"
    assert without["mapping_status"] == "no_mapping_configured"

    with_mapping = roles_svc.map_provider_roles(
        provider_role_claims=["nf-platform-admins"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert with_mapping["least_privilege_role"] == "platform_admin"
    assert with_mapping["can_verify_binding"] is True


def test_tenant_admin_requires_an_explicit_configured_mapping():
    without = roles_svc.map_provider_roles(
        provider_role_claims=["nf-tenant-admins"],
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert without["least_privilege_role"] == "unknown"

    with_mapping = roles_svc.map_provider_roles(
        provider_role_claims=["nf-tenant-admins"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert with_mapping["least_privilege_role"] == "tenant_admin"


def test_grants_viewer_cannot_verify_a_binding():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-grants-viewers"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert result["least_privilege_role"] == "grants_viewer"
    assert result["can_verify_binding"] is False
    assert result["can_edit_grants"] is False
    assert result["can_view_grants"] is True


def test_auditor_cannot_verify_a_binding():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-auditors"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert result["least_privilege_role"] == "auditor"
    assert result["can_verify_binding"] is False
    assert result["can_edit_grants"] is False


def test_grants_manager_can_operate_but_not_verify():
    """Inspecting a binding is not verifying one."""
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-grants-managers"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert result["least_privilege_role"] == "grants_manager"
    assert result["can_edit_grants"] is True
    assert result["can_verify_binding"] is False
    assert "inspect_binding" in result["permissions"]
    assert "verify_binding" not in result["permissions"]


def test_several_claims_resolve_to_the_least_privileged():
    """One stale directory group must not silently widen access."""
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-platform-admins", "nf-grants-viewers"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=True,
        binder_authorized=True,
    )
    assert set(result["mapped_roles"]) == {"platform_admin", "grants_viewer"}
    assert result["least_privilege_role"] == "grants_viewer"
    assert result["can_verify_binding"] is False


def test_no_role_grants_anything_without_organization_resolution():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-platform-admins"],
        configured_mapping=MAPPING,
        organization_id_resolved=False,
        membership_verified=True,
        binder_authorized=True,
    )
    assert result["least_privilege_role"] == "platform_admin"
    assert result["can_view_grants"] is False
    assert result["can_verify_binding"] is False
    assert "organization_id_not_resolved_from_the_claims" in result["blocked_reasons"]


def test_no_role_grants_anything_without_verified_membership():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-platform-admins"],
        configured_mapping=MAPPING,
        organization_id_resolved=True,
        membership_verified=False,
        binder_authorized=True,
    )
    assert result["can_view_grants"] is False
    assert result["can_verify_binding"] is False
    assert "membership_not_verified_for_this_organization" in result["blocked_reasons"]


def test_a_mapping_pointing_at_a_nonexistent_role_grants_nothing():
    result = roles_svc.map_provider_roles(
        provider_role_claims=["nf-superusers"],
        configured_mapping={"nf-superusers": "god_mode"},
        organization_id_resolved=True,
        membership_verified=True,
    )
    assert result["least_privilege_role"] == "unknown"
    assert any("unknown_role" in r for r in result["blocked_reasons"])


def test_no_role_mapping_ever_sets_an_rls_context():
    for claims in ([], ["nf-platform-admins"], ["nf-auditors"]):
        result = roles_svc.map_provider_roles(
            provider_role_claims=claims,
            configured_mapping=MAPPING,
            organization_id_resolved=True,
            membership_verified=True,
            binder_authorized=True,
        )
        assert result["current_org_id_set"] is False


# ------------------------------------------------- dev header shutdown


def test_the_dev_header_is_no_longer_load_bearing():
    """This asserted `dev_header_used_by_routes > 0` until Gate 134.

    That was the honest state for nineteen gates: 207 routes across 14 modules
    obtained an organization from `X-NF-Org-Id`. Gate 134 converted all of them
    onto a session, so the count is zero - measured by walking `api/`, not
    declared, which is why this assertion can move at all.

    `safe_to_disable_now` still needs `auth_replacement_available`, and that is
    asserted below with the evidence that makes it reachable.
    """
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_used_by_routes"] == 0
    assert readiness["dev_header_route_modules"] == []
    # The chain that defines the header is not a consumer of it.
    assert set(readiness["dev_header_provider_modules"]) == {
        "deps_db.py",
        "isolation_deps.py",
    }
    assert header.shutdown_readiness_invariant_failures(readiness) == []


def test_a_returning_consumer_would_be_counted_again():
    """The zero above is measured, so it can go back up.

    Pointed at a directory where a module does use the dev-header chain, the
    detector counts it. Without this the zero could be a detector that stopped
    looking rather than a migration that finished.
    """
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as tmp:
        module = _Path(tmp) / "regressed_routes.py"
        module.write_text(
            "from nativeforge.api.deps_db import require_real_org_db\n"
            "@router.get('/x')\n"
            "def x(ctx=Depends(require_real_org_db)):\n"
            "    return {}\n",
            encoding="utf-8",
        )
        usage = header.detect_dev_header_route_usage(_Path(tmp))
    assert usage["module_count"] == 1
    assert usage["modules"] == ["regressed_routes.py"]


def test_the_replacement_becomes_available_once_a_principal_can_exist():
    """`safe_to_disable_now` is reachable, and only with the evidence.

    Gate 134F found the chain circular: `route_org_resolution_enforced` required
    `customer_auth_live`, which required the dev header gone, which required
    this. It asks for `a principal can exist` now - which Gate 132's binding
    evidence measures and Gate 133 proved in a browser.
    """
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )

    routes = build_route_readiness(
        principal_possible=True,
        session_signing_key_present=True,
        signing_key_readiness={"can_sign_production_session": True},
    )
    assert routes["ready_for_live_login"] is True

    readiness = header.build_dev_header_shutdown_readiness(auth_route_readiness=routes)
    assert readiness["dev_header_used_by_routes"] == 0
    assert readiness["auth_replacement_available"] is True
    assert readiness["safe_to_disable_now"] is True
    assert header.shutdown_readiness_invariant_failures(readiness) == []


def test_the_dev_header_must_never_reach_production_auth():
    """A boundary with no true branch, and an invariant that keeps it that way."""
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["must_disable_before_production_auth"] is True

    forged = dict(readiness)
    forged["must_disable_before_production_auth"] = False
    assert (
        "dev_header_permitted_to_survive_into_production_auth"
        in header.shutdown_readiness_invariant_failures(forged)
    )


def test_the_dev_header_is_not_customer_auth():
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_is_customer_auth"] is False
    assert readiness["dev_header_is_production_safe"] is False
    assert readiness["cloudflare_access_is_customer_auth"] is False


def test_the_safe_to_disable_branch_is_reachable():
    with tempfile.TemporaryDirectory() as tmp:
        readiness = header.build_dev_header_shutdown_readiness(
            api_dir=Path(tmp),
            dev_header_enabled=False,
            auth_route_readiness=_secured_routes(),
        )
        assert readiness["dev_header_used_by_routes"] == 0
        assert readiness["auth_replacement_available"] is True
        assert readiness["safe_to_disable_now"] is True
        assert readiness["must_disable_before_production_auth"] is True
        assert header.shutdown_readiness_invariant_failures(readiness) == []


def test_a_replacement_is_a_route_not_a_set_of_contracts():
    """Contracts existing is not somewhere a customer can authenticate."""
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["organization_id_resolution_available"] is True
    assert readiness["membership_verification_available"] is True
    assert readiness["rls_claim_guard_available"] is True
    assert readiness["replacement_route_available"] is False
    assert readiness["auth_replacement_available"] is False


# ------------------------------------------------- readiness surfaces


def test_every_lane_reads_auth_live_from_the_one_activation_gate():
    from nativeforge.services.customer_auth_live_detector_service import (
        detect_customer_auth_live,
        detect_login_live,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    assert detect_customer_auth_live() is False
    assert detect_login_live() is False
    assert build_capability_matrix()["customer_auth_live"] is False
    assert build_tenant_beta_readiness()["customer_auth_live"] is False


def test_customer_persistence_remains_false():
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )

    matrix = build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    assert matrix["operational_count"] == 0


def test_beta_onboarding_remains_false():
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    beta = build_tenant_beta_readiness()
    assert beta["ready_for_beta_onboarding"] is False
    assert beta["customer_auth_live"] is False


def test_operational_awarded_tracking_remains_false():
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    awarded = build_awarded_requirements_readiness()
    assert awarded["ready_for_operational_awarded_tracking"] is False
    assert awarded["customer_persistence_live"] is False


def test_operational_digest_remains_false():
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    digest = build_digest_readiness()
    assert digest.get("ready_for_operational_digest") is False
    assert digest["customer_persistence_live"] is False


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_activation_demo_fixture_set()
    # Nine as of Gate 119: the set gained a case isolating the signing key's
    # source, the way `dev_header_still_enabled` isolates one input.
    assert fixture["case_count"] == 9
    assert fixture["activation_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixtures.activation_demo_invariant_failures(fixture) == []


def test_the_fixture_set_creates_no_user_session_or_provider_call():
    fixture = fixtures.build_activation_demo_fixture_set()
    assert fixture["real_users_created"] is False
    assert fixture["real_sessions_created"] is False
    assert fixture["identity_provider_contacted"] is False
    assert fixture["network_calls"] is False
    assert fixture["secrets_stored"] is False
    assert fixture["secret_value_emitted"] is False


def test_exactly_one_fixture_case_activates():
    """Zero would make every refusal unfalsifiable."""
    fixture = fixtures.build_activation_demo_fixture_set()
    assert fixture["theoretical_activation_count"] == 1
    activated = [r["case"] for r in fixture["rows"] if r["customer_auth_live"]]
    assert activated == ["all_gates_pass"]


def test_the_theoretical_pass_does_not_describe_the_actual_environment():
    fixture = fixtures.build_activation_demo_fixture_set()
    assert fixture["customer_auth_live_in_actual_environment"] is False
    assert fixture["login_live_in_actual_environment"] is False

    forged = dict(fixture)
    forged["customer_auth_live_in_actual_environment"] = True
    assert (
        "fixture_set_reports_the_actual_environment_as_auth_live"
        in fixtures.activation_demo_invariant_failures(forged)
    )


def test_the_dev_header_fixture_separates_login_from_auth():
    fixture = fixtures.build_activation_demo_fixture_set()
    rows = {row["case"]: row for row in fixture["rows"]}
    both = rows["all_gates_pass"]
    header_on = rows["dev_header_still_enabled"]

    assert both["customer_auth_live"] is True
    assert header_on["customer_auth_live"] is False
    assert header_on["login_live"] is True


def test_a_dropped_case_is_reported_as_a_coverage_gap():
    short = fixtures.build_demo_activation_cases()[:-1]
    covered = fixtures.measure_activation_cases(short)
    assert fixtures.REQUIRED_ACTIVATION_CASES - covered == {"dev_header_still_enabled"}


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_six_artifacts_exist():
    for name in (
        "customer_auth_activation_gate.json",
        "customer_auth_route_readiness_matrix.csv",
        "customer_auth_role_mapping_matrix.csv",
        "dev_org_header_shutdown_readiness.json",
        "customer_auth_activation_demo_fixtures.json",
        "customer_auth_activation_readiness_summary.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_artifacts_regenerate_deterministically():
    with tempfile.TemporaryDirectory() as tmp:
        art.write_activation_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert path.read_text(encoding="utf-8") == _artifact(path.name), path.name


def test_regeneration_is_stable_across_repeated_runs():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        art.write_activation_artifacts(repo_root=a)
        art.write_activation_artifacts(repo_root=b)
        for path in (Path(a) / art.ARTIFACT_DIR).iterdir():
            other = Path(b) / art.ARTIFACT_DIR / path.name
            assert path.read_text(encoding="utf-8") == other.read_text(
                encoding="utf-8"
            ), path.name


def test_the_artifacts_state_every_fixed_claim():
    declaration = art.build_activation_declaration()
    for claim, expected in art.FIXED_CLAIMS.items():
        assert declaration[claim] is expected, claim
    for claim in art.MEASURED_CLAIMS:
        assert isinstance(declaration[claim], bool), claim


def test_the_gate_artifact_reports_auth_not_live():
    payload = json.loads(_artifact("customer_auth_activation_gate.json"))
    assert payload["customer_auth_live"] is False
    assert payload["login_live"] is False
    assert payload["activation_allowed"] is False
    assert payload["secret_value_emitted"] is False
    assert payload["network_calls"] is False
    assert payload["missing_auth_gates"]


def test_the_route_matrix_reports_enforcement_without_login_readiness():
    """Gate 116 added the routes; Gate 117 made one of them refuse.

    Authentication is enforced and organization resolution is not, which is the
    distinction that keeps a 401 from reading as a working login.
    """
    rows = list(
        csv.reader(io.StringIO(_artifact("customer_auth_route_readiness_matrix.csv")))
    )[1:]
    by_name = {row[0]: row for row in rows}
    for field in routes_svc.REQUIRED_ROUTES:
        assert by_name[field][2] == "true", field
    assert by_name["route_auth_enforced"][2] == "true"
    assert by_name["route_org_resolution_enforced"][2] == "false"
    assert by_name["route_role_mapping_enforced"][2] == "false"
    assert by_name["ready_for_live_login"][2] == "false"
    assert by_name["cloudflare_access_is_customer_auth"][2] == "false"


def test_the_role_matrix_never_grants_an_unknown_role():
    rows = list(
        csv.DictReader(io.StringIO(_artifact("customer_auth_role_mapping_matrix.csv")))
    )
    assert rows
    for row in rows:
        if row["least_privilege_role"] == "unknown":
            assert row["can_view_grants"] == "false"
            assert row["can_edit_grants"] == "false"
            assert row["can_verify_binding"] == "false"
        if row["least_privilege_role"] in {
            "grants_viewer",
            "auditor",
            "grants_manager",
        }:
            assert row["can_verify_binding"] == "false", row["least_privilege_role"]


def test_the_shutdown_artifact_keeps_the_boundary():
    payload = json.loads(_artifact("dev_org_header_shutdown_readiness.json"))
    assert payload["must_disable_before_production_auth"] is True
    assert payload["safe_to_disable_now"] is False
    assert payload["dev_header_is_customer_auth"] is False


def test_the_summary_says_what_is_not_live():
    summary = _artifact("customer_auth_activation_readiness_summary.md")
    plain = summary.replace("**", "")
    assert "Customer auth is not live and login is not live" in plain
    assert "Cloudflare Access" in summary
    assert "X-NF-Org-Id" in summary
    assert "No secret value appears" in summary
    assert "## What is true" in summary
    assert "## Claims this gate does not make" in summary


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_activation_declaration())
    declaration["customer_auth_live"] = True
    assert (
        "artifact_claim_wrong:customer_auth_live"
        in art.activation_artifact_invariant_failures(declaration)
    )

    declaration = dict(art.build_activation_declaration())
    declaration["secret_present"] = "a-secret-string"
    fails = art.activation_artifact_invariant_failures(declaration)
    assert "secret_present_is_not_a_boolean" in fails
