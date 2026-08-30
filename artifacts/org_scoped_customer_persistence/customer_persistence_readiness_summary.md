# Org-scoped customer persistence readiness (Gate 114)

A customer persistence **contract** exists. **Customer persistence is not live.** No lane is operational, no customer row has been written, and nobody can authenticate to own one.

## The eight lanes

```text
schema available       3 of 8
under row-level security  3 of 8
complete write path    3 of 8
operational            0 of 8
```

Schema available is not operational. A table is a container; operating it needs an organization anchor, a policy, a repository, a contract and somebody accountable for the row.

## The authority

```text
organization_id = current_setting('app.current_org_id', true)::uuid AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

Never a write authority, at any layer:

```text
customer_org_id
organization_profile_id
tenant_id
```

## What blocks the spine

```text
every_lane_is_waiting_on_an_unmet_prerequisite
no_customer_auth_so_no_lane_can_be_operated
no_document_storage_for_award_evidence
no_email_delivery_for_digest_distribution
no_live_source_collection_for_digest_or_watchlist
no_session_signing_key_fit_to_sign_so_no_session_can_be_issued
```

**Next: customer_authentication.** every lane in the spine lists customer_auth as a prerequisite, so no amount of schema moves any of them. Auth is the only thing that unblocks more than one lane at once.

## The recommended order

```text
1. identity_binding_persistence     waiting on: customer_auth
2. tenant_profile_persistence       waiting on: customer_auth, identity_binding_persistence
3. awarded_grants_persistence       waiting on: customer_auth, tenant_profile_persistence
4. award_requirements_persistence   waiting on: customer_auth, awarded_grants_persistence, document_storage
5. document_library_persistence     waiting on: customer_auth, document_storage
6. tenant_digest_persistence        waiting on: customer_auth, tenant_profile_persistence, live_source_collection
7. source_watchlist_persistence     waiting on: customer_auth, live_source_collection
8. beta_onboarding_persistence      waiting on: customer_auth, identity_binding_persistence, tenant_profile_persistence
```

## What is true

```text
binding_store_schema_available                   true
customer_persistence_contract_available          true
organization_id_required_for_operational_writes  true
```

## Claims this gate does not make

```text
beta_onboarding_ready                            false
customer_auth_live                               false
customer_org_id_write_authority                  false
customer_persistence_live                        false
login_live                                       false
operational_awarded_tracking_ready               false
operational_digest_ready                         false
organization_profile_id_write_authority          false
tenant_id_write_authority                        false
```

No customer data was written, no real database row was inserted, no identity provider was called, no URL was fetched, no collector ran and no source was monitored.

