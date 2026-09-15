"""Gate 154E: operational health, the verifier registry and the runbook.

```text
GET /v1/nf/demo/orgs/{org}/operational-health/summary
GET /v1/nf/demo/orgs/{org}/operational-health/verifier-registry
GET /v1/nf/demo/orgs/{org}/operational-health/runbook
GET /v1/nf/demo/orgs/{org}/operational-health/next-safe-action
```

GET only. Nothing here restarts a service, runs a verifier, applies a migration
or rebuilds the frontend. The runbook prints what an operator should run; the
operator runs it.

## No shell, and therefore an honest gap

A request cannot ask `systemctl` whether a unit is up, cannot ask `git` when
HEAD was committed, and must not - a route that shells out is a remote command
execution surface, and this one is reachable with a session cookie.

So the facts that need a shell are **not supplied here**, and the health model
reports them `unknown`. Unknown is not a pass: these responses carry
`operational_health_ready: false` with `required_unknown` naming exactly which
facts a request could not obtain, and pointing at the verifier that can.

That is the same split Gate 153 used for its readiness route, for the same
reason: declaring a fact true because a request could not check it is the defect
this campaign keeps finding.

## What a request CAN measure

```text
migration drift    the repository's highest revision, and the one the database
                   reports. Both are reads this request already has.
lane values        supplied by the caller from each lane's own service
```

## It cannot claim production monitoring

`production_monitoring_active` is a constant false in the model, and the
registry's own invariants fail if the two backup lanes are ever merged. There is
no argument these routes accept that would change either.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.operational_health_model_service import (
    REQUIRED_COMPONENTS,
    build_operational_health_model,
    health_model_invariant_failures,
)
from nativeforge.services.readiness_verifier_registry_service import (
    build_verifier_registry,
    registry_invariant_failures,
    verifier_expectations,
)
from nativeforge.services.runbook_health_service import (
    build_runbook_health,
    runbook_health_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["operational-health-demo"])

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Facts a request cannot obtain without a shell, and therefore does not claim.
NOT_MEASURABLE_IN_A_REQUEST: tuple[str, ...] = (
    "backend_service",
    "preview_service",
    "tunnel_service",
    "frontend_stamp",
    "backend_code_freshness",
)

MEASURABLE_IN_A_REQUEST: tuple[str, ...] = tuple(
    name for name in REQUIRED_COMPONENTS if name not in NOT_MEASURABLE_IN_A_REQUEST
)


def _repo_migration_head() -> str | None:
    """Highest revision on disk. A directory listing, not a shell call."""
    versions = REPO_ROOT / "alembic" / "versions"
    if not versions.is_dir():
        return None
    revisions = sorted(
        path.name[:4] for path in versions.glob("[0-9][0-9][0-9][0-9]_*.py")
    )
    return revisions[-1] if revisions else None


def _database_migration_current(db: Session) -> str | None:
    try:
        return (
            db.connection()
            .execute(sa.text("SELECT version_num FROM alembic_version"))
            .scalar()
        )
    except Exception:  # noqa: BLE001
        # A health read that 500s because a table is missing is worse than one
        # that reports it could not tell.
        return None


def _model(db: Session, lanes: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_operational_health_model(
        # Deliberately not supplied: a request has no shell. These stay
        # `unknown`, and `unknown` is not a pass.
        backend_service_state=None,
        preview_service_state=None,
        tunnel_service_state=None,
        repo_head_sha=None,
        head_committed_at=None,
        source_dirty=None,
        backend_process_started_at=None,
        frontend_stamp_sha=None,
        # Measured here.
        repo_migration_head=_repo_migration_head(),
        database_migration_current=_database_migration_current(db),
        lanes=lanes,
        verifier_expectations=verifier_expectations(),
    )


def _measurement_split() -> dict[str, Any]:
    return {
        "measured_in_this_request": sorted(MEASURABLE_IN_A_REQUEST),
        "requires_the_verifier": sorted(NOT_MEASURABLE_IN_A_REQUEST),
        "why": (
            "a request cannot run systemctl or git, and a route that shelled "
            "out would be a command execution surface reachable with a session "
            "cookie. The unmeasured facts are reported unknown rather than "
            "assumed, which is why this response is not ready."
        ),
        "the_verifier": "scripts/verify_nativeforge_operational_health_runbook.sh",
        "shell_executed": False,
        "external_call_made": False,
    }


@router.get("/{org_id}/operational-health/summary")
def get_operational_health_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Component-by-component health, with the unmeasured parts named."""
    same_org(org_id, ctx)
    model = _model(db)
    failures = health_model_invariant_failures(model)
    if failures:
        raise HTTPException(status_code=500, detail="health_model_refused")

    return envelope(
        {
            **model,
            **_measurement_split(),
            "invariant_failures": failures,
        }
    )


@router.get("/{org_id}/operational-health/verifier-registry")
def get_verifier_registry(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Every recurring verifier, its lane, and what it is expected to return."""
    same_org(org_id, ctx)
    registry = build_verifier_registry()
    failures = registry_invariant_failures(registry)
    if failures:
        raise HTTPException(status_code=500, detail="verifier_registry_refused")

    return envelope({**registry, "invariant_failures": failures})


@router.get("/{org_id}/operational-health/runbook")
def get_runbook_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What an operator should do next, and what needs a person instead."""
    same_org(org_id, ctx)
    model = _model(db)
    runbook = build_runbook_health(health_model=model)
    failures = runbook_health_invariant_failures(runbook)
    if failures:
        raise HTTPException(status_code=500, detail="runbook_health_refused")

    return envelope(
        {
            **runbook,
            **_measurement_split(),
            "health_overall_status": model["overall_status"],
            "operational_health_ready": model["operational_health_ready"],
            "invariant_failures": failures,
        }
    )


@router.get("/{org_id}/operational-health/next-safe-action")
def get_next_safe_action(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """One action. Derived from the model, never a constant."""
    same_org(org_id, ctx)
    model = _model(db)
    runbook = build_runbook_health(health_model=model)
    failures = runbook_health_invariant_failures(runbook)
    if failures:
        raise HTTPException(status_code=500, detail="runbook_health_refused")

    return envelope(
        {
            "next_safe_action": runbook["next_safe_action"],
            "operator_runnable_count": runbook["operator_runnable_count"],
            "human_approval_required_count": runbook["human_approval_required_count"],
            "awaiting_human_decision": runbook["awaiting_human_decision"],
            "derived_not_declared": runbook["derived_not_declared"],
            **_measurement_split(),
            "production_monitoring_active": False,
        }
    )
