"""Customer session format (Gate 118B).

What a NativeForge session cookie value *is*, and how to tell a real one from
something somebody typed.

## The format

```text
nf1.<base64url(payload_json)>.<base64url(hmac_sha256(payload, key))>
```

Three parts, dot-separated, all URL-safe so a cookie can carry them unescaped.
The version prefix is there so a later format can be introduced without a
verifier having to guess which one it is looking at — an unversioned credential
format is one nobody can ever change.

## Why signed rather than opaque-and-looked-up

A signed value needs no storage: the server can verify it holds without asking a
database. That matters here specifically because Gate 118A found there is no
database table for sessions and this gate deliberately does not add one.

The cost is that a signed session cannot be revoked before it expires, which is
why `max_age_seconds` is bounded and rotation is required by Gate 116B's policy.
Logout clears the cookie; it cannot un-sign a value already issued. That is
stated here rather than discovered later.

## expires_at lives inside the value, not only on the cookie

Gate 116B set the cookie's `Max-Age`. A cookie lifetime is a *request to the
browser* — a browser that ignores it, or an attacker replaying a captured
cookie, is unaffected. So the payload carries its own `expires_at` and the
verifier checks it server-side.

## Signing keys

`signing_key_present` is a boolean. The key is compared inside `hmac.digest`
and never returned, logged, or placed in a field. There is no code path here
that hands a key back, because there is no field for one.

Gate 118A found no signing key configured anywhere in NativeForge, so
`production_session` is false for every session this service can build today.

## Fixture sessions are not production sessions

`build_fixture_session` signs with an obviously-fake key and marks the result
`demo_fixture: True`. An invariant refuses to call such a session a production
one, and a second refuses any session claiming to be production without a
configured key.

The distinction matters because a fixture session is exactly as cryptographically
valid as a real one *under its own key* — the difference is which key, and
whether anybody could have obtained it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_session_format_v1"

# The version prefix. An unversioned credential format is one nobody can change.
SESSION_FORMAT_VERSION = "nf1"

# Where a real signing key would come from. Presence-detected only; the value
# is compared inside hmac.digest and never read into a return.
SIGNING_KEY_ENV = "NF_SESSION_SIGNING_KEY"

# The obviously-fake key fixture sessions are signed with. Committed on purpose:
# it signs nothing anybody would accept, and naming it makes every fixture
# session recognisable as one.
FIXTURE_SIGNING_KEY = "nf-demo-fixture-signing-key-not-a-real-secret"

# Roles a session may carry, bridged from Gate 111 rather than restated.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# A session that outlives the cookie ceiling is a credential pretending to be a
# session. Bridged from Gate 116B.
MAX_SESSION_SECONDS = 7 * 24 * 60 * 60

RESULT_FIELDS: tuple[str, ...] = (
    "session_format_available",
    "session_id",
    "principal_id",
    "organization_id",
    "roles",
    "issued_at",
    "expires_at",
    "expires_in_seconds",
    "signature_present",
    "signature_valid",
    "session_cookie_valid",
    "production_session",
    "demo_fixture",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _uuid_shaped(value: Any) -> bool:
    """Can this survive the ``::uuid`` cast every RLS policy performs?"""
    return bool(_UUID_RE.match(str(value or "").strip()))


def signing_key_present() -> bool:
    """Is a real signing key configured? Presence only; never the value."""
    return bool((os.environ.get(SIGNING_KEY_ENV) or "").strip())


def _sign(payload: str, key: str) -> str:
    return _b64(
        hmac.digest(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    )


def build_session_payload(
    *,
    principal_id: Any = None,
    subject: Any = None,
    email: Any = None,
    organization_id: Any = None,
    roles: list[str] | None = None,
    issued_at: int | None = None,
    expires_at: int | None = None,
    auth_source: Any = None,
    session_id: Any = None,
) -> dict[str, Any]:
    """The payload a session value carries. No email is included, deliberately.

    An email in a cookie is personal data travelling on every request to every
    route, readable by anything that can see the cookie jar. The subject and
    the organization are what a route needs; the email is looked up when it is
    actually wanted.
    """
    return {
        "v": SESSION_FORMAT_VERSION,
        "sid": str(session_id or ""),
        "pid": str(principal_id or ""),
        "sub": str(subject or ""),
        "org": str(organization_id or ""),
        "roles": sorted(str(r) for r in (roles or [])),
        "iat": int(issued_at or 0),
        "exp": int(expires_at or 0),
        "src": str(auth_source or "unknown"),
        # Recorded so a verifier can see what was *not* carried.
        "email_omitted": True,
    }


def build_session(
    *,
    principal_id: Any = None,
    subject: Any = None,
    email: Any = None,
    organization_id: Any = None,
    roles: list[str] | None = None,
    issued_at: int | None = None,
    expires_at: int | None = None,
    auth_source: Any = None,
    session_id: Any = None,
    signing_key: str | None = None,
    is_demo_fixture: bool = False,
    now: int | None = None,
    signing_key_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate one session. Deny by default.

    `email` is accepted and deliberately discarded - see `build_session_payload`.

    Gate 119B: a *present* key and a key fit to sign a production session are
    different facts. A key read from the committed local-dev fixture is present
    and may never sign anything a customer would be held to, so
    `production_session` is derived from readiness and `signing_key_present`
    remains reported alongside it.

    Imported lazily because the readiness service imports this module's fixture
    key and environment name; at module scope the two would be a cycle.
    """
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        build_signing_key_readiness,
    )

    blocked_reasons: list[str] = []

    key_configured = signing_key_present()
    readiness = (
        signing_key_readiness
        if signing_key_readiness is not None
        else build_signing_key_readiness()
    )
    key_ready = bool(readiness.get("can_sign_production_session"))
    key_source = str(readiness.get("signing_key_source") or "unknown")
    # An explicitly supplied key is a test or fixture key. A session signed with
    # one is never a production session, whatever else is true.
    key_supplied = signing_key is not None
    key = signing_key if key_supplied else os.environ.get(SIGNING_KEY_ENV, "")

    payload = build_session_payload(
        principal_id=principal_id,
        subject=subject,
        email=email,
        organization_id=organization_id,
        roles=roles,
        issued_at=issued_at,
        expires_at=expires_at,
        auth_source=auth_source,
        session_id=session_id,
    )

    # -- the fields a session must carry -----------------------------------
    if not payload["sid"]:
        blocked_reasons.append("session_without_a_session_id")
    if not payload["pid"]:
        blocked_reasons.append("session_without_a_principal_id")

    organization_ok = _uuid_shaped(payload["org"])
    if not payload["org"]:
        blocked_reasons.append("session_without_an_organization_id")
    elif not organization_ok:
        # Gates 110-113: a profile id is a real value from a real column in the
        # wrong identity space, and every RLS policy casts to ::uuid.
        blocked_reasons.append("organization_id_is_not_uuid_shaped")

    # -- expiry -------------------------------------------------------------
    issued = payload["iat"]
    expires = payload["exp"]
    if not issued:
        blocked_reasons.append("session_without_an_issued_at")
    if not expires:
        blocked_reasons.append("session_without_an_expires_at")
    if issued and expires and expires <= issued:
        blocked_reasons.append("session_expires_at_is_not_after_issued_at")
    if issued and expires and (expires - issued) > MAX_SESSION_SECONDS:
        blocked_reasons.append("session_lifetime_exceeds_the_cookie_policy_ceiling")

    current = int(now) if now is not None else _clock()
    expired = bool(expires and current >= expires)
    if expired:
        blocked_reasons.append("session_expired")
    expires_in_seconds = int(expires - current) if expires else 0

    # -- signature ----------------------------------------------------------
    encoded_payload = _b64(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature_present = bool(key)
    if not key:
        blocked_reasons.append("no_signing_key_available_so_nothing_was_signed")

    signature = _sign(encoded_payload, key) if key else ""
    cookie_value = (
        f"{SESSION_FORMAT_VERSION}.{encoded_payload}.{signature}" if key else ""
    )
    # A session this service just built verifies against its own key by
    # construction. It is checked anyway rather than assumed, because an
    # assumed-valid signature is the one nobody notices going wrong.
    signature_valid = bool(
        key and hmac.compare_digest(signature, _sign(encoded_payload, key))
    )

    # -- derived affirmatively ---------------------------------------------
    session_cookie_valid = bool(
        signature_valid
        and organization_ok
        and not expired
        and issued
        and expires
        and payload["sid"]
        and payload["pid"]
        and not blocked_reasons
    )

    demo_fixture = bool(is_demo_fixture or key_supplied)
    # A production session needs a key fit to sign one, a signature that
    # verifies under it, and no fixture marking anywhere. `key_ready` rather
    # than `key_configured`: Gate 119B distinguishes the two, and this is the
    # decision the distinction exists for.
    production_session = bool(session_cookie_valid and key_ready and not demo_fixture)
    if session_cookie_valid and key_configured and not key_ready:
        blocked_reasons.append(
            f"signing_key_present_but_not_fit_to_sign:source={key_source}"
        )
    if demo_fixture and not is_demo_fixture:
        blocked_reasons.append("session_signed_with_a_supplied_key_is_not_production")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "session_format_available": True,
            "format_version": SESSION_FORMAT_VERSION,
            "session_id": payload["sid"],
            "principal_id": payload["pid"],
            "subject": payload["sub"],
            "organization_id": payload["org"],
            "organization_id_uuid_shaped": organization_ok,
            "roles": payload["roles"],
            "auth_source": payload["src"],
            "issued_at": issued,
            "expires_at": expires,
            "expires_in_seconds": expires_in_seconds,
            "expired": expired,
            "signature_present": signature_present,
            "signature_valid": signature_valid,
            "signing_key_present": key_configured,
            "signing_key_ready": key_ready,
            "signing_key_source": key_source,
            "session_cookie_valid": session_cookie_valid,
            "production_session": production_session,
            "demo_fixture": demo_fixture,
            # The value itself. Carried so a verifier and a test can use it, and
            # excluded from every artifact by the writer's own scan.
            "session_cookie_value": cookie_value,
            "email_included_in_payload": False,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a format decides. It sets no cookie and stores nothing.
            "signing_key_value_emitted": False,
            "cookie_set_by_this_service": False,
            "persisted": False,
            "real_users_created": False,
            "provider_contacted": False,
            "fabricated": False,
        }
    )


