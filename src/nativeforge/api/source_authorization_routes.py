"""Source authorization routes (Gate 162J).

Four reads. No writes of any kind.

## There is no mutation endpoint, deliberately

No route here approves a source, records a terms decision, records a human
review, flips an allowlist entry, or executes anything. Not even behind a flag.

A generic `POST /authorization` that took a decision would be the shortest path
from "a caller can call an API" to "a source is approved", and the whole point
of Gate 162 is that approval requires a signed record with attribution and
evidence. A human's decision belongs to an explicit human workflow that records
who decided and what they read — not to an endpoint that accepts JSON.

So the mutation surface is empty, and `mutation_endpoints: 0` is asserted by
the gate's own tests rather than left as a claim in this docstring.

## No route accepts a fact

There is no parameter for `terms_status`, no `allow_live_fetch`, no
`activation_status`, and no request body anywhere. Every value these routes
report is resolved from records by
`resolve_source_authorization_facts`, whose signature has no parameter capable
of asserting anything.

A caller can name a `source_id` — which selects which source to ask about, and
cannot change the answer.

## What a green authorization on this surface does not mean

`authorization_status: approved` means eleven facts are signed records. It does
not mean a request is permitted: that additionally needs a live fetch to be
opted in, and Gate 162 opts nothing in. Both fields are returned side by side
so a reader cannot take the first for the second.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.source_activation_packet_service import (
    activation_packet_invariant_failures,
    build_activation_packet,
)
from nativeforge.services.source_allowlist_projection_service import (
    allowlist_projection_invariant_failures,
    project_allowlist,
)
from nativeforge.services.source_authorization_fact_model_service import (
    describe_fact_model,
)
from nativeforge.services.source_live_authorization_service import (
    authorization_invariant_failures,
    authorize_source_for_live_access,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-authorization-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-17T12:00:00Z"

#: Said in every response. A reader who takes only this field still gets the
#: right answer about what an authorization is not.
AUTHORIZATION_IS_NOT_A_REQUEST = (
    "authorization_status=approved means eleven facts are signed records. It "
    "does not mean a request is permitted: that additionally needs a live "
    "fetch to be opted in, and Gate 162 opts nothing in."
)


@router.get("/{org_id}/source-authorization/fact-model")
def get_source_authorization_fact_model(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What facts authorization requires. Reads no source and no database."""
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms the
    # organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    model = describe_fact_model()
    return envelope(
        {
            "fact_model": model,
            "required_fact_count": model["fact_count"],
            "decision_facts": model["decision_facts"],
            "missing_is_not_denied": model["missing_is_not_denied"],
            "authorization_is_not_a_request": AUTHORIZATION_IS_NOT_A_REQUEST,
            "mutation_endpoints": 0,
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/source-authorization/sources/{source_id}")
def get_source_authorization_status(
    org_id: uuid.UUID,
    source_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """One source's standing, resolved from records.

    `source_id` selects WHICH source to ask about. It cannot change the answer:
    every fact comes from a record, and there is no parameter through which a
    caller could supply one.
    """
    same_org(org_id, ctx)

    decision = authorize_source_for_live_access(
        connection=db.connection(),
        organization_id=str(org_id),
        source_id=source_id,
        now=DEFAULT_EVALUATION_INSTANT,
    )

    return envelope(
        {
            "source_id": decision["source_id"],
            "authorization_status": decision["authorization_status"],
            "authorized": decision["authorized"],
            # Reported beside `authorized`, never instead of it.
            "live_fetch_opted_in": bool(decision["guard_allowed"]),
            "live_transport_permitted": False,
            "terms_decision": decision["terms_decision"],
            "human_review_decision": decision["human_review_decision"],
            "activation_decision": decision["activation_decision"],
            "attribution_decision": decision["attribution_decision"],
            "runtime_decision": decision["runtime_decision"],
            "robots_decision": decision["robots_decision"],
            "refusal_reasons": decision["refusal_reasons"],
            "blocking_decisions": decision["blocking_decisions"],
            "blocking_prerequisites": decision["blocking_prerequisites"],
            "denial_is_a_decision": decision["denial_is_a_decision"],
            "evidence_refs": decision["evidence_refs"],
            "is_synthetic_fixture": bool(
                (decision.get("resolution") or {}).get("is_synthetic_fixture")
            ),
            "invariant_failures": authorization_invariant_failures(decision),
            "authorization_is_not_a_request": AUTHORIZATION_IS_NOT_A_REQUEST,
            "caller_can_supply_a_fact": False,
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/source-authorization/sources/{source_id}/requirements")
def get_source_authorization_requirements(
    org_id: uuid.UUID,
    source_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The per-requirement checklist, and who can clear each one."""
    same_org(org_id, ctx)

    packet = build_activation_packet(
        connection=db.connection(),
        organization_id=str(org_id),
        source_id=source_id,
        now=DEFAULT_EVALUATION_INSTANT,
    )

    return envelope(
        {
            "source_id": packet["source_id"],
            "requirements": packet["requirements"],
            "requirement_count": packet["requirement_count"],
            "requirements_satisfied": packet["requirements_satisfied"],
            "unresolved_blockers": packet["unresolved_blockers"],
            "unresolved_human_decisions": packet["unresolved_human_decisions"],
            "activatable": packet["activatable"],
            "grants_nothing": packet["grants_nothing"],
            "gate_163_sequence": packet["gate_163_sequence"],
            "invariant_failures": activation_packet_invariant_failures(packet),
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/source-authorization/allowlist")
def get_source_allowlist_projection(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: int = 200,
) -> dict[str, Any]:
    """The allowlist, computed from facts. Nothing stores it."""
    same_org(org_id, ctx)

    projection = project_allowlist(
        connection=db.connection(),
        organization_id=str(org_id),
        now=DEFAULT_EVALUATION_INSTANT,
        limit=max(1, min(int(limit), 500)),
    )

    # The full per-source list is large and the summary is what an operator
    # reads. The per-source route above answers the detail question.
    summary = {
        key: value
        for key, value in projection.items()
        if key != "projections"
    }

    return envelope(
        {
            "allowlist": summary,
            "evaluated": projection["evaluated"],
            "allowlisted": projection["allowlisted"],
            # THE number. A real source here would be a breach of this gate.
            "real_sources_allowlisted": projection["real_sources_allowlisted"],
            "synthetic_fixtures_allowlisted": projection[
                "synthetic_fixtures_allowlisted"
            ],
            "approved_source_count": projection["approved_source_count"],
            "allowlisted_source_ids": projection["allowlisted_source_ids"],
            "by_authorization_state": projection["by_authorization_state"],
            "is_a_projection": projection["is_a_projection"],
            "invariant_failures": allowlist_projection_invariant_failures(
                projection
            ),
            "live_transport_permitted": False,
            "source_monitoring_live": False,
        }
    )
