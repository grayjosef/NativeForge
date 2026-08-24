# 431 — Gate 77B-E: Corrected corpus unquarantine status

## Status: both tests unquarantined

```text
tests/test_sprint345_nf15_corrected_corpus.py
  test_reingest_fixes_placeholder_grants             UNQUARANTINED — passing
  test_corrected_corpus_no_tribal_federal_irrelevant UNQUARANTINED — passing
```

Gate 77 quarantined both. Gate 77B removed the quarantine because the two
defects that caused it are fixed at the source, not because the assertions were
loosened. Every original assertion still runs.

## The four conditions, each met

| Condition | Status |
| --- | --- |
| No live network by default | **met** — `default_grants_gov_http_post` raises without the flag |
| No committed-fixture write by default | **met** — redirected under `artifacts/` |
| Pass via a recorded/hermetic path | **met** — recorded transport injected |
| Cross-program guard still raises on IHS vs SAMHSA | **met** — asserted with a stub |

## How they pass now

Both tests inject a recorded transport:

```python
load_recorded_transport("nf_seed_2026_fed_021_samhsa_sm_26_024.json")
```

The re-ingest path itself runs for real — search, detail fetch, eligibility
parsing, agency resolution, and the ownership guard all execute. Only the
transport is recorded. This is not a mock of the logic under test; it is a
recording of the third party the logic talks to.

Result, reproduced exactly from committed evidence:

```text
nf13-real-fed-021  reingested=True   agency='SAMHSA / HHS'  number='SM-26-024'
nf13-real-fed-025  no_live_nofo=True
proxy_substitution_count=0
```

`nf-seed-2026-fed-025` has no recording. The transport returns a well-formed
empty result for it — `errorcode: 0`, no hits — which produces `no_live_nofo`,
exactly what the committed corpus already records for that seed
(`diagnosis: no_intent_matching_hit`). No opportunity was invented for it.

## Assertions added beyond the originals

The originals asserted re-ingest succeeded and eligibility was not a
placeholder. Gate 77B added three, so the tests fail loudly if a live response
ever leaks back in:

```python
assert fed021["updated_grant"]["agency"] == "SAMHSA / HHS"
assert fed021["updated_grant"]["opportunity_number"] == "SM-26-024"
assert report["writeback_redirected"] is True
assert report["hermetic_status"]["mode"] == "hermetic"
```

If the live path is ever reached inside these tests, the agency reads `HHS-IHS`
and the first assertion fails. That is the desired failure mode: a leak becomes
a red test rather than a silent data change.

## The guard was not weakened

`assert_source_program_ownership` and `CrossProgramProxyError` are byte-for-byte
unchanged. Gate 77B proves the guard still works **without touching the
network**, by handing it a stubbed live-like IHS payload:

```python
ihs_grant = {"agency": "HHS-IHS",
             "opportunity_number": "HHS-2027-IHS-SPIP-0001", ...}
with pytest.raises(CrossProgramProxyError, match="does not match source agency"):
    assert_source_program_ownership(source=samhsa_source, grant=ihs_grant)
```

and the matching SAMHSA payload passes. Two tests also assert the guard's source
still contains its class, its raise and its function.

## What remains unknown

**Whether SAMHSA `SM-26-024` is still posted on Grants.gov.** Gate 77 found the
live refined search returning `HHS-2027-IHS-SPIP-0001` from `HHS-IHS` instead.
That question is unresolved and still needs external verification.

It is no longer *blocking*, because the tests no longer depend on the answer.
But it matters for a different reason: if `SM-26-024` has closed, then the
recorded transport describes a real opportunity that is no longer open, and the
corpus row is historical rather than current. The recording is explicitly
labelled as repo-recorded evidence, not as a claim about live availability.

Re-recording it, when someone does verify, is a deliberate act:

```bash
NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1 \
NATIVEFORGE_ALLOW_CORPUS_WRITEBACK=1 \
NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE=1 \
  python -c "..."
```

Three flags, none of them defaults, and the resulting diff would be reviewed
like any other change to recorded evidence.

## No fabricated agency ownership

Every value in the recorded transport is transcribed from
`fixtures/real_grants_corpus/nf13_real_ingested_grants.json` and
`nf15_eligibility_reingest_pulls.json`: opportunity number `SM-26-024`,
opportunity id `361976`, agency `SAMHSA / HHS`, the applicant-type descriptions
and the eligibility narrative. Nothing was invented, and a test asserts the
recording's response payloads contain no `HHS-IHS` or `IHS-SPIP` string.
