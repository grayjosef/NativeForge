# Storage Feature-Flag Scaffolding (Gate 18 / Block 42)

## Purpose

Keep local/dev storage validated while preventing accidental production or
customer-persistence claims.

## Feature flag fields

`storage_feature_flag_id`, `environment_scope`, `local_dev_storage_enabled`,
`production_storage_enabled`, `production_storage_config_present`,
`owner_approval_present`, metadata/object/malware/signed-url/backup/retention
config flags, `audit_linkage_present`, RBAC/tenant dependencies,
`customer_data_policy_passed`, `production_storage_claimed=false`,
`customer_data_persistence_claimed=false`.

## Adapter boundary

- Local/dev adapter: available (validated persistent path).
- Production / object / signed-URL / malware / metadata stubs: **blocked** unless
  feature flag + approval + config pass; never mutate production/customer data.

## Readiness validator

Production storage and customer persistence remain false unless all storage,
auth, policy, tenant, audit, and pen-test gates pass. Controlled pilot storage
stays false while pen-test is required and not passed.

## Smoke

```bash
bash scripts/campaign_block42_smoke_verify.sh
```
