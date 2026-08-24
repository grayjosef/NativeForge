# 429 — Gate 77B-B: Hermetic Grants.gov test policy

## The rule

**Live HTTP is forbidden by default, everywhere.** Not only under pytest — the
guard is unconditional, and a deliberate live fetch opts in.

```python
assert_live_network_allowed(url=..., caller=...)
```

sits at the top of `default_grants_gov_http_post`, the single function every
Grants.gov call in the codebase resolves to. Without
`NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1` it raises `LiveNetworkBlockedError`.

## Why unconditional rather than pytest-only

A pytest-only guard protects the suite and leaves every other entry point —
scripts, a REPL, a future scheduled job — able to reach the network silently.
Since there is no live ingestion in this product yet, blocking everywhere costs
nothing and makes the one legitimate case explicit.

The legitimate callers today are operator refresh tools, and they should say so:

```text
scripts/generate_nf_source_seed_2026.py
scripts/la0_federal_active_count.py
scripts/grants_gov_attachment_recoverable_reaudit.sh
scripts/grants_gov_eligibility_completeness_staging_verify.sh
```

## Why it raises instead of returning empty

There is no useful partial answer to "we were not allowed to ask". A silent
empty result is indistinguishable from a genuine no-results response — and that
ambiguity is precisely how Gate 77's offline run wrote a `no_live_nofo`
placeholder over recorded evidence. The exception is loud, names the flag, and
names this document.

## How to run a live refresh intentionally

```bash
NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1 python scripts/la0_federal_active_count.py
```

The flag is deliberately long and conspicuous. Someone scrolling a CI config or
a shell history should notice it.

**Do not set it in CI.** A suite whose result depends on a third party's search
ranking is not testing this product. Gate 77 is the proof: the same test passed
and failed depending on what Grants.gov returned that day.

## What tests do instead

Inject a recorded transport:

```python
from nativeforge.services.hermetic_test_guard_service import load_recorded_transport

transport = load_recorded_transport("nf_seed_2026_fed_021_samhsa_sm_26_024.json")
report = reingest_nf13_placeholder_grants(http_post=transport)
```

Recordings live in `tests/fixtures/grants_gov/` and are keyed by request URL.

The transport is injected at the boundary, so the code under test — search,
detail fetch, eligibility parsing, agency resolution, the ownership guard — all
runs for real. This records the third party, not the logic.

### Missing recordings

`load_recorded_transport` raises `RecordedTransportMissingError` when the file is
absent. It never falls back to a live fetch: *we have no recording* must not
become *so ask the internet*.

### Unrecorded URLs

A URL the recording does not cover returns a well-formed empty success —
`errorcode: 0`, no hits. That models "the search found nothing", which is a real
Grants.gov outcome and the one the corpus already records for
`nf-seed-2026-fed-025`. It invents no opportunity.

## Flag parsing is strict

Accepted as on: `1`, `true`, `yes`, `on` (case-insensitive, trimmed).
Everything else is off, including `flase`, `0`, `no` and empty.

A guard that disables itself on a typo is not a guard. Tested both ways.

## Mode is reported, not silent

`hermetic_status()` returns the current mode and every flag, and it is embedded
in the re-ingest report:

```json
{"mode": "hermetic", "live_network_allowed": false,
 "corpus_writeback_allowed": false, "source_fixture_overwrite_allowed": false}
```

An invariant fails a status claiming `live_network_allowed` without
`mode == "live"`, so the two cannot drift apart.

## Recording a new transport

There is no automated recorder in this gate. Recording one is a deliberate act:
run the live fetch with the flag set, capture the raw responses, and commit them
under `tests/fixtures/grants_gov/` with a `_meta` block stating provenance,
seed, expected grant, and that the values are repo-recorded rather than a claim
about current live availability.

Anything transcribed from existing committed corpus data should say so, as
`nf_seed_2026_fed_021_samhsa_sm_26_024.json` does.
