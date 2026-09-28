"""Customer live federal search — public Grants.gov, collectors still off."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.org_context import OrgContext
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


def _search() -> dict:
    return search_live_federal_opportunities()


@demo_live_federal_search_router.get("/{org_id}/discovery/live-federal-search")
def demo_live_federal_search(
    org_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict:
    _ = org_id, ctx
    return _search()


@real_live_federal_search_router.get("/{org_id}/discovery/live-federal-search")
def real_live_federal_search(
    org_id: str,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
) -> dict:
    _ = org_id, ctx
    return _search()
