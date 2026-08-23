"""Tests: Gate 61 membership directory + storage path.

Two themes:

  1. **Nothing claims production storage.** The adapter is in-memory and says so.
  2. **The full chain is required.** A verified token is not membership; a
     membership record is not a trusted membership; a trusted membership without
     a trusted role source is not a role; and a role still does not bypass a
     blocked production gate.
"""

from __future__ import annotations

import base64
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from nativeforge.services.api_enforcement_service import (
    build_request_enforcement_context,
    enforce_capability,
)
from nativeforge.services.membership_directory_service import (
    ACTING_STATES,
    DENYING_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
    UNTRUSTED_MEMBERSHIP_SOURCES,
    InMemoryMembershipDirectory,
    build_membership_record,
    membership_record_invariant_failures,
    resolve_trusted_membership,
    storage_backend_status,
    storage_status_invariant_failures,
)
from nativeforge.services.oidc_token_verification_service import verify_oidc_token
from nativeforge.services.request_identity_service import (
    identity_from_cloudflare_access,
    identity_from_verified_token,
)

ISSUER = "https://nf-test.example.auth0.com/"
AUDIENCE = "nativeforge-api-test"
KID = "nf-g61-key"
NOW = 1_800_000_000
SUBJECT = "auth0|member-1"
ORG_A = "org-aaaa"
ORG_B = "org-bbbb"


