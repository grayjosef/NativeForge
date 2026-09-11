"""Gate 147B: how far is `verified_operational_binding` from true, and who moves it?

## Five refusals, any one of which is sufficient

Gate 137 built the boundary and proved it refuses. What it did not have is a
single place that answers the question an operator actually asks. Five separate
things stand between today and a verified operational binding:

```text
1  AUTHORIZED_REAL_ORGANIZATION_IDS is empty, deliberately
2  no approval object exists
3  the demo organization is categorically refused
4  the real organization is refused by name
5  customer_auth_live is false
```

A checklist reporting one of them would invite somebody to clear it and expect
the lane to move. All five are reported, each with whether it is code or a
decision, and who owns it.

## Three layers, gathered so no reader has to know there are three

```text
the boundary service     the authorized list, the approval object, the demo
                         and real-org refusals, the environment scope
the workflow service     production_verified_binding_requires_live_customer_auth
the repository           duplicate and ambiguous active bindings
```

Each is correct where it lives. None of them sees the other two, so nothing
before this module could say how far the lane is from true.

## Classification comes from the database

`org_type` is read, never accepted. A caller offering `is_demo`, `org_type`,
`tenant_id`, `customer_org_id`, `organization_profile_id`, `profile_id`,
`subject` or `email` as authority is told those were refused rather than having
them silently dropped — Gates 110-113's subject, restated at a new entry point.

## It writes nothing

No binding row, no approval, no audit event. `build_approval_checklist` reads
and returns. The mutation path stays where Gate 137 put it, behind an approval
object that does not exist.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    APPROVAL_FIELDS,
    AUTHORIZED_REAL_ORGANIZATION_IDS,
    DEMO_ORGANIZATION_ID,
    FORBIDDEN_AUTHORITY_KEYS,
    NON_PRODUCTION_ENVIRONMENTS,
    NOT_AUTHORIZED,
    PRODUCTION_SCOPE,
    REAL_ORG_SCOPE,
    REAL_ORGANIZATION_ID,
    approval_shape_failures,
)

SCHEMA_VERSION = "nf_verified_binding_approval_checklist_v1"

#: Reported when the answer is not knowable from inside this repository.
UNKNOWN = "UNKNOWN"

#: Roles that may act as a verifier principal. Narrower than the inspector set.
VERIFIER_ROLES: frozenset[str] = frozenset({"platform_admin", "tenant_admin"})

#: The statuses that assert somebody verified something. A row in one of these
#: without a verifier behind it is the thing the whole boundary exists to stop.
VERIFIER_REQUIRED_STATUSES: frozenset[str] = frozenset({"verified_binding"})

#: The five refusals, in the order an operator would clear them. Each says
#: whether it is code or a decision, because "blocked" without that distinction
#: sends somebody looking for a bug that is not there.
# Reuse Gate 137's exact wording rather than a near-duplicate. The first
# version of this module coined `organization_not_in_the_authorized_real_org_list`
# beside the boundary service's `organization_is_not_in_the_authorized_real_org_list`,
# and the dry-run composite - which unions both layers' blockers - then
# reported the same refusal twice under two names. A reader counting blockers
# would have found one more problem than exists.
REFUSAL_AUTHORIZED_LIST = NOT_AUTHORIZED
REFUSAL_NO_APPROVAL = "no_approval_object_supplied"
REFUSAL_DEMO_ORG = "demo_organization_is_never_a_verified_operational_binding"
REFUSAL_REAL_ORG = "organization_is_the_explicitly_refused_real_org"
REFUSAL_AUTH_NOT_LIVE = "production_verified_binding_requires_live_customer_auth"
REFUSAL_DUPLICATE = "more_than_one_active_binding_for_this_organization"
REFUSAL_AMBIGUOUS = "active_binding_is_ambiguous"
REFUSAL_PRINCIPAL = "verifier_principal_is_not_qualified"
REFUSAL_REVOKED = "real_org_binding_activation_has_been_revoked"

#: Each refusal, what kind of thing clears it, and who owns it.
REFUSAL_OWNERS: dict[str, dict[str, str]] = {
    REFUSAL_AUTHORIZED_LIST: {
        "kind": "reviewed_code_change",
        "owner": "Mayhem",
        "clears_by": (
            "adding the organization id to AUTHORIZED_REAL_ORGANIZATION_IDS, "
            "which is a code change somebody reads - not an environment "
            "variable, and not the injectable test set, which strips both the "
            "demo and the real organization ids"
        ),
    },
    REFUSAL_NO_APPROVAL: {
        "kind": "recorded_decision",
        "owner": "Mayhem",
        "clears_by": (
            "recording an approval object with all five fields and a scope "
            "that covers the environment"
        ),
    },
    REFUSAL_DEMO_ORG: {
        "kind": "never_clears",
        "owner": "nobody",
        "clears_by": (
            "nothing. The demo organization is never a verified operational "
            "binding, in any environment, with any approval, with any "
            "principal. Derived from organizations.org_type."
        ),
    },
    REFUSAL_REAL_ORG: {
        "kind": "never_clears_without_a_reviewed_code_change",
        "owner": "Mayhem",
        "clears_by": (
            "nothing available here. The standing authorization refuses real "
            "org activation and refuses this id by name."
        ),
    },
    REFUSAL_AUTH_NOT_LIVE: {
        "kind": "an_event",
        "owner": "the second person, then the operator",
        "clears_by": (
            "the second-person invite event - see Gate 146. A verified "
            "binding asserts somebody verified something; writing one while "
            "nobody can authenticate leaves that assertion with no verifier "
            "behind it."
        ),
    },
    REFUSAL_DUPLICATE: {
        "kind": "human_resolution",
        "owner": "an operator",
        "clears_by": (
            "revoking or resolving one of the contradicting rows. Two active "
            "bindings for one organization is a conflict a person resolves."
        ),
    },
    REFUSAL_AMBIGUOUS: {
        "kind": "human_resolution",
        "owner": "an operator",
        "clears_by": "resolving the conflict so one active row remains",
    },
    REFUSAL_PRINCIPAL: {
        "kind": "authenticated_role",
        "owner": "the acting principal",
        "clears_by": (
            "acting as an authenticated platform_admin or tenant_admin with "
            "verified-org status"
        ),
    },
    REFUSAL_REVOKED: {
        "kind": "recorded_decision",
        "owner": "Mayhem",
        "clears_by": "unsetting NF_REAL_ORG_BINDING_ACTIVATION_REVOKED",
    },
}

#: Claims this module never makes, in any branch.
NOT_APPROVED: tuple[str, ...] = (
    "verified_operational_binding",
    "customer_auth_live",
    "controlled_customer_pilot",
    "production_rollout",
    "live_customer_data",
    "real_customer_persistence",
)

#: Ways somebody could try to reach a verified binding without the evidence,
#: and why each fails. Data, so a test can assert every one is still refused.
REFUSED_SHORTCUTS: tuple[dict[str, str], ...] = (
    {
        "shortcut": "pass is_demo=False for the demo organization",
        "refused_because": (
            "classification is read from organizations.org_type, never from "
            "the caller"
        ),
    },
    {
        "shortcut": "pass org_type='real' for the demo organization",
        "refused_because": "same - the label is refused, not merged",
    },
    {
        "shortcut": "offer tenant_id or customer_org_id as the authority",
        "refused_because": (
            "refused by name as authority, rather than silently dropped - "
            "Gates 110-113's subject"
        ),
    },
    {
        "shortcut": "list the real organization in the injectable authorized set",
        "refused_because": (
            "both the demo and real ids are stripped from the injectable set; "
            "Gate 137G's own test found this reaching the real org and writing "
            "the row"
        ),
    },
    {
        "shortcut": "write a binding row directly and call it verified",
        "refused_because": (
            "a verified_binding status requires a verifier identity and a "
            "verified_at, and the database CHECK constraint refuses the row"
        ),
    },
    {
        "shortcut": "treat the demo fixture row as a verified binding",
        "refused_because": (
            "demo_fixture is not in VERIFIER_REQUIRED_STATUSES, so it asserts "
            "no verification at all"
        ),
    },
    {
        "shortcut": "use a synthetic provider subject as the verifier identity",
        "refused_because": (
            "the verifier identity must be a real authenticated principal, "
            "and customer_auth_live is false so there is none"
        ),
    },
    {
        "shortcut": "set an environment variable to grant activation",
        "refused_because": (
            "the one variable in this path can only revoke; none can grant"
        ),
    },
)

#: Shapes that must never appear in a payload from this module.
_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: dict[str, Any]) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def _classification(
    organization_id: str,
    *,
    org_type_in_database: str | None,
) -> dict[str, Any]:
    """Demo or real, from the database. A caller's label is not consulted."""
    normalized = str(organization_id or "").strip().lower()
    declared = str(org_type_in_database or "").strip().lower() or None

    is_the_demo_org = normalized == DEMO_ORGANIZATION_ID
    is_the_real_org = normalized == REAL_ORGANIZATION_ID

    # The id is authoritative for the two organizations named in code. For any
    # other, the database's org_type decides, and its absence is UNKNOWN rather
    # than an assumption in either direction.
    if is_the_demo_org:
        classification = "demo"
    elif is_the_real_org:
        classification = "real"
    elif declared in {"demo", "real"}:
        classification = declared
    else:
        classification = UNKNOWN

    return {
        "organization_id": normalized or None,
        "classification": classification,
        "classification_source": (
            "module_constant"
            if (is_the_demo_org or is_the_real_org)
            else ("database" if declared in {"demo", "real"} else "unavailable")
        ),
        "is_the_demo_organization": is_the_demo_org,
        "is_the_refused_real_organization": is_the_real_org,
    }


