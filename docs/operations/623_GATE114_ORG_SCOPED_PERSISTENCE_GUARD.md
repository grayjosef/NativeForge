# 623 — Gate 114C: the org-scoped persistence guard

`src/nativeforge/services/org_scoped_customer_persistence_guard_service.py`

One place that answers "may this write happen?" for every customer-data lane.

## The rule

```text
a customer-data write requires an organization_id, and organization_id means a
UUID that survives ::uuid, because that is what every RLS policy in the schema
compares against
```

Gate 114A verified that claim rather than assuming it: nineteen tables have
row-level security installed across fifteen migrations, and **every policy
installs the identical predicate**, with no variation anywhere in the
repository:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

Everything else — labels, bindings, demo fixtures, auth status, capability
schema — is a reason to say no, never a substitute for that.

## What is not a write authority

```text
tenant_id                a label. Gate 109.
customer_org_id          a label. Gate 109.
organization_profile_id  a String(128) on a real table, in the wrong identity
                         space. Gate 112.
```

Each gets its own named refusal rather than falling through a generic "no
anchor" branch. A caller who supplied an identifier and is told only that no
anchor was present learns nothing about which identity space theirs was in.

`organization_profile_id` is refused *whether or not* a valid anchor accompanies
it. A request carrying one is ambiguous about which organization it means, and
the guard says so instead of quietly preferring the anchor.

## Nine operations, and which need a binding

```text
write_tenant_profile            binding required
write_beta_onboarding_record    binding required
write_identity_binding          binding required
write_awarded_grant
write_award_requirement
write_digest_record
write_document_library_item
write_source_watchlist
unknown                         refused
```

The three requiring a binding are the ones that touch a tenant or customer
label, and a binding is what says which organization that label corresponds to.

## Derived affirmatively

```python
write_allowed = (
    op in CUSTOMER_DATA_OPERATIONS
    and rls_compatible
    and customer_auth_live
    and auth_status in OPERATIONAL_AUTH_STATUSES
    and (binding_present or not binding_required)
    and not demo_write
    and not blocked_reasons
)
```

`read_allowed` requires the same scoping — an unscoped read is a cross-tenant
read — plus the same named-operation requirement.

## One defect found during construction

The first version granted `read_allowed` for an unrecognised operation. Because
no capability mapped to `unknown`, none of the schema checks applied to it, and
it fell through to a permitted read.

That is the unknown-becomes-permissive failure, and it is the direction that
costs something. `read_allowed` now requires the operation be one the guard can
name, and an invariant catches a forged result that reads under an unnamed
operation.

## Demo writes

A demo fixture write is permitted as a demo fixture and never as anything else.
It is reported through `demo_only`, it can never set `write_allowed`, and a
result claiming both fails its invariants. A demo row that could become an
operational row by being relabelled would make the distinction decorative.

## Its relationship to the Gate 113 guard

`identity_persistence_safety_guard_service` decides whether an *identity name*
may carry a write. This service decides whether a *persistence operation* may
proceed. They overlap deliberately and must never disagree, so this one imports
`OPERATIONAL_BINDING_STATUSES`, `DEMO_LABEL` and the demo-value test rather than
restating them.
