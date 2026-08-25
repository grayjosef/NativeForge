# 473 — Gate 84B: Order independence contract

## Root cause

Neither test was order-dependent. Both failed deterministically; the broad
scoped `-k` simply never selected them, so `6362 passed, 0 failed` was not
evidence that they passed. Full analysis in doc 472.

| Test | Broken by | Mechanism |
| --- | --- | --- |
| `test_nf15_gate_and_closeout` | Gate 77B (`f15f9a5`) | live Grants.gov made opt-in; this path had no way to inject a recorded transport, so the re-ingest was permanently refused |
| `test_unknown_count_drops_ac1` | Tier-2/Tier-3 corpus growth | absolute unknown threshold measured against a corpus that grew from 76 to 168 grants |

## Why it "passed in the full suite"

It did not. That claim in the Gate 84 report was an inference from a green
`-k`-selected run, not a measurement. Neither test was in that selection.

## Why it failed in a subset

For the same reason it fails anywhere: the failures are deterministic. The
"subset" in Gate 84 was the affected-suites run, whose `-k` happened to include
`coverage`, so it selected the recognition test and reported the failure
honestly. The broad run's `-k` did not.

## What was fixed

### NF-15: inject the transport rather than imply it

```python
def run_nf15_no_evidence_honesty_block(*, ..., http_post: Any | None = None):
    reingest = reingest_nf13_placeholder_grants(http_post=http_post)

def verify_nf15_no_evidence_honesty_gates(*, http_post: Any | None = None):
    result = run_nf15_no_evidence_honesty_block(http_post=http_post)
```

Both parameters are keyword-only and optional, so the two API route callers in
`source_ingestion_routes.py` are unaffected. The test supplies the committed
recording for seed `nf-seed-2026-fed-021`.

**The live path stays refused by default.** A guard test asserts that calling
without a transport still yields `fed021_reingested: False` — the fix must not
have quietly reintroduced a live fallback, which is exactly what Gate 77B
existed to prevent.

### AC1: measure the corpus the criterion is about

The assertion is unchanged (`<= 45`, `< 57`). What changed is the corpus it
reads: the tier-1 federal corpus it was calibrated against, rather than that
corpus plus two later layers.

On tier-1 the result is **13 unknowns against a threshold of 45** — comfortably
inside it, not scraping past. Tier-3 foundation grants are 61/66 unknown
because foundation notices mostly do not state a tribal recognition
requirement; `unknown` is the correct answer and assigning a tier would be
fabricating eligibility.

To keep the narrowed scope from becoming a hiding place, a second assertion is
structural rather than a hard-coded count:

```python
assert unknown_ids - tier1_ids <= later_layer_ids
```

Every unknown outside tier-1 must be attributable to tier-2 or tier-3. A
tier-1 derivation regression still fails, and the assertion does not rot the
next time the corpus grows.

## What the guard prevents

`tests/test_gate84b_order_independence.py`:

```text
each formerly failing test runs in its OWN interpreter (subprocess)
  - no neighbour can be supplying setup
NF-15 gates pass with the recorded transport
NF-15 first call == repeated call
NF-15 WITHOUT a transport still refuses the live path
the recording is committed
AC1 holds on the federal corpus
the tier-1 corpus is still substantial (>= 50 grants) - scoping is not a bypass
enrichment is identical across repeated calls
extra unknowns attributable to later layers
neither path mutates a committed fixture (sha256 before/after)
the corpus is read from a committed, git-tracked file
```

The subprocess check is the important one: it is the only way to prove
independence from *any* other test, rather than from the ones I happened to
think of.

## A third case, found while validating this gate

`test_generation_does_not_write_into_artifacts` (added in Gate 83B) counted the
files in `artifacts/auth0_validation_smoke` before and after a demo generation
and asserted the count was unchanged.

Running it while a full-suite run was in progress failed:

```text
assert {PosixPath('/...smoke'): 2497} == {PosixPath('/...smoke'): 2498}
```

The other process wrote a file into that shared directory. The assertion was
about a directory this test does not own, which is the same defect class this
gate is about — it just needed concurrency rather than ordering to expose it.

Rewritten to assert the **mechanism** instead: inside
`deterministic_demo_generation`, every redirected path constant must point into
the scratch directory and outside the repository, and must be restored
afterwards. That tests the property the original test meant to check, and does
not depend on any state the test does not own. It now passes with a full suite
running concurrently.

## A fourth case: the determinism scratch directory

Running `verify_nativeforge_demo_payload_determinism.sh` while the full suite
was in progress crashed:

```text
sqlite3.IntegrityError: UNIQUE constraint failed:
  nf_evidence_intake_records.evidence_intake_id
```

Two processes were inside `deterministic_demo_generation` at once, sharing the
fixed scratch directory `/tmp/nativeforge-demo-determinism`. One wipes that
directory at context entry, so the other lost its lifecycle database mid-run and
re-inserted an id that was still live.

Gate 83B's own doc asserted "generation is sequential, so a stable shared name
is safe". That was an assumption, not a fact, and this gate's validation pattern
— verifier alongside a suite — breaks it.

The name still has to be fixed, because one redirected path is embedded in the
payload. So the context now takes an exclusive `flock` for its duration:
concurrent generations serialise instead of corrupting each other. Doc 465 is
corrected.

## Remaining order-dependent risk

**The real risk this uncovered is not either test.** It is that a `-k`-selected
run was being read as suite health across many gates. The selection has grown
by accretion — a keyword added per gate — and nothing guarantees it covers the
tests a change affects.

Concretely:

- Every prior gate report's "broad scoped pytest: N passed, 0 failed" describes
  a selection, not the suite. Each said "full suite claimed?: NO", which was
  accurate, but the gap between the two was never measured.
- No mechanism flags a test that no gate's `-k` ever selects.

The mitigation applied here is to run the **whole suite** with no `-k` for this
gate, so the number reported is the suite's and not a selection's.