def build_approval_checklist(
    *,
    organization_id: Any = None,
    approval: Any = None,
    org_type_in_database: str | None = None,
    app_env: str | None = None,
    principal: dict[str, Any] | None = None,
    binding_read: dict[str, Any] | None = None,
    customer_auth_live: bool | None = None,
    second_person_event_present: bool | None = None,
    authorized_organization_ids: frozenset[str] | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """Report every refusal standing between today and a verified binding.

    `verified_operational_binding` is **not** a parameter. It is derived, so a
    caller cannot assert the thing this module exists to measure — the
    structural rule Gates 145 and 146 applied to their own headline flags.

    `binding_read` is a `get_active_binding` result, supplied rather than read
    here so this module owns no connection and cannot touch a row.
    """
    environment = str(app_env or "local").strip().lower() or "local"
    classification = _classification(
        str(organization_id or ""), org_type_in_database=org_type_in_database
    )

    # Labels offered as authority are refused by name, not merged and not
    # silently dropped.
    offered_authority = sorted(
        key for key in offered if key in FORBIDDEN_AUTHORITY_KEYS
    )
    # `is_demo` and `org_type` are refused as authority too: classification
    # comes from the database. They are named separately because a caller
    # passing them is making a different mistake from one passing a tenant id.
    offered_classification = sorted(
        key for key in offered if key in {"is_demo", "org_type"}
    )

    authorized = (
        AUTHORIZED_REAL_ORGANIZATION_IDS
        if authorized_organization_ids is None
        # The injectable set can never reach the two organizations named in
        # code. Gate 137G found the first version of this reaching the real org.
        else frozenset(
            str(value).strip().lower()
            for value in authorized_organization_ids
            if str(value).strip().lower()
            not in {DEMO_ORGANIZATION_ID, REAL_ORGANIZATION_ID}
        )
    )

    approval_failures = approval_shape_failures(approval) if approval else None
    approval_present = bool(approval) and not approval_failures
    scope = str((approval or {}).get("authorization_scope") or "").strip().lower()
    scope_covers_environment = bool(
        (scope == REAL_ORG_SCOPE and environment in NON_PRODUCTION_ENVIRONMENTS)
        or scope == PRODUCTION_SCOPE
    )

    role = str((principal or {}).get("role") or "").strip().lower()
    principal_qualified = bool(
        role in VERIFIER_ROLES
        and (principal or {}).get("authenticated")
        and (principal or {}).get("verified_org")
    )

    read = binding_read or {}
    rows_matched = int(read.get("rows_matched") or 0)
    read_blockers = [str(r) for r in (read.get("blocked_reasons") or [])]
    duplicate_active = rows_matched > 1
    ambiguous_active = bool(
        "active_binding_is_ambiguous" in read_blockers or duplicate_active
    )
    existing_status = str(read.get("binding_status") or "") or None
    existing_asserts_verification = bool(
        existing_status in VERIFIER_REQUIRED_STATUSES
        and read.get("verified_by_identity_id")
        and not read.get("demo_fixture")
    )

    auth_live = bool(customer_auth_live)

    # ------------------------------------------------------------- refusals
    refusals: list[str] = []

    if classification["is_the_demo_organization"]:
        refusals.append(REFUSAL_DEMO_ORG)
    if classification["is_the_refused_real_organization"]:
        refusals.append(REFUSAL_REAL_ORG)
    if str(organization_id or "").strip().lower() not in authorized:
        refusals.append(REFUSAL_AUTHORIZED_LIST)
    if not approval_present:
        refusals.append(REFUSAL_NO_APPROVAL)
    if not auth_live:
        refusals.append(REFUSAL_AUTH_NOT_LIVE)
    if not principal_qualified:
        refusals.append(REFUSAL_PRINCIPAL)
    if duplicate_active:
        refusals.append(REFUSAL_DUPLICATE)
    if ambiguous_active:
        refusals.append(REFUSAL_AMBIGUOUS)

    blockers = sorted(set(refusals))

    # Derived. Never supplied, and never true while any refusal stands.
    verified_operational_binding = bool(
        not blockers and approval_present and scope_covers_environment
    )

    # The approval boundary is "ready" when every refusal is nameable and the
    # path evaluates — which is a different question from whether the binding
    # may happen. Gate 146's distinction, at a new subject.
    approval_boundary_ready = bool(
        classification["classification_source"] != "unavailable"
        or classification["is_the_demo_organization"]
        or classification["is_the_refused_real_organization"]
    )

    next_action: dict[str, Any] | None = None
    for refusal in (
        REFUSAL_DEMO_ORG,
        REFUSAL_REAL_ORG,
        REFUSAL_AUTH_NOT_LIVE,
        REFUSAL_AUTHORIZED_LIST,
        REFUSAL_NO_APPROVAL,
        REFUSAL_DUPLICATE,
        REFUSAL_AMBIGUOUS,
        REFUSAL_PRINCIPAL,
    ):
        if refusal in blockers:
            next_action = {"refusal": refusal, **REFUSAL_OWNERS[refusal]}
            break

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "environment": environment,
            **classification,
            # The headline, derived.
            "verified_operational_binding": verified_operational_binding,
            "approval_boundary_ready": approval_boundary_ready,
            # Each input, reported so a reader can check a claim not take one.
            "customer_auth_live": auth_live,
            "second_person_event_present": bool(second_person_event_present),
            "approval_supplied": bool(approval),
            "approval_well_formed": approval_present,
            "approval_shape_failures": sorted(approval_failures or []),
            "approval_fields_required": list(APPROVAL_FIELDS),
            "authorization_scope": scope or None,
            "scope_covers_environment": scope_covers_environment,
            "authorized_organization_count": len(authorized),
            "verifier_principal_qualified": principal_qualified,
            "verifier_roles": sorted(VERIFIER_ROLES),
            "existing_binding_status": existing_status,
            "existing_binding_asserts_verification": existing_asserts_verification,
            "active_binding_rows_matched": rows_matched,
            "duplicate_active_binding": duplicate_active,
            "ambiguous_active_binding": ambiguous_active,
            # Labels refused rather than dropped.
            "offered_authority_keys_refused": offered_authority,
            "offered_classification_keys_refused": offered_classification,
            "forbidden_authority_keys": list(FORBIDDEN_AUTHORITY_KEYS),
            # The answer.
            "blockers": blockers,
            "blocker_owners": {name: REFUSAL_OWNERS[name] for name in blockers},
            "next_human_action": next_action,
            "refused_shortcuts": list(REFUSED_SHORTCUTS),
            "not_approved": list(NOT_APPROVED),
            # Nothing here writes, and each is asserted so a regression that
            # flipped one is a test failure rather than a silently wider gate.
            "binding_written_by_this_module": False,
            "approval_granted_by_this_module": False,
            "real_organization_touched": False,
            "mutation_path_enabled": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def approval_checklist_invariant_failures(checklist: dict[str, Any]) -> list[str]:
    """Refuse a checklist that claims more than its evidence supports."""
    fails: list[str] = []

    if checklist.get("verified_operational_binding"):
        if checklist.get("blockers"):
            fails.append("verified_binding_alongside_blockers")
        if checklist.get("is_the_demo_organization"):
            fails.append("verified_binding_for_the_demo_organization")
        if checklist.get("is_the_refused_real_organization"):
            fails.append("verified_binding_for_the_refused_real_organization")
        if not checklist.get("customer_auth_live"):
            fails.append("verified_binding_without_live_customer_auth")
        if not checklist.get("approval_well_formed"):
            fails.append("verified_binding_without_a_well_formed_approval")
        if not checklist.get("scope_covers_environment"):
            fails.append("verified_binding_with_a_scope_that_does_not_cover_it")
        if not checklist.get("verifier_principal_qualified"):
            fails.append("verified_binding_without_a_qualified_principal")
        if checklist.get("duplicate_active_binding") or checklist.get(
            "ambiguous_active_binding"
        ):
            fails.append("verified_binding_over_an_unresolved_conflict")

    if checklist.get("is_the_demo_organization") and (
        REFUSAL_DEMO_ORG not in (checklist.get("blockers") or [])
    ):
        fails.append("demo_organization_not_refused")

    if checklist.get("is_the_refused_real_organization") and (
        REFUSAL_REAL_ORG not in (checklist.get("blockers") or [])
    ):
        fails.append("real_organization_not_refused")

    for flag in (
        "binding_written_by_this_module",
        "approval_granted_by_this_module",
        "real_organization_touched",
        "mutation_path_enabled",
    ):
        if checklist.get(flag):
            fails.append(f"module_claimed_to_have:{flag}")

    for name in checklist.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
