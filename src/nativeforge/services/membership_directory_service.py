"""Membership directory (Gate 61).

Gate 60 delivered ``verified token -> verified identity``. This module is the
next link — ``verified identity -> trusted membership -> trusted role`` — and it
is deliberately built only as far as it can go honestly without approved
production storage.

**There is no production storage.** ``DATABASE_URL`` defaults to in-memory
SQLite, no Postgres is configured, and there is no users, identities,
memberships or roles table in the schema. The adapter here is therefore named
``InMemoryMembershipDirectory`` and reports
``storage_backend_state="in_memory_test_adapter"``. It is a test and design
vehicle, not a store. Every record it emits carries
``production_storage_live=False`` and ``customer_persistence_claimed=False``, and
invariants fail anything that says otherwise.

The rules that matter, all enforced rather than documented:

  * a verified token alone is not membership
  * an email domain alone is not membership
  * Cloudflare Access is not membership
  * a client header is not membership
  * membership must be ``active``
  * a role is only trusted when it comes from a trusted, active membership
  * ``operator_internal`` never becomes customer authority
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_tenant_seat_model_service import (
    ALL_ROLES,
    INTERNAL_ROLES,
)

SCHEMA_VERSION = "nf_membership_directory_v1"

MEMBERSHIP_STATES = frozenset(
    {
        "invited",
        "pending",
        "active",
        "suspended",
        "revoked",
        "expired",
        "unknown",
    }
)

# Only this state permits acting. Derived denial set so a state added later
# denies by default rather than silently permitting.
ACTING_STATES = frozenset({"active"})
DENYING_STATES = MEMBERSHIP_STATES - ACTING_STATES

TRUSTED_MEMBERSHIP_SOURCES = frozenset(
    {"verified_directory", "operator_approved", "org_owner_approved"}
)

UNTRUSTED_MEMBERSHIP_SOURCES = frozenset(
    {"client_header", "dev_header", "cloudflare_access", "email_domain_only"}
)

ALL_MEMBERSHIP_SOURCES = (
    TRUSTED_MEMBERSHIP_SOURCES | UNTRUSTED_MEMBERSHIP_SOURCES | {"none", "unknown"}
)

ROLE_SOURCES = frozenset(
    {
        "membership_record",  # trusted: role carried by a trusted membership
        "token_claim",  # NOT trusted: an IdP claim is not our directory
        "client_header",  # NOT trusted
        "email_domain",  # NOT trusted
        "none",
        "unknown",
    }
)

TRUSTED_ROLE_SOURCES = frozenset({"membership_record"})

# Honest description of where membership data actually lives today.
STORAGE_BACKEND_STATES = frozenset(
    {
        "no_backend",
        "in_memory_test_adapter",
        "local_dev_sqlite",
        "approved_production_backend",
        "unknown",
    }
)

PRODUCTION_BACKEND_STATES = frozenset({"approved_production_backend"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def storage_backend_status(
    *,
    backend_state: str = "in_memory_test_adapter",
    approval_token_present: bool = False,
) -> dict[str, Any]:
    """Report where membership data lives and what that permits.

    ``production_storage_live`` requires **both** an approved production backend
    and a present approval token. Neither exists, so it is False.
    """
    st = backend_state if backend_state in STORAGE_BACKEND_STATES else "unknown"
    live = st in PRODUCTION_BACKEND_STATES and bool(approval_token_present)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_backend_state": st,
            "approval_token_present": bool(approval_token_present),
            "production_storage_live": live,
            "customer_persistence_claimed": False,
            "live_customer_membership_lookup": False,
            "membership_schema_exists": False,
            "notes": (
                "No users/identities/memberships/roles table exists. "
                "DATABASE_URL defaults to in-memory SQLite."
            ),
        }
    )


def build_membership_record(
    *,
    subject: str | None,
    organization_profile_id: str | None,
    role: str | None = None,
    state: str = "unknown",
    membership_source: str = "none",
    role_source: str = "none",
    email: str | None = None,
    email_verified: bool = False,
    invited_by: str | None = None,
    approved_by: str | None = None,
    created_at: str | None = None,
    revoked_at: str | None = None,
    expires_at: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Build a membership record, deriving trust rather than accepting it.

    ``now`` is caller-supplied so expiry is deterministic and testable.
    """
    st = state if state in MEMBERSHIP_STATES else "unknown"
    msrc = (
        membership_source
        if membership_source in ALL_MEMBERSHIP_SOURCES
        else "unknown"
    )
    rsrc = role_source if role_source in ROLE_SOURCES else "unknown"
    normalized_role = role if role in ALL_ROLES else None

    # Derived, not trusted: an expiry in the past means expired regardless of
    # what state the caller supplied.
    if expires_at and now and str(now) >= str(expires_at):
        st = "expired"
    # A revocation timestamp means revoked, whatever else was claimed.
    if revoked_at:
        st = "revoked"

    # An approved-by-nobody record from an approval-requiring source is not
    # approved.
    if msrc in {"operator_approved", "org_owner_approved"} and not approved_by:
        msrc = "unknown"

    membership_trusted = bool(
        msrc in TRUSTED_MEMBERSHIP_SOURCES
        and subject
        and organization_profile_id
        and st in ACTING_STATES
    )

    role_trusted = bool(
        membership_trusted
        and normalized_role
        and rsrc in TRUSTED_ROLE_SOURCES
        # Internal support roles never become customer authority.
        and normalized_role not in INTERNAL_ROLES
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "subject": subject,
            "email": email,
            "email_verified": bool(email_verified),
            "organization_profile_id": organization_profile_id,
            "state": st,
            "membership_source": msrc,
            "role": normalized_role,
            "role_source": rsrc,
            "invited_by": invited_by,
            "approved_by": approved_by,
            "created_at": created_at,
            "revoked_at": revoked_at,
            "expires_at": expires_at,
            "membership_trusted": membership_trusted,
            "role_trusted": role_trusted,
            "trusted_role": normalized_role if role_trusted else None,
            "is_internal_role": bool(
                normalized_role and normalized_role in INTERNAL_ROLES
            ),
            # Honest boundaries.
            "production_storage_live": False,
            "customer_persistence_claimed": False,
            "persisted": False,
        }
    )


