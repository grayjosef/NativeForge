# NativeForge Handoff — LA Block: Scale Federal Activation + Batch Hardening

**Status:** Closed locally. Push only on explicit operator instruction.

**Baseline:** `c21cd41` (M8) → LA block commit on `main`.

## LA-0 resolved count (pre/post staging)

| Metric | Pre | Post |
|--------|-----|------|
| Batch-eligible seeds (CSV) | 60 | 60 |
| Posture-filtered eligible (live URL check) | — | **50** |
| Active federal tier-1 in DB | **0** | **40** |
| Inactive federal tier-1 | 60 | 20 |

Note: 50 seeds activated across 3 batches (20+20+10); 40 unique source URLs in registry due to seed CSV URL collisions. fed-023 excluded (login). ~10 seeds blocked by posture (dead URL / access posture).

## Sprint deliverables

| Sprint | Deliverable | Status |
|--------|-------------|--------|
| LA-0 | DB active federal count script | `scripts/la0_federal_active_count.py` |
| LA-1 | Pydantic batch confirmation → 422 | `Tier1BatchConfirmationBody` + route mapping |
| LA-2 | M8 publish gate on batch orchestrator | `assert_batch_activation_publish_permitted` |
| LA-3 | Per-source rate limit, O(n) registry persist | `tier1_batch_live_fetch_service`, orchestrator |
| LA-4 | Corpus persist/dedup bridge | `scaled_federal_corpus_persist_service` |
| LA-5 | Live cohort (3×20 batches) | Staging verify shown |
| LA-6 | Scale honesty regression | `la_scale_honesty_regression_service` |
| LA-7 | Staging verify script + tests | `scripts/la_scale_federal_staging_verify.sh` |

## Verify-live AC evidence (staging)

Run: `bash scripts/la_scale_federal_staging_verify.sh`

| AC | Result |
|----|--------|
| **AC-1** | Missing `batch_tier1_public_activation_acknowledged` → **422** with field detail |
| **AC-2** | 76 grants in scaled corpus; classify+match; **all `needs_operator_review`**; provenance on corpus rows |
| **AC-3** | Re-run batch 0 → `skipped_duplicate_count=20`, `inserted_count=0` |
| **AC-4** | Honesty regression passed; no_live_nofo never irrelevant |
| **AC-5** | Kill switch engaged → batch **403** `kill_switch_engaged` (hard gate before LA-5) |
| **AC-6** | `tests/test_la_scale_federal_activation.py` + honesty tests; skip-with-reason without flags |

## Key files

- `src/nativeforge/services/tier1_batch_live_pull_orchestrator_service.py` — M8 gate + corpus persist
- `src/nativeforge/services/scaled_federal_corpus_persist_service.py` — dedup bridge
- `fixtures/real_grants_corpus/la_scaled_federal_grants.json` — scaled corpus artifact
- `src/nativeforge/api/source_ingestion_routes.py` — Pydantic body, batch_offset/max_batch_size

## Test baseline

```bash
uv run pytest tests/test_la_scale_federal_activation.py tests/test_la_scale_honesty_regression.py tests/test_sprint320_tier1_batch_live_pull_closeout.py -q
```

## Governance

- `stash@{0}` preserved (`wip-sprint8-ui-redesign-do-not-commit`)
- Never push without explicit operator instruction
- Tier-2/3 out of scope; synthetic profile matching unchanged
