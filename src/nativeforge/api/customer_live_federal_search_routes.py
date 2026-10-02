"""Customer live federal search — public Grants.gov, collectors still off."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.customer_live_federal_search_service import (
    search_live_federal_opportunities,
)

demo_live_federal_search_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["customer-live-federal-search-demo"],
)
real_live_federal_search_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["customer-live-federal-search-real"],
)


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    """Delegates to the single tenant guard (Gate 58). 403 preserved.

    The payload here is public federal data, identical for every tenant, so
    nothing leaks across organizations and it is tempting to skip this. The
    reason it is here anyway: these routes still carry `{org_id}` in the path,
    and a route that accepts a tenant id it never checks teaches callers - and
    the next handler written by copying this one - that the path tenant is
    decorative. Gate 58 fails on exactly that shape, and the fix belongs in
    the route rather than in the detector.
    """
    guard_same_org_403(path_org, ctx)


def _search() -> dict:
    return search_live_federal_opportunities()


@demo_live_federal_search_router.get("/{org_id}/discovery/live-federal-search")
def demo_live_federal_search(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict:
    _same_org(org_id, ctx)
    return _search()


@real_live_federal_search_router.get("/{org_id}/discovery/live-federal-search")
def real_live_federal_search(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
) -> dict:
    _same_org(org_id, ctx)
    return _search()
