# Customer auth boundary

The contracts that decide who may act, who may verify a binding, and what may set `app.current_org_id`. None of them logs anybody in.

## What exists

```text
customer_auth_contract_available             True
verified_binder_authorization_available      True
rls_context_claim_guard_available            True
binding_store_recommended                    new_identity_binding_table
```

## What is not live

Read from the existing login promotion gate rather than asserted here.

```text
customer_auth_live                           False
login_live                                   False
controlled_pilot_auth_ready                  False
binding_store_built                          False
verified_operational_binding                 False
customer_persistence_live                    False
operational_awarded_tracking_ready           False
operational_digest_ready                     False
beta_onboarding_ready                        False
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

## What the boundary refuses

```text
cloudflare_access_is_app_auth                False
demo_auth_is_production_auth                 False
tenant_id_can_set_current_org_id             False
customer_org_id_can_set_current_org_id       False
identity_provider_contacted                  False
sessions_created                             False
```

Cloudflare Access controls who reaches the host; it establishes no organization and sets no RLS context. A demo principal may verify a demo binding and nothing else. An authenticated person is not a verified member of any organization until somebody establishes one.
