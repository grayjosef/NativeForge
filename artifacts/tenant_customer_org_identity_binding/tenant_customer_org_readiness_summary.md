# Tenant / customer org identity binding

`tenant_id` and `customer_org_id` are not automatically equivalent. A relationship between them exists only where somebody recorded one and it was checked.

## What exists

```text
identity_binding_contract_available          True
demo_fixture_bindings_available              True
awarded_demo_contract_ready                  True
digest_demo_preview_ready                    True
beta_demo_ready                              True
```

## What does not

A demo binding is not production verification. Nothing below can be reached without a verified, non-demo binding.

```text
verified_operational_binding_available       False
operational_awarded_tracking_ready           False
operational_digest_ready                     False
beta_onboarding_ready                        False
customer_auth_live                           False
customer_persistence_live                    False
live_source_collection_available             False
source_monitoring_live                       False
source_coverage_claimed                      False
```

## Nothing is derived

```text
identities_assumed_equivalent                False
tenant_id_derived_from_customer_org_id       False
customer_org_id_derived_from_tenant_id       False
bindings_persisted                           False
live_fetch_performed                         False
```

Matching strings do not create a binding, and neither do matching names. One value used for both identity spaces is a conflict, not a shortcut.
