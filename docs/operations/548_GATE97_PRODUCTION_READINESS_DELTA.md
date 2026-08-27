# 548 — Gate 97: production readiness delta

Supersedes doc 544 (Gate 96) as the current readiness position.

## Readiness is unchanged where it matters

| | Gate 96 | Gate 97 |
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
| raw payload metadata table | available | available |
| raw payload body store — implementation | **none** | **available** |
| raw payload body store — configured | no | no |
| raw payload store — production | NOT AVAILABLE | NOT AVAILABLE |

**A body-store implementation exists. No live object store was contacted and
none is configured. The production raw payload store remains unavailable.
Collectors remain inactive. No live fetch occurred. No source monitoring
started. Secrets are never surfaced.**

`production_storage_live` still requires an active collector, and there are
none.

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

## What Gate 97 built

```text
s3_raw_payload_body_store_service              injected client, no SDK
raw_payload_body_store_readiness_artifact_service
Settings                                       six RAW_PAYLOAD_OBJECT_STORE_*
```

Plus: the body-store contract now detects **values** rather than fields, the
readiness service has five components rather than four, and the repository
accepts a body-store ref.

77 tests in `tests/test_gate97_object_body_store.py`.

## Four of five components

```text
metadata_table_available              true
body_store_implementation_available   true   <- new in Gate 97
body_store_configured                 FALSE  <- the only one missing
secret_scan_available                 true
promotion_gate_available              true
```

The missing one is missing because no environment sets the five required
settings. That is a deployment decision, not code — and the detector can now
say **yes**, which Gate 96's could not. A test configures a synthetic
environment and asserts `production_raw_payload_store_available` becomes `true`
while `production_storage_live` stays `false`, because live additionally
requires a collector.

## Two guards that had encoded a moment as a law

Gate 96 wrote:

```python
if matrix.get("production_raw_payload_store_available") is not False:
    fails.append("matrix_claimed_production_payload_storage")
```

A **constant**, and correct at the time — nothing could configure a body store,
so the flag could only ever be false. Gate 97 makes configuration possible, and
a constant that was true of one moment is not a law: with real settings the
guard would have failed a correct system.

Both are now checks on the derivation — production availability must follow from
its components, and no single component may stand in for the whole. A faked flag
is still caught, by the component it lacks rather than by a blanket rule, and
the Gate 95 test that pinned the old failure name now asserts the new ones.

This is the second time in two gates that a guard written as a constant needed
converting to a derivation. It is worth watching for: a guard that says "this
value is always X" is only correct while X cannot change.

## One robustness fix

`RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE=` — a blank value, an ordinary way to
write "leave this alone" in a `.env` — made pydantic raise, taking the whole
`Settings` object and therefore the app down over an empty line in a config
file. A `mode="before"` validator maps blank to `False`. Found while writing the
tests; fixed in the settings rather than worked around in the test.

## What is still not true

- No object store was contacted. Every write in the suite ran through an
  injected fake, and a test asserts the test file imports no SDK or HTTP client.
- Nothing is configured. All five settings are absent in this checkout.
- Nothing collects. All five Phase 1 sources remain `not_active`, and a test
  asserts they stay that way **even with a fully configured body store** —
  configuring storage does not start anything.
- No write has ever succeeded against a real bucket. Settings being present is
  not the same as a round trip working, and the readiness service says so in its
  own next-actions list.

## Blockers before Phase 1 collection can begin

```text
1  configure the object store in a real environment, then prove a round trip
   in staging — settings present is not a write succeeding
2  SAM.gov API key + role                10/day without it is unusable
3  185 queue items reviewed              148 terms + 62 human-only + 4 SPA + 1 SAM
4  four SPA terms pages read by a human  "no terms found" is not "no terms exist"
5  Simpler.Grants.gov tribal enum        undocumented; needs the live Swagger
6  scheduler + breaker wiring            nothing schedules yet
```

Item 1 changed shape: Gate 96 needed an implementation and a decision; Gate 97
supplied the implementation, leaving a deployment and a proof.

## Carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design. The Gate 89 JWT fixture remains unmodified.
