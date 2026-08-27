"""OIDC token verification (Gate 60).

The first link in the chain Gate 59 identified:

    verified token -> verified identity -> trusted membership
      -> trusted role -> capability

Implemented on PyJWT + cryptography rather than by hand. Signature verification
is the one place in this campaign where a vetted library is clearly correct: a
hand-rolled RSA/PKCS#1 v1.5 verifier is exactly the kind of code that accepts
malformed padding, and this path will eventually gate real customer authority.

What this service does NOT do:

  * it does not claim login is live
  * it does not prove membership — a valid token says who someone is, not which
    organization they may act for
  * it does not prove a role or any authority
  * it never returns or logs the raw token

Every failure is a distinct state so the caller can audit *why* a token was
rejected without re-parsing it.
"""

from __future__ import annotations

import json
import time
from typing import Any

import jwt
from jwt import PyJWK

SCHEMA_VERSION = "nf_oidc_token_verification_v1"

# RS256 only. "none" and HMAC families are excluded deliberately: accepting a
# caller-chosen algorithm is the classic JWT confusion attack, where an attacker
# signs with HS256 using the public key as the shared secret.
ALLOWED_ALGORITHMS = frozenset({"RS256"})

VERIFICATION_STATES = frozenset(
    {
        "verified",
        "missing_token",
        "malformed_token",
        "unsupported_algorithm",
        "missing_kid",
        "unknown_kid",
        "jwks_unavailable",
        "signature_invalid",
        "issuer_invalid",
        "audience_invalid",
        "expired",
        "not_yet_valid",
        "subject_missing",
        "verification_error",
        "unknown",
    }
)

# Only this state means a token verified.
VERIFIED_STATES = frozenset({"verified"})

# Default clock leeway. Small on purpose: generous leeway silently extends the
# life of a revoked or expired token.
DEFAULT_LEEWAY_SECONDS = 30


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _result(
    state: str,
    *,
    failure_reason: str | None = None,
    subject: str | None = None,
    email: str | None = None,
    email_verified: bool = False,
    issuer: str | None = None,
    audience: str | None = None,
    kid: str | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    """Build a verification result. Raw token material is never included."""
    st = state if state in VERIFICATION_STATES else "unknown"
    verified = st in VERIFIED_STATES
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state": st,
            "verified": verified,
            "subject": subject if verified else None,
            "email": email if verified else None,
            "email_verified": bool(email_verified) if verified else False,
            "issuer": issuer,
            "audience": audience,
            "kid": kid,
            "algorithm": algorithm,
            "verification_source": "oidc_token_signature" if verified else "none",
            "failure_reason": failure_reason,
            # Verifying a token is not logging a customer in.
            "login_live_claimed": False,
            "customer_login_live_claimed": False,
            # A token proves identity only. It proves nothing about org or role.
            "membership_proven": False,
            "role_proven": False,
            "authority_proven": False,
        }
    )


def _select_key(
    jwks: dict[str, Any], kid: str | None
) -> tuple[Any | None, str | None, str | None]:
    """Pick a JWKS key by kid. Returns (key, resolved_kid, failure_state)."""
    keys = (jwks or {}).get("keys") or []
    if not keys:
        return None, None, "jwks_unavailable"

    if kid is None:
        # A single key is unambiguous; more than one is not, and guessing would
        # let an attacker steer key selection.
        if len(keys) == 1:
            candidate = keys[0]
        else:
            return None, None, "missing_kid"
    else:
        matches = [k for k in keys if k.get("kid") == kid]
        if not matches:
            return None, kid, "unknown_kid"
        candidate = matches[0]

    if candidate.get("kty") != "RSA":
        return None, candidate.get("kid"), "unsupported_algorithm"
    if candidate.get("alg") and candidate["alg"] not in ALLOWED_ALGORITHMS:
        return None, candidate.get("kid"), "unsupported_algorithm"

    try:
        key = PyJWK.from_dict({**candidate, "alg": candidate.get("alg") or "RS256"})
    except Exception:
        return None, candidate.get("kid"), "jwks_unavailable"
    return key.key, candidate.get("kid"), None


