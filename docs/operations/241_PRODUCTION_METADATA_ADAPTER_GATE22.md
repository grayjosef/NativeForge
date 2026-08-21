# Production Metadata Adapter — Gate 22 / Block 49

> Doc number `241` (requested `232` was already Gate 20 Block 45 spec).

## Implemented

- Production metadata adapter interface (`managed_postgres_metadata`)
- Evidence metadata model (evidence_id, org, package, hashes, lifecycle, audit refs)
- Local/dev metadata write/read with org scoping
- Production write path blocked without owner approval + config + flag
- Audit events for blocked production attempts and cross-org denials

## Blocked / false claims

- production metadata live: **false**
- production storage validated: **false**
- customer persistence: **false**

## Owner requirements

1. Repo-safe storage approval token (`artifacts/owner_storage_approval_token.json`)
2. `NF_PRODUCTION_METADATA_DATABASE_URL` out-of-band (never commit)
3. Keep `production_storage_enabled=false` until validation passes
