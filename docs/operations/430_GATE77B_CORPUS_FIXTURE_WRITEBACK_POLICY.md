# 430 — Gate 77B-C: Corpus fixture write-back policy

## The rule

**A write aimed at committed evidence is redirected, not performed**, unless two
separate flags say otherwise.

```text
NATIVEFORGE_ALLOW_CORPUS_WRITEBACK=1          routine write-back
NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE=1  overwrite committed evidence
```

Both are required to touch a source-controlled path. Either alone redirects.

## What counts as committed evidence

```text
fixtures/
tests/fixtures/
src/nativeforge/data/
```

Redirected writes land under `artifacts/corpus_writeback/<label>/<filename>`,
which is untracked.

## Why redirect rather than refuse

The caller's real work — fetching, deriving, assembling a report — is still
valid, and its output is still worth keeping. Refusing would throw away a good
result because of where it was going to be filed.

The redirect is **reported**, so it cannot be mistaken for a fixture update:

```python
{"requested_path": ".../fixtures/real_grants_corpus/nf15_....json",
 "path": ".../artifacts/corpus_writeback/nf15_eligibility_reingest/nf15_....json",
 "redirected": true,
 "reasons": ["NATIVEFORGE_ALLOW_CORPUS_WRITEBACK_not_set",
             "NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE_not_set",
             "refusing_to_overwrite_committed_evidence"]}
```

`reingest_nf13_placeholder_grants` surfaces this as `writeback_redirected` and
`written_path`, while `fixture_path` keeps naming the intended target so the
difference is visible in the result.

Network is the opposite case and raises — see doc 429 for why.

## Why two flags

Routine write-back and clobbering committed evidence are different acts with
different blast radii. An operator who enabled the first should not silently
acquire the second.

All four combinations are tested:

| `..._CORPUS_WRITEBACK` | `..._SOURCE_FIXTURE_OVERWRITE` | Result |
| --- | --- | --- |
| unset | unset | redirect |
| set | unset | redirect |
| unset | set | redirect |
| set | set | **write the committed path** |

An invariant also fails a status reporting `source_fixture_overwrite_allowed`
without `corpus_writeback_allowed`, so the two cannot disagree.

## Why overwriting a source fixture is dangerous

Gate 77 is the case study. `nf15_eligibility_reingest_pulls.json` is the repo's
recorded evidence for grant `nf13-real-fed-021`, and the service that reads that
evidence also rewrote it.

**Offline run** — the file was rewritten to:

```text
"reingested": false
"diagnosis": "search_api_error: [Errno 111] Connection refused"
"opportunity_number": "FED-021"      (was SM-26-024)
                                     (chosen_opportunity_id 361976 removed)
```

Recorded evidence for a real grant, replaced by a connection error.

**Online run** — worse. It would have written the live `HHS-IHS` /
`HHS-2027-IHS-SPIP-0001` response over the recorded `SAMHSA / HHS` row, and the
repo would then assert that a SAMHSA grant belongs to IHS. Fabricated agency
ownership, produced by nothing more than running the suite, and it would have
looked like a legitimate diff.

This is a self-corrupting evidence file: the artifact recording what was
observed is rewritten by observing again. There is no version of that which is
safe as a default.

## Standing guard

Three tests now watch that one file:

```text
test_committed_fixture_still_records_samhsa_evidence
test_committed_fixture_carries_no_connection_error_placeholder
test_committed_fixture_carries_no_ihs_substitution
```

Plus one that runs the re-ingest and byte-compares the file before and after.

## Deliberate re-recording

When someone verifies the current SAMHSA NOFO and wants to update the record:

```bash
NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1 \
NATIVEFORGE_ALLOW_CORPUS_WRITEBACK=1 \
NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE=1 \
  python -c "from nativeforge.services.tribal_grant_eligibility_reingest_service import reingest_nf13_placeholder_grants; reingest_nf13_placeholder_grants()"
```

Three flags, none of them a default, and the resulting diff gets reviewed like
any other change to recorded evidence about a real federal grant.

## Known remaining exposure

Two services still default to committed paths, though their current tests pass
`tmp_path` and do not mutate anything (verified in doc 428):

```text
tier3_foundation_corpus_persist_service   → ta_tier3_foundation_grants.json, nf14_mixed_corpus.json
scaled_federal_corpus_persist_service     → la_scaled_federal_grants.json
```

Routing their defaults through `resolve_writeback_path` is the obvious next
step and is recorded as engineering-blocked in doc 432. It was left out of this
gate to keep the diff on the path that actually fired.

A CI check asserting `git status` is clean after the suite would catch the whole
class rather than each instance, and is worth adding.
