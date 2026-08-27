# 539 — Gate 95: production readiness delta

Supersedes doc 533 (Gate 94) as the current readiness position.

## Readiness is unchanged

| | Gate 94 | Gate 95 |
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
| raw payload store — local | **none** | **available** |
| raw payload store — production | none | none |

**No collectors were activated. No URLs were fetched. No source monitoring
started. Production raw payload storage is not live. This does not change
Baseline X live coverage.**

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

The store exists so that *future* records do not repeat the 185/18 split. It
does not retroactively verify anything, and none of the 167 unverifiable records
became verifiable by building it.

## What Gate 95 built

```text
raw_payload_evidence_model_service        27 fields, 4 evidence-critical
local_raw_payload_store_service           content-addressed, refuses by default
raw_payload_secret_scan_service           10 finding kinds, values never printed
raw_payload_promotion_gate_service        9 requirements, 11-scenario matrix
raw_payload_store_readiness_artifact_service
```

Plus: `.gitignore` protection for the store root, and the storage-implementation
requirement wired into `source_activation_preflight_service` and
`phase1_collector_activation_policy_service`.

103 tests in `tests/test_gate95_raw_payload_store.py`.

## Three storage facts, never collapsed into one

```text
raw_payload_store_contract_available       true
local_raw_payload_store_available          true
production_raw_payload_store_available     false
```

Reported separately on every preflight and on the Phase 1 matrix, with
invariants failing any result that claims production. A local store is not a
step toward claiming a production one exists; it is a different thing.

`detect_store_implementation()` **imports the module and checks** rather than
reading a caller-supplied flag. A flag saying "the store exists" is the same
shape as the corpus flags Gates 87–89 unpicked: a claim about a claim.

## A hazard the survey found

`artifacts/` is not gitignored in this repo — a dozen artifact directories are
committed deliberately. A payload store written there would have been one
`git add artifacts/...` away from putting agency response bodies, and any
credentials inside them, into git history.

That is the Gate 89 JWT finding with a new directory name, and it would have
been introduced *by this gate*. `artifacts/raw_payload_store/` is now an
explicit ignore rule; the readiness artifacts live in a separate, committed
directory.

## The Gate 89 fixture

`fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json` still
contains its JWT and is **unmodified**. Mutating a committed transport artifact
is its own action needing its own approval, and doing it as a side effect of
building a scanner would destroy the evidence of what the corpus contained.

The scanner was run against it and reports one `jwt_token` finding without
printing the value. A test proves the same detection on a locally reconstructed
shape. **Addressed by contract; not mutated.**

## What is still not true

- Nothing collects. All five Phase 1 sources remain `not_active`, and each is
  still missing its per-source `raw_payload_store` precondition — the store
  existing is not the same as a source being configured against it.
- The store is per-checkout. There is no durable cross-process retention, no
  retention-policy expiry, no multi-tenant isolation, and no object storage.
- No migration was added. `nf_raw_source_payloads` would be Alembic `0028`, and
  adding it is a production-storage commitment that belongs in its own gate with
  a real decision behind it — not as a quiet side effect of this one.
- The 7-day Grants.gov extract window needs real durability to mean anything;
  a local store cannot honour it.

## Blockers before Phase 1 collection can begin

Item 1 from doc 533 is partially closed: the store exists locally, production
storage does not.

```text
1  production raw payload store          migration + object storage decision
2  SAM.gov API key + role                10/day without it is unusable
3  185 queue items reviewed              148 terms + 62 human-only + 4 SPA + 1 SAM
4  four SPA terms pages read by a human  "no terms found" is not "no terms exist"
5  Simpler.Grants.gov tribal enum        undocumented; needs the live Swagger
6  scheduler + breaker wiring            nothing schedules yet
```

## Carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design, still awaiting approval of a filled attestation.
Gate 95 did not touch it.
