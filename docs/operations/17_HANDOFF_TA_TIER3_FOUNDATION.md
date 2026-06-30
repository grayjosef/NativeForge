# Handoff — Tier-3 Foundation Adapters (TA-0…TA-5)

**Baseline:** `62d44f7` (RT partial)  
**Scope:** Tier-3 foundations first; 12-seed cohort; 3 platform adapters (T2 stub deferred).

## Delivered

| Sprint | What |
|--------|------|
| **TA-0** | `source_fetch_adapter_contract_service.py`, `platform_adapter_registry_service.py` |
| **TA-1** | `polite_http_fetch_service.py` (UA, robots.txt, 2s/domain rate limit), `foundation_html_listing_adapter_service.py`, `foundation_fluxx_embed_adapter_service.py`, `html_fetch_honest_labeling_guard_service.py` |
| **TA-2** | `tier3_org_cluster_config_service.py` — org-cluster configs for 5 domains |
| **TA-3** | `tier3_foundation_batch_live_fetch_service.py`, `tier3_foundation_batch_activation_service.py`, `tier3_batch_live_pull_orchestrator_service.py` |
| **TA-4** | `tier3_foundation_corpus_persist_service.py`, `tier3_classify_match_orchestrator_service.py` |
| **TA-5** | `tests/test_ta_tier3_foundation_adapter.py`, `ta_tier3_honesty_regression_service.py`, `scripts/ta_tier3_staging_verify.sh` |

**Deferred:** `state_tribal_affairs_html_adapter_service.py` stub only (T2 pilot).

## 12-seed cohort

`t3-005` (NAP), `t3-006…011` (FPF ×6), `t3-012/013/034` (First Nations ×3), `t3-027` (Honor the Earth), `t3-030` (7gen).

## Verify-live (staging)

```bash
./scripts/ta_tier3_staging_verify.sh
```

## AC-3 live results (shown output)

| Metric | Value |
|--------|-------|
| Federal baseline (nf13) | 40 |
| Live listings extracted | 26 |
| `no_live_nofo` (honest empty / apply-platform blindspot) | 4 |
| Tier-3 corpus rows | 30 (26 live + 4 nofo) |
| Mixed pool (la_scaled + tier3) | 106 |
| Delta vs nf13 baseline | +66 |

**Apply-platform blindspot:** 4 seeds returned honest `no_live_nofo` — grants may exist behind Submittable/Fluxx on deeper pages; not fabricated.

## Per-adapter (live)

- `foundation_html_listing`: 9 seeds
- `foundation_fluxx_embed`: 3 seeds (First Nations cluster)
