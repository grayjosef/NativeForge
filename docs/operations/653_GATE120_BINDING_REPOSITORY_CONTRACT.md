# 653 — Gate 120B: the identity binding repository

`src/nativeforge/services/tenant_customer_org_binding_repository_service.py`

## What was missing, precisely

Gate 113 built the table and the contract that decides what may enter it:

```python
record = build_binding_record(...)
record["write_allowed"]   # True, and nothing consumes it
```

A permission nothing acts on is a permission nobody has tested. Eighteen
repositories existed and none addressed `nf_tenant_customer_org_bindings`; seven
services talked about a "store" and not one opened a session.

This module is what consumes the permission.

## Six operations

```text
prepare_insert                 decide, without a database
insert_binding                 act on that decision
get_active_binding             the one live binding for a label pair
list_bindings_for_organization every binding, revoked ones included
revoke_binding                 an UPDATE
mark_conflict                  an UPDATE that clears the verifier
```

`prepare_insert` is separate on purpose. The verdict is worth being able to ask
for without a connection in hand, and `insert_binding` calls it rather than
duplicating the rules — so the two can never disagree about what is storable.

## organization_id is the anchor and labels never select

```text
organization_id          UUID, the RLS predicate's left-hand side
tenant_id                text label. Narrows a read. Never selects one.
customer_org_id          text label. Same.
organization_profile_id  refused outright
```

Every read takes `organization_id` and applies labels as *additional* filters.
A read anchored on a label is a read the RLS policy cannot scope, which is a
cross-tenant read waiting for a second tenant to exist. A test passes only a
`tenant_id` and asserts nothing comes back.

`organization_profile_id` is **refused rather than ignored**. It is a real value
from a real column in the wrong identity space, and silently dropping it would
let a caller believe it had been honoured. Gates 110–113 exist for this one
substitution.

## A verified binding names its verifier, and the database agrees

```text
verified_binding   verified_by_identity_id AND verified_at, both required
demo_fixture       both forbidden
pending_review     neither required
conflict           authorizes nothing at all
```

Migration 0029 enforces the first two with CHECK constraints. This module
enforces them *before* the statement, so a caller gets a named refusal rather
than an `IntegrityError` — and the constraints stay in place as the thing that
catches the case this module gets wrong. A test inserts around the module and
asserts `ck_nf_binding_verified_needs_verifier` fires.

## The Core table restates the migration's constraints

Gate 119C shipped a Core `sa.Table` carrying every column and none of the
constraints. A test that built a table from it exercised a **weaker schema than
production** and passed on writes the real database refuses.

That mistake is not repeated. `BINDINGS` declares all four CHECK constraints,
and two tests compare the Core definition against migration 0029 — one by column
name, one by constraint name — so the two cannot drift.

## Revocation is an UPDATE

Nothing here deletes. `revoke_binding` sets `revoked_at` and
`revoked_by_identity_id` and leaves the row; `rows_deleted` is a constant `0`,
an invariant refuses any result claiming otherwise, and a test greps the module
for `sa.delete`.

The partial unique index is what makes that safe:

```sql
uq_nf_binding_active UNIQUE (organization_id, tenant_id, customer_org_id)
                     WHERE revoked_at IS NULL
```

A revoked row stops being the live binding for its label pair without
disappearing from the audit trail, so a replacement can be created.

`list_bindings_for_organization` returns revoked rows by default. A listing that
hid them would make a revocation indistinguishable from a row that never
existed.

## A conflict is not a revocation

`mark_conflict` leaves the row live and clears `verified_by_identity_id` and
`verified_at`. Whatever the binding asserted is exactly what is in dispute, so
it stops asserting it while somebody looks.

`human_review_required` goes true and stays true.

## Contract mode is the default

Without a connection nothing is written, nothing is read, and the result says so
with a named reason. Importing this module touches no database.

The `database` path is exercised against isolated in-memory databases in tests
and fixtures. It is reached by nothing in the running application.

```text
rows written in the application database   0
production verified bindings created       0
```