class InMemoryMembershipDirectory:
    """Design and test vehicle. **Not** a store, and named so it cannot be
    mistaken for one.

    Holds records for the duration of a process. Nothing is written anywhere,
    nothing survives a restart, and ``production_storage_live`` is always False.
    """

    storage_backend_state = "in_memory_test_adapter"

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], dict[str, Any]] = {}

    def put(self, record: dict[str, Any]) -> None:
        subject = str(record.get("subject") or "")
        org = str(record.get("organization_profile_id") or "")
        if not subject or not org:
            return
        self._records[(subject, org)] = dict(record)

    def lookup(
        self,
        *,
        subject: str | None,
        organization_profile_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Look up a record by whichever organization key the caller holds.

        This directory is a plain dict with no UUID column and no row-level
        security behind it, so profile keying is correct here - unlike the
        Postgres directory, where the same name was bound to a UUID column.
        Gate 113 added ``organization_id`` for vocabulary agreement, not because
        the in-memory keying was wrong.
        """
        key = organization_id if organization_id is not None else (
            organization_profile_id
        )
        if not subject or not key:
            return None
        rec = self._records.get((str(subject), str(key)))
        return dict(rec) if rec else None

    def status(self) -> dict[str, Any]:
        return storage_backend_status(
            backend_state=self.storage_backend_state, approval_token_present=False
        )


def resolve_trusted_membership(
    *,
    identity: dict[str, Any],
    organization_profile_id: str | None,
    directory: InMemoryMembershipDirectory | None = None,
) -> dict[str, Any]:
    """Bridge a verified identity to a trusted membership and role.

    This is the link Gate 60 could not build. It denies unless every step holds:
    the identity's verification is trusted, a membership record exists for that
    subject and organization, that record came from a trusted source, and it is
    active.
    """
    reasons: list[str] = []

    subject = identity.get("subject")
    if not identity.get("verification_trusted"):
        reasons.append("identity_verification_not_trusted")
    if not subject:
        reasons.append("identity_has_no_subject")
    if not organization_profile_id:
        reasons.append("no_organization_requested")

    record: dict[str, Any] | None = None
    if directory is not None and subject and organization_profile_id:
        record = directory.lookup(
            subject=subject, organization_profile_id=organization_profile_id
        )
    if record is None:
        reasons.append("no_membership_record")
    else:
        state = record.get("state")
        if state in DENYING_STATES:
            reasons.append(f"membership_state_denies:{state}")
        if not record.get("membership_trusted"):
            reasons.append(
                f"membership_source_not_trusted:{record.get('membership_source')}"
            )
        if not record.get("role_trusted"):
            reasons.append("role_not_trusted")
        if record.get("is_internal_role"):
            reasons.append("internal_role_cannot_hold_customer_authority")

    allowed = not reasons
    trusted_role = record.get("trusted_role") if (allowed and record) else None

    status = (
        directory.status()
        if directory is not None
        else storage_backend_status(backend_state="no_backend")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": allowed,
            "blocked_reasons": reasons,
            "subject": subject,
            "organization_profile_id": organization_profile_id,
            "trusted_role": trusted_role,
            "membership_state": (record or {}).get("state"),
            "membership_source": (record or {}).get("membership_source"),
            "storage_backend_state": status["storage_backend_state"],
            "production_storage_live": status["production_storage_live"],
            "live_customer_membership_lookup": False,
            "customer_login_live_claimed": False,
            "customer_persistence_claimed": False,
            "audit_event": (
                None
                if allowed
                else {
                    "event_type": "tenant_access_denied",
                    "subject": subject,
                    "organization_profile_id": organization_profile_id,
                    "reasons": reasons,
                    "persisted": False,
                }
            ),
        }
    )


def membership_record_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("state") not in MEMBERSHIP_STATES:
        fails.append("state_invalid")
    if record.get("membership_source") not in ALL_MEMBERSHIP_SOURCES:
        fails.append("membership_source_invalid")
    if record.get("role_source") not in ROLE_SOURCES:
        fails.append("role_source_invalid")

    # Trust must never come from an untrusted source or a non-active state.
    if record.get("membership_trusted"):
        if record.get("membership_source") not in TRUSTED_MEMBERSHIP_SOURCES:
            fails.append("membership_trusted_from_untrusted_source")
        if record.get("state") not in ACTING_STATES:
            fails.append("membership_trusted_while_not_active")
    if record.get("role_trusted"):
        if not record.get("membership_trusted"):
            fails.append("role_trusted_without_trusted_membership")
        if record.get("role_source") not in TRUSTED_ROLE_SOURCES:
            fails.append("role_trusted_from_untrusted_source")
        if record.get("is_internal_role"):
            fails.append("internal_role_trusted_as_customer_authority")
    if record.get("trusted_role") and not record.get("role_trusted"):
        fails.append("trusted_role_set_without_role_trust")

    for forbidden in (
        "production_storage_live",
        "customer_persistence_claimed",
        "persisted",
    ):
        if record.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails


def storage_status_invariant_failures(status: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if status.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if status.get("storage_backend_state") not in STORAGE_BACKEND_STATES:
        fails.append("storage_backend_state_invalid")
    # production_storage_live requires an approved backend AND a token.
    if status.get("production_storage_live"):
        if status.get("storage_backend_state") not in PRODUCTION_BACKEND_STATES:
            fails.append("production_live_without_approved_backend")
        if not status.get("approval_token_present"):
            fails.append("production_live_without_approval_token")
    for forbidden in (
        "customer_persistence_claimed",
        "live_customer_membership_lookup",
        "membership_schema_exists",
    ):
        if status.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
