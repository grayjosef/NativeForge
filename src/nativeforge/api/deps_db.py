"""Database session dependency.

## What used to be here

Three functions that turned `X-NF-Org-Id` into an organization context, and
through it into `app.current_org_id` — the session variable every row-level
security policy reads:

```text
get_org_context_with_db   an unauthenticated header -> OrgContext + RLS GUCs
require_demo_org_db       the same, refusing a real organization
require_real_org_db       the same, refusing a demo one
```

Gate 111A named this as the one code path in the tree that set the RLS context
from an unauthenticated request. Gates 122 through 134 replaced it: 207 routes
across 14 modules now derive their organization from a membership row through
`api/customer_org_context_dependency.py`, and Gate 135 deleted these.

## Why deleting was the right end and not the fix

They were correct for what they were — a development convenience, honestly
named, gated by `NF_DEV_ORG_HEADERS`. What made them dangerous was that they
were *load-bearing*: 207 routes could not answer without them, so the header
could not be turned off, so `dev_header_disabled_for_production` could not pass,
so customer auth could not go live. Removing the setting would have broken the
application without making anything safer.

Converting first and deleting second is the order that works. A deletion here in
Gate 122 would have returned 401 to every caller.

## `get_db_session` stays

Twelve route modules import it. It hands out a database session and reads no
header; it was never part of the chain that made the header authority.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from nativeforge.db.rls import clear_org_rls_gucs
from nativeforge.db.session import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """A session that starts with no authorized tenant, stated explicitly.

    Saying "no tenant" out loud matters because the alternative is not silence.
    A pooled connection that served a tenant-scoped request earlier leaves
    `app.current_org_id` as the empty string once its transaction-local value
    reverts, and the RLS policies cast that anchor to `uuid` - so the next
    request's first tenant-scoped read raises `invalid input syntax for type
    uuid: ""` and aborts the transaction rather than simply returning nothing.

    `clear_org_rls_gucs` writes the nil-UUID sentinel instead. The policies
    evaluate and deny, which is the behaviour every route below already
    expects. A route that has a real organization overwrites it through
    `apply_org_rls_gucs` in the ordinary way.
    """
    db = SessionLocal()
    try:
        clear_org_rls_gucs(db)
        yield db
    finally:
        db.close()
