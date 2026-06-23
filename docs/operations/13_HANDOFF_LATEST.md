# NativeForge Handoff — Block NF-16: No-Proxy Honesty (Sprints 349–355)

**Status:** Complete (local). **WAIT** — do not push unless explicitly approved.

## Summary

Killed proxy substitution. Ingested opportunities must belong to the source's own program/agency — no cross-program backfill. Introduced **`no_live_nofo`** as a first-class honest state: empty eligibility, true catalog identity preserved (like `fed-001` empty-but-honest pattern). Reverted `nf13-real-fed-025` EPA proxy (362798); it is now honestly `no_live_nofo` / `uncertain_relevance` / `insufficient_data`, not `irrelevant` and not EPA CWA data under the GAP id.

NF-15 guards preserved: no-evidence → `uncertain_relevance`, tribal-agency safety net.

## New services

| Service | Role |
|---------|------|
| `no_live_nofo_state_service` | `build_no_live_nofo_grant()`, `assert_no_live_nofo_honest()` |
| `source_program_ownership_guard_service` | `assert_source_program_ownership()`, `CrossProgramProxyError` |
| `nf16_no_proxy_corpus_classification_service` | Corpus re-classify vs NF-15 baseline |
| `nf16_no_proxy_honesty_orchestrator_service` | Block orchestrator |
| `nf16_no_proxy_honesty_gate_verification_service` | Gate checks |
| `nf16_no_proxy_honesty_closeout_packet_service` | Closeout artifact |

## Removed patterns

- `reingest_program_proxy`
- `SEED_FALLBACK_OPPORTUNITY_IDS` / EPA tribal environmental fallback (`iegap_nofo_absent_epa_tribal_environmental_fallback`)
- Grants.gov opportunity 362798 under GAP source

## fed-025 honest state

| Field | Value |
|-------|-------|
| `opportunity_number` | `FED-025` |
| `opportunity_title` | General Assistance Program (GAP) |
| `agency` | EPA |
| `eligibility_text` | *(empty)* |
| `source_ingestion_state` | `no_live_nofo` |
| `no_live_nofo` | `true` |
| `reingest_program_proxy` | `false` |
| Classification | `uncertain_relevance` / `insufficient_data` |

## Corrected corpus label distribution vs NF-15

| Label | NF-15 | NF-16 | Δ |
|-------|------:|------:|--:|
| `tribal_government_specific` | 43 | 43 | 0 |
| `irrelevant` | 4 | 4 | 0 |
| `uncertain_relevance` | 4 | 5 | +1 |
| `weak_native_relevance` | 2 | 1 | −1 |
| `native_entity_eligible_broad` | 3 | 3 | 0 |
| `native_specific` | 1 | 1 | 0 |

**Invariants (tested):** zero proxy substitutions; `no_live_nofo` never `irrelevant`; no tribal-federal grant in `irrelevant`.

## Routes

`POST .../no-proxy-honesty` (demo + real, plan-gated)

## Test baseline

`pytest` — **5173 passed**, 11 skipped (after NF-16). NF-16/15 gate + ownership + no_live_nofo tests green.

## Governance

- Staging only, **never pushed**, `stash@{0}` preserved (`wip-sprint8-ui-redesign-do-not-commit`)