def verify_oidc_token(
    *,
    token: str | None,
    jwks: dict[str, Any] | None,
    expected_issuer: str | None,
    expected_audience: str | None,
    now: int | None = None,
    leeway_seconds: int = DEFAULT_LEEWAY_SECONDS,
) -> dict[str, Any]:
    """Verify an OIDC ID/access token. Fails closed on every error path."""
    if not token or not str(token).strip():
        return _result("missing_token", failure_reason="no token supplied")
    if not expected_issuer:
        return _result("issuer_invalid", failure_reason="no expected issuer configured")
    if not expected_audience:
        return _result(
            "audience_invalid", failure_reason="no expected audience configured"
        )
    if not jwks or not (jwks or {}).get("keys"):
        return _result("jwks_unavailable", failure_reason="no JWKS keys available")

    tok = str(token).strip()

    # Peek at the header for key selection and algorithm gating only. Nothing
    # here is trusted; the signature check below is what decides.
    try:
        header = jwt.get_unverified_header(tok)
    except Exception as e:
        return _result("malformed_token", failure_reason=type(e).__name__)

    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        return _result(
            "unsupported_algorithm",
            failure_reason=f"algorithm not allowed: {alg!r}",
            kid=header.get("kid"),
            algorithm=alg if isinstance(alg, str) else None,
        )

    key, resolved_kid, key_failure = _select_key(jwks, header.get("kid"))
    if key_failure:
        return _result(
            key_failure, failure_reason=key_failure, kid=resolved_kid, algorithm=alg
        )

    current = int(now if now is not None else time.time())

    try:
        claims = jwt.decode(
            tok,
            key=key,
            algorithms=sorted(ALLOWED_ALGORITHMS),
            audience=expected_audience,
            issuer=expected_issuer,
            leeway=int(leeway_seconds),
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True,
                # Time claims are validated below against the supplied `now`.
                # PyJWT has no `now` hook and would use the wall clock, which
                # would make this service non-deterministic and would silently
                # ignore a caller-supplied clock.
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.ExpiredSignatureError:
        return _result(
            "expired", failure_reason="exp in the past", kid=resolved_kid, algorithm=alg
        )
    except jwt.ImmatureSignatureError:
        return _result(
            "not_yet_valid",
            failure_reason="nbf in the future",
            kid=resolved_kid,
            algorithm=alg,
        )
    except jwt.InvalidIssuerError:
        return _result(
            "issuer_invalid",
            failure_reason="issuer mismatch",
            kid=resolved_kid,
            algorithm=alg,
        )
    except jwt.InvalidAudienceError:
        return _result(
            "audience_invalid",
            failure_reason="audience mismatch",
            kid=resolved_kid,
            algorithm=alg,
        )
    except jwt.MissingRequiredClaimError as e:
        claim = getattr(e, "claim", None)
        state = "subject_missing" if claim == "sub" else "verification_error"
        return _result(
            state,
            failure_reason=f"missing required claim: {claim}",
            kid=resolved_kid,
            algorithm=alg,
        )
    except jwt.InvalidSignatureError:
        return _result(
            "signature_invalid",
            failure_reason="signature did not verify",
            kid=resolved_kid,
            algorithm=alg,
        )
    except jwt.DecodeError as e:
        return _result(
            "malformed_token", failure_reason=type(e).__name__, kid=resolved_kid
        )
    except jwt.InvalidTokenError as e:
        return _result(
            "verification_error",
            failure_reason=type(e).__name__,
            kid=resolved_kid,
            algorithm=alg,
        )
    except Exception as e:  # pragma: no cover - defensive fail-closed
        return _result("verification_error", failure_reason=type(e).__name__)

    subject = claims.get("sub")
    if not subject or not str(subject).strip():
        return _result(
            "subject_missing",
            failure_reason="sub claim empty",
            kid=resolved_kid,
            algorithm=alg,
        )

    # Time validation, owned here so the supplied `now` is authoritative.
    # Checked in this order so an expired token reports "expired" even when its
    # nbf is also historic.
    try:
        exp = claims.get("exp")
        if exp is None or int(exp) < current - int(leeway_seconds):
            return _result(
                "expired",
                failure_reason="exp missing or in the past",
                kid=resolved_kid,
                algorithm=alg,
            )
        nbf = claims.get("nbf")
        if nbf is not None and int(nbf) > current + int(leeway_seconds):
            return _result(
                "not_yet_valid",
                failure_reason="nbf in the future",
                kid=resolved_kid,
                algorithm=alg,
            )
        iat = claims.get("iat")
        if iat is not None and int(iat) > current + int(leeway_seconds):
            return _result(
                "not_yet_valid",
                failure_reason="iat in the future",
                kid=resolved_kid,
                algorithm=alg,
            )
    except (TypeError, ValueError):
        return _result(
            "malformed_token",
            failure_reason="non-numeric time claim",
            kid=resolved_kid,
            algorithm=alg,
        )

    return _result(
        "verified",
        subject=str(subject),
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        issuer=claims.get("iss"),
        audience=expected_audience,
        kid=resolved_kid,
        algorithm=alg,
    )


def fetch_jwks(
    *, jwks_url: str | None, allow_network: bool = False, timeout_seconds: float = 5.0
) -> dict[str, Any]:
    """Fetch a JWKS document. Opt-in, hard timeout, fails closed.

    Network access is **off by default** and never enabled implicitly by the
    verifier — a verification path that silently reaches the internet is a
    surprise in a demo environment and a hang risk in a request path.
    """
    if not allow_network:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "jwks": None,
                "reason": "network_disabled",
                "network_access_attempted": False,
            }
        )
    if not jwks_url:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "jwks": None,
                "reason": "no_jwks_url",
                "network_access_attempted": False,
            }
        )

    # Gate 94A: this scheme check used to sit INSIDE the `with`, after the
    # request had already gone out - the old comment read "https enforced
    # below", and below was too late. An http:// JWKS URL was contacted in
    # plaintext and only then rejected. Checked before the call now.
    if not str(jwks_url).lower().startswith("https://"):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "jwks": None,
                "reason": "insecure_scheme",
                "network_access_attempted": False,
            }
        )

    # Gate 94B: the global choke point. This path already denied by default via
    # `allow_network`, but a private gate is not the shared one - the whole
    # point of the choke point is that every egress decision is visible in one
    # place and carries a caller name.
    from nativeforge.services.live_network_guard_service import (
        build_live_network_decision,
    )

    decision = build_live_network_decision(
        purpose="identity_verification",
        target_url=jwks_url,
        caller="oidc_token_verification_service.fetch_jwks",
        method="GET",
        allow_live_fetch=bool(allow_network),
        issuer_configured=bool(jwks_url),
    )
    if not decision["allowed"]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "jwks": None,
                "reason": "live_network_refused",
                "blocked_reasons": decision["blocked_reasons"],
                "network_access_attempted": False,
            }
        )

    import urllib.request

    try:
        with urllib.request.urlopen(  # noqa: S310 - https enforced above
            jwks_url, timeout=float(timeout_seconds)
        ) as resp:
            body = resp.read(1_000_000)
        doc = json.loads(body)
        if not isinstance(doc, dict) or not doc.get("keys"):
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "ok": False,
                    "jwks": None,
                    "reason": "malformed_jwks",
                    "network_access_attempted": True,
                }
            )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": True,
                "jwks": doc,
                "reason": None,
                "network_access_attempted": True,
            }
        )
    except Exception as e:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "jwks": None,
                "reason": f"fetch_failed:{type(e).__name__}",
                "network_access_attempted": True,
            }
        )


def token_verification_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("state") not in VERIFICATION_STATES:
        fails.append("state_invalid")

    verified = bool(result.get("verified"))
    if verified and result.get("state") not in VERIFIED_STATES:
        fails.append("verified_without_verified_state")
    if verified and not result.get("subject"):
        fails.append("verified_without_subject")
    if verified and result.get("verification_source") != "oidc_token_signature":
        fails.append("verified_without_signature_source")
    if not verified and result.get("verification_source") != "none":
        fails.append("unverified_with_verification_source")
    if not verified and result.get("subject"):
        fails.append("unverified_result_leaks_subject")

    # A token never proves membership, role or authority.
    for f in ("membership_proven", "role_proven", "authority_proven"):
        if result.get(f) is not False:
            fails.append(f"token_overclaims:{f}")

    for f in ("login_live_claimed", "customer_login_live_claimed"):
        if result.get(f) is not False:
            fails.append(f"forbidden_claim:{f}")

    # The raw token must never be echoed back.
    blob = json.dumps(result)
    if blob.count(".") > 0 and any(
        len(part) > 200 for part in blob.replace('"', " ").split()
    ):
        fails.append("possible_raw_token_in_result")

    return fails
