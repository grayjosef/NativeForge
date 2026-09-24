"""178C/D/G/H: what a customer may do right now, and why.

`derive_entitlement` is the one function that answers "can this organisation
use the product today". It is deterministic, it takes the clock as an
argument, and it returns the three underlying states alongside the answer so
that nothing downstream has to re-derive them - and so that a refusal can be
explained to the customer in the same words the ledger uses.

## The extension rule, which is the whole gate in one sentence

A temporary extension changes BENEFIT ACCESS and nothing else.

It does not move the paid-through date. It does not reduce the delinquency
count. It does not pause the three-year expiry clock. It does not make an
invoice less owed. An organisation on day 400 of delinquency with a 30-day
extension is on day 400 of delinquency, has full benefits, and is still 695
days from losing its licence.

Getting this wrong in the generous direction is worse than getting it wrong
in the harsh direction, because it is invisible: a vendor who quietly forgives
debt by granting extensions discovers it at the end of the year, and the
customer discovers it when somebody finally reconciles and sends them a bill
they were never told was accruing.

So `derive_entitlement` computes maintenance and licence state from the
LEDGER, then applies the extension only to the benefit answer, and returns
`billing_truth_unchanged_by_extension` as a field somebody can assert on.

## 178H: who may do what

Customer administrators - including `ORG_SUPER_ADMIN` - cannot forgive debt,
grant an extension, alter licence truth, move a paid-through date, or
relicense themselves. That is not a UI restriction; `authorize_commercial_
action` refuses it and `COMMERCIAL_ACTIONS` names every action that exists,
so a new one cannot quietly default to permitted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

from nativeforge.services.commercial_license_model_service import (
    ALWAYS_AVAILABLE,
    BENEFIT_EXTENDED,
    BENEFIT_FROZEN,
    BENEFIT_FULL,
    BENEFIT_NONE,
    BENEFIT_WORKING,
    DELINQUENCY_DAYS_BEFORE_EXPIRATION,
    EXTENSION_DAYS,
    GRACE_PERIOD_DAYS,
    LICENSE_EXPIRED,
    LICENSE_NONE,
    LICENSE_STATES,
    LICENSED_ACTIVE,
    LICENSED_FROZEN,
    LICENSED_GRACE,
    MAINTENANCE_STATES,
    POLICY_VERSION,
    SUBSTANTIVE_WORKFLOWS,
    delinquency_days,
    derive_license_state,
    derive_maintenance_state,
)

SCHEMA_VERSION = "nf_commercial_entitlement_v1"

# ---------------------------------------------------------------------------
# 178H: the actions that exist, and who may take them.
# ---------------------------------------------------------------------------

ACTION_GRANT_EXTENSION = "GRANT_BENEFIT_EXTENSION"
ACTION_REVOKE_EXTENSION = "REVOKE_BENEFIT_EXTENSION"
ACTION_FORGIVE_DEBT = "FORGIVE_MAINTENANCE_DEBT"
ACTION_SET_PAID_THROUGH = "SET_MAINTENANCE_PAID_THROUGH"
ACTION_RECORD_LICENSE_PURCHASE = "RECORD_LICENSE_PURCHASE"
ACTION_RELICENSE = "RELICENSE_ORGANIZATION"
ACTION_CORRECT_LEDGER = "CORRECT_ENTITLEMENT_LEDGER"
ACTION_VIEW_ENTITLEMENT = "VIEW_ENTITLEMENT"

COMMERCIAL_ACTIONS: tuple[str, ...] = (
    ACTION_GRANT_EXTENSION,
    ACTION_REVOKE_EXTENSION,
    ACTION_FORGIVE_DEBT,
    ACTION_SET_PAID_THROUGH,
    ACTION_RECORD_LICENSE_PURCHASE,
    ACTION_RELICENSE,
    ACTION_CORRECT_LEDGER,
    ACTION_VIEW_ENTITLEMENT,
)

CONTROLLING_COMPANY_ADMIN = "CONTROLLING_COMPANY_ADMIN"

#: Everything except viewing is controlling-company only. Listed positively
#: rather than as "not the customer roles", so adding an action without
#: deciding who may take it fails rather than defaulting open.
ACTION_PERMITTED_BY: dict[str, frozenset[str]] = {
    ACTION_GRANT_EXTENSION: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_REVOKE_EXTENSION: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_FORGIVE_DEBT: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_SET_PAID_THROUGH: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_RECORD_LICENSE_PURCHASE: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_RELICENSE: frozenset({CONTROLLING_COMPANY_ADMIN}),
    ACTION_CORRECT_LEDGER: frozenset({CONTROLLING_COMPANY_ADMIN}),
    # A customer may always SEE their own standing, in every state.
    ACTION_VIEW_ENTITLEMENT: frozenset(
        {
            CONTROLLING_COMPANY_ADMIN,
            "ORG_SUPER_ADMIN",
            "ORG_ADMIN",
            "ORG_REVIEWER",
            "ORG_MEMBER",
        }
    ),
}

#: Derived, so it cannot drift from the table above.
CONTROLLING_COMPANY_ONLY: frozenset[str] = frozenset(
    action
    for action, roles in ACTION_PERMITTED_BY.items()
    if roles == frozenset({CONTROLLING_COMPANY_ADMIN})
)

EXTENSION_FIELDS: tuple[str, ...] = (
    "extension_id",
    "organization_id",
    "granted_by",
    "granted_by_role",
    "granted_at",
    "duration_days",
    "expires_at",
    "reason",
    "underlying_license_state",
    "underlying_maintenance_state",
    "underlying_delinquency_days",
    "revoked_at",
    "revoked_by",
    "is_demo",
    "policy_version",
)


def _as_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def authorize_commercial_action(*, action: str, actor_role: str) -> dict[str, Any]:
    """178H. May this role take this commercial action?"""
    act = str(action)
    role = str(actor_role)
    if act not in COMMERCIAL_ACTIONS:
        return {
            "permitted": False,
            "why": f"{act} is not a commercial action",
            "action": act,
        }
    permitted = role in ACTION_PERMITTED_BY[act]
    return {
        "permitted": permitted,
        "action": act,
        "actor_role": role,
        "controlling_company_only": act in CONTROLLING_COMPANY_ONLY,
        "why": (f"{role} may {act}" if permitted else f"{role} may not {act}"),
    }


def build_extension_id(
    *, organization_id: Any, granted_at: Any, duration_days: Any
) -> str:
    parts = [str(organization_id or ""), str(granted_at or ""), str(duration_days)]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def grant_benefit_extension(
    *,
    organization_id: Any,
    duration_days: int,
    granted_by: Any,
    granted_by_role: str,
    reason: Any,
    ledger: dict[str, Any],
    as_of: Any,
    is_demo: bool = False,
) -> dict[str, Any]:
    """178G. Grant benefits for 7, 14 or 30 days. Change nothing else.

    The underlying licence and maintenance states are computed from the
    LEDGER and recorded ON the extension, so the extension itself carries the
    evidence of what was true when it was granted. An extension that claimed
    the customer was current would be a lie with a timestamp.
    """
    decision = authorize_commercial_action(
        action=ACTION_GRANT_EXTENSION, actor_role=granted_by_role
    )
    if not decision["permitted"]:
        return {"accepted": False, "why": decision["why"], "extension": None}
    if int(duration_days) not in EXTENSION_DAYS:
        return {
            "accepted": False,
            "why": f"{duration_days} is not one of {list(EXTENSION_DAYS)} days",
            "extension": None,
        }
    if not granted_by:
        return {
            "accepted": False,
            "why": "an extension requires a named grantor",
            "extension": None,
        }
    if not reason:
        return {
            "accepted": False,
            "why": "an extension requires a stated reason",
            "extension": None,
        }

    today = _as_date(as_of)
    if today is None:
        return {
            "accepted": False,
            "why": "an extension requires the date it was granted",
            "extension": None,
        }

    # What is TRUE right now, recorded on the extension so the grant cannot
    # later be mistaken for a statement that the customer was current.
    maintenance = derive_maintenance_state(
        paid_through=ledger.get("paid_through"),
        as_of=today,
        forgiven=bool(ledger.get("maintenance_forgiven")),
    )
    license_state = derive_license_state(
        license_purchased_at=ledger.get("license_purchased_at"),
        paid_through=ledger.get("paid_through"),
        as_of=today,
        relicensed_at=ledger.get("relicensed_at"),
    )
    days = delinquency_days(paid_through=ledger.get("paid_through"), as_of=today)

    extension = {
        "schema_version": SCHEMA_VERSION,
        "extension_id": build_extension_id(
            organization_id=organization_id,
            granted_at=today.isoformat(),
            duration_days=int(duration_days),
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "granted_by": str(granted_by),
        "granted_by_role": str(granted_by_role),
        "granted_at": today.isoformat(),
        "duration_days": int(duration_days),
        "expires_at": (today + dt.timedelta(days=int(duration_days))).isoformat(),
        "reason": str(reason),
        # The truth at grant time. Not changed by this grant.
        "underlying_license_state": license_state,
        "underlying_maintenance_state": maintenance,
        "underlying_delinquency_days": days,
        "revoked_at": None,
        "revoked_by": None,
        "is_demo": bool(is_demo),
        "policy_version": POLICY_VERSION,
    }
    return {
        "accepted": True,
        "extension": extension,
        "audit_event": {
            "action": "commercial.extension_granted",
            "organization_id": extension["organization_id"],
            "actor_id": str(granted_by),
            "duration_days": int(duration_days),
            "reason": str(reason),
            "underlying_maintenance_state": maintenance,
            "occurred_at": today.isoformat(),
        },
        # The claim this gate is built on, stated where it can be asserted.
        "billing_truth_unchanged": True,
        "paid_through_unchanged": ledger.get("paid_through"),
        "delinquency_days_unchanged": days,
        "why": str(reason),
    }


def active_extension(
    *, extensions: list[dict[str, Any]], as_of: Any
) -> dict[str, Any] | None:
    """The extension in force today, if any. Expiry applied at read time."""
    today = _as_date(as_of)
    if today is None:
        return None
    live = [
        row
        for row in extensions
        if not row.get("revoked_at")
        and (_as_date(row.get("granted_at")) or today) <= today
        and (_as_date(row.get("expires_at")) or today) > today
    ]
    if not live:
        return None
    # The one that runs longest, so overlapping grants behave the way the
    # person granting the second one expected.
    return max(live, key=lambda row: str(row.get("expires_at") or ""))


def derive_entitlement(
    *,
    organization_id: Any,
    ledger: dict[str, Any],
    extensions: list[dict[str, Any]] | None = None,
    as_of: Any,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    """178C. The one answer, with the three states it was derived from.

    Deterministic: the same ledger and the same `as_of` always produce the
    same result. Nothing here reads a clock, a feature flag, or a UI setting.
    """
    today = _as_date(as_of)
    if today is None:
        raise ValueError("as_of is required; entitlement never reads the clock")

    forgiven = bool(ledger.get("maintenance_forgiven"))
    maintenance_state = derive_maintenance_state(
        paid_through=ledger.get("paid_through"), as_of=today, forgiven=forgiven
    )
    license_state = derive_license_state(
        license_purchased_at=ledger.get("license_purchased_at"),
        paid_through=ledger.get("paid_through"),
        as_of=today,
        relicensed_at=ledger.get("relicensed_at"),
    )
    days = delinquency_days(paid_through=ledger.get("paid_through"), as_of=today)
    extension = active_extension(extensions=extensions or [], as_of=today)

    # ---- benefit access, and ONLY benefit access -------------------
    if license_state == LICENSE_NONE:
        benefit = BENEFIT_NONE
        why = "no persistent licence has been held"
    elif license_state in {LICENSED_ACTIVE, LICENSED_GRACE}:
        benefit = BENEFIT_FULL
        why = (
            "maintenance is current"
            if license_state == LICENSED_ACTIVE
            else f"within the {GRACE_PERIOD_DAYS}-day grace window"
        )
    elif extension is not None:
        # The only place an extension is consulted. Note what is NOT
        # recomputed here: maintenance_state, license_state and days are
        # already fixed above, from the ledger.
        benefit = BENEFIT_EXTENDED
        why = (
            f"a {extension['duration_days']}-day extension granted by "
            f"{extension['granted_by']} runs to {extension['expires_at']}"
        )
    elif license_state == LICENSED_FROZEN:
        benefit = BENEFIT_FROZEN
        why = f"maintenance delinquent for {days} days, past grace"
    else:
        benefit = BENEFIT_FROZEN
        why = (
            f"the persistent licence expired after {days} days of continuous "
            "delinquency; the account and its data remain"
        )

    working = benefit in BENEFIT_WORKING
    days_until_expiration = max(0, DELINQUENCY_DAYS_BEFORE_EXPIRATION - days)

    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": str(policy_version),
        "organization_id": str(organization_id) if organization_id else None,
        "as_of": today.isoformat(),
        # THREE states, reported separately. Never one flag.
        "license_state": license_state,
        "maintenance_state": maintenance_state,
        "benefit_access": benefit,
        "why": why,
        # The derivation inputs, echoed so a decision can be re-checked
        # without re-reading the ledger.
        "paid_through": ledger.get("paid_through"),
        "delinquency_days": days,
        "days_until_license_expiration": (
            days_until_expiration if license_state != LICENSE_EXPIRED else 0
        ),
        "license_held": license_state != LICENSE_EXPIRED
        and license_state != LICENSE_NONE,
        "maintenance_forgiven": forgiven,
        "active_extension_id": extension["extension_id"] if extension else None,
        "extension_expires_at": extension["expires_at"] if extension else None,
        # 178D: what they can do, either way.
        "available_actions": list(ALWAYS_AVAILABLE)
        + (list(SUBSTANTIVE_WORKFLOWS) if working else []),
        "locked_actions": [] if working else list(SUBSTANTIVE_WORKFLOWS),
        "substantive_workflows_available": working,
        # The refusals, stated on every answer.
        "data_deleted": False,
        "organization_deleted": False,
        "history_deleted": False,
        "billing_truth_unchanged_by_extension": True,
        "derived_deterministically": True,
    }


def entitlement_invariant_failures(entitlement: dict[str, Any]) -> list[str]:
    """Refuse an entitlement that cannot be justified by its own states."""
    failures: list[str] = []

    license_state = str(entitlement.get("license_state") or "")
    maintenance = str(entitlement.get("maintenance_state") or "")
    benefit = str(entitlement.get("benefit_access") or "")
    days = int(entitlement.get("delinquency_days") or 0)

    if license_state not in LICENSE_STATES:
        failures.append(f"license_state_outside_the_vocabulary:{license_state}")
    if maintenance not in MAINTENANCE_STATES:
        failures.append(f"maintenance_state_outside_the_vocabulary:{maintenance}")
    if benefit not in {BENEFIT_FULL, BENEFIT_EXTENDED, BENEFIT_FROZEN, BENEFIT_NONE}:
        failures.append(f"benefit_state_outside_the_vocabulary:{benefit}")

    if days < 0:
        failures.append(f"negative_delinquency_duration:{days}")

    # Working benefits must have a REASON: current maintenance, grace, or a
    # named extension. "Active for no reason" is the detector 178L wants.
    if benefit == BENEFIT_FULL and license_state not in {
        LICENSED_ACTIVE,
        LICENSED_GRACE,
    }:
        failures.append(f"full_benefits_while_license_is_{license_state}")
    if benefit == BENEFIT_EXTENDED and not entitlement.get("active_extension_id"):
        failures.append("extended_benefits_name_no_extension")

    # Expiry may not happen early.
    if license_state == LICENSE_EXPIRED and days <= DELINQUENCY_DAYS_BEFORE_EXPIRATION:
        failures.append(f"license_expired_after_only_{days}_days")

    # Nothing is ever deleted.
    for flag in ("data_deleted", "organization_deleted", "history_deleted"):
        if entitlement.get(flag):
            failures.append(f"entitlement_claims_{flag}")

    if not entitlement.get("available_actions"):
        failures.append("entitlement_offers_no_actions_at_all")
    missing = set(ALWAYS_AVAILABLE) - set(entitlement.get("available_actions") or [])
    if missing:
        failures.append(f"always_available_action_was_locked:{sorted(missing)}")

    if not entitlement.get("policy_version"):
        failures.append("entitlement_names_no_policy_version")

    return sorted(set(failures))


def extension_invariant_failures(extension: dict[str, Any]) -> list[str]:
    """Refuse an extension that rewrote something it may not touch."""
    failures: list[str] = []

    for field in EXTENSION_FIELDS:
        if field not in extension:
            failures.append(f"extension_missing_field:{field}")

    if int(extension.get("duration_days") or 0) not in EXTENSION_DAYS:
        failures.append(
            f"extension_duration_not_allowed:{extension.get('duration_days')}"
        )
    if str(extension.get("granted_by_role") or "") != CONTROLLING_COMPANY_ADMIN:
        failures.append(f"extension_granted_by_{extension.get('granted_by_role')}")
    if not extension.get("granted_by"):
        failures.append("extension_names_no_grantor")
    if not extension.get("reason"):
        failures.append("extension_states_no_reason")

    # The load-bearing one: an extension must RECORD the delinquency it did
    # not cure. An extension claiming the customer was current is a lie.
    if extension.get("underlying_maintenance_state") in {None, ""}:
        failures.append("extension_does_not_record_the_underlying_maintenance_state")
    if int(extension.get("underlying_delinquency_days") or 0) < 0:
        failures.append("extension_records_negative_delinquency")

    granted = _as_date(extension.get("granted_at"))
    expires = _as_date(extension.get("expires_at"))
    if granted and expires:
        actual = (expires - granted).days
        if actual != int(extension.get("duration_days") or 0):
            failures.append(
                f"extension_window_is_{actual}_days_not_{extension.get('duration_days')}"
            )
        if expires <= granted:
            failures.append("extension_expires_before_it_begins")

    return sorted(set(failures))


def describe_entitlement_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "commercial_actions": list(COMMERCIAL_ACTIONS),
        "controlling_company_only_actions": sorted(CONTROLLING_COMPANY_ONLY),
        "extension_days": list(EXTENSION_DAYS),
        "every_action_names_its_roles": set(ACTION_PERMITTED_BY)
        == set(COMMERCIAL_ACTIONS),
        # 178H, checked rather than claimed.
        "customer_admin_cannot_grant_extension": "ORG_SUPER_ADMIN"
        not in ACTION_PERMITTED_BY[ACTION_GRANT_EXTENSION],
        "customer_admin_cannot_forgive_debt": "ORG_SUPER_ADMIN"
        not in ACTION_PERMITTED_BY[ACTION_FORGIVE_DEBT],
        "customer_admin_cannot_set_paid_through": "ORG_SUPER_ADMIN"
        not in ACTION_PERMITTED_BY[ACTION_SET_PAID_THROUGH],
        "customer_admin_cannot_relicense": "ORG_SUPER_ADMIN"
        not in ACTION_PERMITTED_BY[ACTION_RELICENSE],
        "customer_may_always_view_their_own_entitlement": "ORG_MEMBER"
        in ACTION_PERMITTED_BY[ACTION_VIEW_ENTITLEMENT],
        # The rule the gate turns on.
        "extension_changes_benefit_access_only": True,
        "extension_does_not_move_paid_through": True,
        "extension_does_not_reduce_delinquency": True,
        "extension_does_not_pause_expiration": True,
        "extension_records_the_delinquency_it_did_not_cure": True,
        "entitlement_is_deterministic": True,
        "no_magic_ui_only_gating": True,
        "frozen_preserves_every_always_available_action": True,
    }
