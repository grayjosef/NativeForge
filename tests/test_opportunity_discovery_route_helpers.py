"""Route helper boundaries (no FastAPI app required)."""

import uuid

import pytest
from fastapi import HTTPException

from nativeforge.api.opportunity_discovery_route_helpers import same_org
from nativeforge.api.org_context import OrgContext


def test_same_org_mismatch_raises() -> None:
    oid = uuid.uuid4()
    ctx = OrgContext(org_id=uuid.uuid4(), org_type="demo")
    with pytest.raises(HTTPException) as ei:
        same_org(oid, ctx)
    assert ei.value.status_code == 403
