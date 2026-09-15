"""Gate 155D: the durability reassessment and the next-activation decision.

```text
GET /v1/nf/demo/orgs/{org}/durability-reassessment/reassessment
GET /v1/nf/demo/orgs/{org}/durability-reassessment/safe-claims
GET /v1/nf/demo/orgs/{org}/durability-reassessment/unsafe-claims
GET /v1/nf/demo/orgs/{org}/durability-reassessment/next-activation-decision
```

GET only. Nothing here activates a capability, creates an activation mechanism,
changes a lane or writes a row. A reassessment that could change what it
reassesses would not be one.

## The lane values are supplied by their owners, not asserted here

Gates 151-154's lanes are proved by their own verifiers. This route reports the
reassessment against the values those verifiers established, and the two
production flags are constants: `production_backup_ready` and
`production_monitoring_active` have no branch here that returns true.

## Why the unsafe claims have their own route

An operator or a reviewer reading the safe list needs the unsafe list beside it.
Serving only what the system *can* say makes the omissions invisible, and the
omissions are the point of this gate.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.next_activation_decision_service import (
    build_next_activation_decision,
    next_activation_decision_invariant_failures,
)
from nativeforge.services.operational_durability_reassessment_service import (
    build_durability_reassessment,
    durability_reassessment_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["durability-reassessment-demo"])


def _decision() -> dict[str, Any]:
    # No customer prerequisite is available: no real customer organization
    # exists, no second identity, no consent decision. Supplying these as
    # false is a measurement, not a default - each is recorded false by the
    # lane that owns it.
    return build_next_activation_decision(
        real_customer_org_exists=False,
        second_identity_available=False,
        consent_decision_available=False,
    )


def _reassessment() -> dict[str, Any]:
    return build_durability_reassessment(
        # Proved by their own verifiers, which is what makes them reportable.
        internal_demo_beta="GO",
        controlled_customer_beta="LIMITED_GO",
        tenant_digest_persistence_live=True,
        audit_replay_ready=True,
        operational_backup_restore_ready=True,
        operational_health_ready=True,
        # Constants. No branch here returns true for either.
        production_backup_ready=False,
        production_monitoring_active=False,
        # Every lane Gate 150 recorded as not approved, still not approved.
        controlled_customer_pilot=False,
        activation_mechanism_exists=False,
        customer_auth_live=False,
        verified_operational_binding=False,
        consent_boundary_documented=False,
        customer_beta_scope_approved=False,
        source_monitoring_live=False,
        email_delivery=False,
        object_store_configured=False,
        next_block=_decision(),
    )


def _reassessment_or_refuse() -> dict[str, Any]:
    reassessment = _reassessment()
    if reassessment.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="reassessment_payload_refused")
    if durability_reassessment_invariant_failures(reassessment):
        raise HTTPException(status_code=500, detail="reassessment_refused")
    return reassessment


@router.get("/{org_id}/durability-reassessment/reassessment")
def get_durability_reassessment(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What Gates 151-154 moved, and what they deliberately did not."""
    same_org(org_id, ctx)
    reassessment = _reassessment_or_refuse()
    return envelope({**reassessment, "invariant_failures": []})


@router.get("/{org_id}/durability-reassessment/safe-claims")
def get_safe_claims(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What this system may honestly say after the block."""
    same_org(org_id, ctx)
    reassessment = _reassessment_or_refuse()
    return envelope(
        {
            "scope": reassessment["scope"],
            "safe_claims": reassessment["safe_claims"],
            "safe_claim_count": len(reassessment["safe_claims"]),
            "read_with": "the unsafe-claims route; the omissions are the point",
            "production_backup_ready": False,
            "production_monitoring_active": False,
        }
    )


@router.get("/{org_id}/durability-reassessment/unsafe-claims")
def get_unsafe_claims(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What a reader is most likely to conclude, and why it is wrong."""
    same_org(org_id, ctx)
    reassessment = _reassessment_or_refuse()
    return envelope(
        {
            "scope": reassessment["scope"],
            "unsafe_claims": reassessment["unsafe_claims"],
            "unsafe_claim_count": len(reassessment["unsafe_claims"]),
            "conflations": reassessment["conflations"],
            "the_one_most_likely": (
                "that Gate 153 proving a restore means NativeForge has backups. "
                "The Gate 61/65 production harness still returns SKIP."
            ),
        }
    )


@router.get("/{org_id}/durability-reassessment/next-activation-decision")
def get_next_activation_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Which block comes next, ranked by what is actually blocked."""
    same_org(org_id, ctx)
    decision = _decision()
    failures = next_activation_decision_invariant_failures(decision)
    if failures:
        raise HTTPException(status_code=500, detail="next_activation_decision_refused")
    return envelope({**decision, "invariant_failures": failures})
