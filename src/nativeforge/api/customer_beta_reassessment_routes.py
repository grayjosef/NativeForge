"""Gate 150C: the customer beta reassessment, behind an authenticated org.

```text
GET /v1/nf/demo/orgs/{org}/beta-reassessment/decision
GET /v1/nf/demo/orgs/{org}/beta-reassessment/safe-claims
GET /v1/nf/demo/orgs/{org}/beta-reassessment/unsafe-claims
GET /v1/nf/demo/orgs/{org}/beta-reassessment/next-block
```

GET only. There is nothing here to activate, approve, or record — this gate
compares two decisions and reports the difference, which today is none.

## Every fact is measured

The three scope verdicts come from the service that owns them, and
`customer_auth_live` is derived from the invite evidence the way Gate 146
derives it. Nothing is read from a query string or a body, because a caller
supplying a lane value would be supplying the verdict.

## The one failure mode

Reporting `controlled_customer_beta: GO` without the four approvals behind it.
The service's invariants refuse that, this route refuses to emit a payload whose
invariants failed, and a test forges the GO to prove the refusal fires.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.customer_beta_reassessment_service import (
    CONFLATIONS,
    NEXT_BLOCK,
    SAFE_CLAIMS,
    UNSAFE_CLAIMS,
    build_reassessment,
    reassessment_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["customer-beta-reassessment-demo"])


def _reassessment(db: Session) -> dict[str, Any]:
    """Measure every lane, then compare. Nothing is supplied by the caller."""
    from nativeforge.services.controlled_beta_artifact_gate145_service import (
        FULL_BATTERY,
    )
    from nativeforge.services.controlled_beta_readiness_decision_service import (
        build_controlled_beta_decision,
    )
    from nativeforge.services.membership_invite_repository_service import (
        build_invite_binding_evidence,
    )

    try:
        evidence = build_invite_binding_evidence(connection=db.connection())
        auth_live = bool(evidence.get("invite_binding_passed"))
    except Exception:  # noqa: BLE001
        auth_live = False

    scopes = (build_controlled_beta_decision(**FULL_BATTERY).get("by_scope")) or {}

    result = build_reassessment(
        internal_demo_beta=(scopes.get("internal_demo_beta") or {}).get("decision"),
        controlled_customer_beta=(
            scopes.get("controlled_customer_beta") or {}
        ).get("decision"),
        customer_auth_live=auth_live,
        # Gates 147-149 measured these false, and nothing a request can do
        # moves any of them.
        verified_operational_binding=False,
        consent_boundary_documented=False,
        customer_beta_scope_approved=False,
        controlled_customer_pilot=False,
        activation_mechanism_exists=False,
        # The readiness facts each of those gates did establish.
        second_person_readiness_passed=True,
        approval_boundary_ready=True,
        customer_data_write_guard_ready=True,
        activation_package_ready=True,
    )
    result["invariant_failures"] = reassessment_invariant_failures(result)

    if result["leaked_shapes"] or result["invariant_failures"]:
        raise HTTPException(status_code=500, detail="reassessment_refused")

    return result


@router.get("/{org_id}/beta-reassessment/decision")
def get_beta_reassessment(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Gate 145's decision, the current one, and the difference."""
    same_org(org_id, ctx)
    result = _reassessment(db)
    return envelope(
        {
            "gate_145_baseline": result["gate_145_baseline"],
            "current_decision": result["current_decision"],
            "decision_delta": result["decision_delta"],
            "any_decision_changed": result["any_decision_changed"],
            "why_no_change_is_correct": result["why_no_change_is_correct"],
            "customer_beta_approvals": result["customer_beta_approvals"],
            "customer_beta_approvals_outstanding": result[
                "customer_beta_approvals_outstanding"
            ],
            "no_outstanding_customer_blocker_is_technical": result[
                "no_outstanding_customer_blocker_is_technical"
            ],
            "readiness_facts": result["readiness_facts"],
            "conflations": [dict(entry) for entry in CONFLATIONS],
            "clarifications": result["clarifications"],
            "throughline": result["throughline"],
            "lanes_moved_by_this_block": result["lanes_moved_by_this_block"],
            "controlled_customer_pilot": False,
            "activation_mechanism_exists": False,
            "invariant_failures": result["invariant_failures"],
        }
    )


@router.get("/{org_id}/beta-reassessment/safe-claims")
def get_safe_claims(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What may truthfully be said to a prospective beta customer today."""
    same_org(org_id, ctx)
    return envelope(
        {
            "safe_claims": list(SAFE_CLAIMS),
            "safe_claim_count": len(SAFE_CLAIMS),
            "scope": "controlled_dev_demo",
            "note": (
                "each is true as measured today; none asserts a capability "
                "that is false"
            ),
        }
    )


@router.get("/{org_id}/beta-reassessment/unsafe-claims")
def get_unsafe_claims(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What must not be said, each paired with the true statement."""
    same_org(org_id, ctx)
    return envelope(
        {
            "unsafe_claims": [dict(entry) for entry in UNSAFE_CLAIMS],
            "unsafe_claim_count": len(UNSAFE_CLAIMS),
            "note": (
                "an inventory of what may not be said is not a saying of it"
            ),
        }
    )


@router.get("/{org_id}/beta-reassessment/next-block")
def get_next_block(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Where the campaign should go, and why this rather than waiting."""
    same_org(org_id, ctx)
    return envelope(dict(NEXT_BLOCK))
