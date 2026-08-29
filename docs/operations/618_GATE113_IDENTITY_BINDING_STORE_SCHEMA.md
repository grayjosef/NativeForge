# 618 — Gate 113B/C: the identity binding store

Migration `0029_nf_tenant_customer_org_bindings`, and the contract service that
decides what may enter the table it creates.

## The table

```text
nf_tenant_customer_org_bindings
  id                       uuid PK
  organization_id          uuid NOT NULL FK organizations.id CASCADE   <- anchor
  tenant_id                text NOT NULL    label, no foreign key
  customer_org_id          text NOT NULL    label, no foreign key
  binding_status           varchar(32) NOT NULL  CHECK, Gate 109 vocabulary
  binding_source           varchar(32) NOT NULL  CHECK, Gate 109 vocabulary
  binding_confidence       varchar(16) NOT NULL
  verified_by_identity_id  uuid NULL FK nf_identities.id SET NULL
  verified_at              timestamptz NULL
  revoked_at               timestamptz NULL
  revoked_by_identity_id   uuid NULL FK nf_identities.id SET NULL
  is_demo                  boolean NOT NULL DEFAULT false
  human_review_required    boolean NOT NULL DEFAULT true
  blocked_reasons          json NOT NULL DEFAULT '[]'
  created_at, updated_at   timestamptz NOT NULL DEFAULT now()
```

Constraints:

```text
ck_nf_binding_status                    status in the Gate 109 vocabulary
ck_nf_binding_source                    source in the Gate 109 vocabulary
ck_nf_binding_verified_needs_verifier   verified => verified_at AND verifier
ck_nf_binding_demo_has_no_verifier      demo     => neither
uq_nf_binding_active                    UNIQUE (organization_id, tenant_id,
                                        customer_org_id) WHERE revoked_at IS NULL
```

RLS, matching migration 0027's shape exactly:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

PostgreSQL only. On SQLite the policy statements are skipped, as in 0002 and
0027 — the same no-op, not a different security model.

## Why the labels carry no foreign key

`tenant_id` and `customer_org_id` are `text` and reference nothing. This is the
single most deliberate decision in the schema.

A foreign key would make each of them an identity space: a thing with its own
table, its own uniqueness, and eventually its own claim to being what a row
belongs to. That is the conflation Gates 109 through 112 exist to prevent, and
it would arrive here not as a decision but as a convenience. They are labels.
The row belongs to `organization_id` and to nothing else.

A test asserts the absence directly, reading the migration source, so adding one
later is a failure rather than a diff nobody looked at.

## Why the vocabularies are written twice

A `CHECK` constraint cannot import Python. The statuses and sources are
therefore stated in the migration and again in
`tenant_customer_org_identity_binding_service`, and a test asserts the two sets
are equal. Bridged, not forked — the duplication is unavoidable, the drift is
not.

## The contract service

`tenant_customer_org_binding_store_service` decides whether a record may be
stored. It writes nothing; every function is pure.

```text
build_stored_binding_id            deterministic id from the anchor and labels
build_binding_record               the decision about one record
revoke_binding                     status -> revoked, history preserved
read_bindings_for_organization     a read that requires a uuid anchor
binding_store_invariant_failures   what must never be true of a record
```

Permission is derived affirmatively — every condition must hold, nothing is
subtracted from a permissive default, and no caller flag grants anything:

```python
storage_allowed = (
    anchor_shape == "uuid"
    and not anchor_is_demo
    and not organization_profile_id
    and status in STORABLE_BINDING_STATUSES
    and tenant_id and customer_org_id
    and not blocked_reasons
)
write_allowed = storage_allowed and not revoked
read_allowed  = anchor_shape == "uuid" and not blocked_reasons
```

### Storable and operational are different questions

Three statuses are storable that carry no authority whatsoever:

```text
demo_fixture   stored inside the demo scope, is_demo true, never a verifier
revoked        stored precisely so the withdrawal is on the record
pending_review stored so a person can look at it
```

A single `accepted` boolean would blur exactly the line that matters. The
demo fixture set (doc 619) reports both, and its invariants require that exactly
one of its nine cases is operational while three are storable.

## The near-miss case

`organization_profile_id` supplied as the anchor is refused with its own named
reason rather than falling through the generic "no anchor" branch:

```text
binding_without_an_organization_id_anchor
organization_profile_id_is_not_an_organization_id_anchor
```

Two reasons because they are two different facts, and the second is the one a
reader needs. A profile id is a real value from a real column on a real table.
It is simply not the column RLS enforces on, and a store that accepted it would
write rows no policy could ever see.

## What creating this table did not do

Gate 110 reported `migration_safe_now: False` for three reasons: no customer
auth to supply a verifier, no customer persistence to write into, and no
verified binding to store. None of those is a reason the table cannot exist, and
none of them is addressed by its existing.

The table is empty, no database has applied the migration, and
`operational_binding_storage_allowed` is still false. Doc 620 records how that
is now measured rather than asserted.
