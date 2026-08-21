# Object Storage + Signed URL Path — Gate 22 / Block 50

> Doc number `242` (requested `233` was already taken).

## Implemented

- S3-compatible object storage adapter interface
- Org-scoped object key builder:
  `environment/org/{org_id}/ws/{ws}/ev/{evidence}/{hash}/{filename}`
- Signed upload/download URL paths (blocked without approval/config)
- Malware scan hook (unsatisfied blocks persistence)
- SSE/encryption requirement model
- Archive/delete with audit; cross-org denied

## Blocked / false claims

- production object storage live: **false**
- production upload live: **false**
- signed URLs live in production: **false**
- customer uploads durable in production: **false**

## Owner requirements

1. Storage approval token
2. `NF_OBJECT_STORAGE_BUCKET` + `NF_OBJECT_STORAGE_ENDPOINT` out-of-band
3. Malware scan config before persistence claims
4. No fake upload UI — claims remain false until validated
