"""Membership invite / approval workflow (Gate 67).

Every prior gate built the *read* side of membership: verified token ->
identity -> membership row -> trusted role -> capability. This module is the
missing write side, and specifically the thing that stops a membership row from
existing because an internal operator typed one in.

The survey (doc 403) found that the two existing services here record an actor
without ever authorizing one. ``evaluate_seat_invite`` takes ``actor_id``,
writes it into an audit event, and never asks whether that actor holds
``manage_seats``. ``record_role_change`` does the same. Seat-cap enforcement was
real; inviter and approver authorization did not exist. This module is the
authorization layer those two lack.

It composes with them rather than replacing them — ``org_tenant_seat_model_service``
and ``rbac_privilege_matrix_service`` are untouched, so their existing tests keep
their meaning.

**Nothing here persists.** There is no provisioned database. Every emitted audit
event carries ``persisted: false``, and the invariants fail anything claiming
otherwise. This is a decision service: given a proposed action it says whether
that action is permitted and what would be recorded.

Design choices worth naming, because each is a place this could quietly permit
too much:

  * **Deny by default on unknown.** Unknown invite state, unknown approval
    state, unknown role, unrecognised actor role — all denials. Denying sets are
    derived by set-difference so a state added later denies until someone
    deliberately permits it.
  * **A request is not an approval.** Requesting a seat override and approving
    one are separate acts, and for the override they must be separate *people*.
    Self-approving your own exception to the seat cap is the hole that makes a
    cap decorative.
  * **Acceptance is not activation.** An accepted invite yields
    ``pending_approval`` membership, not ``active``, unless approval already
    landed.
  * **Provenance is load-bearing.** A membership whose provenance is not a
    completed invite is untrusted, whatever its other fields say.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.domain.enums import AuditAction
from nativeforge.services.org_tenant_seat_model_service import (
    ALL_ROLES,
    DEFAULT_SEAT_CAP,
    INTERNAL_ROLES,
    ORG_ROLES,
    SEAT_CONSUMING_ROLES,
)
from nativeforge.services.rbac_privilege_matrix_service import ROLE_CAPABILITIES

SCHEMA_VERSION = "nf_membership_invite_approval_v1"

# ── vocabularies ────────────────────────────────────────────────────────────

INVITE_STATES = frozenset(
    {
        "draft",
        "pending_approval",
        "approved",
        "sent",
        "accepted",
        "expired",
        "revoked",
        "rejected",
        "unknown",
    }
)

# The only states from which an invite can go on to produce a membership.
# Derived denial set: a state added to INVITE_STATES later denies by default.
INVITE_LIVE_STATES = frozenset({"approved", "sent", "accepted"})
INVITE_DENYING_STATES = INVITE_STATES - INVITE_LIVE_STATES

APPROVAL_STATES = frozenset(
    {
        "not_required",
        "required",
        "pending",
        "approved",
        "rejected",
        "expired",
        "revoked",
        "unknown",
    }
)

APPROVAL_SATISFIED_STATES = frozenset({"approved", "not_required"})
APPROVAL_DENYING_STATES = APPROVAL_STATES - APPROVAL_SATISFIED_STATES

MEMBERSHIP_STATES_AFTER_ACCEPTANCE = frozenset({"none", "pending_approval", "active"})

# The capability that gates both inviting and approving. Held by org_owner and
# org_admin only, per the Gate 57 matrix.
SEAT_MANAGEMENT_CAPABILITY = "manage_seats"

# Where a membership row came from. Only a completed invite is trusted, which is
# the entire point of this gate.
MEMBERSHIP_PROVENANCES = frozenset(
    {
        "completed_invite",
        "operator_direct_write",
        "migration_backfill",
        "unknown",
    }
)
TRUSTED_PROVENANCES = frozenset({"completed_invite"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _role_has_seat_management(role: str | None) -> bool:
    """Whether a role may invite or approve seats.

    Reads the Gate 57 matrix rather than hardcoding a role list, so a matrix
    change cannot silently diverge from this gate.
    """
    if not role or role not in ROLE_CAPABILITIES:
        return False
    return SEAT_MANAGEMENT_CAPABILITY in ROLE_CAPABILITIES[role]


def make_audit_event(
    action: AuditAction,
    *,
    organization_id: str | None,
    actor_id: str | None = None,
    subject_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A modeled audit event. Never persisted, and says so."""
    return {
        "event_type": action.value,
        "organization_profile_id": organization_id,
        "actor_id": actor_id,
        "subject_id": subject_id,
        "detail": dict(detail or {}),
        # No provisioned database, no audit sink. Flips only when doc 391's
        # wiring lands against real storage.
        "persisted": False,
    }


