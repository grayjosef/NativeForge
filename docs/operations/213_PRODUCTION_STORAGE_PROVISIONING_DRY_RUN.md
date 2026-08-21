# Production Storage Provisioning Dry-Run (Gate 17 / Block 40)

## Recommended backend

Managed Postgres (encrypted at rest) + S3-compatible object store with SSE + short-TTL signed URLs + malware scanning.

## Environment variables needed (names only)

* `DATABASE_URL` (production Postgres — not local sqlite)
* `OBJECT_STORAGE_ENDPOINT`
* `OBJECT_STORAGE_BUCKET`
* `OBJECT_STORAGE_ACCESS_KEY_ID` / `OBJECT_STORAGE_SECRET_ACCESS_KEY` (outside git)
* `OBJECT_STORAGE_SSE_MODE`
* `SIGNED_URL_TTL_SECONDS`
* `MALWARE_SCAN_WEBHOOK_URL` (or vendor adapter)

## Checklist

1. Owner approval packet signed (`206`)
2. Provision managed Postgres (non-prod first)
3. Create isolated bucket + SSE + prefix-per-org
4. Wire signed URL minting behind RBAC/tenant checks
5. Enable malware scan before accepting customer blobs
6. Validate backup/restore drill
7. Validate retention/delete + audit events
8. Feature-flag production adapter OFF until validated

## Validation commands (dry-run)

```bash
bash scripts/campaign_block40_smoke_verify.sh
# Do not claim production_storage_validated until real resources tested
```

## No-go rules

* No production storage claim without owner approval
* No customer persistence claim without auth live + storage validated
* No secrets in repo
* Local/dev sqlite remains demo-only
