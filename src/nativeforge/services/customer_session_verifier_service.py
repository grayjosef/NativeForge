"""Customer session verifier (Gate 118C).

Turns a cookie value into something the auth dependency can act on, or into a
named refusal.

## Six things that can be wrong, and they are checked in order

```text
cookie_present      nothing was sent
cookie_parseable    three dot-separated parts, version prefix, decodable base64
signature_valid     the payload was not altered, and we signed it
session_expired     the value carries its own expiry and it has passed
organization_id     UUID-shaped, because every RLS policy casts to ::uuid
membership          a record backs the organization the session names
```

The order matters for what gets reported, not for safety - every one is
required, and a failure at any step leaves `session_cookie_valid` false. But a
caller who gets "malformed" learns something different from one who gets
"expired", and lumping them into one refusal would waste that.

## Verifying is not authorizing, and neither is authenticating

Three separate outputs, deliberately:

```text
session_cookie_valid        the value is genuine and unexpired
auth_dependency_can_authorize   ...and a principal came out of it
rls_context_allowed         ...and an organization_id resolved and a
                            membership was verified
```

Gate 112's rule, restated at the verifier: **a valid session is not an
organization.** A signed cookie proves somebody held a credential we issued. It
does not prove the organization named inside it is one they still belong to -
memberships get revoked, and a session outlives the revocation until it expires.

So `membership_required` is true and `membership_verified` is an input this
service will not invent.

## A valid session does not make customer auth live

`customer_auth_live` is measured from Gate 115's activation gate and is false.
A fixture session can be perfectly valid under a fixture key while nobody in the
world can authenticate — those are different facts and the verifier reports
both.

## Nothing is logged

The cookie value is parsed and never returned, never logged, and never placed in
a field. An invariant refuses any result carrying one.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from nativeforge.services.customer_session_format_service import (
    SESSION_FORMAT_VERSION,
    SIGNING_KEY_ENV,
)

SCHEMA_VERSION = "nf_customer_session_verifier_v1"

RESULT_FIELDS: tuple[str, ...] = (
    "cookie_present",
    "cookie_parseable",
    "signature_valid",
    "session_expired",
    "organization_id_valid",
    "principal_resolved",
    "membership_required",
    "membership_verified",
    "session_cookie_valid",
    "auth_dependency_can_authorize",
    "rls_context_allowed",
    "blocked_reasons",
)

# Field names that would mean a credential had entered a verifier result.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {"session_cookie_value", "cookie", "cookie_value", "signing_key", "signature"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def verify_session_cookie(
    *,
    cookie_value: Any = None,
    signing_key: str | None = None,
    membership_verified: bool = False,
    now: int | None = None,
    customer_auth_live: bool | None = None,
) -> dict[str, Any]:
    """Verify a cookie into a principal-shaped result. Deny by default."""
    import os

    from nativeforge.services.customer_session_format_service import (
        _clock,
        _uuid_shaped,
        signing_key_present,
    )

    blocked_reasons: list[str] = []

    raw = str(cookie_value or "")
    cookie_present = bool(raw)
    if not cookie_present:
        blocked_reasons.append("no_session_cookie_was_sent")

    key = signing_key if signing_key is not None else os.environ.get(
        SIGNING_KEY_ENV, ""
    )
    if cookie_present and not key:
        blocked_reasons.append("no_signing_key_available_so_nothing_can_be_verified")

    # -- parse --------------------------------------------------------------
    payload: dict[str, Any] = {}
    cookie_parseable = False
    encoded_payload = ""
    signature = ""

    if cookie_present:
        parts = raw.split(".")
        if len(parts) != 3:
            blocked_reasons.append("session_cookie_is_not_three_dot_separated_parts")
        elif parts[0] != SESSION_FORMAT_VERSION:
            blocked_reasons.append(f"session_cookie_version_unrecognised:{parts[0]}")
        else:
            encoded_payload, signature = parts[1], parts[2]
            try:
                decoded = json.loads(_unb64(encoded_payload))
            except (ValueError, binascii.Error, UnicodeDecodeError):
                blocked_reasons.append("session_cookie_payload_is_not_decodable_json")
            else:
                if not isinstance(decoded, dict):
                    blocked_reasons.append("session_cookie_payload_is_not_an_object")
                else:
                    payload = decoded
                    cookie_parseable = True

    # -- signature ----------------------------------------------------------
    signature_valid = False
    if cookie_parseable and key:
        expected = base64.urlsafe_b64encode(
            hmac.digest(
                key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256
            )
        ).decode("ascii").rstrip("=")
        # Constant-time. An early-returning comparison leaks the prefix to
        # anybody who can time it, and a signature is exactly what an attacker
        # cannot produce.
        signature_valid = hmac.compare_digest(signature, expected)
        if not signature_valid:
            blocked_reasons.append("session_cookie_signature_does_not_verify")

    # -- expiry -------------------------------------------------------------
    current = int(now) if now is not None else _clock()
    expires = int(payload.get("exp") or 0)
    session_expired = bool(cookie_parseable and (not expires or current >= expires))
    if cookie_parseable and not expires:
        blocked_reasons.append("session_cookie_carries_no_expiry")
    elif session_expired:
        blocked_reasons.append("session_expired")

    # -- the organization ---------------------------------------------------
    organization_id = str(payload.get("org") or "")
    organization_id_valid = bool(organization_id and _uuid_shaped(organization_id))
    if cookie_parseable and not organization_id:
        blocked_reasons.append("session_cookie_carries_no_organization_id")
    elif cookie_parseable and not organization_id_valid:
        # Gates 110-113: a profile id is a real value in the wrong identity
        # space, and every RLS policy casts to ::uuid.
        blocked_reasons.append("session_organization_id_is_not_uuid_shaped")

    # -- derived affirmatively ---------------------------------------------
    session_cookie_valid = bool(
        cookie_present
        and cookie_parseable
        and signature_valid
        and not session_expired
        and organization_id_valid
    )

    # A principal comes out of a valid session and out of nothing else.
    principal_id = str(payload.get("pid") or "")
    principal_resolved = bool(session_cookie_valid and principal_id)
    if session_cookie_valid and not principal_id:
        blocked_reasons.append("valid_session_carries_no_principal_id")

    auth_dependency_can_authorize = principal_resolved

    # Gate 112's rule: a valid session is not a membership. Memberships get
    # revoked and a session outlives the revocation until it expires.
    membership_required = True
    if principal_resolved and not membership_verified:
        blocked_reasons.append("membership_not_verified_for_this_organization")

    rls_context_allowed = bool(
        principal_resolved and organization_id_valid and membership_verified
    )

    if customer_auth_live is None:
        customer_auth_live = _customer_auth_live()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cookie_present": cookie_present,
            "cookie_parseable": cookie_parseable,
            "signature_valid": signature_valid,
            "session_expired": session_expired,
            "organization_id": organization_id or None,
            "organization_id_valid": organization_id_valid,
            "principal_id": principal_id or None,
            "principal_resolved": principal_resolved,
            "roles": list(payload.get("roles") or []),
            "session_id": str(payload.get("sid") or "") or None,
            "expires_at": expires or None,
            "membership_required": membership_required,
            "membership_verified": bool(membership_verified),
            "session_cookie_valid": session_cookie_valid,
            "auth_dependency_can_authorize": auth_dependency_can_authorize,
            "rls_context_allowed": rls_context_allowed,
            "signing_key_present": signing_key_present(),
            # Measured, and reported beside the rest so a valid fixture session
            # cannot be mistaken for working authentication.
            "customer_auth_live": bool(customer_auth_live),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a verifier reads. It writes nothing and echoes nothing.
            "cookie_value_emitted": False,
            "signing_key_value_emitted": False,
            "current_org_id_set": False,
            "real_sessions_created": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def _customer_auth_live() -> bool:
    try:
        from nativeforge.services.customer_auth_live_detector_service import (
            detect_customer_auth_live,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    return detect_customer_auth_live()


def build_verifier_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Every supplied case, verified. Takes its input so a test can shrink it."""
    rows = [verify_session_cookie(**case) for case in cases]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "session_verifier_contract_available": True,
            "rows": rows,
            "case_count": len(rows),
            "valid_count": sum(1 for r in rows if r["session_cookie_valid"]),
            "authorizable_count": sum(
                1 for r in rows if r["auth_dependency_can_authorize"]
            ),
            "rls_allowed_count": sum(1 for r in rows if r["rls_context_allowed"]),
            "cookie_value_emitted": False,
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def verifier_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"verifier_missing_field:{field}")

    for constant in (
        "cookie_value_emitted",
        "signing_key_value_emitted",
        "current_org_id_set",
        "real_sessions_created",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"verifier_claimed:{constant}")

    # No credential may appear in a verifier result, by field name.
    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            fails.append(f"verifier_result_carries_a_value_field:{field}")

    # Validity requires all of it.
    if result.get("session_cookie_valid"):
        for required in (
            "cookie_present",
            "cookie_parseable",
            "signature_valid",
            "organization_id_valid",
        ):
            if not result.get(required):
                fails.append(f"valid_session_without:{required}")
        if result.get("session_expired"):
            fails.append("valid_session_that_is_expired")

    # A principal comes out of a valid session and nothing else.
    if result.get("principal_resolved") and not result.get("session_cookie_valid"):
        fails.append("principal_resolved_without_a_valid_session")

    if result.get("auth_dependency_can_authorize") and not result.get(
        "principal_resolved"
    ):
        fails.append("authorization_permitted_without_a_principal")

    # Membership is always required, and RLS needs it plus an organization.
    if result.get("membership_required") is not True:
        fails.append("membership_not_required")

    if result.get("rls_context_allowed"):
        if not result.get("membership_verified"):
            fails.append("rls_context_without_a_verified_membership")
        if not result.get("organization_id_valid"):
            fails.append("rls_context_without_a_uuid_organization_id")
        if not result.get("principal_resolved"):
            fails.append("rls_context_without_a_principal")

    # And no verifier ever sets one.
    if result.get("current_org_id_set"):
        fails.append("verifier_set_an_rls_context")

    # A parseable cookie needs one to have been sent.
    if result.get("cookie_parseable") and not result.get("cookie_present"):
        fails.append("cookie_parseable_without_a_cookie")

    # A signature cannot verify a cookie that did not parse.
    if result.get("signature_valid") and not result.get("cookie_parseable"):
        fails.append("signature_valid_without_a_parseable_cookie")

    # A refusal must name itself.
    if not result.get("session_cookie_valid") and not result.get("blocked_reasons"):
        fails.append("session_refused_without_a_reason")

    return fails


def verifier_matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = matrix.get("rows") or []
    for index, row in enumerate(rows):
        fails.extend(f"row{index}:{f}" for f in verifier_invariant_failures(row))

    if matrix.get("valid_count") != sum(
        1 for r in rows if r.get("session_cookie_valid")
    ):
        fails.append("valid_count_disagrees_with_the_rows")

    if matrix.get("rls_allowed_count") != sum(
        1 for r in rows if r.get("rls_context_allowed")
    ):
        fails.append("rls_allowed_count_disagrees_with_the_rows")

    for constant in ("cookie_value_emitted", "current_org_id_set", "fabricated"):
        if matrix.get(constant) is not False:
            fails.append(f"verifier_matrix_claimed:{constant}")

    return fails
