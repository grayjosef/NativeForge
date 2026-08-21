# Local/Dev Persistent Storage Applied (Gate 10 / Block 25)

> **Approved environment:** `local_dev_only`
> **Approval source:** `current_chat_mayhem_gate10`
> **Production / customer data mutation:** forbidden / not performed

## What was applied

| Item | Value |
|------|--------|
| Alembic revision | `0022` (`nf_evidence_intake_records`) |
| Down revision | `0021` |
| Local demo DB | `nativeforge.local.db` upgraded to `0022` |
| Adapter local DB | `artifacts/local_dev_evidence.sqlite3` (metadata) |
| Blob root | `artifacts/local_dev_evidence_store/` |

## Rollback posture

```bash
# Local/dev only — never against production:
DATABASE_URL="sqlite+pysqlite:///./nativeforge.local.db" alembic downgrade 0021
```

## Claims (honest)

| Claim | Status |
|-------|--------|
| Local/dev migration applied | true |
| validated_persistent works in local/dev | true |
| Upload persistence validated in local/dev | true |
| Production storage | **false** |
| Customer data persistence | **false** |
| Controlled customer pilot GO | **false (NO_GO)** |
| Pen-test passed | **false** |

## Validation performed

- Create / read / link / review / reject / archive
- Unreviewed/rejected cannot unlock package
- Cross-org read blocked
- MIME allowlist enforced
