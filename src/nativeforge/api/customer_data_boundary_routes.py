"""Gate 148E: the consent and customer data boundary, behind an authenticated org.

```text
GET  /v1/nf/demo/orgs/{org}/data-boundary/readiness     the two headline facts
GET  /v1/nf/demo/orgs/{org}/data-boundary/classes       the nine data classes
GET  /v1/nf/demo/orgs/{org}/data-boundary/consent-blockers
POST /v1/nf/demo/orgs/{org}/data-boundary/dry-run-write
```

## The POST evaluates a write; it never performs one

The underlying guard opens no connection and returns `rows_written: 0` on every
branch. The POST exists so a future write path — or an operator asking "would
this be allowed?" — gets an answer without anything being stored.

A caller supplies a data class and, optionally, a hypothetical consent record
and beta scope approval. Those are **evaluated, never recorded**: asking whether
an approval would be enough must not be the same action as granting it.

## Capability flags are measured, not accepted

`customer_auth_live`, `verified_operational_binding`, `object_store_configured`,
`email_delivery` and `source_monitoring_live` are not read from the body. A
caller handing the guard its own capability flags would be handing it the
answer. They are measured here, and `customer_auth_live` is derived from the
invite evidence the same way Gate 146 derives it.

## Nothing leaves that should not

No provider subject, address, recipient, document body, token, cookie, state or
PKCE verifier. The payload is scanned before it is returned and the route
refuses rather than emits.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.customer_beta_consent_boundary_service import (
    BETA_SCOPE_APPROVAL_FIELDS,
    CONSENT_RECORD_FIELDS,
    build_consent_boundary,
    consent_boundary_invariant_failures,
)
from nativeforge.services.customer_data_classification_service import (
    NOT_CONSENT,
    build_data_class_catalogue,
)
from nativeforge.services.customer_data_write_guard_service import (
    CONTROLLED_SCOPE,
    evaluate_write,
    write_guard_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["customer-data-boundary-demo"])


def _org_type(db: Session, org_id: uuid.UUID) -> str | None:
    row = (
        db.connection()
        .execute(
            sa.text("SELECT org_type FROM organizations WHERE id = :i"),
            {"i": str(org_id).replace("-", "")},
        )
        .first()
    )
    return str(row[0]) if row and row[0] is not None else None


def _customer_auth_live(connection: Any) -> bool:
    from nativeforge.services.membership_invite_repository_service import (
        build_invite_binding_evidence,
    )

    try:
        return bool(
            build_invite_binding_evidence(connection=connection).get(
                "invite_binding_passed"
            )
        )
    except Exception:  # noqa: BLE001
        return False


def _measured(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    """Everything the guard needs that a caller must not be allowed to supply."""
    return {
        "org_type_in_database": _org_type(db, org_id),
        "customer_auth_live": _customer_auth_live(db.connection()),
        # Gate 147 measured this false, behind five refusals. Nothing a request
        # can do makes it true, so it is not computed per-request.
        "verified_operational_binding": False,
        "object_store_configured": False,
        "email_delivery": False,
        "source_monitoring_live": False,
    }


def _refuse_if_leaked(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="data_boundary_payload_refused")
    return payload


@router.get("/{org_id}/data-boundary/readiness")
def get_data_boundary_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Is there a consent boundary, and is the customer beta scope approved?"""
    same_org(org_id, ctx)
    decision = _refuse_if_leaked(
        build_consent_boundary(
            organization_id=str(org_id),
            data_class="customer_operational_data",
            **_measured(db, org_id),
        )
    )
    return envelope(
        {
            "consent_boundary_documented": decision["consent_boundary_documented"],
            "customer_beta_scope_approved": decision["customer_beta_scope_approved"],
            "organization_kind": decision["organization_kind"],
            "organization_kind_source": decision["organization_kind_source"],
            "customer_auth_live": decision["customer_auth_live"],
            "verified_operational_binding": decision["verified_operational_binding"],
            "capabilities": decision["capabilities"],
            "blocker_count": len(decision["blockers"]),
            "invariant_failures": consent_boundary_invariant_failures(decision),
            "demo_fixture_writes_still_allowed": True,
            "customer_data_writes_allowed": False,
            "controlled_customer_pilot": False,
            "production_rollout": False,
        }
    )


@router.get("/{org_id}/data-boundary/classes")
def get_data_classes(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """The nine classes, with examples, non-examples and what is not consent."""
    same_org(org_id, ctx)
    return envelope(build_data_class_catalogue())


@router.get("/{org_id}/data-boundary/consent-blockers")
def get_consent_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Every blocker, with whether it is a document, a decision or a customer."""
    same_org(org_id, ctx)
    decision = _refuse_if_leaked(
        build_consent_boundary(
            organization_id=str(org_id),
            data_class="customer_operational_data",
            **_measured(db, org_id),
        )
    )
    return envelope(
        {
            "blockers": decision["blockers"],
            "blocker_owners": decision["blocker_owners"],
            "next_human_action": decision["next_human_action"],
            "not_consent": [dict(entry) for entry in NOT_CONSENT],
            "consent_record_fields_required": list(CONSENT_RECORD_FIELDS),
            "beta_scope_fields_required": list(BETA_SCOPE_APPROVAL_FIELDS),
            "not_approved": decision["not_approved"],
        }
    )


@router.post("/{org_id}/data-boundary/dry-run-write")
def post_dry_run_write(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Would this write be allowed? Evaluates only; records and writes nothing."""
    same_org(org_id, ctx)
    supplied = body or {}

    decision = evaluate_write(
        organization_id=str(org_id),
        data_class=supplied.get("data_class"),
        scope=supplied.get("scope") or CONTROLLED_SCOPE,
        fact_status=supplied.get("fact_status"),
        route_context=supplied.get("route_context") or "data_boundary_dry_run",
        # Hypotheticals, evaluated and never stored.
        consent_record=supplied.get("consent_record"),
        beta_scope_approval=supplied.get("beta_scope_approval"),
        # Measured. Never taken from the body.
        **_measured(db, org_id),
    )
    decision["invariant_failures"] = write_guard_invariant_failures(decision)
    _refuse_if_leaked(decision)

    if decision["invariant_failures"]:
        raise HTTPException(status_code=500, detail="write_guard_decision_refused")

    return envelope(
        {
            **decision,
            "consent_recorded": False,
            "beta_scope_approved_by_this_call": False,
            "write_performed": False,
            "note": (
                "a dry run evaluates a write; it does not perform one, and no "
                "branch of this route records consent or approves a scope"
            ),
        }
    )
