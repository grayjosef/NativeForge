"""FastAPI dependencies (database session; auth added in later tickets).

## Every session starts by saying it has no tenant

Silence is not the same as "no tenant". A pooled connection that served a
tenant-scoped request earlier leaves `app.current_org_id` holding the empty
string once its transaction-local value reverts, and every RLS policy in this
schema casts that anchor with `::uuid`. `''::uuid` raises rather than
returning NULL, so the next request's first tenant-scoped read aborts the
whole transaction instead of simply returning no rows.

That is what stopped the controlled-live OAuth callback: the first read of
`nf_org_memberships` errored, and everything after it in that transaction -
including the demo-organization bootstrap - was refused with "current
transaction is aborted".

So the nil-UUID sentinel is written explicitly at the start. The policies then
evaluate and deny, which is what the routes below already expect. A request
that resolves a real organization overwrites it through `apply_org_rls_gucs`.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from nativeforge.db.rls import clear_org_rls_gucs
from nativeforge.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        clear_org_rls_gucs(db)
        yield db
    finally:
        db.close()
