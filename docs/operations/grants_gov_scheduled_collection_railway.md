# Grants.gov bounded collection — Railway cron (Block 5B)

One authorized source only: `nf-seed-2026-api-grants-gov-search2`.

## Mechanism

Railway **Cron** invokes the production image with the bounded corpus operator
script. Each run:

- Sets demo-org RLS via the script (production `DATABASE_URL` + demo GUCs)
- Re-evaluates warrant + live-fetch opt-in (fail closed; no new authorization rows)
- Performs one bounded Search2 POST when permitted
- Persists raw bytes, canonical graph, and `nf_grant_sparks`

## Recommended cadence

**Every 12 hours** (`0 */12 * * *` UTC) — bounded `rows=200`, no fleet activation.

## Human configuration (Railway)

1. Open the NativeForge **backend** service on Railway.
2. Add a **Cron** schedule (or a one-off Job using the same image/env as production).
3. Command (no secrets on the CLI):

```bash
python scripts/run_gate163_grants_gov_bounded_corpus_collection.py --apply --pass 1 --rows 200
```

4. Ensure the cron service uses the **same** `DATABASE_URL` and runtime env as the
   live API container.
5. Do **not** run overlapping schedules; one invocation at a time.

## Overlap guard

If Railway cannot guarantee exclusivity, wrap:

```bash
flock -n /tmp/nf-grants-gov-collect.lock \
  python scripts/run_gate163_grants_gov_bounded_corpus_collection.py --apply --pass 1 --rows 200
```

(`flock` requires the util in the image; omit if using Railway’s single-slot cron only.)

## Status until configured

Until a cron job exists in Railway, recurring collection is **not deployed** — only
manual operator runs via SSH/console are available.
