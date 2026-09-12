"""Gate 149D: the pilot activation package, behind an authenticated org.

```text
GET  /v1/nf/demo/orgs/{org}/pilot-activation/checklist
GET  /v1/nf/demo/orgs/{org}/pilot-activation/blockers
GET  /v1/nf/demo/orgs/{org}/pilot-activation/unsafe-bundled-requests
POST /v1/nf/demo/orgs/{org}/pilot-activation/dry-run-decision
```

## No route here can activate a pilot, because nothing can

There is no table recording a pilot approval, no environment flag, and no code
path that sets the value true. The POST is a dry run over a boundary that takes
no connection and returns `mutation_performed: False` and `rows_written: 0` on
every branch.

`may_activate` is false on every branch too, and the response says why: the
prerequisites question is answered by `prerequisites_would_permit`, and
`may_activate` answers whether anything could act on it. Nothing can.

## The prerequisites are measured, not accepted

A caller cannot hand this route `customer_auth_live: true` and get a different
answer. The identity and consent facts are measured — `customer_auth_live` from
the invite evidence the way Gate 146 derives it, the rest from the services that
own them. What the body may supply is a hypothetical activation approval and a
support/rollback owner, both evaluated and neither recorded.

## Bundling is refused and reported

A body asking for email, source monitoring, object storage or production
alongside the pilot is refused as a bundle with each target named, even when
every prerequisite is satisfied. Being allowed to start a pilot is not being
allowed to start anything else.
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
from nativeforge.services.controlled_customer_pilot_activation_boundary_service import (  # noqa: E501
    ACTIVATION_APPROVAL_FIELDS,
    UNSAFE_BUNDLE_KEYS,
    activation_decision_invariant_failures,
    build_pilot_activation_decision,
)
from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    PREREQUISITE_OWNERS,
    PREREQUISITES,
    SEPARATELY_GATED,
    build_pilot_activation_checklist,
    checklist_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["controlled-customer-pilot-demo"])


def _measured(db: Session) -> dict[str, Any]:
    """Every prerequisite this request can honestly measure.

    Nothing here is taken from a request body. A caller supplying
    `customer_auth_live` would be supplying the answer.
    """
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
        second_person = auth_live
    except Exception:  # noqa: BLE001
        auth_live = False
        second_person = False

    beta = build_controlled_beta_decision(**FULL_BATTERY)
    scopes = beta.get("by_scope") or {}

    return {
        # Measured.
        "customer_auth_live": auth_live,
        "second_person_event_complete": second_person,
        # Gate 147 measured this false behind five refusals, and Gate 148
        # measured the consent lanes false. Nothing a request can do moves any
        # of them, so they are not recomputed per-request.
        "verified_operational_binding": False,
        "consent_boundary_documented": False,
        "customer_beta_scope_approved": False,
        "real_customer_organization_exists": False,
        # Gate 148 built and proved it.
        "customer_data_write_guard_ready": True,
        # This gate's docs state them; an owner still has to accept them.
        "pilot_scope_limitations_documented": False,
        "internal_demo_beta": (scopes.get("internal_demo_beta") or {}).get("decision"),
        "controlled_customer_beta": (
            scopes.get("controlled_customer_beta") or {}
        ).get("decision"),
    }


def _checklist(db: Session) -> dict[str, Any]:
    checklist = build_pilot_activation_checklist(**_measured(db))
    checklist["invariant_failures"] = checklist_invariant_failures(checklist)
    if checklist.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="pilot_checklist_refused")
    return checklist


@router.get("/{org_id}/pilot-activation/checklist")
def get_pilot_activation_checklist(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Every prerequisite, and what a pilot would and would not unlock."""
    same_org(org_id, ctx)
    checklist = _checklist(db)
    return envelope(
        {
            "controlled_customer_pilot": checklist["controlled_customer_pilot"],
            "activation_package_ready": checklist["activation_package_ready"],
            "package_ready_is_not_an_activated_pilot": checklist[
                "package_ready_is_not_an_activated_pilot"
            ],
            "internal_demo_beta": checklist["internal_demo_beta"],
            "controlled_customer_beta": checklist["controlled_customer_beta"],
            "production_rollout": checklist["production_rollout"],
            "prerequisites": list(PREREQUISITES),
            "prerequisites_satisfied": checklist["prerequisites_satisfied"],
            "prerequisites_missing": checklist["prerequisites_missing"],
            "prerequisites_satisfied_count": checklist[
                "prerequisites_satisfied_count"
            ],
            "prerequisite_count": checklist["prerequisite_count"],
            "would_unlock": checklist["would_unlock"],
            "would_not_unlock": checklist["would_not_unlock"],
            "separately_gated": checklist["separately_gated"],
            "activation_mechanism_exists": False,
            "invariant_failures": checklist["invariant_failures"],
        }
    )


@router.get("/{org_id}/pilot-activation/blockers")
def get_pilot_activation_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Each missing prerequisite, with what satisfies it and who owns it."""
    same_org(org_id, ctx)
    checklist = _checklist(db)
    return envelope(
        {
            "prerequisites_missing": checklist["prerequisites_missing"],
            "prerequisite_owners": {
                name: PREREQUISITE_OWNERS[name]
                for name in checklist["prerequisites_missing"]
            },
            "next_human_action": checklist["next_human_action"],
            "controlled_customer_pilot": False,
            "production_rollout": checklist["production_rollout"],
            "not_approved": checklist["not_approved"],
        }
    )


@router.get("/{org_id}/pilot-activation/unsafe-bundled-requests")
def get_unsafe_bundled_requests(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What a pilot activation may never carry with it, and why each is separate."""
    same_org(org_id, ctx)
    return envelope(
        {
            "unsafe_bundle_keys": list(UNSAFE_BUNDLE_KEYS),
            "separately_gated": {
                name: dict(entry) for name, entry in SEPARATELY_GATED.items()
            },
            "refused_even_when_prerequisites_are_met": True,
            "why": (
                "a pilot that quietly turned on email because a pilot "
                "obviously needs notifications would undo four gates in one "
                "sentence. Being allowed to start a pilot is not being allowed "
                "to start anything else."
            ),
            "activation_approval_fields_required": list(ACTIVATION_APPROVAL_FIELDS),
        }
    )


@router.post("/{org_id}/pilot-activation/dry-run-decision")
def post_dry_run_activation_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Would a pilot be permitted? Decides; activates and records nothing."""
    same_org(org_id, ctx)
    supplied = body or {}

    # Only the hypotheticals come from the body. Every prerequisite is measured.
    bundled = {
        key: True for key in UNSAFE_BUNDLE_KEYS if supplied.get(key)
    }

    decision = build_pilot_activation_decision(
        activation_approval=supplied.get("activation_approval"),
        support_and_rollback_owner=supplied.get("support_and_rollback_owner"),
        **_measured(db),
        **bundled,
    )
    decision["invariant_failures"] = activation_decision_invariant_failures(decision)

    if decision["leaked_shapes"] or decision["invariant_failures"]:
        raise HTTPException(status_code=500, detail="pilot_decision_refused")

    return envelope(
        {
            **decision,
            "pilot_activated": False,
            "approval_recorded": False,
            "note": (
                "a dry run decides; it does not activate. No table records a "
                "pilot approval, no flag exists, and no branch of this route "
                "writes anything."
            ),
        }
    )
