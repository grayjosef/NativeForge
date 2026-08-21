# Gate 25 — Storage Approval Ingest (Block 55)

## Mode A (default)
- No owner approval token → production metadata validation blocked
- Prompt text is **not** approval
- `production_storage_claimed=false`
- `customer_persistence_claimed=false`

## Approval scopes
none | invalid | expired | revoked | dry_run_only | metadata_only | object_storage | controlled_pilot | production_rollout

## Required owner action
Place repo-safe approval JSON (no secrets) + metadata config out-of-band; re-run validators.
