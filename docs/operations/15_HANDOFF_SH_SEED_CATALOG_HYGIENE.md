# NativeForge Handoff — SH Block: Seed Catalog Hygiene

**Status:** Closed locally at SH commit. Push only on explicit operator instruction.

**Baseline:** `cd9499f` (LA block) → SH commit on `main`.

## Reconciliation (honest accounting)

```
177 = 122 activatable + 34 blocked_login_portal + 5 dead + 3 login + 13 members_gated
```

| Bucket | Count |
|--------|------:|
| Catalog programs (rows) | **177** |
| Activatable now | **122** |
| Blocked login portal (CSV posture corrected) | **34** |
| Dead URL | **5** |
| Login gated (fed-023 + 2) | **3** |
| Members gated | **13** |

**Zero true duplicate rows** — all URL collisions are shared-resolver (16 groups, 41 seeds).

## Root cause fixed

Registry persist / activation / freshness re-keyed from `source_url` → **`seed_id`** (`canonical_source_id` secondary). Migration `0021` adds `seed_id` to `nf_opportunity_sources`.

## Deliverables

| Sprint | Artifact |
|--------|----------|
| SH-0 | `scripts/seed_catalog_hygiene_report.py` |
| SH-1 | `scripts/apply_seed_catalog_hygiene.py` + updated `NF_SOURCE_SEED_2026.csv` + `NF_SOURCE_SEED_HEALTH_SUMMARY.json` |
| SH-2 | Migration `0021`, orchestrator + activation + freshness services |
| SH-3 | `seed_catalog_health_service.py`, batch selector `is_seed_activatable` |
| SH-4 | `scripts/seed_hygiene_staging_verify.sh` |
| SH-5 | `tests/test_sh_seed_catalog_hygiene.py` |

## Verify-live

```bash
bash scripts/seed_hygiene_staging_verify.sh
```

**AC-2 proof:** `bia.gov/topic/grants` → **3 distinct active rows** (fed-001, fed-003, fed-004), not 1.

## Governance

- `stash@{0}` preserved
- No rows deleted from CSV
- fed-023 stays login-blocked
- ALN binding expansion: out of scope
