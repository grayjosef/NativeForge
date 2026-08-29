# Org identity canonicalization

Every row-level security policy reads `organization_id = current_setting('app.current_org_id', true)::uuid`. That is the authority, and it is read from the migrations rather than assumed.

## Which identity carries authority

```text
organization_id_is_rls_authority             True
tenant_id_is_rls_authority                   False
demo_tenant_ids_rls_allowed                  False
names_allowing_rls                           ['current_org_id', 'organization_id']
names_allowing_persistence                   ['org_id', 'organization_id']
names_requiring_binding                      ['customer_org_id', 'tenant_id']
```

## Where a binding should live

```text
binding_store_decision_available             True
recommended_store                            new_identity_binding_table
recommended_primary_key                      organization_id
rls_enforced_by                              organization_id
requires_migration                           True
migration_safe_now                           False
migration_applied                            False
```

A recommendation can be right while the migration remains wrong to apply. No schema was changed and no row was written.

## What remains false

```text
customer_persistence_live                    False
customer_auth_live                           False
operational_awarded_tracking_ready           False
operational_digest_ready                     False
beta_onboarding_ready                        False
source_monitoring_live                       False
source_coverage_claimed                      False
live_fetch_performed                         False
```

## Next

1. **stand_up_customer_auth** — a verified binding needs a verifier, and nobody can be one until a person can authenticate. Gate 111 built the contracts that decide who may verify - the auth principal, the binder authorization and the RLS claim guard - but the login promotion gate still reports seven of ten gates missing, so no provider is attached
1. **map_oidc_claims_to_organization_id** — the OIDC identity mapper resolves a claim to organization_profile_id, a String(128) with no foreign key on a table with no RLS. Even a live login would not produce the UUID the policies enforce on
1. **resolve_org_id_overloading_in_persistence_paths** — org_id is a uuid.UUID in routes and a free-form string in most of the ~70 services using it; a migration assuming the first is wrong wherever the second holds
1. **create_the_identity_binding_table_under_rls** — organization_id primary anchor, tenant label column, the Gate 109 statuses, a verifier and a verified_at
1. **backfill_nothing** — there is no verified binding to migrate; the table starts empty and fills as bindings are verified
