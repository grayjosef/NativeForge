# Storage Approval and Provisioning Execution Runbook (Gate 19 / Block 44)

> Note: Doc number `224` (requested 216 was already used).

## Distinctions

| State | Meaning |
|-------|---------|
| planned | Recommendation exists |
| approved | Repo-safe owner approval token present |
| configured | Feature flags + config present |
| provisioned | Real provisioning executed |
| validated | Readiness validator passed |
| customer persistence ready | Auth + policy + storage + tenant + audit |

Approval alone does **not** validate storage or enable customer persistence.

## Mode A

- Approval absent → production storage false
- Dry-run provisioning allowed
- Real provisioning blocked

```bash
bash scripts/campaign_block44_smoke_verify.sh
```

## Mode B

Owner supplies approval token fields (no secrets) out-of-band, then config.
Keep `production_storage_claimed=false` until validation passes.
