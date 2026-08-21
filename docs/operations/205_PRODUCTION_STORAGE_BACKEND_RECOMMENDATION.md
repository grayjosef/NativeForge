# Production Storage Backend Recommendation (Gate 16 / Block 38)

## Recommended

* Metadata: managed Postgres (encrypted at rest)
* Objects: S3-compatible managed store with SSE
* Access: short-TTL signed URLs + RBAC/tenant checks
* Malware scanning: required before customer uploads
* Backup/restore + retention/delete + audit linkage: required

## Rejected

* Local SQLite for production
* Unencrypted local disk blobs
* Shared cross-org bucket without prefix isolation

## Claims

* production_storage_approved: **false** (needs owner packet)
* production_storage_validated: **false**
* customer_data_persistence_claimed: **false**
* local_dev_storage_validated: **true**