# ── invite evaluation ───────────────────────────────────────────────────────


def evaluate_invite(
    *,
    invite_id: str,
    organization_id: str,
    requested_role: str,
    requested_by: str,
    requested_by_role: str,
    invited_email: str | None = None,
    invited_subject: str | None = None,
    invited_issuer: str | None = None,
    invite_state: str = "draft",
    approval_required: bool = True,
    approval_state: str = "pending",
    approved_by: str | None = None,
    approved_by_role: str | None = None,
    seat_cap: int = DEFAULT_SEAT_CAP,
    seat_count: int = 0,
    seat_override_requested: bool = False,
    seat_override_approved_by: str | None = None,
    seat_override_approved_by_role: str | None = None,
    created_at: str | None = None,
    expires_at: str | None = None,
    accepted_at: str | None = None,
    revoked_at: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Decide whether an invite may produce a membership, and in what state.

    ``now`` is caller-supplied so expiry is deterministic under test rather than
    dependent on the wall clock.
    """
    blocked: list[str] = []
    audit: list[dict[str, Any]] = []

    state = invite_state if invite_state in INVITE_STATES else "unknown"
    astate = approval_state if approval_state in APPROVAL_STATES else "unknown"
    role = requested_role if requested_role in ALL_ROLES else "unknown"

    # ── derived state overrides ──────────────────────────────────────────
    # A revocation timestamp means revoked whatever the state column says, and
    # an elapsed expiry means expired. Trusting the column over the timestamp is
    # how a revoked invite gets accepted.
    if revoked_at:
        state = "revoked"
    elif expires_at and now and str(now) >= str(expires_at) and state != "accepted":
        state = "expired"

    if state == "unknown":
        blocked.append("invite_state_unknown")
    elif state in INVITE_DENYING_STATES:
        blocked.append(f"invite_state_denies:{state}")

    # ── role rules ───────────────────────────────────────────────────────
    if role == "unknown":
        blocked.append("requested_role_unknown")
    elif role in INTERNAL_ROLES:
        # Internal support is granted by us, not invited by a customer, and it
        # never carries customer authority.
        blocked.append("internal_role_cannot_be_invited_as_customer_role")
    elif role not in ORG_ROLES:
        blocked.append(f"requested_role_not_invitable:{role}")

    # ── inviter authorization ────────────────────────────────────────────
    # The gap the survey found: the existing seat service records this actor
    # without checking them.
    if not requested_by:
        blocked.append("inviter_missing")
    if not _role_has_seat_management(requested_by_role):
        blocked.append(
            f"inviter_lacks_{SEAT_MANAGEMENT_CAPABILITY}:{requested_by_role or 'none'}"
        )

    # ── approval ─────────────────────────────────────────────────────────
    if not approval_required:
        # Only meaningful when the workflow explicitly says so; the default is
        # that approval is required.
        astate = "not_required" if astate in {"not_required", "pending"} else astate

    if astate in APPROVAL_DENYING_STATES:
        blocked.append(f"approval_state_denies:{astate}")

    if astate == "approved":
        if not approved_by:
            blocked.append("approval_claimed_without_approver")
        if not _role_has_seat_management(approved_by_role):
            blocked.append(
                f"approver_lacks_{SEAT_MANAGEMENT_CAPABILITY}:"
                f"{approved_by_role or 'none'}"
            )

    # ── seats ────────────────────────────────────────────────────────────
    consumes_seat = role in SEAT_CONSUMING_ROLES
    cap = int(seat_cap or DEFAULT_SEAT_CAP)
    used = int(seat_count or 0)
    override_ok = False

    if consumes_seat and used >= cap:
        # A request is not an approval. The override needs its own approved-by,
        # that approver needs manage_seats, and — for the override specifically
        # — it must not be the person who asked for it. Self-approving your own
        # exception to the cap is what makes a cap decorative.
        if not seat_override_approved_by:
            blocked.append("seat_cap_reached_no_override_approval")
            if seat_override_requested:
                blocked.append("seat_override_requested_but_not_approved")
        elif not _role_has_seat_management(seat_override_approved_by_role):
            blocked.append(
                "seat_override_approver_lacks_"
                f"{SEAT_MANAGEMENT_CAPABILITY}:"
                f"{seat_override_approved_by_role or 'none'}"
            )
        elif seat_override_approved_by == requested_by:
            blocked.append("seat_override_self_approved")
        else:
            override_ok = True

    # ── outcome ──────────────────────────────────────────────────────────
    allowed = not blocked

    if not allowed:
        membership_after = "none"
    elif state == "accepted":
        # Acceptance is not activation. Only a satisfied approval turns an
        # accepted invite into an active membership.
        membership_after = (
            "active" if astate in APPROVAL_SATISFIED_STATES else "pending_approval"
        )
    else:
        membership_after = "none"

    if membership_after == "active":
        audit.append(
            make_audit_event(
                AuditAction.membership_created,
                organization_id=organization_id,
                actor_id=approved_by or requested_by,
                subject_id=invited_subject or invited_email,
                detail={
                    "invite_id": invite_id,
                    "role": role,
                    "provenance": "completed_invite",
                    "consumes_seat": consumes_seat,
                    "seat_override_used": override_ok,
                },
            )
        )
    if blocked:
        audit.append(
            make_audit_event(
                AuditAction.tenant_access_denied,
                organization_id=organization_id,
                actor_id=requested_by,
                subject_id=invited_subject or invited_email,
                detail={"invite_id": invite_id, "reasons": list(blocked)},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invite_id": invite_id,
            "organization_id": organization_id,
            "invited_email": invited_email,
            "invited_subject": invited_subject,
            "invited_issuer": invited_issuer,
            "requested_role": role,
            "requested_by": requested_by,
            "approved_by": approved_by if astate == "approved" else None,
            "invite_state": state,
            "approval_state": astate,
            "approval_required": bool(approval_required),
            "allowed": allowed,
            "blocked_reasons": blocked,
            "consumes_seat": consumes_seat,
            "seat_cap": cap,
            "seat_count": used,
            "seat_override_requested": bool(seat_override_requested),
            "seat_override_approved": override_ok,
            "membership_state_after_acceptance": membership_after,
            "can_activate_membership": membership_after == "active",
            "carries_customer_authority": False,
            "created_at": created_at,
            "expires_at": expires_at,
            "accepted_at": accepted_at,
            "revoked_at": revoked_at,
            "audit_events": audit,
            "persisted": False,
            "customer_login_live": False,
        }
    )


# ── membership provenance ───────────────────────────────────────────────────


def evaluate_membership_provenance(
    *,
    organization_id: str,
    subject_id: str | None,
    provenance: str = "unknown",
    invite_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Whether a membership row's origin makes it trustworthy.

    This is the gate's central claim in one function: a membership that did not
    come through a completed invite is not trusted, however well-formed its
    other columns are. An operator direct-write is the specific case this
    exists to refuse.
    """
    prov = provenance if provenance in MEMBERSHIP_PROVENANCES else "unknown"
    blocked: list[str] = []

    if prov not in TRUSTED_PROVENANCES:
        blocked.append(f"untrusted_membership_provenance:{prov}")
    if prov == "completed_invite" and not invite_id:
        # Claiming invite provenance without naming the invite is unfalsifiable.
        blocked.append("completed_invite_provenance_without_invite_id")

    trusted = not blocked
    audit: list[dict[str, Any]] = []
    if not trusted:
        audit.append(
            make_audit_event(
                AuditAction.authority_sensitive_action_blocked,
                organization_id=organization_id,
                actor_id=actor_id,
                subject_id=subject_id,
                detail={"reasons": list(blocked), "provenance": prov},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "subject_id": subject_id,
            "provenance": prov,
            "invite_id": invite_id,
            "trusted": trusted,
            "blocked_reasons": blocked,
            "audit_events": audit,
            "persisted": False,
        }
    )


# ── role change ─────────────────────────────────────────────────────────────

_AUTHORITY_ROLES = frozenset({"org_owner", "org_admin", "authorized_representative"})

# Rough seniority, used only to label a change as upgrade or downgrade so the
# two are distinguishable in an audit trail.
_ROLE_RANK = {
    "viewer": 1,
    "reviewer": 2,
    "grant_lead": 3,
    "authorized_representative": 4,
    "org_admin": 5,
    "org_owner": 6,
}


def evaluate_role_change(
    *,
    organization_id: str,
    subject_id: str,
    old_role: str,
    new_role: str,
    actor_id: str,
    actor_role: str,
) -> dict[str, Any]:
    """Authorize a role change, then describe it.

    ``record_role_change`` in the RBAC service describes one without
    authorizing it. This adds the missing check.
    """
    blocked: list[str] = []
    old = old_role if old_role in ALL_ROLES else "unknown"
    new = new_role if new_role in ALL_ROLES else "unknown"

    if new == "unknown":
        blocked.append("new_role_unknown")
    elif new in INTERNAL_ROLES:
        blocked.append("cannot_change_customer_role_to_internal_role")
    elif new not in ORG_ROLES:
        blocked.append(f"new_role_not_assignable:{new}")

    if old in INTERNAL_ROLES:
        blocked.append("cannot_change_an_internal_support_role_through_this_path")

    if not actor_id:
        blocked.append("actor_missing")
    if not _role_has_seat_management(actor_role):
        blocked.append(
            f"actor_lacks_{SEAT_MANAGEMENT_CAPABILITY}:{actor_role or 'none'}"
        )
    if old == new:
        blocked.append("no_op_role_change")

    allowed = not blocked

    old_rank = _ROLE_RANK.get(old, 0)
    new_rank = _ROLE_RANK.get(new, 0)
    direction = "unchanged"
    if new_rank > old_rank:
        direction = "upgrade"
    elif new_rank < old_rank:
        direction = "downgrade"

    audit: list[dict[str, Any]] = []
    if allowed:
        audit.append(
            make_audit_event(
                AuditAction.role_changed,
                organization_id=organization_id,
                actor_id=actor_id,
                subject_id=subject_id,
                detail={
                    "old_role": old,
                    "new_role": new,
                    "direction": direction,
                    "is_privilege_escalation": (
                        new in _AUTHORITY_ROLES and old not in _AUTHORITY_ROLES
                    ),
                },
            )
        )
    else:
        audit.append(
            make_audit_event(
                AuditAction.tenant_access_denied,
                organization_id=organization_id,
                actor_id=actor_id,
                subject_id=subject_id,
                detail={"reasons": list(blocked), "attempted_new_role": new},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "subject_id": subject_id,
            "old_role": old,
            "new_role": new if allowed else old,
            "attempted_new_role": new,
            "direction": direction,
            "allowed": allowed,
            "blocked_reasons": blocked,
            "is_privilege_escalation": (
                allowed and new in _AUTHORITY_ROLES and old not in _AUTHORITY_ROLES
            ),
            # A role is a permission to ask, not a granted authority. Authority
            # still requires a verified authority proof at use time.
            "grants_customer_authority_immediately": False,
            "audit_events": audit,
            "persisted": False,
        }
    )


# ── revocation and expiry ───────────────────────────────────────────────────


def evaluate_membership_revocation(
    *,
    organization_id: str,
    subject_id: str,
    actor_id: str,
    actor_role: str,
    reason: str | None = None,
) -> dict[str, Any]:
    blocked: list[str] = []
    if not actor_id:
        blocked.append("actor_missing")
    if not _role_has_seat_management(actor_role):
        blocked.append(
            f"actor_lacks_{SEAT_MANAGEMENT_CAPABILITY}:{actor_role or 'none'}"
        )

    allowed = not blocked
    audit = [
        make_audit_event(
            AuditAction.membership_revoked
            if allowed
            else AuditAction.tenant_access_denied,
            organization_id=organization_id,
            actor_id=actor_id,
            subject_id=subject_id,
            detail=({"reason": reason} if allowed else {"reasons": list(blocked)}),
        )
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "subject_id": subject_id,
            "allowed": allowed,
            "blocked_reasons": blocked,
            "membership_state_after": "revoked" if allowed else "unchanged",
            "seat_released": allowed,
            "audit_events": audit,
            "persisted": False,
        }
    )


