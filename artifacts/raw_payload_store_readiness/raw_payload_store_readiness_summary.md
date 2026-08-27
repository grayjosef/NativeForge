# Raw payload store readiness

A local, deterministic store for raw source responses, and the gates a payload passes before anything parsed from it may be called collected. **Nothing here fetches.**

```text
local_raw_payload_store_available: true
production_raw_payload_store_available: false
live_fetch_performed: false
collectors_active: false
source_monitoring_active: false
live_source_coverage: false
```

## Why the store exists

Gates 87 to 89 measured the corpus and found **185 records, 18 with independent transport evidence**. The other 167 were parsed and persisted while the bytes were discarded, so their origin can only be believed. Keeping the response, hashing it, and refusing to promote a parse without it is the whole of the fix.

## Promotion matrix

| Scenario | Promotes | Status | Human review |
| --- | --- | --- | --- |
| clean fixture payload | yes | `evidence_ready` | no |
| secret scan pending | no | `quarantine` | no |
| secret findings | no | `quarantine` | no |
| redaction pending | no | `quarantine` | no |
| redaction failed | no | `quarantine` | no |
| terms review required | no | `quarantine` | no |
| human review only | no | `quarantine` | yes |
| terms unknown | no | `quarantine` | no |
| parse failed | no | `quarantine` | no |
| parser unavailable | no | `quarantine` | no |
| live payload, no preflight | no | `quarantine` | no |

1 of 11 scenarios promote. Every row is produced by calling the real promotion gate, so this table cannot drift from the code that enforces it.

## What the local store is not

It writes to `artifacts/raw_payload_store` at storage mode `local_dev_only`, refuses to write unless explicitly enabled, refuses customer data unless separately allowed, and never calls `now()` - the caller supplies `retrieved_at`, because a timestamp the store invents describes the store rather than the fetch.

The store root is gitignored. These readiness artifacts live in a different directory precisely so that one is committable and the other is not.

## Secret scanning

11 finding kinds. Gate 89 found a committed JWT inside a recorded API response; a store that keeps bodies without scanning them is a machine for repeating that. Findings report kind, location and an 8-hex fingerprint - never the value.

