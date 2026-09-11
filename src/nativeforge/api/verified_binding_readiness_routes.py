"""Gate 147D: the verified-binding approval boundary, behind an authenticated org.

```text
GET  /v1/nf/demo/orgs/{org}/verified-binding/readiness    the five refusals
GET  /v1/nf/demo/orgs/{org}/verified-binding/blockers     each, with its owner
GET  /v1/nf/demo/orgs/{org}/verified-binding/checklist    the full checklist
POST /v1/nf/demo/orgs/{org}/verified-binding/dry-run-decision
```

## The POST writes nothing, and is named so nobody has to take that on trust

It is the only non-GET here and it is a decision, not an activation. The
underlying composite takes no connection, imports no repository, and returns
`mutation_performed: false` and `rows_written: 0` on every branch. A route that
could activate a real-organization binding is not something this gate builds;
Gate 137 put the mutation path behind an approval object that does not exist,
and it stays there.

The reason it is a POST at all is that a caller supplies an approval object to
be evaluated — a hypothetical, so an operator can ask "would this approval be
enough?" without recording one. The answer today is no, for five reasons.

## Demo organization only

The org comes from the session context; a forged header cannot choose it. The
real organization is refused by name inside the service, before any read. And
the demo organization is refused for a different reason that no approval
touches: it is never a verified operational binding, in any environment.

That second refusal is the point of the whole gate, so these routes report it
rather than returning 404 and letting the reader guess.

## Nothing is activated

No binding row, no approval record, no audit event. No live source, no mail, no
object store, no customer data.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.tenant_customer_org_binding_repository_service import (
    get_active_binding,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    DECISION_LAYERS,
    build_verified_binding_dry_run_decision,
    dry_run_decision_invariant_failures,
)
from nativeforge.services.verified_operational_binding_approval_checklist_service import (  # noqa: E501
    REFUSED_SHORTCUTS,
    approval_checklist_invariant_failures,
    build_approval_checklist,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["verified-binding-readiness-demo"])


def _org_type(db: Session, org_id: uuid.UUID) -> str | None:
    """Classification from the database. Never from the caller."""
    import sqlalchemy as sa

    row = (
        db.connection()
        .execute(
            sa.text("SELECT org_type FROM organizations WHERE id = :i"),
            {"i": str(org_id).replace("-", "")},
        )
        .first()
    )
    return str(row[0]) if row and row[0] is not None else None


def _checklist(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    connection = db.connection()
    read = get_active_binding(connection=connection, organization_id=str(org_id))

    checklist = build_approval_checklist(
        organization_id=str(org_id),
        org_type_in_database=_org_type(db, org_id),
        binding_read=read,
        # Measured, not assumed. This request cannot prove the second-person
        # event happened, and the checklist derives the lane from it rather
        # than being handed a value.
        customer_auth_live=_customer_auth_live(connection),
    )
    checklist["invariant_failures"] = approval_checklist_invariant_failures(checklist)

    if checklist.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="checklist_payload_refused")

    return checklist


def _customer_auth_live(connection: Any) -> bool:
    """Derived from the invite evidence, the same way Gate 146 derives it."""
    from nativeforge.services.membership_invite_repository_service import (
        build_invite_binding_evidence,
    )

    try:
        evidence = build_invite_binding_evidence(connection=connection)
    except Exception:  # noqa: BLE001
        return False
    return bool(evidence.get("invite_binding_passed"))


@router.get("/{org_id}/verified-binding/readiness")
def get_verified_binding_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """How far `verified_operational_binding` is from true, and why."""
    same_org(org_id, ctx)
    checklist = _checklist(db, org_id)
    return envelope(
        {
            "verified_operational_binding": checklist["verified_operational_binding"],
            "approval_boundary_ready": checklist["approval_boundary_ready"],
            "classification": checklist["classification"],
            "classification_source": checklist["classification_source"],
            "customer_auth_live": checklist["customer_auth_live"],
            "verifier_principal_qualified": checklist["verifier_principal_qualified"],
            "active_binding_rows_matched": checklist["active_binding_rows_matched"],
            "duplicate_active_binding": checklist["duplicate_active_binding"],
            "ambiguous_active_binding": checklist["ambiguous_active_binding"],
            "existing_binding_status": checklist["existing_binding_status"],
            "existing_binding_asserts_verification": checklist[
                "existing_binding_asserts_verification"
            ],
            "blocker_count": len(checklist["blockers"]),
            "invariant_failures": checklist["invariant_failures"],
            "demo_organization_can_never_satisfy_this": checklist[
                "is_the_demo_organization"
            ],
            "mutation_path_enabled": False,
            "controlled_customer_pilot": False,
            "production_rollout": False,
        }
    )


@router.get("/{org_id}/verified-binding/blockers")
def get_verified_binding_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Every refusal, and whether it is code, a decision, or never clears."""
    same_org(org_id, ctx)
    checklist = _checklist(db, org_id)
    return envelope(
        {
            "blockers": checklist["blockers"],
            "blocker_owners": checklist["blocker_owners"],
            "next_human_action": checklist["next_human_action"],
            "refused_shortcuts": list(REFUSED_SHORTCUTS),
            "not_approved": checklist["not_approved"],
            "verified_operational_binding": checklist["verified_operational_binding"],
        }
    )


@router.get("/{org_id}/verified-binding/checklist")
def get_verified_binding_checklist(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The whole checklist, for a cockpit that wants every field."""
    same_org(org_id, ctx)
    return envelope(_checklist(db, org_id))


@router.post("/{org_id}/verified-binding/dry-run-decision")
def post_dry_run_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Evaluate a hypothetical approval. Records nothing, writes nothing.

    The approval in the body is *evaluated*, never stored. Asking "would this
    be enough?" must not be the same action as deciding it is.
    """
    same_org(org_id, ctx)
    supplied = body or {}

    connection = db.connection()
    read = get_active_binding(connection=connection, organization_id=str(org_id))

    decision = build_verified_binding_dry_run_decision(
        organization_id=str(org_id),
        approval=supplied.get("approval"),
        org_type_in_database=_org_type(db, org_id),
        # The principal is taken from the session context, never from the body.
        # A caller naming their own role would be choosing their own authority.
        principal={
            "role": getattr(ctx, "role", None),
            "authenticated": True,
            "verified_org": False,
        },
        binding_read=read,
        customer_auth_live=_customer_auth_live(connection),
    )
    decision["invariant_failures"] = dry_run_decision_invariant_failures(decision)

    if decision["invariant_failures"]:
        raise HTTPException(status_code=500, detail="dry_run_decision_refused")

    return envelope(
        {
            **decision,
            "decision_layers": list(DECISION_LAYERS),
            "approval_recorded": False,
            "binding_written": False,
            "note": (
                "a dry run evaluates an approval; it does not record one, and "
                "no branch of this route writes a binding row"
            ),
        }
    )