def evaluate_membership_expiry(
    *,
    organization_id: str,
    subject_id: str,
    expires_at: str | None,
    now: str | None,
) -> dict[str, Any]:
    """Expiry is a fact about time, not an action someone takes.

    Deliberately requires no actor: it needs no authorization, and modelling it
    as an action would imply someone must remember to perform it.
    """
    expired = bool(expires_at and now and str(now) >= str(expires_at))
    audit: list[dict[str, Any]] = []
    if expired:
        audit.append(
            make_audit_event(
                AuditAction.membership_expired,
                organization_id=organization_id,
                actor_id=None,
                subject_id=subject_id,
                detail={"expires_at": expires_at, "observed_at": now},
            )
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "subject_id": subject_id,
            "expired": expired,
            "expires_at": expires_at,
            "observed_at": now,
            "membership_state_after": "expired" if expired else "unchanged",
            "seat_released": expired,
            "audit_events": audit,
            "persisted": False,
        }
    )


# ── invariants ──────────────────────────────────────────────────────────────


def _audit_invariant_failures(events: list[dict[str, Any]]) -> list[str]:
    fails: list[str] = []
    for event in events or []:
        if event.get("persisted") is not False:
            fails.append("audit_event_claims_persistence")
        if event.get("event_type") == AuditAction.cross_org_access_attempt.value:
            # Gate 65 established this cannot be represented by the current
            # schema. It must not appear here either.
            fails.append("emits_unpersistable_cross_org_access_attempt")
    return fails


