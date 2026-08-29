# Binding store readiness (Gate 113)

The table `nf_tenant_customer_org_bindings` exists as of migration 0029. **It is empty, no database has applied it, and no customer binding can be stored today.**

## What is still refused, and why

```text
no_customer_auth_so_nobody_can_verify_a_binding
no_customer_persistence_to_write_a_binding_into
no_database_has_applied_the_binding_store_migration
no_verified_binding_exists_to_store
```

None of these is addressed by a `CREATE TABLE`. A table under RLS holding zero rows is a container, not a capability.

## The distinction this gate turns on

```text
migration_defined                  true   the revision file is in this repository
migration_applied                  false   a database has actually run it
store_writable                     false   there is somewhere to write
operational_binding_storage_ready  false   a verified binding may be stored
```

These were a single hard-coded `migration_applied: False` before this gate. That constant was accidentally correct while no migration and no database existed, and would have become a lie the moment revision 0029 landed.

## The authority

```text
organization_id = current_setting('app.current_org_id', true)::uuid AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

`tenant_id` and `customer_org_id` are `text` columns carrying no foreign key. They are labels. A label with a foreign key becomes an identity space by accident.

## Claims this gate does not make

```text
customer_bindings_stored                     false
customer_auth_live                           false
customer_persistence_live                    false
tenant_id_is_rls_authority                   false
customer_org_id_is_rls_authority             false
organization_profile_id_is_rls_authority     false
beta_onboarding_ready                        false
production_rollout_ready                     false
```

