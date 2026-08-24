# 428 — Gate 77B-A: Hermetic test survey

Every path that could call a live endpoint or rewrite committed evidence, and
what each did by default before this gate.

## Live network callers

Six services import an HTTP client:

| Service | Client | Test-reachable live? |
| --- | --- | --- |
| `grants_gov_search_api_adapter_service` | `httpx` | **yes — the defect** |
| `polite_http_fetch_service` | `httpx` | no test imports it |
| `real_url_resolver_service` | `httpx` | imported by 2 tests, **not reached live** |
| `oidc_token_verification_service` | `httpx` | JWKS path, not reached live |
| `feedback_slack_alert_service` | `httpx` | dry-run only, never proven live |
| `active_source_activation_m1_audit_export_..._service` | `httpx` | not reached |

### The one that mattered

Every Grants.gov call funnels through a single function:

```python
def default_grants_gov_http_post(url, body):
    with httpx.Client(timeout=20.0) as client: ...
```

Three call sites resolve to it (`do_post = http_post or default_grants_gov_http_post`)
in `grants_gov_search_api_adapter_service` (×2) and
`grants_gov_seed_search_refinement_service` (×1). `fetch_mode` defaults to
`FETCH_MODE_LIVE`.

**Default before this gate: live HTTP, unconditionally.**

That single choke point is why the fix is one guard call rather than a
refactor.

### Verified not-live

`test_sprint288_real_url_resolver.py` and
`test_sprint294_real_resolver_validation_orchestrator.py` were run with the
network blackholed: **4 passed in 0.73s**. They do not touch the network in the
paths they exercise, so blocking live HTTP does not affect them.

## Fixture write-back paths

Three services write into `fixtures/real_grants_corpus/`, which is committed:

| Service | Target(s) | Path parameter? | Default risk |
| --- | --- | --- | --- |
| `tribal_grant_eligibility_reingest_service` | `nf15_eligibility_reingest_pulls.json` | **no** | **active — writes on every call** |
| `tier3_foundation_corpus_persist_service` | `ta_tier3_foundation_grants.json`, `nf14_mixed_corpus.json` | yes | latent — default points at committed path |
| `scaled_federal_corpus_persist_service` | `la_scaled_federal_grants.json` | yes | latent — default points at committed path |

**Gate 77 reported one service and one fixture. It is three services and four
fixtures** — and `nf14_mixed_corpus.json` is one of the five files carrying the
`nf13-real-fed-021` SAMHSA record.

### Which are actually exercised

Empirically verified by running the three implicated test files and checking
`git status fixtures/`:

```text
tests/test_recognition_requirement_coverage_expansion.py   load-only
tests/test_ta_tier3_foundation_adapter.py                  persists to tmp_path
tests/test_la_scale_federal_activation.py                  persists to tmp_path
→ fixtures/ clean afterwards
```

So the latter two are used safely today. Their **defaults** remain dangerous: a
future caller omitting `path` writes committed evidence. Latent, not active.

`tribal_grant_eligibility_reingest_service` had no `path` parameter at all —
`FIXTURE_PATH.write_text(...)` unconditionally. That is the one that fired.

## Affected tests

Only `tests/test_sprint345_nf15_corrected_corpus.py` reached both the live
network and the unconditional fixture write. Two tests in it:

```text
test_reingest_fixes_placeholder_grants
test_corrected_corpus_no_tribal_federal_irrelevant
```

## Committed fixtures at risk

```text
fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json   ← was corrupted in Gate 77
fixtures/real_grants_corpus/nf14_mixed_corpus.json                 ← latent
fixtures/real_grants_corpus/ta_tier3_foundation_grants.json        ← latent
fixtures/real_grants_corpus/la_scaled_federal_grants.json          ← latent
```

## Exact default behaviour before Gate 77B

```text
pytest → live HTTP to api.grants.gov          ALLOWED
pytest → overwrite committed corpus fixture   ALLOWED
live response written as recorded evidence    ALLOWED
missing recording → falls through to live     ALLOWED
mode reported anywhere in output              NO
```

Every one of those is now denied by default. The combination was the real
hazard: a green online CI run would have written a live `HHS-IHS` response over
the recorded `SAMHSA / HHS` row and committed fabricated agency ownership,
produced by nothing more than running the suite.

## What Gate 77B changes

- `assert_live_network_allowed` at `default_grants_gov_http_post`.
- `guarded_write_json` / `resolve_writeback_path` at the reingest write.
- A recorded transport fixture plus an injectable `http_post` threaded through
  `reingest_nf13_placeholder_grants` → `reingest_tribal_grant_eligibility` →
  `fetch_refined_grants_gov_for_seed`, and through
  `classify_nf15_corrected_corpus` → `build_nf15_corrected_corpus`.

## What Gate 77B does not change

The two latent persist services keep committed-path defaults. Routing them
through `resolve_writeback_path` is straightforward and is recorded as
engineering-blocked in doc 432 rather than done here, to keep this gate's diff
to the path that actually fired.