def invite_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("invite_state") not in INVITE_STATES:
        fails.append("invite_state_invalid")
    if result.get("approval_state") not in APPROVAL_STATES:
        fails.append("approval_state_invalid")
    if result.get("membership_state_after_acceptance") not in (
        MEMBERSHIP_STATES_AFTER_ACCEPTANCE
    ):
        fails.append("membership_state_after_acceptance_invalid")

    if result.get("can_activate_membership"):
        if not result.get("allowed"):
            fails.append("activation_while_denied")
        if result.get("blocked_reasons"):
            fails.append("activation_with_blocked_reasons")
        if result.get("invite_state") != "accepted":
            fails.append("activation_without_accepted_invite")
        if result.get("approval_state") not in APPROVAL_SATISFIED_STATES:
            fails.append("activation_without_satisfied_approval")
        if result.get("requested_role") in INTERNAL_ROLES:
            fails.append("activation_of_internal_role")

    if result.get("allowed") and result.get("blocked_reasons"):
        fails.append("allowed_with_blocked_reasons")
    if not result.get("allowed") and not result.get("blocked_reasons"):
        fails.append("denied_without_reason")

    # A seat may only be exceeded through an approved override.
    if (
        result.get("consumes_seat")
        and result.get("seat_count", 0) >= result.get("seat_cap", DEFAULT_SEAT_CAP)
        and result.get("allowed")
        and not result.get("seat_override_approved")
    ):
        fails.append("seat_cap_exceeded_without_override")

    for forbidden in ("persisted", "customer_login_live", "carries_customer_authority"):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    fails.extend(_audit_invariant_failures(result.get("audit_events", [])))
    return fails


def role_change_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("allowed"):
        if result.get("blocked_reasons"):
            fails.append("allowed_with_blocked_reasons")
        if result.get("new_role") in INTERNAL_ROLES:
            fails.append("role_changed_into_internal_role")
    else:
        if not result.get("blocked_reasons"):
            fails.append("denied_without_reason")
        if result.get("new_role") != result.get("old_role"):
            fails.append("denied_change_altered_the_role")
    if result.get("grants_customer_authority_immediately") is not False:
        fails.append("forbidden_claim:grants_customer_authority_immediately")
    if result.get("persisted") is not False:
        fails.append("forbidden_claim:persisted")
    fails.extend(_audit_invariant_failures(result.get("audit_events", [])))
    return fails


def lifecycle_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("persisted") is not False:
        fails.append("forbidden_claim:persisted")
    fails.extend(_audit_invariant_failures(result.get("audit_events", [])))
    return fails
