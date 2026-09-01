"""Demo vs real separation (NF-001), proved through a session (Gate 133F).

## What changed, and why these two routes first

These were the last two routes on the `isolation_deps` chain — the one that
resolves `org_type` from the `NF_DEMO_ORG_IDS` allowlist rather than from the
`organizations` row. Gate 132 found that chain classifying the demo
organization as `real` because the allowlist was empty, which made
`/v1/isolation/demo-only` refuse the demo organization and
`/v1/isolation/real-only` admit it. Exactly backwards, and it had been that way
since the allowlist was introduced.

They are converted first because they are the only dev-header module that is not
part of the demo product. Nothing calls them: no frontend code, no script, no
e2e spec. Their entire purpose is proving the separation, and proving it through
an authenticated session is a better proof than proving it through a header
anybody can set.

```text
before   X-NF-Org-Id -> isolation_deps -> settings allowlist -> org_type
after    nf_session  -> membership row -> organizations.org_type -> org_type
```

## The header no longer works here

A request with `X-NF-Org-Id` and no session gets 401. That is the point: the
header selects an organization and authenticates nobody, and these routes now
require somebody. `isolation_deps` still exists and now has **zero route
consumers**, which is what makes deleting it a real option rather than a
rewrite.

## The other fourteen modules

207 routes still read the header, and the demo shell is among them: it sends a
header and no cookie, so converting them today would return 401 to the demo.
The plan, module by module with an order and a risk for each, is in
`docs/operations/703_GATE133_DEV_HEADER_KILL_PLAN.md`. This is one conversion,
not a half-conversion of many.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from nativeforge.api.deps_customer_auth import (
    require_customer_demo_org,
    require_customer_real_org,
)
from nativeforge.api.org_context import OrgContext

router = APIRouter(prefix="/v1/isolation", tags=["demo-isolation"])


@router.get("/demo-only")
def demo_only_ping(
    org: Annotated[OrgContext, Depends(require_customer_demo_org)],
) -> dict[str, str]:
    return {"scope": "demo", "org_id": str(org.org_id)}


@router.get("/real-only")
def real_only_ping(
    org: Annotated[OrgContext, Depends(require_customer_real_org)],
) -> dict[str, str]:
    return {"scope": "real", "org_id": str(org.org_id)}
