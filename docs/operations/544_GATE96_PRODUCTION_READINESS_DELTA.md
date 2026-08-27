# 544 — Gate 96: production readiness delta

Supersedes doc 539 (Gate 95) as the current readiness position.

## Readiness is unchanged where it matters

| | Gate 95 | Gate 96 |
| --- | --- | --- |
| controlled customer pilot | NO_GO | NO_GO |
| production rollout | NO_GO | NO_GO |
| login live | no | no |
| production storage | no | no |
| customer persistence | no | no |
| pen-test passed | no | no |
| live source coverage | none | none |
| sources monitored | 0 | 0 |
| collectors live | 0 | 0 |
| raw payload store — local | available | available |
| raw payload metadata table | **none** | **available** |
| raw payload body store — production | none | none |
| raw payload store — production | NOT AVAILABLE | NOT AVAILABLE |

**Migration 0028 adds a metadata table only. The production body store remains
unconfigured, so the production raw payload store remains unavailable.
Collectors remain inactive. No live fetch occurred. No source monitoring
started. No live source coverage is claimed.**

**Adding a table is not the same as production storage being live.**

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

## What Gate 96 built

```text
alembic/versions/0028_nf_raw_source_payloads.py
  31 columns, 5 indexes, 1 unique, 7 check constraints. Applies on SQLite.

production_raw_payload_repository_service      metadata only; dry-run default
raw_payload_body_store_contract_service        4 modes, 1 production-capable
raw_payload_production_readiness_service       4 components, 2 derived verdicts
raw_payload_production_readiness_artifact_service
```

Plus `collection_intent` on the activation preflight, and the production
distinction reported on the Phase 1 matrix.

87 tests in `tests/test_gate96_production_raw_payload_storage.py`.

## One component of four

```text
metadata_table_available      true
secret_scan_available         true
promotion_gate_available      true
body_store_configured         FALSE   <- the only one missing
```

The survey established why, and it is not a judgment call: there is **no
object-store client anywhere in this project**. Not in `src/`, not in
`pyproject.toml`, not in `uv.lock`. No `src/nativeforge/storage/` package. No
bucket, endpoint or credential field on the Settings model.

So `body_store_configured` is `False` by detection, and every function in this
gate that could report otherwise is guarded by an invariant that fires when it
does.

## What is still not true

- Nothing collects. All five Phase 1 sources remain `not_active`, and
  `may_fetch_live_now` / `may_schedule_monitor` are `False` on every one.
- The table is empty. It exists; nothing has written a production row to it.
- No body has been stored anywhere durable. Gate 95's local store is
  per-checkout and gitignored; that has not changed.
- `production_storage_live` is `False` and would stay `False` even if a body
  store appeared tomorrow, because it also requires an active collector — which
  is a separate decision with its own preflight.
- The Grants.gov 7-day retention window still cannot be honoured. It needs
  durable body storage, which is the missing component.

## Blockers before Phase 1 collection can begin

Item 1 from doc 539 is now half closed: the metadata table exists, the body
store does not.

```text
1  object store: choose one, add a client, add endpoint/bucket/credential
   settings, implement against the four guarantees, prove in staging
2  SAM.gov API key + role                10/day without it is unusable
3  185 queue items reviewed              148 terms + 62 human-only + 4 SPA + 1 SAM
4  four SPA terms pages read by a human  "no terms found" is not "no terms exist"
5  Simpler.Grants.gov tribal enum        undocumented; needs the live Swagger
6  scheduler + breaker wiring            nothing schedules yet
```

## Carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design, still awaiting approval of a filled attestation.
Gate 96 did not touch it.

The Gate 89 JWT fixture
(`fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json`) remains
unmodified, as in Gate 95.
