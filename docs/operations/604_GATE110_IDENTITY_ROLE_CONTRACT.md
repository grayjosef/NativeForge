# 604 — Gate 110B: identity role contract

`src/nativeforge/services/org_identity_role_contract_service.py`

## organization_id is the RLS authority

Not a preference, not an interpretation. Every row-level security policy in the
migrations reads:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
```

21 columns, 21 policies, `Uuid(as_uuid=True)`, foreign key to `organizations.id`.

```text
organization_id    rls_authority         may scope RLS, may persist
current_org_id     rls_session_context   may scope RLS, is not a column
org_id             service_alias         see below
customer_org_id    customer_surface_alias  label, requires a binding
tenant_id          product label         label, requires a binding
```

## org_id is an alias only where its value is a UUID

Routes declare `org_id: uuid.UUID` and hand it to repositories as
`organization_id=`. In that lane the two names are the same value.

But `org_id` appears in ~70 services, most of them in-memory contracts where it
is a free-form string. **The name is overloaded**, so the contract resolves it
from the value:

```text
org_id, uuid value        alias_of_authority   may persist
org_id, free-form value   label                may not persist, requires binding
```

A mutation letting a free-form `org_id` claim alias authority is caught.

## customer_org_id is a surface name, not a foreign key

Zero DB columns, zero repositories, zero routes, no service authorizes on it.
`persistence_allowed` is False and `requires_binding` is True. Invariants fail a
record that assigns it `db_foreign_key`, permits it to persist, or drops its
binding requirement.

## tenant_id is not RLS authority

Zero columns, zero repositories, zero routes, and no service authorizes on it.

The rule is enforced on the **name**, not the value. A UUID-shaped `tenant_id`
still gets `rls_allowed: False` and `persistence_allowed: False`, and a test pins
exactly that case. The name governs the authority question; the shape only
governs whether an already-eligible name may act.

Invariants fail any `tenant_id` row permitted RLS or persistence, or assigned the
authority role.

## Demo identifiers are refused on the value

`is_demo_identity_value` checks for `nf-demo-` and `demo-` prefixes, so the
refusal applies whatever name carries them — including `organization_id`. A demo
value gets no RLS and no persistence, and a test proves the authority name does
not rescue it.

This is the specific accident the contract exists to make impossible: a demo
tenant id reaching an RLS path.

## Shape is read, not assumed

```text
uuid            8-4-4-4-12 hex
gate51_derived  tn_ followed by 16 hex
free_form       anything else
absent          empty
```

Only `uuid` can satisfy the `::uuid` cast. A free-form value cannot match an RLS
policy even by accident — the database raises rather than matching, which is a
useful property: it refuses the mistake this contract is about.

## Everything derived affirmatively

`rls_allowed` requires an authority name, a UUID shape, and a non-demo value.
`persistence_allowed` requires a persisting name, a UUID shape, and a non-demo
value. Nothing is subtracted from a permissive default, and no caller-supplied
flag appears in either decision.
