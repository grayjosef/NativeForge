# 603 — Gate 110A: org identity canonicalization survey

Written before any implementation. Every claim was reproduced by reading the
schema, the migrations and the routes.

## The question, answered

**`organization_id` is the RLS authority, and it is proven rather than assumed.**

Every row-level security policy in the migrations reads literally:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
```

```text
organization_id columns in db/models.py     21
tables carrying it                          21 (NfActivationState ... NfTribalProfile)
column type                                 Uuid(as_uuid=True)
foreign key                                 organizations.id ON DELETE CASCADE
```

`organizations.id` is a UUID primary key, and the table's own docstring calls it
the tenant root with `org_type` distinguishing demo from real.

## app.current_org_id must be a UUID

The `::uuid` cast is in every policy. A value that cannot be cast raises rather
than matching, so a free-form identifier can never satisfy an RLS check even by
accident. That is a useful property: the database refuses the mistake this gate
is about.

## The five names, and what each actually is

```text
organization_id          UUID       21 db columns, 21 RLS policies   AUTHORITY
app.current_org_id       UUID       session GUC, cast in every policy  CONTEXT
org_id                   overloaded see below                          ALIAS
customer_org_id          string     6 services, 0 db columns           SURFACE
tenant_id                string     20 services, 0 db columns          LABEL
organization_profile_id  String(128) 1 db column, no FK, no RLS        SEPARATE
```

Gate 109 found four. There are five.

## org_id usually does mean organization_id — in the lane that persists

```python
# src/nativeforge/api/activation_routes.py
org_id: uuid.UUID,
_same_org(org_id, ctx)
... organization_id=ctx.org_id,
```

Routes declare `org_id` as `uuid.UUID` and pass it to repositories as
`organization_id=`. In the persistence lane the two names are the same value.

But `org_id` appears in ~70 services, most of which are in-memory contract and
demo services where it is a free-form string. **The name is overloaded**, and
that is why it may be treated as an alias only where it is verifiably the UUID —
never on the strength of the name alone.

## customer_org_id is a surface name, not a foreign key

```text
db columns                0
repositories              0
routes                    0
services                  6, all in-memory contract services
values observed           nf-demo-org-01 - free-form, not UUID
used for authorization    no
```

It names the customer organization on the Gate 90–91 awarded lane. Nothing
stores it and nothing authorizes on it.

## tenant_id is a product label

```text
db columns                0
repositories              0
routes                    0
services                  20
values observed           nf-demo-tenant-01 (free_form), tn_<hash> (Gate 51)
UUID-shaped values        none
used for authorization    no
```

No repository or route accepts a `tenant_id`. **Nothing writes customer data
keyed only by tenant_id, because nothing in those lanes writes at all.**

The one place `tenant_id` appears in an authorization-shaped context is Gate
109's own resolution guard, which decides whether a join may be *attempted*. It
enforces no storage and reaches no database.

## make_tenant_id is not safe as an operational identity

Gate 109 recorded that `org_tenant_seat_model_service.make_tenant_id` derives
`tn_<hash>` from an `organization_profile_id`. This survey adds the part that
settles it:

```python
# db/models.py:1874, on nf_evidence_intake_records
organization_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
```

`organization_profile_id` is a **String(128) with no foreign key to
`organizations`**, on a table with **no RLS policy at all**. It is not the RLS
authority and it is not derivable from it.

So a `tn_<hash>` tenant id is a hash of something that is itself not the
authority. It cannot be reversed to an `organization_id`, cannot be cast to
UUID, and must not be treated as an operational identity. Gate 109 classified it
as evidence; this survey shows why that classification was the right one.

## A table scoped outside the RLS boundary

Worth recording because a future gate could mistake it for a persistence
precedent:

```text
nf_evidence_intake_records
    scoped by       organization_profile_id (String(128), no FK)
    RLS policy      none
    persistence_scope CHECK IN (local_dev_only, not_claimed, production_forbidden)
```

It is not a hole — the check constraint forbids production use in the schema
itself, which is the honest way to build a dev-only table. But it is the one
persistence-facing place where org scoping is a string rather than the UUID, and
anything modelled on it would inherit that.

## Answers to the specific questions

```text
Is organization_id the RLS authority?              yes, proven by policy text
Is app.current_org_id always a UUID?               yes, ::uuid cast everywhere
Are any tenant_id values UUID-shaped?              no
Are any customer_org_id values UUID-shaped?        no
Are demo tenant IDs ever allowed into RLS paths?   no - they cannot cast to uuid
Does any service use tenant_id for authorization?  no
Does any service use customer_org_id for authz?    no
Does any service write customer data keyed only
  by tenant_id?                                    no - nothing writes at all
```

## What breaks either way

### If tenant_id became a DB column

```text
it would still not be the RLS authority - policies key on organization_id
21 tables and 21 policies would need a second scoping column and a second policy
two scoping keys on one row is how they drift apart
demo tenant ids would sit in the same column as real ones
```

The database would have two answers to "whose row is this", and the answers
would eventually disagree.

### If tenant_id remains product-only

```text
tenant-scoped surfaces cannot persist without resolving to an organization_id
every persist path needs the Gate 109 binding first
nothing breaks today - none of those surfaces persists
```

This is the cheaper failure, and it is the one already in force.

## The safest binding-store key

`organization_id`. It is the RLS authority, it is a UUID with a real foreign
key, and a binding anchored to it inherits the isolation that already works.

A binding keyed on `tenant_id` would be a record the database cannot protect.

## What this gate does not attempt

```text
renaming org_id to organization_id across ~70 services   large, and mostly
                                                         in-memory contracts
adding RLS to nf_evidence_intake_records                 its check constraint
                                                         already forbids
                                                         production use
applying any migration                                   nothing to store yet
```
