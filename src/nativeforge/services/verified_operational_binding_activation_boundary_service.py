"""Gate 137C: who may activate a verified operational binding, and where.

Gate 137A measured the state this closes. With a fully-qualified verifier
principal and `customer_auth_live` true, a **real-organization production
verified binding** was fully writable:

```text
authorization_allowed         True
repository_write_performed    True
verified_operational_binding  TRUE
blocked_reasons               []
stored: organization_id=aaaaaaaa-…, verified_binding, is_demo=0
```

Nothing in the chain checked which organization it was.
`verified_binder_authorization_service` decides by **role** -
`{platform_admin, tenant_admin}` plus an authenticated verified-org status - and
a role is not an authorization to bind a particular Tribe's organization.

The only thing holding it shut was
`production_verified_binding_requires_live_customer_auth`, and Gate 136 made
`customer_auth_live` reachable in minutes. This module is what stands behind
that guard when it opens.

## The shape, copied from Gate 133D/135D

`customer_auth_owner_activation_decision_service` already established it: a
recorded decision, checked per call against subject and environment, refusing
the real organization by name, with one environment variable that can only
revoke and none that can grant. This is the same shape for a different subject.

## Why the authorized list is empty

Mayhem's standing authorization, verbatim from Gate 135, enumerates what it does
*not* cover:

```text
This does not authorize:
  production rollout
  controlled customer pilot
  real org activation
  live customer data
  binding to aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
```

`real org activation` and the binding to that id are refused explicitly. So
`AUTHORIZED_REAL_ORGANIZATION_IDS` is empty, deliberately, and the constant
carries the reason. Authorizing one is a code change somebody reads, plus an
approval object naming it - not an environment variable somebody exports.

## Three refusals that are not about approval at all

```text
a demo organization                 never a verified operational binding,
                                    derived from organizations.org_type
tenant_id / customer_org_id /
  organization_profile_id           refused as authority, by name
production environment              needs its own approval scope; the
                                    real-org scope does not reach it
```

The second is Gates 110-113's subject and is restated here because this is a
new entry point: a caller offering a label as authority learns it was refused
rather than silently dropped.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

SCHEMA_VERSION = "nf_verified_operational_binding_activation_boundary_v1"

#: The demo organization. Never a verified operational binding, in any
#: environment, with any approval. Gate 113's contract, enforced here against
#: the organization rather than against a label a caller supplied.
DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: The real organization, refused by name so nobody has to recognise a uuid.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Empty, and empty is the decision.
#:
#: Mayhem's standing authorization refuses `real org activation` and refuses
#: binding to `aaaaaaaa-…` by name. Adding an id here is a reviewed code change,
#: and it is still not sufficient on its own - an approval object naming the
#: same organization is required alongside it.
AUTHORIZED_REAL_ORGANIZATION_IDS: frozenset[str] = frozenset()

#: What an approval must say. A dict missing any of these is not an approval,
#: it is a dict.
APPROVAL_FIELDS: tuple[str, ...] = (
    "organization_id",
    "authorized_by",
    "authorization_scope",
    "environment",
    "recorded_at",
)

#: Two scopes, and the narrow one does not reach the broad one. Binding a real
#: organization in dev is a different decision from binding one in production,
#: which is the distinction Gate 133D had to introduce for logins after one
#: variable had been gating both.
REAL_ORG_SCOPE = "real_org_binding_activation"
PRODUCTION_SCOPE = "production_binding_activation"
APPROVAL_SCOPES: frozenset[str] = frozenset({REAL_ORG_SCOPE, PRODUCTION_SCOPE})

#: Environments in which a real-org binding may be activated with the narrow
#: scope. `production` needs `PRODUCTION_SCOPE` and is not in this set.
NON_PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"local", "dev", "test"})
PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})

#: Reads one variable, and it can only turn an activation off.
REVOCATION_ENV = "NF_REAL_ORG_BINDING_ACTIVATION_REVOKED"

#: Values that are never authority for a binding, however a caller labels them.
#: Refused by name rather than ignored.
FORBIDDEN_AUTHORITY_KEYS: tuple[str, ...] = (
    "tenant_id",
    "customer_org_id",
    "organization_profile_id",
    "profile_id",
    "subject",
    "email",
)

#: Claims this module never makes, in any branch.
NOT_APPROVED: tuple[str, ...] = (
    "production_rollout",
    "controlled_customer_pilot",
    "live_customer_data",
    "real_customer_persistence",
    "email_delivery",
    "object_store_activation",
    "live_grant_source_monitoring",
)

DEMO_REFUSED = "demo_organization_is_never_a_verified_operational_binding"
NOT_AUTHORIZED = "organization_is_not_in_the_authorized_real_org_list"
REAL_ORG_REFUSED = "organization_is_the_explicitly_refused_real_org"
NO_APPROVAL = "no_approval_object_supplied"
SCOPE_TOO_NARROW = "approval_scope_does_not_cover_production"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _environment(app_env: str | None = None) -> str:
    if app_env is not None:
        return str(app_env).strip().lower()
    from nativeforge.lib.settings import get_settings

    return str(get_settings().app_env or "").strip().lower()


def _revoked() -> bool:
    return str(os.environ.get(REVOCATION_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def approval_shape_failures(approval: Any) -> list[str]:
    """Is this an approval, or a dict somebody hoped would pass for one?

    Checked before anything is compared, because an approval missing its
    ``authorized_by`` is an approval nobody gave, and comparing its
    organization id first would make the missing field look incidental.
    """
    fails: list[str] = []
    if not isinstance(approval, dict) or not approval:
        return [NO_APPROVAL]

    for field in APPROVAL_FIELDS:
        if not str(approval.get(field) or "").strip():
            fails.append(f"approval_missing_field:{field}")

    scope = str(approval.get("authorization_scope") or "").strip().lower()
    if scope and scope not in APPROVAL_SCOPES:
        fails.append(f"approval_scope_not_recognised:{scope}")

    if not _uuid_shaped(approval.get("organization_id")):
        fails.append("approval_organization_id_is_not_uuid_shaped")

    # An approval that carries a label as its subject is an approval for
    # something this module cannot check.
    for key in FORBIDDEN_AUTHORITY_KEYS:
        if str(approval.get(key) or "").strip():
            fails.append(f"approval_carries_a_non_authority_subject:{key}")

    return sorted(set(fails))


def build_real_org_binding_activation_decision(
    *,
    organization_id: Any = None,
    approval: Any = None,
    app_env: str | None = None,
    connection: Any = None,
    org_type_in_database: str | None = None,
    authorized_organization_ids: frozenset[str] | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """May a verified operational binding be activated for this organization?

    Deny by default, and every branch grants rather than subtracts.

    ``authorized_organization_ids`` is injectable so the approved branch is
    reachable in a hermetic test against a fixture organization that is neither
    the demo org nor the real one.

    It cannot authorize either of those two, whatever it contains. Found by
    Gate 137G's own test: the injectable set was consulted for every id, so
    listing ``aaaaaaaa-…`` in it approved a real-org binding and wrote the row.
    An escape hatch that reaches the one organization the whole module exists
    to refuse is not an escape hatch, it is the hole. So both ids are stripped
    from it, and reaching them needs the module constant instead - a reviewed
    code change, not a keyword argument.
    """
    requested = str(organization_id or "").strip().lower()
    environment = _environment(app_env)
    if authorized_organization_ids is None:
        authorized = AUTHORIZED_REAL_ORGANIZATION_IDS
        injected_ids_ignored: list[str] = []
    else:
        offered_ids = frozenset(
            str(x).strip().lower() for x in authorized_organization_ids
        )
        protected = {DEMO_ORGANIZATION_ID, REAL_ORGANIZATION_ID}
        authorized = offered_ids - protected
        injected_ids_ignored = sorted(offered_ids & protected)

    blocked_reasons: list[str] = []

    # -- 1. a label is never authority --------------------------------------
    for key in FORBIDDEN_AUTHORITY_KEYS:
        if str(offered.get(key) or "").strip():
            blocked_reasons.append(f"not_an_authority_for_a_binding:{key}")

    # -- 2. the anchor -------------------------------------------------------
    if not requested:
        blocked_reasons.append("no_organization_id_supplied")
    elif not _uuid_shaped(requested):
        blocked_reasons.append("organization_id_is_not_uuid_shaped")

    # -- 3. demo, derived from the row --------------------------------------
    #
    # Not from a parameter, and not from the principal. Gate 137A found a
    # verified binding written onto the demo organization with `is_demo=False`
    # because both of those were the caller's word for it.
    from nativeforge.services.demo_org_classification_service import (
        classify_organization,
    )

    classification = classify_organization(
        requested or None,
        connection=connection,
        org_type_in_database=org_type_in_database,
    )
    classified = bool(classification.get("classification_available"))
    is_demo = bool(classification.get("is_demo"))

    if not classified:
        blocked_reasons.append("organization_could_not_be_classified")
    if is_demo or requested == DEMO_ORGANIZATION_ID:
        # Both, because the id is refused even where no row can be read: an
        # unclassifiable demo organization is still the demo organization.
        blocked_reasons.append(DEMO_REFUSED)

    # -- 4. the authorized list, which is empty ------------------------------
    if injected_ids_ignored:
        # Named rather than silently dropped: a caller that offered one should
        # learn it was refused, which is the same rule the label refusals follow.
        blocked_reasons.extend(
            f"injected_authorization_ignored_for_a_protected_organization:{value}"
            for value in injected_ids_ignored
        )

    listed = requested in authorized
    if requested and not listed:
        # The real organization gets its own name so nobody has to recognise a
        # uuid to understand the refusal. Any other unlisted organization gets
        # the general one. Written as three branches first, two of which were
        # the same branch with a guard that changed nothing.
        blocked_reasons.append(
            REAL_ORG_REFUSED if requested == REAL_ORGANIZATION_ID else NOT_AUTHORIZED
        )

    # -- 5. the approval object ---------------------------------------------
    approval_failures = approval_shape_failures(approval)
    blocked_reasons.extend(approval_failures)

    approval_dict = approval if isinstance(approval, dict) else {}
    approval_scope = str(approval_dict.get("authorization_scope") or "").strip().lower()
    approval_org = str(approval_dict.get("organization_id") or "").strip().lower()

    if approval_dict and approval_org and approval_org != requested:
        # An approval for a different organization is not an approval for this
        # one, and this is the substitution that would matter most.
        blocked_reasons.append("approval_names_a_different_organization")

    approval_env = str(approval_dict.get("environment") or "").strip().lower()
    if approval_dict and approval_env and approval_env != environment:
        blocked_reasons.append(
            f"approval_recorded_for_a_different_environment:{approval_env}"
        )

    # -- 6. production is its own decision ----------------------------------
    is_production = environment in PRODUCTION_ENVIRONMENTS
    if is_production and approval_scope != PRODUCTION_SCOPE:
        blocked_reasons.append(SCOPE_TOO_NARROW)
    if not is_production and environment not in NON_PRODUCTION_ENVIRONMENTS:
        blocked_reasons.append(f"environment_not_recognised:{environment or 'unset'}")

    # -- 7. revocation, the only thing an env var can do --------------------
    revoked = _revoked()
    if revoked:
        blocked_reasons.append("activation_revoked_by_environment")

    approves = bool(
        requested
        and listed
        and classified
        and not is_demo
        and not approval_failures
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "decision_recorded": True,
            "approves_real_org_binding_activation": approves,
            "approves_production_binding_activation": bool(
                approves and approval_scope == PRODUCTION_SCOPE and is_production
            ),
            # No parameter reaches these. They are the shape of the decision.
            "approves_production_rollout": False,
            "approves_controlled_customer_pilot": False,
            "organization_id": requested or None,
            "organization_classified": classified,
            "organization_is_demo": is_demo,
            "organization_in_authorized_list": listed,
            "authorized_list_size": len(authorized),
            "injected_authorization_ignored_for": injected_ids_ignored,
            "approval_supplied": bool(approval_dict),
            "approval_scope": approval_scope or None,
            "approval_authorized_by": (
                str(approval_dict.get("authorized_by") or "").strip() or None
            ),
            "environment": environment or None,
            "environment_is_production": is_production,
            "revoked": revoked,
            "revocation_environment_variable": REVOCATION_ENV,
            "grant_environment_variable": None,
            "not_approved": list(NOT_APPROVED),
            "forbidden_authority_keys": list(FORBIDDEN_AUTHORITY_KEYS),
            "real_organization_id_refused_by_name": REAL_ORGANIZATION_ID,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def activation_boundary_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """What must never be true of an activation decision."""
    fails: list[str] = []

    if decision.get("approves_production_rollout"):
        fails.append("decision_approved_production_rollout")
    if decision.get("approves_controlled_customer_pilot"):
        fails.append("decision_approved_a_controlled_customer_pilot")

    if decision.get("approves_real_org_binding_activation"):
        if decision.get("organization_is_demo"):
            fails.append("activation_approved_for_a_demo_organization")
        if decision.get("organization_id") == DEMO_ORGANIZATION_ID:
            fails.append("activation_approved_for_the_demo_organization_id")
        if not decision.get("organization_classified"):
            fails.append("activation_approved_without_classifying_the_organization")
        if not decision.get("organization_in_authorized_list"):
            fails.append("activation_approved_for_an_unauthorized_organization")
        if decision.get("organization_id") == REAL_ORGANIZATION_ID:
            fails.append("activation_approved_for_the_refused_real_org")
        if not decision.get("approval_supplied"):
            fails.append("activation_approved_without_an_approval_object")
        if decision.get("revoked"):
            fails.append("activation_approved_while_revoked")
        if decision.get("blocked_reasons"):
            fails.append("activation_approved_alongside_blockers")

    if decision.get("approves_production_binding_activation"):
        if not decision.get("approves_real_org_binding_activation"):
            fails.append("production_activation_without_real_org_activation")
        if decision.get("approval_scope") != PRODUCTION_SCOPE:
            fails.append("production_activation_without_the_production_scope")
        if not decision.get("environment_is_production"):
            fails.append("production_activation_outside_production")

    # A grant variable is the thing this module must never acquire.
    if decision.get("grant_environment_variable"):
        fails.append("an_environment_variable_can_grant_activation")

    missing = set(NOT_APPROVED) - set(decision.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    if not decision.get("approves_real_org_binding_activation") and not decision.get(
        "blocked_reasons"
    ):
        fails.append("nothing_approved_and_nothing_blocked_it")

    return fails
