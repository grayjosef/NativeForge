# 605 — Gate 110C: binding store decision

`src/nativeforge/services/tenant_customer_org_binding_store_decision_service.py`

## The recommendation

```text
recommended_store         new_identity_binding_table
recommended_primary_key   organization_id (UUID, FK organizations.id)
rls_enforced_by           organization_id
binding_lookup_key        organization_id
label columns             tenant_id, customer_org_id
requires_migration        true
migration_safe_now        FALSE
migration_applied         FALSE
```

## Why organization_id, and not a choice between reasonable options

A binding is a record the database must be able to protect, and the only thing
this database protects is `organization_id`. A binding keyed on `tenant_id` would
sit in a table whose entire purpose is preventing cross-tenant access, in a row
row-level security cannot see.

An invariant fails any decision whose primary key or lookup key is a label, and
a mutation setting the key to `tenant_id` is caught.

## Why a table rather than a column on organizations

A binding has a lifecycle — pending, verified, revoked — plus a verifier, a
verification time, and history that must survive revocation. Gate 109 built those
statuses for a reason.

A `tenant_label` column on `organizations` would hold the current value and
nothing else: no verifier, no revocation history, no way to distinguish "never
bound" from "bound then withdrawn". The first question after an incident is *when
did this binding change and who approved it*, and a column cannot answer it.

## migration_safe_now is false, and the reasons are specific

The recommendation is clear. Acting on it is not safe, and not out of general
caution:

```text
no_customer_auth_so_nobody_can_verify_a_binding
no_customer_persistence_to_write_a_binding_into
no_verified_binding_exists_to_store
```

**A recommendation can be right while the migration remains wrong to apply.**
Those are separate questions and the service answers both separately —
`recommended_store` is decided from where isolation is enforced,
`migration_safe_now` from whether every precondition holds.

The permission path is reachable and tested: supply all four preconditions and
`migration_safe_now` becomes true. A refusal that can never lift is a constant,
not a decision.

## No migration was applied

```text
migration_applied  false
schema_changed     false
rows_written       0
```

Constants on every result, held by invariants. This gate wrote no migration file,
altered no table, and inserted no row.

## What is deliberately not recommended

```text
tenant_id as RLS authority   no column, no route, no repository, cannot cast
demo ids as persistence keys nf-demo- values must never reach a real table
organization_profile_id      String(128), no FK, on a table with no RLS and a
                             check constraint forbidding production use
```

The third is worth naming. `nf_evidence_intake_records` scopes by
`organization_profile_id` and has no RLS policy at all — but its
`persistence_scope` check constraint permits only `local_dev_only`,
`not_claimed` and `production_forbidden`. It is an honest dev-only table, and
precisely the wrong thing to model a customer-facing binding store on.

## Next required actions, in order

1. **Stand up customer auth** — a verified binding needs a verifier, and nobody
   can be one until a person can authenticate.
2. **Resolve `org_id` overloading in persistence paths** — a `uuid.UUID` in
   routes, a free-form string in most of the ~70 services using the name. A
   migration assuming the first is wrong wherever the second holds.
3. **Create the identity binding table under RLS** — `organization_id` anchor,
   label columns, the Gate 109 statuses, a verifier and a `verified_at`.
4. **Backfill nothing** — there is no verified binding to migrate. The table
   starts empty and fills as bindings are verified.
