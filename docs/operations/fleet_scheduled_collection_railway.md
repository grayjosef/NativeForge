# Multi-source bounded collection — Railway cron

Each **activated** source with signed live-fetch authority may run on its own
cadence. Do not overlap runs for the same source.

## Grants.gov Search2 (live today)

```bash
python scripts/run_gate163_grants_gov_bounded_corpus_collection.py --apply --pass 1 --rows 200
```

Cadence: every **12 hours** (`0 */12 * * *` UTC).

Optional lock:

```bash
flock -n /tmp/nf-grants-gov-collect.lock \
  python scripts/run_gate163_grants_gov_bounded_corpus_collection.py --apply --pass 1 --rows 200
```

## Future sources

Use the same backend image and `DATABASE_URL`. One cron job per source id, with
staggered schedules (e.g. FR at `15 */12 * * *`, SC listing at daily off-peak)
once human authorization and activation rows exist.

Before adding a cron:

1. Confirm `nf_source_authorization_decisions` + activation for that `source_id`.
2. Run one manual `--apply` pass from Railway SSH and verify collector gates.
3. Add cron with `flock` or Railway single-slot semantics.

## Inventory

```bash
python scripts/inventory_source_fleet.py
```

Reports classification counts, priority shortlist, and measured `collectors_live`.
