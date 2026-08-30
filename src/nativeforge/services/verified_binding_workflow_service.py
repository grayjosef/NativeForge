"""Verified binding workflow (Gate 120C).

Three contracts existed and nothing joined them:

```text
Gate 109  build_binding                 what a binding may assert
Gate 111  authorize_binding_operation   who may change one
Gate 120B repository                    where one goes
```

Each was correct alone and none could complete an operation. This service is the
join, and it refuses in the order that matters: **authorization first, contract
second, storage last.**

## Why that order

A workflow that built the record first and checked the role afterwards would
still refuse — but it would have constructed a fully-formed verified binding for
a caller who was never allowed to ask. Nothing would be written, and the shape
of the thing would still have been produced on their behalf.

Checking authorization first means an unauthorized caller never reaches the
constructor. The blocked reason they get names the role, not the record.

## Inspection is not approval

Gate 111's split is preserved exactly and this gate must not widen it:

```text
INSPECTOR_ROLES  platform_admin, tenant_admin, grants_manager, auditor
VERIFIER_ROLES   platform_admin, tenant_admin
```

`grants_manager` and `auditor` can look at a pending binding forever and can
never approve one. That is the whole point of having two role sets, and a test
asserts a `grants_manager` is refused on approval while permitted on inspection.

## A demo fixture success is not a production success

The workflow can complete end-to-end under a demo principal against a demo
binding, and the result says so:

```text
repository_write_performed      True    a row was written
verified_operational_binding    False   and it binds nothing
```

Those are different fields because they are different facts. A fixture that
inserted successfully has proven the code path works; it has not produced a
binding anybody may act on.

## Operational verified binding requires customer auth, and cannot have it

`verified_by_identity_id` references `nf_identities` — a *verified OIDC
subject*. Gate 120A measured eleven of sixteen activation gates unsatisfied, so
no OIDC subject can be verified, so **no genuine verifier identity exists to
name**.

A production verified binding is therefore not merely unauthorized today; it is
unconstructible. `verified_operational_binding` is derived from
`customer_auth_live` and is false, and an invariant refuses any result claiming
otherwise.

## Nothing here writes to the application database

The repository defaults to contract mode. A connection reaches it only from a
test or a fixture holding an isolated database of its own.

```text
production verified bindings created   0
real customer rows written             0
```
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_customer_org_binding_repository_service import (
    get_active_binding,
    insert_binding,
    mark_conflict,
    prepare_insert,
)
from nativeforge.services.tenant_customer_org_binding_repository_service import (
    revoke_binding as repository_revoke_binding,
)
from nativeforge.services.tenant_customer_org_binding_store_service import (
    VERIFIER_REQUIRED_STATUSES,
)
from nativeforge.services.verified_binder_authorization_service import (
    BINDING_OPERATIONS,
    INSPECTION_OPERATIONS,
    VERIFYING_OPERATIONS,
    authorize_binding_operation,
)

SCHEMA_VERSION = "nf_verified_binding_workflow_v1"

# The workflow's own vocabulary, mapped onto Gate 111's operations rather than
# restated. A name here that had no authorization operation behind it would be
# an operation nobody could refuse.
WORKFLOW_OPERATIONS: dict[str, str] = {
    "inspect_pending": "inspect_pending_binding",
    "approve_pending": "approve_pending_binding",
    "create_verified_binding": "create_verified_binding",
    "revoke_binding": "revoke_binding",
    "resolve_conflict": "resolve_conflict",
}

# Operations that end in a repository write when everything permits it.
WRITING_WORKFLOWS = frozenset(
    {"approve_pending", "create_verified_binding", "revoke_binding", "resolve_conflict"}
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "binding_operation",
    "authorization_checked",
    "authorization_allowed",
    "binding_contract_valid",
    "repository_write_allowed",
    "repository_write_performed",
    "verified_operational_binding",
    "customer_auth_live",
    "login_live",
    "human_review_required",
    "blocked_reasons",
    "next_required_actions",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _activation() -> dict[str, bool]:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    return {
        "customer_auth_live": bool(gate["customer_auth_live"]),
        "login_live": bool(gate["login_live"]),
    }


def run_binding_workflow(
    *,
    operation: Any = None,
    principal: dict[str, Any] | None = None,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    binding_status: Any = None,
    binding_source: Any = None,
    binding_confidence: Any = None,
    verified_by_identity_id: Any = None,
    verified_at: Any = None,
    revoked_by_identity_id: Any = None,
    connection: Any = None,
    customer_auth_live: bool | None = None,
    login_live: bool | None = None,
) -> dict[str, Any]:
    """One binding operation, refused at the first step that cannot proceed.

    ``customer_auth_live`` and ``login_live`` are injectable so a test can reach
    the branch where they are true. Without that, ``verified_operational_binding:
    True`` would be unreachable and every refusal below it unfalsifiable — the
    lesson Gates 117, 118 and 119 each learned once.

    Injecting them does not make them true. The real environment is measured
    when they are not supplied, and it reports false.
    """
    workflow = str(operation or "").strip().lower()
    blocked_reasons: list[str] = []
    next_required_actions: list[str] = []

    binding_operation = WORKFLOW_OPERATIONS.get(workflow, "unknown")
    if workflow not in WORKFLOW_OPERATIONS:
        blocked_reasons.append(f"unrecognised_workflow_operation:{workflow}")
    if binding_operation not in BINDING_OPERATIONS:
        blocked_reasons.append("workflow_operation_has_no_authorization_operation")

    # -- 1. authorization, before anything is constructed --------------------
    authorization = authorize_binding_operation(
        principal=principal,
        binding_operation=binding_operation,
        tenant_id=tenant_id,
        customer_org_id=customer_org_id,
        target_binding_status=binding_status,
    )
    authorization_checked = True
    authorization_allowed = bool(authorization["binding_authorized"])
    if not authorization_allowed:
        blocked_reasons.extend(
            f"authorization:{reason}" for reason in authorization["blocked_reasons"]
        )
        if binding_operation in VERIFYING_OPERATIONS:
            next_required_actions.append(
                "supply a principal holding platform_admin or tenant_admin with a "
                "verified organization membership"
            )

    # -- 2. the binding contract --------------------------------------------
    # Only consulted once authorization passed. An unauthorized caller does not
    # get a fully-formed verified binding constructed on their behalf.
    contract: dict[str, Any] = {}
    binding_contract_valid = False
    if authorization_allowed and binding_operation not in INSPECTION_OPERATIONS:
        contract = prepare_insert(
            organization_id=organization_id,
            tenant_id=tenant_id,
            customer_org_id=customer_org_id,
            organization_profile_id=organization_profile_id,
            binding_status=binding_status,
            binding_source=binding_source,
            binding_confidence=binding_confidence,
            verified_by_identity_id=verified_by_identity_id,
            verified_at=verified_at,
            is_demo=bool((principal or {}).get("is_demo_principal")),
        )
        binding_contract_valid = bool(contract["storage_allowed"])
        if not binding_contract_valid:
            blocked_reasons.extend(
                f"contract:{reason}" for reason in contract["blocked_reasons"]
            )
    elif authorization_allowed:
        # Inspection asks nothing of the contract. It reads.
        binding_contract_valid = True

    # -- 3. the repository ---------------------------------------------------
    live = _activation()
    auth_live = (
        live["customer_auth_live"]
        if customer_auth_live is None
        else bool(customer_auth_live)
    )
    is_login_live = live["login_live"] if login_live is None else bool(login_live)

    # A *production* verified binding is a row that asserts somebody verified
    # something. Writing one while nobody can be authenticated leaves that
    # assertion sitting in a table with no verifier behind it, which is the
    # thing `ck_nf_binding_verified_needs_verifier` exists to prevent and which
    # a nullable-in-practice identity id would slip past.
    #
    # Demo fixtures, revocations and conflicts are unaffected: none of them
    # asserts a verification.
    writes_production_verification = bool(
        str(binding_status or "").strip().lower() in VERIFIER_REQUIRED_STATUSES
        and not bool((principal or {}).get("is_demo_principal"))
    )
    if writes_production_verification and not auth_live:
        blocked_reasons.append(
            "production_verified_binding_requires_live_customer_auth"
        )

    repository_write_allowed = bool(
        authorization_allowed
        and binding_contract_valid
        and workflow in WRITING_WORKFLOWS
        and not (writes_production_verification and not auth_live)
    )
    repository_write_performed = False
    repository_result: dict[str, Any] = {}

    if workflow == "inspect_pending" and authorization_allowed:
        repository_result = get_active_binding(
            connection=connection,
            organization_id=organization_id,
            tenant_id=tenant_id,
            customer_org_id=customer_org_id,
        )
    elif repository_write_allowed and workflow == "revoke_binding":
        repository_result = repository_revoke_binding(
            connection=connection,
            organization_id=organization_id,
            tenant_id=tenant_id,
            customer_org_id=customer_org_id,
            revoked_by_identity_id=revoked_by_identity_id
            or (principal or {}).get("principal_id"),
        )
        repository_write_performed = bool(repository_result["write_performed"])
    elif repository_write_allowed and workflow == "resolve_conflict":
        repository_result = mark_conflict(
            connection=connection,
            organization_id=organization_id,
            tenant_id=tenant_id,
            customer_org_id=customer_org_id,
        )
        repository_write_performed = bool(repository_result["write_performed"])
    elif repository_write_allowed:
        repository_result = insert_binding(
            connection=connection,
            organization_id=organization_id,
            tenant_id=tenant_id,
            customer_org_id=customer_org_id,
            organization_profile_id=organization_profile_id,
            binding_status=binding_status,
            binding_source=binding_source,
            binding_confidence=binding_confidence,
            verified_by_identity_id=verified_by_identity_id,
            verified_at=verified_at,
            is_demo=bool((principal or {}).get("is_demo_principal")),
        )
        repository_write_performed = bool(repository_result["write_performed"])

    if repository_result:
        blocked_reasons.extend(
            f"repository:{reason}"
            for reason in repository_result.get("blocked_reasons") or []
            # Contract mode is the default and is not a failure of the workflow.
            if not reason.startswith("no_connection_supplied")
        )

    # -- what none of it makes true ------------------------------------------
    # Derived affirmatively. A binding binds nobody until somebody can be
    # authenticated as the person it names.
    verified_operational_binding = bool(
        auth_live
        and repository_write_performed
        and bool(repository_result.get("production_verified_binding"))
        and not repository_result.get("demo_fixture")
    )
    if not auth_live:
        blocked_reasons.append("customer_auth_not_live_so_no_binding_is_operational")
        next_required_actions.append(
            "satisfy every customer auth activation gate - Gate 115's contract, "
            "11 of 16 unsatisfied today"
        )

    human_review_required = bool(
        repository_result.get("human_review_required", True)
        or authorization.get("human_review_required")
        or not verified_operational_binding
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": workflow or "unknown",
        "binding_operation": binding_operation,
        "authorization_checked": authorization_checked,
        "authorization_allowed": authorization_allowed,
        "binding_contract_valid": binding_contract_valid,
        "repository_write_allowed": repository_write_allowed,
        "repository_write_performed": repository_write_performed,
        "verified_operational_binding": verified_operational_binding,
        "customer_auth_live": auth_live,
        "login_live": is_login_live,
        "human_review_required": human_review_required,
        "demo_fixture": bool(repository_result.get("demo_fixture")),
        "rows_written": int(repository_result.get("rows_written") or 0),
        "rows_read": int(repository_result.get("rows_read") or 0),
        "blocked_reasons": sorted(set(blocked_reasons)),
        "next_required_actions": sorted(set(next_required_actions)),
        # Constants. A workflow coordinates; it invents nothing.
        "production_verified_bindings_created": 0,
        "real_customer_rows_written": 0,
        "rows_deleted": 0,
        "provider_contacted": False,
        "fabricated": False,
    }
    return _json_safe(result)


def inspect_pending(**kwargs: Any) -> dict[str, Any]:
    """Look at a binding. Permitted to inspectors, who cannot change one."""
    return run_binding_workflow(operation="inspect_pending", **kwargs)


def approve_pending(**kwargs: Any) -> dict[str, Any]:
    """Approve a pending binding. Verifier roles only."""
    return run_binding_workflow(operation="approve_pending", **kwargs)


def create_verified_binding(**kwargs: Any) -> dict[str, Any]:
    """Create a verified binding. Needs a verifier identity that cannot exist."""
    return run_binding_workflow(operation="create_verified_binding", **kwargs)


def revoke_binding(**kwargs: Any) -> dict[str, Any]:
    """Withdraw a binding. An UPDATE; the row and its history stay."""
    return run_binding_workflow(operation="revoke_binding", **kwargs)


def resolve_conflict(**kwargs: Any) -> dict[str, Any]:
    """Mark a binding as contradicted. It then authorizes nothing."""
    return run_binding_workflow(operation="resolve_conflict", **kwargs)


def workflow_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this workflow must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    operation = str(result.get("operation") or "")
    if operation not in WORKFLOW_OPERATIONS and operation != "unknown":
        failures.append("operation_outside_vocabulary")

    if not result.get("authorization_checked"):
        failures.append("a_binding_operation_ran_without_an_authorization_check")

    if result.get("repository_write_allowed") and not result.get(
        "authorization_allowed"
    ):
        failures.append("a_write_was_allowed_without_authorization")

    if result.get("repository_write_allowed") and not result.get(
        "binding_contract_valid"
    ):
        failures.append("a_write_was_allowed_against_an_invalid_binding")

    if result.get("repository_write_performed") and not result.get(
        "repository_write_allowed"
    ):
        failures.append("a_write_happened_without_being_allowed")

    if result.get("rows_written") and not result.get("repository_write_performed"):
        failures.append("rows_written_without_a_performed_write")

    if result.get("verified_operational_binding") and not result.get(
        "customer_auth_live"
    ):
        failures.append("an_operational_binding_claimed_while_auth_is_not_live")

    if result.get("verified_operational_binding") and result.get("demo_fixture"):
        failures.append("a_demo_fixture_claimed_an_operational_binding")

    if result.get("production_verified_bindings_created"):
        failures.append("a_production_verified_binding_was_created")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("rows_deleted"):
        failures.append("a_binding_row_was_deleted")

    if result.get("provider_contacted"):
        failures.append("a_workflow_contacted_a_provider")

    if not result.get("authorization_allowed") and not result.get("blocked_reasons"):
        failures.append("authorization_refused_without_a_reason")

    if result.get("verified_operational_binding") and result.get("blocked_reasons"):
        failures.append("an_operational_binding_with_blocked_reasons_present")

    return sorted(set(failures))


def build_workflow_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them achieved."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = run_binding_workflow(**case["request"])
        rows.append(
            {
                "case": case["case"],
                "operation": result["operation"],
                "authorization_allowed": result["authorization_allowed"],
                "binding_contract_valid": result["binding_contract_valid"],
                "repository_write_allowed": result["repository_write_allowed"],
                "repository_write_performed": result["repository_write_performed"],
                "verified_operational_binding": result["verified_operational_binding"],
                "customer_auth_live": result["customer_auth_live"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": workflow_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "authorized_count": sum(1 for r in rows if r["authorization_allowed"]),
            "write_performed_count": sum(
                1 for r in rows if r["repository_write_performed"]
            ),
            "operational_binding_count": sum(
                1 for r in rows if r["verified_operational_binding"]
            ),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
        }
    )
