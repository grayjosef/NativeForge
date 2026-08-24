# 432 — Gate 77B-H: Production readiness delta

Gate 77B made the federal corpus tests hermetic and locked down fixture
write-back. It provisioned nothing and monitored nothing.

## Hermetic tests: now

| | Before | After |
| --- | --- | --- |
| Suite can call `api.grants.gov` | **yes, by default** | **no — raises without an explicit flag** |
| Suite can overwrite committed fixtures | **yes, by default** | **no — redirected under `artifacts/`** |
| Overwriting committed evidence | silent side effect | needs **two** separate flags |
| Live mode visible in results | no | `hermetic_status()` on every re-ingest report |
| Missing recording falls back to live | n/a | raises `RecordedTransportMissingError` |

The network guard sits at `default_grants_gov_http_post`, the single choke point
every Grants.gov call funnels through. The write guard sits in
`hermetic_test_guard_service.resolve_writeback_path`.

**Why network raises but writes redirect.** There is no useful partial answer to
"we were not allowed to ask", and a silent empty result is indistinguishable
from a genuine no-results response — which is exactly how the corpus fixture got
overwritten with a placeholder in Gate 77. A blocked *write*, by contrast, still
has real output worth keeping, so it lands in `artifacts/` and the redirect is
reported.

**Why two flags for source overwrite.** An operator who enabled routine
write-back should not thereby gain the ability to clobber committed evidence.
`NATIVEFORGE_ALLOW_CORPUS_WRITEBACK=1` alone redirects;
`NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE=1` alone redirects; both together
permit. Tested in all four combinations.

Flag parsing is strict — `flase` is off. A guard that disables itself on a typo
is not a guard.

## Corpus status

**Both tests unquarantined and passing.**

```text
tests/test_sprint345_nf15_corrected_corpus.py
  test_reingest_fixes_placeholder_grants             PASS (hermetic)
  test_corrected_corpus_no_tribal_federal_irrelevant PASS (hermetic)
```

They now inject a recorded transport transcribed from committed corpus evidence.
The re-ingest path runs for real; only the transport is recorded. The tests
additionally assert that the re-ingested agency is still `SAMHSA / HHS` and the
run redirected its write-back — so if a live response ever leaks into them, they
fail rather than pass quietly.

Fixed at the source rather than worked around: the quarantine was removed
because the defects are gone, not because the assertions were loosened.

## Live fetch status

```text
Live fetch by default:        BLOCKED
Live fetch flag:              NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1
Live fetch performed in CI:   NO
Live fetch performed in Gate 77B: NO
```

Nothing in this gate called the network. The "live-like IHS response" case is a
stub, which is the point — the cross-program guard is proved to work without
needing the internet to misbehave on cue.

## Source fixture mutation status

```text
Committed fixtures mutated:   NONE
nf15_eligibility_reingest_pulls.json: intact, SAMHSA / HHS, SM-26-024, 361976
Connection-error placeholder: absent (asserted)
HHS-IHS substitution:         absent (asserted)
```

Three tests now stand guard over that one file: one asserts the SAMHSA row is
intact, one asserts the Gate 77 offline corruption string is absent, one asserts
the IHS substitution is absent.

## Wider survey result

The survey (doc 428) found the blast radius was **wider than Gate 77 reported**:
three services write to four committed fixtures, not one service to one.

- `tribal_grant_eligibility_reingest_service` → `nf15_eligibility_reingest_pulls.json`
  — unconditional, no path parameter. **The live defect. Now guarded.**
- `tier3_foundation_corpus_persist_service` → `ta_tier3_foundation_grants.json`,
  `nf14_mixed_corpus.json`
- `scaled_federal_corpus_persist_service` → `la_scaled_federal_grants.json`

The latter two accept a `path` parameter and their tests pass `tmp_path`, so
they do not mutate committed evidence today — verified empirically. But their
**defaults still point at committed paths**, so a caller omitting `path` would
write them. That is latent, not active.

Also confirmed: the other live-HTTP services (`polite_http_fetch_service`,
`real_url_resolver_service`, `oidc_token_verification_service`,
`feedback_slack_alert_service`) are not reached live by any test —
`test_sprint288` and `test_sprint294` pass offline in under a second.

## Federal coverage status

Unchanged by this gate.

```text
Live federal source coverage: NONE
Federal sources monitored:    0
Federal coverage complete:    NOT CLAIMED
65% improvement:              NOT CLAIMED
```

## Owner-blocked

- External verification of SAMHSA `SM-26-024` — still unknown whether it is
  currently posted. **No longer blocking the tests**, but still the open
  question about live data.
- Robots/terms review per federal source.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test, Slack webhook.

## Engineering-blocked

- Routing `tier3_foundation_corpus_persist_service` and
  `scaled_federal_corpus_persist_service` defaults through
  `resolve_writeback_path` too, closing the latent risk.
- A CI assertion that `git status` is clean after the suite runs.
- Enumerating real agency NOFO pages and Native-specific program pages.
- Federal source persistence and RLS; gates 78, 80–86.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot:    NO_GO
Production rollout:           NO_GO
Customer login live:          NO
Production storage live:      NO
Customer persistence:         NO
Pen-test passed:              NO
```

What genuinely changed: the test suite can no longer fabricate agency ownership
by running. Before this gate, a green online CI run would have silently
committed a live `HHS-IHS` response over recorded `SAMHSA / HHS` evidence — a
fabrication produced by the safety mechanism itself. That path is closed, and
two tests that were red are now green for the right reason.
