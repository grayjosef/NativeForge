"""177E/F/G: establishing a tenant, its roles, and who may invite whom.

The survey found one role in use across the whole system - `org_owner` - and
no controlling-company boundary at all: the phrase appears nowhere in the
package. So a customer administrator and the vendor's own staff were, as far
as the model was concerned, the same kind of thing.

## The boundary that matters most

`CONTROLLING_COMPANY_ADMIN` is not the top of the customer role ladder. It is
a different ladder. An organisation's most senior administrator is
`ORG_SUPER_ADMIN`, and there is no sequence of legitimate actions by which
they reach `CONTROLLING_COMPANY_ADMIN`, because `ASSIGNABLE_BY` never lists a
customer role as able to confer it.

This is stated as data rather than as a series of `if` statements, because a
privilege boundary spread across conditionals is a boundary that will be
re-implemented slightly differently somewhere else. One table answers "who may
confer what", and every path asks it.

## Tenancy

Every membership and every invitation names exactly one organisation, and
every authorisation check compares the actor's organisation with the target's.
Cross-tenant administration is refused by comparison, not by absence of a
route: `authorize_admin_action` takes both organisations and requires them to
match before it considers anything else.

## Invitations are not authority

An invitation from an authorised administrator is evidence toward
`ORG_ADMIN_CONFIRMED` authority - it is in `ESTABLISHES_AUTHORITY` for that
reason. An invitation from an ordinary member is nothing at all, and is
refused at issue rather than accepted and filtered later, so an unauthorised
invitation never exists to be found in an inbox.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

SCHEMA_VERSION = "nf_tenant_administration_v1"

ADMINISTRATION_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 177F: two ladders, not one.
# ---------------------------------------------------------------------------

CONTROLLING_COMPANY_ADMIN = "CONTROLLING_COMPANY_ADMIN"

ORG_SUPER_ADMIN = "ORG_SUPER_ADMIN"
ORG_ADMIN = "ORG_ADMIN"
ORG_REVIEWER = "ORG_REVIEWER"
ORG_MEMBER = "ORG_MEMBER"

ROLES: tuple[str, ...] = (
    CONTROLLING_COMPANY_ADMIN,
    ORG_SUPER_ADMIN,
    ORG_ADMIN,
    ORG_REVIEWER,
    ORG_MEMBER,
)

ROLE_MEANINGS: dict[str, str] = {
    CONTROLLING_COMPANY_ADMIN: (
        "vendor staff. Not the top of the customer ladder - a different one"
    ),
    ORG_SUPER_ADMIN: (
        "the organisation's most senior administrator; may administer the "
        "tenant and confer ORG_ADMIN"
    ),
    ORG_ADMIN: "may manage members and the organisation profile",
    ORG_REVIEWER: "read-only across the organisation's work",
    ORG_MEMBER: "an ordinary member of the organisation",
}

#: Roles that belong to the customer. The complement is not "everything else",
#: it is one role, and keeping the two sets explicit is what makes
#: `customer_admin_cannot_become_controlling_company` checkable.
CUSTOMER_ROLES: frozenset[str] = frozenset(
    {ORG_SUPER_ADMIN, ORG_ADMIN, ORG_REVIEWER, ORG_MEMBER}
)

CONTROLLING_COMPANY_ROLES: frozenset[str] = frozenset({CONTROLLING_COMPANY_ADMIN})

#: WHO MAY CONFER WHAT. The one table that answers the privilege question.
#: No customer role appears as a conferrer of CONTROLLING_COMPANY_ADMIN, and
#: no chain of legitimate actions can add one at runtime.
ASSIGNABLE_BY: dict[str, frozenset[str]] = {
    CONTROLLING_COMPANY_ADMIN: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ORG_SUPER_ADMIN: frozenset({CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN}),
    ORG_ADMIN: frozenset({CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN}),
    ORG_REVIEWER: frozenset({CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}),
    ORG_MEMBER: frozenset({CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}),
}

#: Actions and the roles that may take them, within ONE organisation.
ACTION_INVITE_MEMBER = "INVITE_MEMBER"
ACTION_REVOKE_INVITATION = "REVOKE_INVITATION"
ACTION_RESEND_INVITATION = "RESEND_INVITATION"
ACTION_REMOVE_MEMBER = "REMOVE_MEMBER"
ACTION_CHANGE_ROLE = "CHANGE_ROLE"
ACTION_EDIT_PROFILE = "EDIT_PROFILE"
ACTION_PUBLISH_ORG_DEFAULTS = "PUBLISH_ORG_DEFAULTS"
ACTION_VERIFY_AUTHORITY_MANUALLY = "VERIFY_AUTHORITY_MANUALLY"
ACTION_CREATE_ORGANIZATION = "CREATE_ORGANIZATION"

ACTIONS: tuple[str, ...] = (
    ACTION_INVITE_MEMBER,
    ACTION_REVOKE_INVITATION,
    ACTION_RESEND_INVITATION,
    ACTION_REMOVE_MEMBER,
    ACTION_CHANGE_ROLE,
    ACTION_EDIT_PROFILE,
    ACTION_PUBLISH_ORG_DEFAULTS,
    ACTION_VERIFY_AUTHORITY_MANUALLY,
    ACTION_CREATE_ORGANIZATION,
)

PERMITTED_BY: dict[str, frozenset[str]] = {
    ACTION_INVITE_MEMBER: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    ACTION_REVOKE_INVITATION: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    ACTION_RESEND_INVITATION: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    ACTION_REMOVE_MEMBER: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    ACTION_CHANGE_ROLE: frozenset({CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN}),
    ACTION_EDIT_PROFILE: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    ACTION_PUBLISH_ORG_DEFAULTS: frozenset(
        {CONTROLLING_COMPANY_ADMIN, ORG_SUPER_ADMIN, ORG_ADMIN}
    ),
    # Controlling-company only, by construction and by test.
    ACTION_VERIFY_AUTHORITY_MANUALLY: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_CREATE_ORGANIZATION: frozenset({CONTROLLING_COMPANY_ADMIN}),
}

#: Actions no customer role may ever take, derived rather than listed twice.
CONTROLLING_COMPANY_ONLY: frozenset[str] = frozenset(
    action for action, roles in PERMITTED_BY.items() if not (roles & CUSTOMER_ROLES)
)

# ---- invitations --------------------------------------------------------
INVITE_PENDING = "PENDING"
INVITE_ACCEPTED = "ACCEPTED"
INVITE_REVOKED = "REVOKED"
INVITE_EXPIRED = "EXPIRED"

INVITE_STATES: tuple[str, ...] = (
    INVITE_PENDING,
    INVITE_ACCEPTED,
    INVITE_REVOKED,
    INVITE_EXPIRED,
)

INVITE_MEANINGS: dict[str, str] = {
    INVITE_PENDING: "issued and not yet answered",
    INVITE_ACCEPTED: "the invited person joined the organisation",
    INVITE_REVOKED: "an authorised administrator withdrew it",
    INVITE_EXPIRED: "it had an end date and that date has passed",
}

INVITE_FIELDS: tuple[str, ...] = (
    "invitation_id",
    "organization_id",
    "invited_by",
    "invited_by_role",
    "invited_subject_ref",
    "offered_role",
    "invite_state",
    "issued_at",
    "expires_at",
    "answered_at",
    "revoked_by",
    "revoked_reason",
    "is_demo",
    "model_version",
)


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _refused(why: str, **extra: Any) -> dict[str, Any]:
    return {"permitted": False, "accepted": False, "why": why, **extra}


def authorize_admin_action(
    *,
    action: str,
    actor_role: str,
    actor_organization_id: Any,
    target_organization_id: Any,
    target_role: Any = None,
) -> dict[str, Any]:
    """May this actor take this action, in THIS organisation, on THIS role?

    Four questions, asked in order, each answerable on its own:

      1. is the action one we know?
      2. is the actor's organisation the target's? (tenancy)
      3. does the actor's role permit the action? (privilege)
      4. if a role is being conferred, may the actor confer THAT role?

    Question 4 is separate from question 3 on purpose. An ORG_ADMIN may invite
    members - but that must not let them invite somebody as
    CONTROLLING_COMPANY_ADMIN, and a single "can they invite" check would.
    """
    act = str(action)
    role = str(actor_role)

    if act not in ACTIONS:
        return _refused(f"{act} is not an action", action=act)
    if role not in ROLES:
        return _refused(f"{role} is not a role", action=act)

    # Tenancy first: a cross-tenant attempt is refused before privilege is
    # even considered, so a genuine org admin cannot reach another tenant.
    same_tenant = bool(actor_organization_id) and str(actor_organization_id) == str(
        target_organization_id
    )
    controlling = role in CONTROLLING_COMPANY_ROLES
    if not same_tenant and not controlling:
        return _refused(
            "cross-tenant administration is refused",
            action=act,
            cross_tenant_attempt=True,
            actor_organization_id=str(actor_organization_id or ""),
            target_organization_id=str(target_organization_id or ""),
        )

    if role not in PERMITTED_BY[act]:
        return _refused(
            f"{role} may not {act}",
            action=act,
            controlling_company_only=act in CONTROLLING_COMPANY_ONLY,
        )

    # The role being conferred is a separate question from the action.
    if target_role is not None:
        conferred = str(target_role)
        if conferred not in ROLES:
            return _refused(f"{conferred} is not a role", action=act)
        if role not in ASSIGNABLE_BY[conferred]:
            return _refused(
                f"{role} may not confer {conferred}",
                action=act,
                privilege_escalation_attempt=conferred in CONTROLLING_COMPANY_ROLES,
            )

    return {
        "permitted": True,
        "accepted": True,
        "action": act,
        "actor_role": role,
        "same_tenant": same_tenant,
        "cross_tenant_attempt": False,
        "privilege_escalation_attempt": False,
        "why": f"{role} may {act}",
    }


def build_invitation_id(
    *, organization_id: Any, invited_subject_ref: Any, offered_role: Any
) -> str:
    parts = [
        str(organization_id or ""),
        str(invited_subject_ref or ""),
        str(offered_role or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def issue_invitation(
    *,
    organization_id: Any,
    invited_subject_ref: Any,
    offered_role: str,
    invited_by: Any,
    invited_by_role: str,
    invited_by_organization_id: Any,
    expires_at: Any = None,
    issued_at: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """177G. An invitation an unauthorised person tried to send never exists.

    Refusing at issue rather than at acceptance matters: a pending invitation
    in somebody's inbox is a claim about who NativeForge thinks may speak for
    a Tribe, and it should not be possible to create one without the standing
    to do so.
    """
    decision = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=invited_by_role,
        actor_organization_id=invited_by_organization_id,
        target_organization_id=organization_id,
        target_role=offered_role,
    )
    if not decision["permitted"]:
        return {
            "accepted": False,
            "why": decision["why"],
            "invitation": None,
            "decision": decision,
        }
    if not invited_subject_ref:
        return {
            "accepted": False,
            "why": "an invitation needs somebody to invite",
            "invitation": None,
            "decision": decision,
        }

    when = issued_at or _now()
    invitation = {
        "schema_version": SCHEMA_VERSION,
        "invitation_id": build_invitation_id(
            organization_id=organization_id,
            invited_subject_ref=invited_subject_ref,
            offered_role=offered_role,
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "invited_by": str(invited_by) if invited_by else None,
        "invited_by_role": str(invited_by_role),
        "invited_subject_ref": str(invited_subject_ref),
        "offered_role": str(offered_role),
        "invite_state": INVITE_PENDING,
        "issued_at": when,
        "expires_at": expires_at,
        "answered_at": None,
        "revoked_by": None,
        "revoked_reason": None,
        "is_demo": bool(is_demo),
        "model_version": ADMINISTRATION_MODEL_VERSION,
    }
    return {
        "accepted": True,
        "invitation": invitation,
        "decision": decision,
        "audit_event": {
            "action": "organization.invitation_issued",
            "organization_id": str(organization_id) if organization_id else None,
            "actor_id": str(invited_by) if invited_by else None,
            "actor_role": str(invited_by_role),
            "offered_role": str(offered_role),
            "occurred_at": when,
        },
        "why": f"{invited_by_role} invited a {offered_role}",
    }


def revoke_invitation(
    *,
    invitation: dict[str, Any],
    revoked_by: Any,
    revoked_by_role: str,
    revoked_by_organization_id: Any,
    reason: Any,
    revoked_at: Any = None,
) -> dict[str, Any]:
    decision = authorize_admin_action(
        action=ACTION_REVOKE_INVITATION,
        actor_role=revoked_by_role,
        actor_organization_id=revoked_by_organization_id,
        target_organization_id=invitation.get("organization_id"),
    )
    if not decision["permitted"]:
        return {"accepted": False, "why": decision["why"], "invitation": invitation}
    if not reason:
        return {
            "accepted": False,
            "why": "revoking an invitation requires a stated reason",
            "invitation": invitation,
        }
    if str(invitation.get("invite_state")) != INVITE_PENDING:
        return {
            "accepted": False,
            "why": f"only a {INVITE_PENDING} invitation can be revoked",
            "invitation": invitation,
        }

    when = revoked_at or _now()
    revoked = dict(invitation)
    revoked["invite_state"] = INVITE_REVOKED
    revoked["revoked_by"] = str(revoked_by) if revoked_by else None
    revoked["revoked_reason"] = str(reason)
    revoked["answered_at"] = when
    return {
        "accepted": True,
        "invitation": revoked,
        "audit_event": {
            "action": "organization.invitation_revoked",
            "organization_id": invitation.get("organization_id"),
            "actor_id": str(revoked_by) if revoked_by else None,
            "reason": str(reason),
            "occurred_at": when,
        },
        "why": str(reason),
    }


def effective_invite_state(invitation: dict[str, Any], *, now: Any = None) -> str:
    """Expiry at read time, as everywhere else in this gate."""
    stored = str(invitation.get("invite_state") or INVITE_PENDING)
    if stored != INVITE_PENDING:
        return stored
    expires = invitation.get("expires_at")
    if not expires:
        return stored
    try:
        end = dt.date.fromisoformat(str(expires)[:10])
    except ValueError:
        return stored
    today = (
        dt.date.fromisoformat(str(now)[:10]) if now else dt.datetime.now(dt.UTC).date()
    )
    return INVITE_EXPIRED if today > end else stored


def invitation_invariant_failures(invitation: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    for field in INVITE_FIELDS:
        if field not in invitation:
            failures.append(f"invitation_missing_field:{field}")

    state = str(invitation.get("invite_state") or "")
    if state not in INVITE_STATES:
        failures.append(f"invite_state_outside_the_vocabulary:{state or 'missing'}")

    offered = str(invitation.get("offered_role") or "")
    inviter = str(invitation.get("invited_by_role") or "")
    if offered not in ROLES:
        failures.append(f"offered_role_outside_the_vocabulary:{offered or 'missing'}")
    if inviter not in ROLES:
        failures.append(f"inviter_role_outside_the_vocabulary:{inviter or 'missing'}")

    if not invitation.get("organization_id"):
        failures.append("invitation_names_no_organization")
    if not invitation.get("invited_subject_ref"):
        failures.append("invitation_names_nobody")

    # The escalation refusal, restated on the row.
    if offered in ROLES and inviter in ROLES:
        if inviter not in ASSIGNABLE_BY[offered]:
            failures.append(f"invitation_offers_{offered}_from_{inviter}")
    if offered in CONTROLLING_COMPANY_ROLES and inviter in CUSTOMER_ROLES:
        failures.append("customer_role_invited_somebody_as_controlling_company")

    if state == INVITE_REVOKED:
        if not invitation.get("revoked_by"):
            failures.append("revoked_invitation_names_no_actor")
        if not invitation.get("revoked_reason"):
            failures.append("revoked_invitation_states_no_reason")

    return sorted(set(failures))


def describe_administration_model() -> dict[str, Any]:
    customer_can_confer_controlling = any(
        role in CUSTOMER_ROLES for role in ASSIGNABLE_BY[CONTROLLING_COMPANY_ADMIN]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": ADMINISTRATION_MODEL_VERSION,
        "roles": list(ROLES),
        "customer_roles": sorted(CUSTOMER_ROLES),
        "controlling_company_roles": sorted(CONTROLLING_COMPANY_ROLES),
        "actions": list(ACTIONS),
        "controlling_company_only_actions": sorted(CONTROLLING_COMPANY_ONLY),
        "invite_states": list(INVITE_STATES),
        "every_role_has_a_meaning": set(ROLE_MEANINGS) == set(ROLES),
        "every_action_names_its_roles": set(PERMITTED_BY) == set(ACTIONS),
        "every_role_names_who_may_confer_it": set(ASSIGNABLE_BY) == set(ROLES),
        "every_invite_state_has_a_meaning": set(INVITE_MEANINGS) == set(INVITE_STATES),
        # The boundary, checked rather than asserted.
        "customer_admin_cannot_become_controlling_company": (
            not customer_can_confer_controlling
        ),
        "customer_and_controlling_roles_are_disjoint": not (
            CUSTOMER_ROLES & CONTROLLING_COMPANY_ROLES
        ),
        "manual_verification_is_controlling_company_only": (
            ACTION_VERIFY_AUTHORITY_MANUALLY in CONTROLLING_COMPANY_ONLY
        ),
        "organization_creation_is_controlling_company_only": (
            ACTION_CREATE_ORGANIZATION in CONTROLLING_COMPANY_ONLY
        ),
        "tenancy_is_checked_before_privilege": True,
        "unauthorized_invitations_are_refused_at_issue": True,
    }
