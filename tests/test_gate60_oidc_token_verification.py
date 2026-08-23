"""Tests: Gate 60 OIDC token verification.

The RSA keypair is **generated in-process** for each test session. No private
key is committed to the repo and none is printed. That also means the suite
needs no Auth0 credentials to prove the verification path works.

The theme is fail-closed: every malformed, mis-signed, mis-scoped or expired
token must be rejected with a specific state, and a verified token must still
prove nothing about membership, role or authority.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from nativeforge.services.oidc_readiness_service import (
    build_oidc_readiness,
    oidc_readiness_invariant_failures,
)
from nativeforge.services.oidc_token_verification_service import (
    ALLOWED_ALGORITHMS,
    fetch_jwks,
    token_verification_invariant_failures,
    verify_oidc_token,
)
from nativeforge.services.request_identity_service import (
    identity_from_cloudflare_access,
    identity_from_verified_token,
    request_identity_invariant_failures,
)

ISSUER = "https://nf-test.example.auth0.com/"
AUDIENCE = "nativeforge-api-test"
KID = "nf-test-key-1"
NOW = 1_800_000_000


def _b64u(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def keypair() -> dict[str, Any]:
    """Generate a throwaway RSA keypair. TEST ONLY, never persisted."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KID,
                "n": _b64u(numbers.n),
                "e": _b64u(numbers.e),
            }
        ]
    }
    return {"private": private, "jwks": jwks}


