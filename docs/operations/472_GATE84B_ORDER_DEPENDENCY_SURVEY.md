# 472 — Gate 84B-A/B: Order dependency survey

## Correction first: they were not order-dependent

Gate 84's report described these two tests as passing in the full suite and
failing in smaller subsets. **That was wrong, and it was my inference rather
than a measurement.**

Both fail **deterministically**, in every arrangement tested:

```text
                                              alone   own file   at HEAD (worktree)
test_unknown_count_drops_ac1                   FAIL     FAIL       FAIL
test_nf15_gate_and_closeout                    FAIL     FAIL       FAIL
```

What actually happened is worse than an ordering bug: **the broad scoped `-k`
never selected them.**

```text
tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout
    not selected by the broad -k at all

tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1
    not selected by the broad -k either; three *other* tests in that file are,
    which is why the file appeared in the run
```

The Gate 84 broad run reported `6362 passed, 0 failed` and never executed
either test. I read that as "the full suite is green" and inferred ordering as
the explanation for the subset failures. The honest statement is that these
tests had been failing for some time and the `-k` selection hid them.

There is also positive evidence *against* order dependence: the
fixture-cleanliness verifier passes, which means no test mutates `fixtures/`.
Both tests read only committed fixtures, so no earlier test can change what they
see.

## Test 1 — `test_nf15_gate_and_closeout`

**Root cause: Gate 77B broke it, and nothing noticed.**

`verify_nf15_no_evidence_honesty_gates()` calls
`run_nf15_no_evidence_honesty_block()`, which calls
`reingest_nf13_placeholder_grants()` with no `http_post`. That reaches
`default_grants_gov_http_post`, which since Gate 77B refuses unless live
network is explicitly enabled:

```python
assert_live_network_allowed(url=url, caller="default_grants_gov_http_post")
```

So the re-ingest always fails and `fed021_reingested` is permanently `False`:

```text
fed021_reingested            false   <-- the only failing check
fed025_no_live_nofo          true
fed021_not_placeholder       true
no_tribal_federal_in_irrelevant  true
... all others true
```

Gate 77B added the `http_post` parameter to
`reingest_nf13_placeholder_grants` precisely so callers could inject a recorded
transport — but never threaded one through the orchestrator, and the test had no
way to supply it. The test predates the guard (commit `ac2e0d8`, before
`f15f9a5`).

The recording exists and is committed:
`tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json`. Driving
the re-ingest with it reproduces the committed evidence exactly:

```text
nf13-real-fed-021  reingested=True   no_live_nofo=False  refined_hit_matched
nf13-real-fed-025  reingested=False  no_live_nofo=True   no_intent_matching_hit
```

## Test 2 — `test_unknown_count_drops_ac1`

**Root cause: an absolute threshold measured against a corpus that grew.**

```python
corpus = load_mixed_tier13_corpus()          # 168 grants today
unknowns = [... recognition_requirement == "unknown"]
assert len(unknowns) <= 45                   # got 80
```

Distribution across the mixed corpus:

```text
unknown            80
federal_required   55
state_ok           32
open_nonprofit      1
```

Of the 80 unknowns, **61 come from tier-3 foundation grants and 6 from tier-2
state grants** — layers added to the mixed corpus after AC1 was written
(commits `ec59481`, `fd2b44a`, `12e0ae3`, `cd01ced`). The sibling test in the
same file still names a "49-grant baseline".

On the corpus AC1 was calibrated against, the assertion is comfortably true:

```text
tier-1 federal only   76 grants    13 unknown   (threshold <= 45)
mixed (all layers)   168 grants    80 unknown
```

Foundation and state sources mostly do not state a tribal recognition
requirement at all. `unknown` is the **correct** answer for them; assigning a
recognition tier would be fabricating eligibility. So counting them in AC1
measured corpus growth, not derivation quality.

## Hidden state actually found

None in these two paths. Specifically checked and clear:

```text
module-level lists/dicts/sets   none in the corpus, rules or enrichment services
caches / lru_cache              none on the load or enrich path
sqlite / fixed temp paths       none read by either test
os.environ writes in tests      only conftest.py DATABASE_URL, set once at import
transport monkeypatching        no test replaces default_grants_gov_http_post
corpus mutation during a run    impossible; writes go through guarded_write_text
                                and fixture-cleanliness passes
```

The one genuine environment dependency is the `staging_gates` fixture in the
NF-15 test, which uses `monkeypatch.setenv` and `get_settings.cache_clear()` —
correctly scoped, and it undoes itself.

## Patch plan

1. Thread `http_post` through `run_nf15_no_evidence_honesty_block` and
   `verify_nf15_no_evidence_honesty_gates`; the test injects the committed
   recording. Keyword-only and optional, so the two API route callers are
   unaffected and the live path stays refused by default.
2. Scope AC1 to the tier-1 federal corpus it was calibrated for, and add a
   structural assertion that every unknown outside tier-1 is attributable to a
   later corpus layer — so the scoping cannot become a place for a tier-1
   regression to hide.
3. Add `tests/test_gate84b_order_independence.py`, which runs each formerly
   failing test **in its own interpreter** and asserts repeated calls are
   stable and no committed fixture is mutated.

## Remaining risk

The real defect this uncovered is not either test — it is that a `-k`-selected
run was being read as suite health. Recorded in doc 474.
