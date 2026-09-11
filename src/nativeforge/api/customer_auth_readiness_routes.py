"""Gate 146D: the second-person invite checklist, behind an authenticated org.

```text
GET /v1/nf/demo/orgs/{org}/auth-readiness/second-person   stage and counts
GET /v1/nf/demo/orgs/{org}/auth-readiness/blockers        what is outstanding
GET /v1/nf/demo/orgs/{org}/auth-readiness/next-action     the one next step
```

## These routes read. They do not invite, accept, or activate

There is no POST here. Issuing an invite and accepting one are the two scripts
Gate 136 built, run by an operator at a terminal, and putting either behind a
route would put the one irreversible step of this path one request away from
anybody holding a session. `customer_auth_live` has no branch anywhere that a
request can reach.

## What a request may read

`nf_identities` is **counted, never selected**. The row holds a real address and
the provider subject; a route that returned either would hand out the two values
this entire path exists to keep out of logs, artifacts and terminals. The
checklist payload is scanned for both shapes before it is returned, and the
route refuses rather than emits if one appears.

## Demo organization only

The real organization is refused by name by the underlying service, before any
count is read. An unauthenticated caller gets 401, and a forged header cannot
choose the organization: the org comes from the session context.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.customer_auth_second_person_event_checklist_service import (
    GOOGLE_TEST_USER_ENROLMENT,
    REFUSED_SHORTCUTS,
    STAGE_OWNERS,
    STAGES,
    build_second_person_checklist,
    checklist_invariant_failures,
)
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["customer-auth-readiness-demo"])


def _checklist(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    """Read the evidence and build the checklist. Nothing is written."""
    connection = db.connection()
    evidence = build_invite_binding_evidence(connection=connection)
    # Counted, never selected. See the module docstring.
    evidence["identity_rows"] = connection.execute(
        sa.text("SELECT count(*) FROM nf_identities")
    ).scalar()

    checklist = build_second_person_checklist(
        evidence=evidence, organization_id=str(org_id)
    )
    checklist["invariant_failures"] = checklist_invariant_failures(checklist)

    # A payload that leaked is not returned. The scan already ran inside the
    # service; this refuses on its result rather than trusting it silently.
    if checklist.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="checklist_payload_refused")

    return checklist


@router.get("/{org_id}/auth-readiness/second-person")
def get_second_person_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Where the second-person invite path has got to, and what is left."""
    same_org(org_id, ctx)
    checklist = _checklist(db, org_id)
    return envelope(
        {
            "readiness_passed": checklist["readiness_passed"],
            "customer_auth_live": checklist["customer_auth_live"],
            "invite_binding_passed": checklist["invite_binding_passed"],
            "stage": checklist["stage"],
            "stages": checklist["stages"],
            "stage_order": checklist["stage_order"],
            "counts": checklist["counts"],
            "second_identity_required": checklist["second_identity_required"],
            "second_identity_must_be_distinct_from_owner": checklist[
                "second_identity_must_be_distinct_from_owner"
            ],
            "google_test_user_enrolment": checklist["google_test_user_enrolment"],
            "invariant_failures": checklist["invariant_failures"],
            # Named on the response so a reader cannot mistake a readiness pass
            # for the event having happened.
            "readiness_is_not_the_event": (
                "readiness_passed says the path is correct and runnable. "
                "customer_auth_live says somebody walked it. They are "
                "different questions and both are reported."
            ),
        }
    )


@router.get("/{org_id}/auth-readiness/blockers")
def get_auth_readiness_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Everything outstanding, and every shortcut that will not work."""
    same_org(org_id, ctx)
    checklist = _checklist(db, org_id)
    return envelope(
        {
            "blockers": checklist["blockers"],
            "stage": checklist["stage"],
            "stages": checklist["stages"],
            "refused_shortcuts": list(REFUSED_SHORTCUTS),
            "google_test_user_enrolment": GOOGLE_TEST_USER_ENROLMENT,
            "customer_auth_live": checklist["customer_auth_live"],
            "controlled_customer_pilot": False,
            "production_rollout": False,
        }
    )


@router.get("/{org_id}/auth-readiness/next-action")
def get_next_human_action(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The one next step, not the three that are all still outstanding."""
    same_org(org_id, ctx)
    checklist = _checklist(db, org_id)
    return envelope(
        {
            "next_human_action": checklist["next_human_action"],
            "stage": checklist["stage"],
            "remaining_stages": [
                {"stage": name, **STAGE_OWNERS[name]}
                for name in STAGES
                if not checklist["stages"].get(name)
            ],
            "google_test_user_enrolment": GOOGLE_TEST_USER_ENROLMENT,
            "runbook": "docs/operations/765_GATE146_NEXT_HUMAN_ACTION.md",
            # No route can do any of it, and saying so here is cheaper than a
            # reader discovering it by looking for the POST.
            "no_route_performs_these_steps": True,
        }
    )
