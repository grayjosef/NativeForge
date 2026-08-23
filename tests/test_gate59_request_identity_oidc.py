"""Tests: Gate 59 request identity + OIDC Mode B readiness.

The theme is that every step of the chain is independently required:

    verified identity -> membership -> role -> capability -> (not) production gate

Breaking any single link denies, and no link can be supplied by the client.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from nativeforge.api.request_identity import (
    ROLE_ASSERTION_HEADERS,
    reject_role_assertion_headers,
    require_customer_identity,
    resolve_request_identity,
)
from nativeforge.services.api_enforcement_service import (
    build_request_enforcement_context,
    enforce_capability,
)
from nativeforge.services.oidc_readiness_service import (
    build_oidc_readiness,
    oidc_readiness_invariant_failures,
)
from nativeforge.services.request_identity_service import (
    build_request_identity,
    evaluate_customer_action,
    identity_from_cloudflare_access,
    request_identity_invariant_failures,
)

OIDC_ENV = (
    "OIDC_ISSUER",
    "OIDC_AUDIENCE",
    "OIDC_JWKS_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "NATIVEFORGE_OIDC_ISSUER",
    "NATIVEFORGE_OIDC_AUDIENCE",
    "NATIVEFORGE_OIDC_JWKS_URL",
    "NATIVEFORGE_OIDC_CLIENT_ID",
)


@pytest.fixture
def no_oidc_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in OIDC_ENV:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def full_oidc_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in OIDC_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OIDC_ISSUER", "https://example.auth0.com/")
    monkeypatch.setenv("OIDC_AUDIENCE", "nativeforge-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://example.auth0.com/.well-known/jwks.json")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-abc")


# ───────────────────────── OIDC readiness ─────────────────────────


def test_missing_oidc_config_does_not_claim_login_live(no_oidc_env: None) -> None:
    r = build_oidc_readiness()
    assert r["readiness_state"] == "oidc_unconfigured"
    assert r["login_live_claimed"] is False
    assert r["customer_login_live_claimed"] is False
    assert r["ok"] is True, "default mode must not fail when OIDC is absent"
    assert oidc_readiness_invariant_failures(r) == []


def test_strict_oidc_readiness_fails_closed_when_config_missing(
    no_oidc_env: None,
) -> None:
    r = build_oidc_readiness(strict=True)
    assert r["ok"] is False
    assert r["strict_failure"] is True
    assert any("missing_required_config" in b for b in r["blocked_reasons"])
    assert oidc_readiness_invariant_failures(r) == []


def test_complete_config_is_still_not_verification(full_oidc_env: None) -> None:
    """Config presence must never be mistaken for a working login.

    Gate 60 implemented the verifier, so the blocking reason MOVED rather than
    disappearing: strict readiness now fails on missing live Auth0 proof instead
    of on a missing verifier. The invariant this test protects is unchanged —
    complete config alone never makes login live.
    """
    r = build_oidc_readiness(strict=True)
    assert r["config_complete"] is True
    assert r["token_verification_implemented"] is True, "Gate 60 implemented it"
    assert r["live_auth0_token_proven"] is False
    assert r["ok"] is False, "strict must fail while live Auth0 proof is absent"
    assert "live_auth0_token_not_proven" in r["blocked_reasons"]
    assert r["login_live_claimed"] is False
    assert r["customer_login_live_claimed"] is False
    assert r["readiness_state"] == "oidc_configured_unverified"
    assert oidc_readiness_invariant_failures(r) == []


def test_readiness_never_reports_verified_state(full_oidc_env: None) -> None:
    r = build_oidc_readiness()
    assert r["readiness_state"] != "oidc_verified"


def test_readiness_reports_presence_booleans_not_values(full_oidc_env: None) -> None:
    r = build_oidc_readiness()
    for _, v in r["config_present"].items():
        assert isinstance(v, bool)
    blob = str(r)
    assert "client-abc" not in blob, "config value leaked into the readiness record"
    assert "nativeforge-api" not in blob
    assert r["secret_values_read"] is False
    assert r["network_access_attempted"] is False
    assert r["jwks_fetched"] is False


def test_nativeforge_prefixed_env_alias_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k in OIDC_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NATIVEFORGE_OIDC_ISSUER", "https://example.auth0.com/")
    r = build_oidc_readiness()
    assert r["config_present"]["issuer"] is True
    assert r["config_source_keys"]["issuer"] == "NATIVEFORGE_OIDC_ISSUER"


# ───────────────────────── Cloudflare Access boundary ─────────────────────


def test_cloudflare_access_is_not_customer_login() -> None:
    ident = identity_from_cloudflare_access(access_email="op@example.com")
    assert ident["identity_state"] == "demo_operator"
    assert ident["verification_source"] == "cloudflare_access"
    assert ident["verification_trusted"] is False
    assert ident["may_act_as_customer"] is False
    assert ident["may_hold_customer_authority"] is False
    assert ident["cloudflare_access_is_customer_login"] is False
    assert ident["customer_login_live_claimed"] is False
    assert request_identity_invariant_failures(ident) == []


def test_demo_operator_cannot_become_customer_authority() -> None:
    ident = identity_from_cloudflare_access(access_email="op@example.com")
    d = evaluate_customer_action(
        identity=ident, action="official_package_approval"
    )
    assert d["allowed"] is False
    assert "verification_not_trusted" in d["blocked_reasons"]
    assert d["audit_event"]["persisted"] is False


# ───────────────────────── client-supplied claims ─────────────────────────


def test_client_supplied_role_is_never_trusted() -> None:
    ident = build_request_identity(
        identity_state="oidc_configured_unverified",
        asserted_role_claims=["org_owner", "authorized_representative"],
        oidc_configured=True,
    )
    assert ident["asserted_role_claims"] == [
        "org_owner",
        "authorized_representative",
    ]
    assert ident["client_asserted_role_trusted"] is False
    assert ident["verified_role"] is None
    assert ident["role_trusted"] is False
    assert request_identity_invariant_failures(ident) == []

    d = evaluate_customer_action(identity=ident, action="certify_official_org_facts")
    assert d["allowed"] is False
    assert "client_asserted_role_ignored" in d["blocked_reasons"]


def test_client_supplied_org_is_not_membership_proof() -> None:
    ident = build_request_identity(
        identity_state="oidc_configured_unverified",
        asserted_org_claims=["org-bbbb"],
        membership_source="client_asserted",
        verified_org_id="org-bbbb",
        oidc_configured=True,
    )
    assert ident["client_asserted_org_trusted"] is False
    assert ident["membership_trusted"] is False
    assert ident["verified_org_id"] is None, (
        "an org id from an untrusted source must not survive as verified"
    )
    assert request_identity_invariant_failures(ident) == []


def test_dev_header_membership_source_is_not_trusted() -> None:
    ident = build_request_identity(
        identity_state="oidc_verified",
        membership_source="dev_header",
        verification_source="oidc_token_signature",
        verified_org_id="org-aaaa",
        verified_role="org_owner",
        oidc_configured=True,
    )
    assert ident["membership_trusted"] is False
    assert ident["role_trusted"] is False
    assert ident["may_act_as_customer"] is False


def test_role_assertion_headers_are_rejected() -> None:
    for header in ROLE_ASSERTION_HEADERS:
        with pytest.raises(HTTPException) as e:
            reject_role_assertion_headers({header: "org_owner"})
        assert e.value.status_code == 400
        assert "may not be supplied by the client" in str(e.value.detail)


def test_benign_headers_are_not_rejected() -> None:
    reject_role_assertion_headers({"X-NF-Org-Id": str(uuid.uuid4())})


# ───────────────────────── identity state denials ─────────────────────────


@pytest.mark.parametrize(
    "state",
    [
        "anonymous",
        "demo_operator",
        "oidc_unconfigured",
        "oidc_configured_unverified",
        "invalid",
        "unknown",
    ],
)
def test_non_verified_states_deny_customer_actions(state: str) -> None:
    ident = build_request_identity(identity_state=state, oidc_configured=True)
    d = evaluate_customer_action(identity=ident, action="official_submission_readiness")
    assert d["allowed"] is False
    assert d["customer_login_live_claimed"] is False


def test_anonymous_cannot_access_customer_actions() -> None:
    ident = build_request_identity(identity_state="anonymous")
    d = evaluate_customer_action(identity=ident, action="read_workspace")
    assert d["allowed"] is False
    assert "identity_state_denies_customer_action:anonymous" in d["blocked_reasons"]


def test_unknown_identity_denies_by_default() -> None:
    ident = build_request_identity(identity_state="not_a_real_state")
    assert ident["identity_state"] == "unknown"
    d = evaluate_customer_action(identity=ident, action="read_workspace")
    assert d["allowed"] is False


def test_verified_claim_without_trusted_source_is_downgraded() -> None:
    ident = build_request_identity(
        identity_state="oidc_verified",
        verification_source="cloudflare_access",
        oidc_configured=True,
    )
    assert ident["identity_state"] == "oidc_configured_unverified"
    assert ident["verification_trusted"] is False


def test_verified_state_requires_oidc_configured() -> None:
    ident = build_request_identity(
        identity_state="oidc_verified",
        verification_source="oidc_token_signature",
        oidc_configured=False,
    )
    assert ident["identity_state"] == "oidc_unconfigured"


# ─────────────── the chain: verification -> membership -> role -> capability ───


def _verified_identity(**kw) -> dict:
    base = dict(
        identity_state="oidc_verified",
        subject="auth0|abc",
        verification_source="oidc_token_signature",
        membership_source="verified_directory",
        verified_org_id="org-aaaa",
        verified_role="org_admin",
        oidc_configured=True,
    )
    base.update(kw)
    return build_request_identity(**base)


def test_verified_identity_still_needs_membership() -> None:
    ident = _verified_identity(membership_source="none", verified_org_id=None)
    assert ident["verification_trusted"] is True
    assert ident["membership_trusted"] is False
    d = evaluate_customer_action(identity=ident, action="read_workspace")
    assert d["allowed"] is False
    assert "membership_not_trusted" in d["blocked_reasons"]


def test_membership_still_needs_role() -> None:
    ident = _verified_identity(verified_role=None)
    assert ident["membership_trusted"] is True
    assert ident["role_trusted"] is False
    d = evaluate_customer_action(identity=ident, action="read_workspace")
    assert d["allowed"] is False
    assert "role_not_trusted" in d["blocked_reasons"]


def test_full_chain_allows_then_role_still_needs_capability() -> None:
    ident = _verified_identity()
    assert ident["may_act_as_customer"] is True
    assert request_identity_invariant_failures(ident) == []

    d = evaluate_customer_action(identity=ident, action="read_workspace")
    assert d["allowed"] is True
    assert d["effective_role"] == "org_admin"

    # Having a trusted role is not having every capability. org_admin cannot
    # certify org facts.
    ctx = build_request_enforcement_context(
        requesting_org_id="org-aaaa",
        actor_id="auth0|abc",
        actor_role="org_admin",
        membership_state="active",
    )
    cap = enforce_capability(context=ctx, capability="certify_org_facts")
    assert cap["allowed"] is False


@pytest.mark.parametrize(
    "capability",
    [
        "controlled_customer_pilot_go",
        "production_rollout_go",
        "enable_login_live",
        "enable_production_storage",
        "declare_pen_test_passed",
        "final_submit_to_portal",
    ],
)
def test_capability_cannot_bypass_blocked_production_gates(capability: str) -> None:
    """Even a fully verified org_owner cannot flip a production gate."""
    ctx = build_request_enforcement_context(
        requesting_org_id="org-aaaa",
        actor_id="auth0|abc",
        actor_role="org_owner",
        membership_state="active",
    )
    d = enforce_capability(context=ctx, capability=capability)
    assert d["allowed"] is False
    assert "capability_permanently_blocked_at_this_stage" in d["blocked_reasons"]


def test_require_customer_identity_raises_for_untrusted_identity() -> None:
    ident = identity_from_cloudflare_access(access_email="op@example.com")
    with pytest.raises(HTTPException) as e:
        require_customer_identity(ident)
    assert e.value.status_code == 403


def test_require_customer_identity_passes_for_full_chain() -> None:
    decision = require_customer_identity(_verified_identity())
    assert decision["allowed"] is True


# ───────────────────────── request adapter behaviour ─────────────────────────


def test_resolver_treats_bearer_token_as_unverified(no_oidc_env: None) -> None:
    ident = resolve_request_identity(authorization="Bearer some.jwt.value")
    assert ident["identity_state"] == "oidc_unconfigured"
    assert ident["verification_trusted"] is False
    assert ident["may_act_as_customer"] is False


def test_resolver_records_but_does_not_trust_role_header(no_oidc_env: None) -> None:
    ident = resolve_request_identity(
        cf_access_email="op@example.com", x_nf_role="org_owner"
    )
    assert "org_owner" in ident["asserted_role_claims"]
    assert ident["role_trusted"] is False
    assert ident["client_asserted_role_trusted"] is False


def test_resolver_anonymous_when_no_headers(no_oidc_env: None) -> None:
    ident = resolve_request_identity()
    assert ident["identity_state"] == "anonymous"
    assert request_identity_invariant_failures(ident) == []


def test_x_nf_org_id_is_not_read_as_identity(no_oidc_env: None) -> None:
    """X-NF-Org-Id is demo/dev routing only and must not appear as membership."""
    ident = resolve_request_identity()
    assert ident["membership_source"] in {"none", "client_asserted"}
    assert ident["membership_trusted"] is False
    assert ident["verified_org_id"] is None