def _b64u(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def keypair() -> dict[str, Any]:
    """In-process RSA keypair. TEST ONLY, never persisted or printed."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = private.public_key().public_numbers()
    return {
        "private": private,
        "jwks": {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": KID,
                    "n": _b64u(nums.n),
                    "e": _b64u(nums.e),
                }
            ]
        },
    }


@pytest.fixture
def verified_identity(keypair: dict) -> dict[str, Any]:
    token = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": SUBJECT,
            "email": "member@example.org",
            "email_verified": True,
            "iat": NOW - 60,
            "nbf": NOW - 60,
            "exp": NOW + 3600,
        },
        keypair["private"],
        algorithm="RS256",
        headers={"kid": KID},
    )
    v = verify_oidc_token(
        token=token,
        jwks=keypair["jwks"],
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        now=NOW,
    )
    assert v["verified"] is True, v["failure_reason"]
    return identity_from_verified_token(verification=v)


def _active_record(**kw: Any) -> dict[str, Any]:
    base = dict(
        subject=SUBJECT,
        organization_profile_id=ORG_A,
        role="grant_lead",
        state="active",
        membership_source="verified_directory",
        role_source="membership_record",
        email="member@example.org",
        email_verified=True,
        approved_by="owner-1",
        created_at="2026-08-01",
    )
    base.update(kw)
    return build_membership_record(**base)


# ───────────────────────── storage honesty ─────────────────────────


def test_storage_approval_absent_means_production_storage_not_live() -> None:
    s = storage_backend_status()
    assert s["production_storage_live"] is False
    assert s["approval_token_present"] is False
    assert s["customer_persistence_claimed"] is False
    assert s["membership_schema_exists"] is False
    assert storage_status_invariant_failures(s) == []


def test_approved_backend_without_token_is_still_not_live() -> None:
    s = storage_backend_status(
        backend_state="approved_production_backend", approval_token_present=False
    )
    assert s["production_storage_live"] is False
    assert storage_status_invariant_failures(s) == []


def test_token_without_approved_backend_is_still_not_live() -> None:
    s = storage_backend_status(
        backend_state="in_memory_test_adapter", approval_token_present=True
    )
    assert s["production_storage_live"] is False
    assert storage_status_invariant_failures(s) == []


def test_in_memory_adapter_does_not_claim_production_persistence() -> None:
    d = InMemoryMembershipDirectory()
    assert d.storage_backend_state == "in_memory_test_adapter"
    s = d.status()
    assert s["storage_backend_state"] == "in_memory_test_adapter"
    assert s["production_storage_live"] is False
    assert s["customer_persistence_claimed"] is False
    assert s["live_customer_membership_lookup"] is False


def test_adapter_name_is_not_production_or_live() -> None:
    name = InMemoryMembershipDirectory.__name__.lower()
    assert "production" not in name
    assert "live" not in name
    assert "inmemory" in name


def test_every_membership_record_disclaims_persistence() -> None:
    r = _active_record()
    assert r["production_storage_live"] is False
    assert r["customer_persistence_claimed"] is False
    assert r["persisted"] is False
    assert membership_record_invariant_failures(r) == []


# ───────────────── verified identity alone is not membership ─────────────────


def test_verified_oidc_identity_alone_cannot_act(
    verified_identity: dict,
) -> None:
    assert verified_identity["verification_trusted"] is True
    assert verified_identity["membership_trusted"] is False
    assert verified_identity["may_act_as_customer"] is False

    d = resolve_trusted_membership(
        identity=verified_identity,
        organization_profile_id=ORG_A,
        directory=InMemoryMembershipDirectory(),
    )
    assert d["allowed"] is False
    assert "no_membership_record" in d["blocked_reasons"]
    assert d["trusted_role"] is None
    assert d["audit_event"]["persisted"] is False


def test_no_directory_at_all_denies(verified_identity: dict) -> None:
    d = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=None
    )
    assert d["allowed"] is False
    assert d["storage_backend_state"] == "no_backend"


def test_membership_in_a_different_org_does_not_grant_access(
    verified_identity: dict,
) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(organization_profile_id=ORG_B))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False
    assert "no_membership_record" in r["blocked_reasons"]


# ───────────────────── the happy path, and only it ─────────────────────


def test_active_trusted_membership_maps_role(verified_identity: dict) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record())
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is True, r["blocked_reasons"]
    assert r["trusted_role"] == "grant_lead"
    assert r["membership_state"] == "active"
    assert r["production_storage_live"] is False
    assert r["customer_login_live_claimed"] is False
    assert r["live_customer_membership_lookup"] is False


def test_trusted_role_flows_into_enforce_capability(
    verified_identity: dict,
) -> None:
    """The point of the whole chain: a trusted role reaching a capability check."""
    d = InMemoryMembershipDirectory()
    d.put(_active_record(role="grant_lead"))
    m = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert m["allowed"] is True

    ctx = build_request_enforcement_context(
        requesting_org_id=ORG_A,
        actor_id=str(verified_identity["subject"]),
        actor_role=str(m["trusted_role"]),
        membership_state="active",
    )
    granted = enforce_capability(context=ctx, capability="assemble_evidence")
    assert granted["allowed"] is True

    # grant_lead still cannot certify org facts — role is not omnipotence.
    denied = enforce_capability(context=ctx, capability="certify_org_facts")
    assert denied["allowed"] is False


@pytest.mark.parametrize("source", sorted(TRUSTED_MEMBERSHIP_SOURCES))
def test_each_trusted_source_can_grant_when_active(
    source: str, verified_identity: dict
) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(membership_source=source, approved_by="approver-1"))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is True, (source, r["blocked_reasons"])


# ───────────────────────── denial paths ─────────────────────────


@pytest.mark.parametrize("state", sorted(DENYING_STATES))
def test_non_active_membership_states_deny(
    state: str, verified_identity: dict
) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(state=state))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False, state
    assert r["trusted_role"] is None


def test_revoked_at_forces_revoked_regardless_of_claimed_state() -> None:
    r = _active_record(state="active", revoked_at="2026-08-10")
    assert r["state"] == "revoked"
    assert r["membership_trusted"] is False
    assert membership_record_invariant_failures(r) == []


def test_expiry_is_derived_against_supplied_now() -> None:
    r = _active_record(state="active", expires_at="2026-01-01", now="2026-08-23")
    assert r["state"] == "expired"
    assert r["membership_trusted"] is False
    assert r["role_trusted"] is False


@pytest.mark.parametrize("source", sorted(UNTRUSTED_MEMBERSHIP_SOURCES))
def test_untrusted_membership_sources_deny(
    source: str, verified_identity: dict
) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(membership_source=source))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False, source
    assert any("membership_source_not_trusted" in x for x in r["blocked_reasons"])


def test_email_domain_alone_denies(verified_identity: dict) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(membership_source="email_domain_only"))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False


def test_approval_requiring_source_without_approver_is_untrusted() -> None:
    for src in ("operator_approved", "org_owner_approved"):
        r = _active_record(membership_source=src, approved_by=None)
        assert r["membership_source"] == "unknown", src
        assert r["membership_trusted"] is False


@pytest.mark.parametrize(
    "role_source", ["token_claim", "client_header", "email_domain"]
)
def test_untrusted_role_sources_deny_role(
    role_source: str, verified_identity: dict
) -> None:
    """An IdP role claim is not our directory. Only membership_record is trusted."""
    d = InMemoryMembershipDirectory()
    d.put(_active_record(role_source=role_source))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False, role_source
    assert "role_not_trusted" in r["blocked_reasons"]


def test_operator_internal_cannot_become_customer_authority(
    verified_identity: dict,
) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record(role="operator_internal"))
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False
    assert "internal_role_cannot_hold_customer_authority" in r["blocked_reasons"]

    rec = _active_record(role="operator_internal")
    assert rec["is_internal_role"] is True
    assert rec["role_trusted"] is False
    assert membership_record_invariant_failures(rec) == []


def test_unknown_role_is_not_mapped() -> None:
    r = _active_record(role="supreme_admin")
    assert r["role"] is None
    assert r["role_trusted"] is False


# ───────────── Cloudflare Access and client headers stay out ─────────────


def test_cloudflare_access_identity_cannot_become_customer_membership() -> None:
    ident = identity_from_cloudflare_access(access_email="op@example.com")
    d = InMemoryMembershipDirectory()
    # Even with an otherwise-valid record present, the identity is not verified.
    d.put(_active_record(subject="op@example.com"))
    r = resolve_trusted_membership(
        identity=ident, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False
    assert "identity_verification_not_trusted" in r["blocked_reasons"]


def test_client_supplied_role_and_org_are_denied(verified_identity: dict) -> None:
    """A client header cannot manufacture membership or role."""
    d = InMemoryMembershipDirectory()
    d.put(
        _active_record(
            membership_source="client_header", role_source="client_header"
        )
    )
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is False
    assert r["trusted_role"] is None


# ───────────────── production boundary stays where it was ─────────────────


def test_customer_login_live_remains_false(verified_identity: dict) -> None:
    d = InMemoryMembershipDirectory()
    d.put(_active_record())
    r = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert r["allowed"] is True
    assert r["customer_login_live_claimed"] is False
    assert verified_identity["customer_login_live_claimed"] is False


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
def test_pilot_and_production_gates_remain_blocked(
    capability: str, verified_identity: dict
) -> None:
    """A fully trusted org_owner still cannot flip a production gate."""
    d = InMemoryMembershipDirectory()
    d.put(_active_record(role="org_owner"))
    m = resolve_trusted_membership(
        identity=verified_identity, organization_profile_id=ORG_A, directory=d
    )
    assert m["allowed"] is True
    ctx = build_request_enforcement_context(
        requesting_org_id=ORG_A,
        actor_id=SUBJECT,
        actor_role="org_owner",
        membership_state="active",
    )
    r = enforce_capability(context=ctx, capability=capability)
    assert r["allowed"] is False
    assert "capability_permanently_blocked_at_this_stage" in r["blocked_reasons"]


def test_acting_states_is_only_active() -> None:
    assert ACTING_STATES == frozenset({"active"})