def _clock() -> int:
    """Wall clock, isolated so every caller can inject one instead."""
    import time

    return int(time.time())


def build_fixture_session(
    *,
    organization_id: str = "00000000-0000-4000-8000-000000000118",
    roles: list[str] | None = None,
    issued_at: int = 1_700_000_000,
    lifetime_seconds: int = 8 * 60 * 60,
    session_id: str = "nf-demo-fixture-session-118",
    principal_id: str = "nf-demo-fixture-principal-118",
    now: int | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """A deterministic session signed with an obviously-fake key.

    Fixed timestamps so an artifact does not churn, and a `now` pinned inside
    the window so the fixture is valid rather than expired the moment the clock
    moves past it.
    """
    kwargs: dict[str, Any] = {
        "principal_id": principal_id,
        "subject": "nf-demo-fixture-subject-118",
        "organization_id": organization_id,
        "roles": roles if roles is not None else ["grants_viewer"],
        "issued_at": issued_at,
        "expires_at": issued_at + lifetime_seconds,
        "auth_source": "demo_fixture",
        "session_id": session_id,
        "signing_key": FIXTURE_SIGNING_KEY,
        "is_demo_fixture": True,
        "now": now if now is not None else issued_at + 60,
    }
    kwargs.update(overrides)
    return build_session(**kwargs)


def session_format_invariant_failures(session: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if session.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in session:
            fails.append(f"session_format_missing_field:{field}")

    for constant in (
        "signing_key_value_emitted",
        "cookie_set_by_this_service",
        "persisted",
        "real_users_created",
        "provider_contacted",
        "fabricated",
    ):
        if session.get(constant) is not False:
            fails.append(f"session_format_claimed:{constant}")

    # A session may never carry an email. Personal data on every request.
    if session.get("email_included_in_payload"):
        fails.append("session_payload_carries_an_email")
    if "email" in session:
        fails.append("session_result_carries_an_email_field")

    # Nor a signing key, under any name.
    for field in ("signing_key", "signing_key_value", "secret", "key"):
        if field in session:
            fails.append(f"session_result_carries_a_key_field:{field}")

    # The organization is the RLS authority or the session is worthless.
    if session.get("session_cookie_valid"):
        if not session.get("organization_id_uuid_shaped"):
            fails.append("valid_session_without_a_uuid_organization_id")
        if not session.get("signature_valid"):
            fails.append("valid_session_without_a_valid_signature")
        if session.get("expired"):
            fails.append("valid_session_that_is_expired")
        if session.get("blocked_reasons"):
            fails.append("valid_session_despite_blocked_reasons")

    # A signature cannot be valid without one being present.
    if session.get("signature_valid") and not session.get("signature_present"):
        fails.append("signature_valid_without_a_signature")

    # Production requires a configured key and no fixture marking.
    if session.get("production_session"):
        if not session.get("signing_key_ready"):
            fails.append("production_session_without_a_signing_key_fit_to_sign")
        if not session.get("signing_key_present"):
            fails.append("production_session_without_a_configured_signing_key")
        if session.get("demo_fixture"):
            fails.append("production_session_marked_as_a_demo_fixture")
        if not session.get("session_cookie_valid"):
            fails.append("production_session_that_is_not_valid")

    # A fixture may never be production, whatever else it says.
    if session.get("demo_fixture") and session.get("production_session"):
        fails.append("fixture_session_reported_as_production")

    # Expiry must be sane.
    issued = session.get("issued_at") or 0
    expires = session.get("expires_at") or 0
    if issued and expires and expires <= issued:
        if not session.get("blocked_reasons"):
            fails.append("expiry_before_issue_without_a_reason")

    # A refusal must name itself.
    if not session.get("session_cookie_valid") and not session.get("blocked_reasons"):
        fails.append("session_refused_without_a_reason")

    return fails