@pytest.fixture(scope="module")
def other_keypair() -> dict[str, Any]:
    """A second, unrelated keypair — used to forge a wrongly-signed token."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {"private": private}


def _sign(
    private: Any,
    *,
    kid: str | None = KID,
    algorithm: str = "RS256",
    **claim_overrides: Any,
) -> str:
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "auth0|test-subject-123",
        "email": "person@example.org",
        "email_verified": True,
        "iat": NOW - 60,
        "nbf": NOW - 60,
        "exp": NOW + 3600,
    }
    claims.update(claim_overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims, private, algorithm=algorithm, headers=headers)


def _verify(
    token: str | None, jwks: dict[str, Any] | None, **kw: Any
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "token": token,
        "jwks": jwks,
        "expected_issuer": ISSUER,
        "expected_audience": AUDIENCE,
        "now": NOW,
    }
    params.update(kw)
    return verify_oidc_token(**params)


# ───────────────────────── the happy path ─────────────────────────


def test_valid_rs256_token_verifies_against_local_jwks(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"]), keypair["jwks"])
    assert r["state"] == "verified", r["failure_reason"]
    assert r["verified"] is True
    assert r["subject"] == "auth0|test-subject-123"
    assert r["email"] == "person@example.org"
    assert r["email_verified"] is True
    assert r["algorithm"] == "RS256"
    assert r["kid"] == KID
    assert r["verification_source"] == "oidc_token_signature"
    assert token_verification_invariant_failures(r) == []


def test_only_rs256_is_allowed() -> None:
    assert ALLOWED_ALGORITHMS == frozenset({"RS256"})


# ───────────────────────── fail-closed paths ─────────────────────────


def test_wrong_issuer_fails(keypair: dict) -> None:
    r = _verify(
        _sign(keypair["private"], iss="https://evil.example.com/"), keypair["jwks"]
    )
    assert r["state"] == "issuer_invalid"
    assert r["verified"] is False
    assert r["subject"] is None
    assert token_verification_invariant_failures(r) == []


def test_wrong_audience_fails(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], aud="some-other-api"), keypair["jwks"])
    assert r["state"] == "audience_invalid"
    assert r["verified"] is False


def test_expired_token_fails(keypair: dict) -> None:
    r = _verify(
        _sign(keypair["private"], exp=NOW - 3600, nbf=NOW - 7200, iat=NOW - 7200),
        keypair["jwks"],
    )
    assert r["state"] == "expired"
    assert r["verified"] is False


def test_future_nbf_token_fails(keypair: dict) -> None:
    r = _verify(
        _sign(keypair["private"], nbf=NOW + 3600, iat=NOW + 3600, exp=NOW + 7200),
        keypair["jwks"],
    )
    assert r["state"] == "not_yet_valid"
    assert r["verified"] is False


def test_missing_sub_fails(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], sub=None), keypair["jwks"])
    assert r["state"] == "subject_missing"
    assert r["verified"] is False


def test_empty_sub_fails(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], sub="   "), keypair["jwks"])
    assert r["state"] == "subject_missing"
    assert r["verified"] is False


def test_missing_exp_fails(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], exp=None), keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] in {"verification_error", "expired"}


def test_unknown_kid_fails(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], kid="not-a-real-kid"), keypair["jwks"])
    assert r["state"] == "unknown_kid"
    assert r["verified"] is False


def test_missing_kid_with_multiple_keys_fails(keypair: dict) -> None:
    two_keys = {
        "keys": [
            keypair["jwks"]["keys"][0],
            {**keypair["jwks"]["keys"][0], "kid": "second-key"},
        ]
    }
    r = _verify(_sign(keypair["private"], kid=None), two_keys)
    assert r["state"] == "missing_kid"
    assert r["verified"] is False


def test_missing_kid_with_single_key_is_unambiguous(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], kid=None), keypair["jwks"])
    assert r["state"] == "verified"


def test_signature_from_wrong_key_fails(
    keypair: dict, other_keypair: dict
) -> None:
    """A well-formed token signed by an unrelated key must not verify."""
    forged = _sign(other_keypair["private"])
    r = _verify(forged, keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] == "signature_invalid"


def test_unsigned_alg_none_token_is_rejected(keypair: dict) -> None:
    """The classic attack: strip the signature and set alg=none."""
    unsigned = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "auth0|attacker",
            "exp": NOW + 3600,
        },
        key="",
        algorithm="none",
        headers={"kid": KID},
    )
    r = _verify(unsigned, keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] == "unsupported_algorithm"


def test_hs256_algorithm_confusion_is_rejected(keypair: dict) -> None:
    """The classic confusion attack: HS256 signed with the RSA public key.

    Hand-crafted rather than built with jwt.encode, because PyJWT itself
    refuses to sign HS256 with an asymmetric key. That is a useful second line
    of defence, but the allowlist in our verifier is what this test exercises.
    """
    pub_pem = (
        keypair["private"]
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    def seg(obj: Any) -> bytes:
        return base64.urlsafe_b64encode(
            json.dumps(obj, separators=(",", ":")).encode()
        ).rstrip(b"=")

    header = seg({"alg": "HS256", "typ": "JWT", "kid": KID})
    payload = seg(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "auth0|attacker", "exp": NOW + 3600}
    )
    signing_input = header + b"." + payload
    mac = hmac.new(pub_pem, signing_input, hashlib.sha256).digest()
    forged = (
        signing_input + b"." + base64.urlsafe_b64encode(mac).rstrip(b"=")
    ).decode()

    r = _verify(forged, keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] == "unsupported_algorithm"
    assert token_verification_invariant_failures(r) == []


@pytest.mark.parametrize(
    "bad", ["", "   ", "not.a.jwt", "abc", "a.b", "a.b.c.d", "...", "e30.e30.xxx"]
)
def test_malformed_tokens_fail_closed(bad: str, keypair: dict) -> None:
    r = _verify(bad, keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] in {"malformed_token", "missing_token", "unsupported_algorithm"}
    assert token_verification_invariant_failures(r) == []


def test_no_token_fails_closed(keypair: dict) -> None:
    r = _verify(None, keypair["jwks"])
    assert r["state"] == "missing_token"
    assert r["verified"] is False


def test_no_jwks_fails_closed(keypair: dict) -> None:
    for jwks in (None, {}, {"keys": []}):
        r = _verify(_sign(keypair["private"]), jwks)
        assert r["state"] == "jwks_unavailable"
        assert r["verified"] is False


def test_missing_expected_issuer_or_audience_fails_closed(keypair: dict) -> None:
    tok = _sign(keypair["private"])
    assert _verify(tok, keypair["jwks"], expected_issuer=None)["verified"] is False
    assert _verify(tok, keypair["jwks"], expected_audience=None)["verified"] is False


# ───────────────────────── result hygiene ─────────────────────────


def test_raw_token_never_appears_in_result(keypair: dict) -> None:
    tok = _sign(keypair["private"])
    for result in (
        _verify(tok, keypair["jwks"]),
        _verify(tok, keypair["jwks"], expected_issuer="https://wrong/"),
    ):
        blob = str(result)
        assert tok not in blob
        # No JWT segment should appear either.
        for segment in tok.split("."):
            if len(segment) > 24:
                assert segment not in blob


def test_failed_verification_leaks_no_subject_or_email(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"], iss="https://evil/"), keypair["jwks"])
    assert r["subject"] is None
    assert r["email"] is None
    assert r["email_verified"] is False


def test_verified_result_never_claims_login_live(keypair: dict) -> None:
    r = _verify(_sign(keypair["private"]), keypair["jwks"])
    assert r["login_live_claimed"] is False
    assert r["customer_login_live_claimed"] is False
    assert r["membership_proven"] is False
    assert r["role_proven"] is False
    assert r["authority_proven"] is False


# ───────────────────────── JWKS fetch safety ─────────────────────────


def test_jwks_fetch_is_off_by_default() -> None:
    r = fetch_jwks(jwks_url="https://example.com/jwks.json")
    assert r["ok"] is False
    assert r["reason"] == "network_disabled"
    assert r["network_access_attempted"] is False


def test_jwks_fetch_without_url_fails_closed() -> None:
    r = fetch_jwks(jwks_url=None, allow_network=True)
    assert r["ok"] is False
    assert r["network_access_attempted"] is False


# ───────────── identity mapping: token proves WHO, nothing more ─────────────


def test_verified_token_maps_to_oidc_verified_identity(keypair: dict) -> None:
    v = _verify(_sign(keypair["private"]), keypair["jwks"])
    ident = identity_from_verified_token(verification=v)
    assert ident["identity_state"] == "oidc_verified"
    assert ident["verification_source"] == "oidc_token_signature"
    assert ident["verification_trusted"] is True
    assert ident["subject"] == "auth0|test-subject-123"
    assert request_identity_invariant_failures(ident) == []


def test_verified_token_does_not_imply_membership(keypair: dict) -> None:
    v = _verify(_sign(keypair["private"]), keypair["jwks"])
    ident = identity_from_verified_token(verification=v)
    assert ident["membership_trusted"] is False
    assert ident["verified_org_id"] is None
    assert ident["may_act_as_customer"] is False


def test_verified_token_with_untrusted_membership_source_stays_untrusted(
    keypair: dict,
) -> None:
    v = _verify(_sign(keypair["private"]), keypair["jwks"])
    ident = identity_from_verified_token(
        verification=v,
        verified_org_id="org-aaaa",
        verified_role="org_owner",
        membership_source="client_asserted",
    )
    assert ident["membership_trusted"] is False
    assert ident["role_trusted"] is False
    assert ident["verified_org_id"] is None
    assert ident["may_hold_customer_authority"] is False


def test_verified_token_does_not_imply_role_or_authority(keypair: dict) -> None:
    v = _verify(_sign(keypair["private"]), keypair["jwks"])
    ident = identity_from_verified_token(
        verification=v,
        verified_org_id="org-aaaa",
        membership_source="verified_directory",
    )
    assert ident["membership_trusted"] is True, "trusted directory grants membership"
    assert ident["role_trusted"] is False, "no role claim means no role"
    assert ident["may_hold_customer_authority"] is False


def test_full_trusted_chain_is_the_only_path_to_customer_action(
    keypair: dict,
) -> None:
    v = _verify(_sign(keypair["private"]), keypair["jwks"])
    ident = identity_from_verified_token(
        verification=v,
        verified_org_id="org-aaaa",
        verified_role="org_admin",
        membership_source="verified_directory",
    )
    assert ident["may_act_as_customer"] is True
    assert ident["customer_login_live_claimed"] is False
    assert request_identity_invariant_failures(ident) == []


def test_failed_verification_maps_to_denying_identity(keypair: dict) -> None:
    v = _verify(_sign(keypair["private"], iss="https://evil/"), keypair["jwks"])
    ident = identity_from_verified_token(verification=v)
    assert ident["identity_state"] in {"invalid", "oidc_configured_unverified"}
    assert ident["verification_trusted"] is False
    assert ident["may_act_as_customer"] is False
    assert request_identity_invariant_failures(ident) == []


def test_cloudflare_access_still_not_customer_login() -> None:
    ident = identity_from_cloudflare_access(access_email="op@example.com")
    assert ident["identity_state"] == "demo_operator"
    assert ident["verification_trusted"] is False
    assert ident["cloudflare_access_is_customer_login"] is False
    assert ident["may_hold_customer_authority"] is False


# ───────────────────────── readiness after Gate 60 ─────────────────────────


@pytest.fixture
def full_oidc_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OIDC_JWKS_URL", "https://example/jwks.json")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-abc")


def test_readiness_reports_verifier_implemented(full_oidc_env: None) -> None:
    r = build_oidc_readiness()
    assert r["token_verification_implemented"] is True
    assert r["local_token_verification_passed"] is True
    assert oidc_readiness_invariant_failures(r) == []


def test_strict_now_fails_only_on_live_auth0_proof(full_oidc_env: None) -> None:
    """The failure reason has moved on: the verifier exists, live proof does not."""
    r = build_oidc_readiness(strict=True)
    assert r["config_complete"] is True
    assert r["token_verification_implemented"] is True
    assert r["live_auth0_token_proven"] is False
    assert r["ok"] is False
    assert "live_auth0_token_not_proven" in r["blocked_reasons"]
    assert "token_verification_path_not_implemented" not in r["blocked_reasons"]
    assert r["login_live_claimed"] is False
    assert oidc_readiness_invariant_failures(r) == []


def test_default_mode_still_passes_without_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k in ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL", "OIDC_CLIENT_ID"):
        monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("NATIVEFORGE_" + k, raising=False)
    r = build_oidc_readiness()
    assert r["ok"] is True
    assert r["readiness_state"] == "oidc_unconfigured"
    assert r["login_live_claimed"] is False


def test_leeway_does_not_resurrect_a_long_expired_token(keypair: dict) -> None:
    """A small leeway must not extend a token's life meaningfully."""
    tok = _sign(keypair["private"], exp=NOW - 600, nbf=NOW - 1200, iat=NOW - 1200)
    r = _verify(tok, keypair["jwks"], leeway_seconds=30)
    assert r["state"] == "expired"


def test_verification_uses_supplied_clock_not_wall_clock(keypair: dict) -> None:
    """`now` must be authoritative, not the wall clock.

    Two halves:
      * a window entirely AFTER `now` must be not_yet_valid, and
      * the happy-path test is itself proof the wall clock is unused — NOW is
        set months ahead of real time, so a wall-clock check would reject the
        valid token as not_yet_valid.
    """
    future = NOW + 10_000_000
    tok = _sign(keypair["private"], nbf=future, iat=future, exp=future + 3600)
    r = _verify(tok, keypair["jwks"])
    assert r["verified"] is False
    assert r["state"] == "not_yet_valid"

    # Sanity: NOW really is ahead of the real clock, so the happy path could not
    # have passed under wall-clock validation.
    assert NOW > int(time.time()), (
        "NOW must stay ahead of real time for this proof to hold"
    )
