# 735 — Gate 140: pursuit suppression, and the audit row behind it

## What suppression is for

A tenant sees an opportunity in the new-opportunity digest, starts a pursuit,
and does not want to keep being told about it. Gate 104 built the contract that
decides whether that is allowed. It had nowhere to store the answer.

```text
tenant_pursuit_suppression_service     built in Gate 104
persistence                            ABSENT
```

## The table

Migration `0040` adds `nf_tenant_pursuit_suppressions`:

```text
id                              uuid, primary key
organization_id                 uuid, FK organizations.id ON DELETE CASCADE
is_demo                         boolean
tenant_id_label                 text, a LABEL
opportunity_id                  text
suppression_status              text, CHECK
suppression_reason              text, CHECK
pursuit_record_id               text
audit_event_id                  text
source_history_preserved        boolean
provenance_preserved            boolean
visible_in_pipeline             boolean
visible_in_awarded_workspace    boolean
fact_status                     text
blocked_reasons                 text
created_by_identity_id          uuid
suppressed_at / created_at      timestamp
lifted_at                       timestamp, null while suppressed
```

with a partial unique index on `(organization_id, opportunity_id) WHERE
lifted_at IS NULL`, the campaign's RLS policy, and one CHECK worth quoting:

```sql
CHECK (source_history_preserved AND provenance_preserved)
```

A suppression that lost either is not storable. That is a database-level
statement, not a service-level convention, because the whole risk of this
feature is that something quietly stops appearing.

## Suppression needs audit evidence, and the route supplies it

Gate 104's contract refuses a suppression that cannot name an audit event:

```text
contract:no_audit_event_recorded
```

That refusal is correct — suppressing an opportunity is an act somebody took,
and a suppression nobody can trace is a way for things to disappear without
anybody having decided. So the route **appends a real `nf_audit_events` row
first** and passes its id:

```text
1. append_org_audit_event(action=grant_pursuit_updated, payload={
     event: suppressed_from_new_opportunity_digest,
     opportunity_id, suppression_reason, pursuit_record_id,
     source_record_deleted: false, provenance_preserved: true })
2. db.flush()
3. record_suppression(..., audit_event_id=str(audit.id), ...)
4. if the suppression was refused: db.rollback()
5. db.commit()
```

Step 4 matters. An audit event for something that did not happen is worse than
no audit event, so a refused suppression takes its audit row with it. A test
reads the row back out of `nf_audit_events` by the id the route reported, and a
second test drives the refusal directly with `audit_event_id=None` so the
contract's own branch stays reachable.

The route does not mint an id and hope. `audit_event_id` in the stored row is
the primary key of a row that exists.

## Suppression hides a view; it deletes nothing

```text
before      items_visible 9   items_suppressed 0   items_total 9
suppress    rows_written 1    rows_deleted 0       opportunity_deleted false
after       items_visible 8   items_suppressed 1   items_total 9
```

The total is unchanged. The item **moved** — out of `items` and into
`suppressed_items` — so a tenant can always see that something was withheld and
go look at it. An invariant on the digest asserts `visible + suppressed ==
total`, which is what stops a future change hiding an item by dropping it.

Lifting is an UPDATE that sets `lifted_at`:

```text
lift        rows_written 1    rows_deleted 0
after       the item is back in items
```

## What a caller may not do

```text
suppress with no audit event         refused by the contract, named
suppress with a reason that needs a
  pursuit and no pursuit_record_id   refused, named
set is_demo or fact_status           400, named
suppress in another organization     403/404
store a row that lost the provenance a CHECK refuses it
suppress the same opportunity twice  the partial unique index refuses it
```

Suppressions are read back org-anchored. A second organization reading the same
repository sees zero rows, and a test asserts both sides of that rather than
only the empty one.

## One shape note

`_row_to_record` hands Gate 104's service a `tenant_id` field carrying the
**organization id**. That is deliberate and documented in the module:

> `tenant_id` is the ORGANIZATION id, because that is what this repository
> anchored on when it wrote the row. The Gate 104 service uses the field as an
> opaque key, so handing it the anchor keeps the two consistent without either
> pretending a tenant label is authority.

The alternative — passing the tenant label — would have made a label decide
which rows a digest suppresses, which is exactly the substitution Gates 110–113
exist to prevent.

## What this does not do

```text
delete an opportunity              no
remove a source record             no
drop provenance                    a CHECK refuses it
hide it from the pursuit pipeline   no — visible_in_pipeline stays true
hide it from awarded workspace      not applicable; the flag says so
send anybody a notification         no. There is no email service.
```
