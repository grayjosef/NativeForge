# Evidence Upload Storage Proposal (Gate 08 / Block 21)

> **Status:** Proposal only. Migrations are **not** applied.  
> `upload_persistence_claimed=false`, `production_storage_claimed=false`.

## Why this exists

NativeForge can map required attachments and show evidence gaps, but durable binary upload storage is not validated. Gate 08 implements an evidence intake **contract** and a **fixture/planned** adapter only.

## Recommended storage model (not implemented)

| Concern | Proposal |
| --- | --- |
| DB tables | `nf_evidence_intake_records` (+ optional blob metadata) keyed by org, workspace, checklist/binder/forms map refs |
| Blob store | Object storage (S3-compatible) or approved local path for `local_dev_only` |
| Migration need | **Yes** — Alembic migration required after owner approval |
| File size limits | Start 25 MB/file; reject larger until scanned |
| Allowed MIME types | `application/pdf`, `image/png`, `image/jpeg`, `text/plain` initially |
| Malware scanning | Future requirement before any customer upload path |
| Retention/deletion | Org-scoped retention policy + soft-delete + audit |
| Customer data boundary | Per-org isolation; no cross-org access |
| Audit log | Append-only audit on provide/review/approve/reject/delete |
| Production blockers | No migration approval; no scanner; no auth upload UI; no tenant IAM |

## Storage modes in Gate 08

- `fixture_backed` — placeholder references only
- `external_storage_required` — durable binary path not available
- `validated_persistent` — **not claimed** in this gate

## Do not claim

- Uploaded files are stored
- Customer uploads are durable
- Attachment persistence is complete
- Production customer data storage is ready
- Auth/user upload flow is live

## Gate 09 update — approval gate

See `docs/operations/166_PERSISTENT_STORAGE_APPROVAL_GATE.md`.

- `OWNER_APPROVED_MIGRATIONS=false` (this run)
- Adapter dry-run validates fixture/local_dev/planned_external only
- `validated_persistent` remains unavailable
- No Alembic migrations applied
