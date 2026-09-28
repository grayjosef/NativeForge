"""Postgres RLS session variables (Layer 5). SQLite no-ops.

## Why "no tenant" is a UUID and not an empty string

Every policy in this schema reads the tenant anchor the same way:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
```

`current_setting(..., missing_ok => true)` returns NULL for a GUC that was
never set, and `NULL::uuid` is NULL, so the comparison is NULL, so the row is
not visible. That is the intended deny.

But once a custom GUC has been set on a connection and then reverted - which
is what `set_config(..., is_local => true)` does at the end of every
transaction - it does not go back to NULL. It reads back as the **empty
string**. And `''::uuid` does not return NULL; it raises:

```text
ERROR: invalid input syntax for type uuid: ""
```

which aborts the whole transaction, taking every later statement with it.

On controlled-live that is exactly what happened: a pooled connection that had
served one tenant-scoped request poisoned the next OAuth callback, so the
first read of `nf_org_memberships` errored and the demo-organization bootstrap
downstream of it never got the chance to run. The membership table was never
the problem; the empty string was.

So "no tenant" is stated explicitly, as a syntactically valid UUID that cannot
match anything:

```text
00000000-0000-0000-0000-000000000000
```

The policy then evaluates normally and denies, which is what it was always
meant to do. Nothing is widened: the sentinel is not an organization, no
`organizations` row has that id, and a write checked against it fails its
`WITH CHECK` exactly as an unset context should.

A policy-level repair - `NULLIF(current_setting(...), '')::uuid` - is the
better long-term fix and belongs in a migration with its own RLS regression
coverage. This is the application-side half, and it needs no migration.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from nativeforge.lib.demo_isolation import OrgType

ORG_ID_GUC = "app.current_org_id"
IS_DEMO_GUC = "app.current_org_is_demo"

#: No authorized tenant. A valid UUID so the policies can evaluate, and the nil
#: UUID specifically so it can never collide with a real organization.
#:
#: This must never appear as an `organizations.id`. It is the absence of a
#: tenant, spelled in a way PostgreSQL can cast.
NO_TENANT_ORG_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _postgres(session: Session) -> bool:
    return session.bind is not None and session.bind.dialect.name == "postgresql"


def _set(session: Session, org_id: str, is_demo: bool) -> None:
    session.execute(
        text(f"SELECT set_config('{ORG_ID_GUC}', :oid, true)"),
        {"oid": org_id},
    )
    session.execute(
        text(f"SELECT set_config('{IS_DEMO_GUC}', :d, true)"),
        {"d": "true" if is_demo else "false"},
    )


def apply_org_rls_gucs(session: Session, org_id: uuid.UUID, org_type: OrgType) -> None:
    """Set per-transaction GUCs expected by nf_* RLS policies (PostgreSQL only)."""
    if not _postgres(session):
        return
    _set(session, str(org_id), org_type == "demo")


def clear_org_rls_gucs(session: Session) -> None:
    """State that this transaction has no authorized tenant.

    Not the same as leaving the GUC alone. On a pooled connection "alone" can
    mean the empty string left behind by an earlier request, which makes the
    policy's `::uuid` cast raise and aborts the transaction before anything
    has a chance to establish real context.

    `is_demo` goes to `false` alongside it, so the pair is never half-set:
    a sentinel organization that claimed to be a demo would be a stranger
    combination than either field on its own.
    """
    if not _postgres(session):
        return
    _set(session, str(NO_TENANT_ORG_ID), False)
