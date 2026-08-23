"""Request identity contract (Gate 59).

Gate 58 enforced tenant isolation on every org-scoped route. The remaining gap
was identity: there is no authenticated actor, so role, membership and authority
enforcement had nothing trustworthy to key on.

This module defines what a request identity *is* and, more importantly, what it
is not. The governing rules:

  * **A client never supplies its own authority.** A role or org arriving in a
    header, body or unverified token claim is recorded as *asserted* and is
    never promoted to trusted. Trusting it would be worse than having no check,
    because it would look like enforcement.
  * **Cloudflare Access is not customer login.** Access protects the demo URL
    and proves someone passed an operator gate. It says nothing about which
    customer organization a person may act for.
  * **Unverified is not verified.** Configured-but-unverified OIDC unlocks
    nothing.

Nothing here performs network I/O or token cryptography. Verification is an
input to this contract, supplied by a real verifier once one exists;
``oidc_readiness_service`` reports whether that is even possible yet.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_request_identity_v1"

IDENTITY_STATES = frozenset(
    {
        "anonymous",
        "demo_operator",
        "oidc_unconfigured",
        "oidc_configured_unverified",
        "oidc_verified",
        "invalid",
        "unknown",
    }
)

# The only state from which customer authority can ever flow.
CUSTOMER_AUTHORITY_CAPABLE_STATES = frozenset({"oidc_verified"})

# States that may read demo surfaces but never act as a customer.
DEMO_ONLY_STATES = frozenset({"demo_operator"})

# Everything else denies customer actions outright.
DENY_CUSTOMER_ACTION_STATES = IDENTITY_STATES - CUSTOMER_AUTHORITY_CAPABLE_STATES

MEMBERSHIP_SOURCES = frozenset(
    {
        "none",
        "client_asserted",  # never trusted
        "dev_header",  # demo/dev routing only, never membership proof
        "verified_directory",  # trusted; does not exist yet
        "unknown",
    }
)

TRUSTED_MEMBERSHIP_SOURCES = frozenset({"verified_directory"})

VERIFICATION_SOURCES = frozenset(
    {
        "none",
        "cloudflare_access",  # operator gate, NOT customer login
        "oidc_token_signature",  # trusted; requires a real verifier
        "dev_fixture",
        "unknown",
    }
)

TRUSTED_VERIFICATION_SOURCES = frozenset({"oidc_token_signature"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_request_identity(
    *,
    identity_state: str = "unknown",
    subject: str | None = None,
    email: str | None = None,
    email_verified: bool = False,
    issuer: str | None = None,
    audience: str | None = None,
    asserted_org_claims: list[str] | None = None,
    asserted_role_claims: list[str] | None = None,
    membership_source: str = "none",
    verification_source: str = "none",
    verified_org_id: str | None = None,
    verified_role: str | None = None,
    oidc_configured: bool = False,
) -> dict[str, Any]:
    """Build a request identity, normalizing anything unknown to a denial.

    ``asserted_*`` fields are what the client claimed. ``verified_*`` fields are
    what a trusted source confirmed. They are kept separate on purpose so no
    later code can confuse one for the other.
    """
    state = identity_state if identity_state in IDENTITY_STATES else "unknown"
    msrc = membership_source if membership_source in MEMBERSHIP_SOURCES else "unknown"
    vsrc = (
        verification_source
        if verification_source in VERIFICATION_SOURCES
        else "unknown"
    )

    # An identity claiming verification without a trusted verification source is
    # not verified, whatever the caller passed in.
    if state == "oidc_verified" and vsrc not in TRUSTED_VERIFICATION_SOURCES:
        state = "oidc_configured_unverified"

    # OIDC cannot be verified if it is not even configured.
    if state in {"oidc_verified", "oidc_configured_unverified"} and not oidc_configured:
        state = "oidc_unconfigured"

    membership_trusted = msrc in TRUSTED_MEMBERSHIP_SOURCES and bool(verified_org_id)
    verification_trusted = vsrc in TRUSTED_VERIFICATION_SOURCES

    # A role is trusted only when it arrived with trusted verification AND a
    # trusted membership. A verified token for an org you are not a member of
    # grants nothing.
    role_trusted = bool(
        verified_role and verification_trusted and membership_trusted
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_state": state,
            "subject": subject,
            "email": email,
            "email_verified": bool(email_verified),
            "issuer": issuer,
            "audience": audience,
            # What the client said. Recorded, never trusted.
            "asserted_org_claims": list(asserted_org_claims or []),
            "asserted_role_claims": list(asserted_role_claims or []),
            "client_asserted_role_trusted": False,
            "client_asserted_org_trusted": False,
            # What a trusted source confirmed.
            "membership_source": msrc,
            "verification_source": vsrc,
            "verified_org_id": verified_org_id if membership_trusted else None,
            "verified_role": verified_role if role_trusted else None,
            "membership_trusted": membership_trusted,
            "verification_trusted": verification_trusted,
            "role_trusted": role_trusted,
            # Capability / authority posture.
            "may_act_as_customer": state in CUSTOMER_AUTHORITY_CAPABLE_STATES
            and membership_trusted
            and role_trusted,
            "may_read_demo_surfaces": state in DEMO_ONLY_STATES
            or state in CUSTOMER_AUTHORITY_CAPABLE_STATES,
            "may_hold_customer_authority": state
            in CUSTOMER_AUTHORITY_CAPABLE_STATES
            and role_trusted,
            # Honest boundaries — never true in this gate.
            "oidc_configured": bool(oidc_configured),
            "login_live_claimed": False,
            "customer_login_live_claimed": False,
            "cloudflare_access_is_customer_login": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
        }
    )


def identity_from_cloudflare_access(
    *, access_email: str | None, oidc_configured: bool = False
) -> dict[str, Any]:
    """Map a Cloudflare Access session to a demo-operator identity.

    Access proves someone cleared an operator gate on the demo hostname. It is
    **not** customer login: it carries no organization membership and no
    customer role, so this returns ``demo_operator``, never ``oidc_verified``.
    """
    return build_request_identity(
        identity_state="demo_operator" if access_email else "anonymous",
        email=access_email,
        email_verified=False,
        membership_source="none",
        verification_source="cloudflare_access",
        oidc_configured=oidc_configured,
    )


def evaluate_customer_action(
    *, identity: dict[str, Any], action: str
) -> dict[str, Any]:
    """Decide whether an identity may perform a customer action at all.

    This runs *before* role capability. It answers "is there a trustworthy actor
    here", not "what may that actor do".
    """
    reasons: list[str] = []
    state = identity.get("identity_state")

    if state not in IDENTITY_STATES:
        reasons.append("identity_state_unknown")
    elif state in DENY_CUSTOMER_ACTION_STATES:
        reasons.append(f"identity_state_denies_customer_action:{state}")

    if not identity.get("verification_trusted"):
        reasons.append("verification_not_trusted")
    if not identity.get("membership_trusted"):
        reasons.append("membership_not_trusted")
    if not identity.get("role_trusted"):
        reasons.append("role_not_trusted")

    if identity.get("asserted_role_claims") and not identity.get("role_trusted"):
        reasons.append("client_asserted_role_ignored")

    allowed = not reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "action": action,
            "allowed": allowed,
            "blocked_reasons": reasons,
            "identity_state": state,
            "effective_role": identity.get("verified_role"),
            "effective_org_id": identity.get("verified_org_id"),
            "login_live_claimed": False,
            "customer_login_live_claimed": False,
            "audit_event": (
                None
                if allowed
                else {
                    "event_type": "authority_sensitive_action_blocked",
                    "action": action,
                    "identity_state": state,
                    "reasons": reasons,
                    "persisted": False,
                }
            ),
        }
    )


def request_identity_invariant_failures(identity: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if identity.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if identity.get("identity_state") not in IDENTITY_STATES:
        fails.append("identity_state_invalid")

    # Client assertions must never be marked trusted.
    for f in ("client_asserted_role_trusted", "client_asserted_org_trusted"):
        if identity.get(f) is not False:
            fails.append(f"client_assertion_trusted:{f}")

    # Trust flags must be consistent with their sources.
    if identity.get("verification_trusted") and identity.get(
        "verification_source"
    ) not in TRUSTED_VERIFICATION_SOURCES:
        fails.append("verification_trusted_without_trusted_source")
    if identity.get("membership_trusted") and identity.get(
        "membership_source"
    ) not in TRUSTED_MEMBERSHIP_SOURCES:
        fails.append("membership_trusted_without_trusted_source")
    if identity.get("role_trusted") and not (
        identity.get("verification_trusted") and identity.get("membership_trusted")
    ):
        fails.append("role_trusted_without_verification_and_membership")

    # Customer authority requires a verified state.
    if identity.get("may_hold_customer_authority") and identity.get(
        "identity_state"
    ) not in CUSTOMER_AUTHORITY_CAPABLE_STATES:
        fails.append("authority_without_verified_state")
    if identity.get("may_act_as_customer") and not identity.get("role_trusted"):
        fails.append("customer_action_without_trusted_role")

    # Cloudflare Access must never be recorded as customer login.
    if identity.get("cloudflare_access_is_customer_login") is not False:
        fails.append("cloudflare_access_claimed_as_customer_login")
    if identity.get("verification_source") == "cloudflare_access" and identity.get(
        "verification_trusted"
    ):
        fails.append("cloudflare_access_treated_as_trusted_verification")

    for forbidden in (
        "login_live_claimed",
        "customer_login_live_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
    ):
        if identity.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
