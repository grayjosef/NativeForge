# OIDC organization_id resolution

Every row-level security policy reads `organization_id = current_setting('app.current_org_id', true)::uuid`. A claim reaches that boundary only by resolving to an organization_id and only alongside verified membership.

## What exists

```text
oidc_organization_id_resolution_contract_available   True
membership_verification_contract_available           True
dev_header_containment_contract_available            True
organization_id_required_for_rls                     True
```

## What is not live

Read from the login promotion gate and the containment service rather than asserted here.

```text
customer_auth_live                                   False
login_live                                           False
dev_header_production_safe                           False
binding_store_built                                  False
verified_operational_binding                         False
customer_persistence_live                            False
operational_awarded_tracking_ready                   False
operational_digest_ready                             False
beta_onboarding_ready                                False
```

Login promotion gates still missing:

```text
provider_configured
secret_present
issuer_jwks_validated
callback_session_validated
invite_binding_passed
org_binding_passed
role_mapping_passed
```

## What the contract refuses

```text
organization_profile_id_is_rls_authority             False
migration_applied                                    False
schema_changed                                       False
identity_provider_contacted                          False
current_org_id_set                                   False
live_fetch_performed                                 False
```

An organization_profile_id is carried as evidence and never promoted. The dev header is contained by deployment posture today and is still not production-safe, because an unauthenticated header can set the org context regardless of how well the deployment happens to be closed.
