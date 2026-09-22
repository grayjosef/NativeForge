# Gate 171 — Real Multi-Source Operational Proof

**Verifier:** `scripts/verify_nativeforge_real_multisource_gate171.sh` → `RESULT=PASS`, `gate171_ready=true` (118 checks)
**Migrations:** `0056_provisional_identity_uniqueness`, `0057_identity_lookup_index` (head `0055` → `0057`)
**Live requests: 5, all operator-approved. 0 after the live phase.**
**`REAL_OVERLAP_OBSERVED=false`** — no overlap was hunted and none was manufactured.

---

## 1. Three real source families

| | Grants.gov | BIA TTGP | Federal Register |
|---|---|---|---|
| shape | structured API (POST) | HTML program page | JSON API, paginated |
| adapter | `grants_gov_search2` | `bia_program_page_html` | `federal_register_documents_json` |
| identity layer | L1 | **L4 provisional** | **L1** |
| real observations | 1 (Gate 163) | **1** | **20** |
| provenance fields | 10 | 4 | 8 |
| health | healthy | **degraded (named gap)** | healthy |

The identity layer is **chosen from what each source publishes**, not from its
name. A program page that publishes no opportunity number cannot have a
settleable identity; an API that publishes a document number can.

## 2. The network, exactly

| # | request | status | bytes | outcome |
|---|---|---|---|---|
| 1 | `www.bia.gov/robots.txt` | — | — | dispatched, **response discarded by a defect** |
| 2 | `www.bia.gov/robots.txt` *(operator-approved replacement)* | 200 | 2,027 | `allowed` |
| 3 | `www.federalregister.gov/robots.txt` | 200 | 320 | `allowed` |
| 4 | `www.bia.gov/service/grants/ttgp/apply-ttgp-grant` | 200 | 49,354 | persisted, hash verified |
| 5 | `www.federalregister.gov/api/v1/documents.json?…` | 200 | 19,642 | persisted, hash verified |

Request 1 was spent by two defects of mine. The runner read
`result["response"]` — a key `execute_request` does not return — so a dispatch
that had already happened was reported as "no request was made". A prior run
had been **blocked** before dispatch for a missing policy and derived
`status=None` into an `unreachable` verdict: a caller's refusal about to be
filed as a publisher's restriction, stopped only by a `fact_status` CHECK
constraint. Both are fixed; the runner now reads `dispatched` directly and a
blocked dispatch can never become a verdict.

The Federal Register endpoint was **PROPOSED, not established** by this
repository. It was authorized for exactly one test and it was correct — path,
parameters and envelope all matched.

## 3. The defect this gate existed to find

```sql
-- Gate 167
CREATE UNIQUE INDEX uq_nf_canonical_opportunities_identity
  ON nf_canonical_opportunities (normalized_opportunity_number, doc_type)
```

Correct while every source published a number. Every L4 provisional row stores
`''` and `'unknown'`, so **the graph could hold exactly one provisional
opportunity, ever.** The real BIA page took the slot; the next document-shaped
record was an `IntegrityError`, and because a failure rolls back its batch it
took 500 valid records with it.

At a thousand sources this is not an edge case — most agency program pages
publish no opportunity number.

**Migration 0056** makes the index partial:

```sql
... WHERE normalized_opportunity_number <> ''
```

Uniqueness applies to a **published** identity. A record without one is already
unique by `canonical_id`, derived from its L4 fuzzy key.

### And then 0056 broke every identity lookup

The back-to-back battery caught what the full suite could not: a partial index
only serves a query whose predicate **implies** the index predicate. The write
path's lookup does not carry `normalized_opportunity_number <> ''`, so it
became a full table scan — **0.09 ms → 9.85 ms at 50,000 rows**, and linear
from there. A scan is correct, just slow, which is exactly why 13,241 tests
passed over it.

`0057` adds a **second, non-unique** index on the same columns. Two indexes
because there are two jobs: the partial one is the *constraint*, the full one
is the *access path*. Adding `<> ''` to the query was rejected — it couples
every caller to an index predicate and returns nothing for the provisional
rows 0056 exists to support.

**Index use is the invariant; latency is INFO.** A scan is *fastest* on a
small table, so a latency threshold would look healthiest exactly where the
defect hides, and machine variance would turn a gate into a coin flip.

| rows | plan | lookup |
|---|---|---|
| 1,022 | `SEARCH … USING INDEX ix_…_identity_lookup` | 0.018 ms |
| 10,022 | same | 0.017 ms |
| 50,022 | same | 0.028 ms |

Flat, not linear. All three planner cases — populated, nonexistent, and the
provisional empty-number shape — use the index.

### The sequential lineage failure: what was ruled out, and what was not

Gate 168's lineage checks failed **only** in the battery. Four mechanisms were
tested and rejected with evidence rather than dismissed:

| hypothesis | result |
|---|---|
| the 0056 index regression caused it | **rejected** — downgraded to 0056, ran the exact 167→168 sequence, both checks passed |
| cleanup leaves orphans or dangling pointers | **rejected** — 0 dangling `current_version_id`, 0 orphan versions, counts consistent |
| replay against accumulated dirty state | **rejected** — the chain held across repeated runs |
| `created_at` ties making the sort ambiguous | **rejected** — microsecond timestamps, 6 distinct of 6 |

**The root cause was not identified.** The one precondition that could not be
reproduced is the one that produced it: the battery ran immediately after a
two-hour full suite, which writes to the same database. That is stated as an
open unknown rather than closed with a plausible story.

What the investigation *did* establish was a real gap, and that is fixed:

- Gate 167's verifier has **no preclean**, so the phase runs on inherited
  state. Against leftovers its writes become idempotent replays and its
  assertions silently describe stale rows. The phase now reports
  `g_started_from_a_clean_fixture` and `g_versions_present_before_this_run` —
  reported, not enforced, because a phase that deleted rows to suit itself
  would be worse than one that starts dirty.
- `ORDER BY created_at` was **ambiguous**: `versions[-1]` meant whatever the
  query plan returned. Now `ORDER BY created_at, version_id`.
- The supersession links are the authoritative order, so the check walks the
  chain and asserts it agrees with the timestamp order, plus
  `g_exactly_one_chain_root`. A bare `g_lineage_is_a_chain=False` sent this
  gate hunting a cleanup bug when the question was which version the phase
  believed was newest.

`sequential_lineage_isolation` is the permanent regression: 167-owned setup →
cleanup → 168 lineage setup, **each step in its own process**, because
in-process reuse would share the very state it exists to detect.

### Proven, not assumed (171W)

| | |
|---|---|
| five L4 records written in one batch | all `inserted`, canonical ids distinct |
| every L4 row | `is_provisional = 1`, empty number, `doc_type = unknown` |
| two sources, one published number | **one** canonical row — L1 uniqueness intact |
| `PROVISIONAL_MATCH` | still **not** machine-settleable |
| migration round trip | `0056 → 0055 → 0056`, index correct at each step |

## 4. Canonical outcomes (171J)

| classification | count |
|---|---|
| `NEW_CANONICAL` | **21** |
| `MATCH_EXISTING_CANONICAL` · `PROVISIONAL_MATCH` · `RELATED` · `DISTINCT` · `REVIEW_REQUIRED` | 0 |

`REAL_OVERLAP_OBSERVED=false`. The 21 real records did **not** converge, and
saying otherwise would be the one claim in this campaign that could not be
trusted. Convergence, conflict and corroboration behaviour remain proven
structurally on source-shaped fixtures.

**What is REAL versus what is STRUCTURAL:**

| proven REAL | proven STRUCTURALLY (fixtures, no network) |
|---|---|
| heterogeneous collection | cross-source same-opportunity convergence |
| persisted evidence, hashes verified | conflict behaviour |
| normalization through the existing path | corroboration behaviour |
| canonical writes, identity layer choice | overlap identity behaviour |
| independent field provenance | deadline / status / funding change classification |
| fleet health, zero-network replay | pagination, crawl bounds, failure isolation |

## 5. Change intelligence on real data (171N)

**135 real change events, every one `FIRST_OBSERVED`.** 0 conflicts, 0
corroborations — correct, because there is no overlap. No change was
manufactured to produce a more interesting number.

## 6. Replay (171S)

Both payloads replayed with the socket refused: identical bytes, identical
sha256, identical records, identical identity layers (L4 / L1), identical
provenance, **graph completely unchanged**, `network_requests = 0`. Idempotence
is checked by comparing graph state before and after, not by trusting the
writer's own report.

## 7. The BIA evidence gap (171Z)

```text
bia_robots_body_retained=false
bia_robots_evidence_gap_named=true
```

The replacement robots request succeeded and the row insert then failed on a
CHECK constraint — this table's `fact_status` vocabulary is migration 0049's
`('live_fetch', …)`, not the identically-named tuple used by the tenant
tables. The bytes went with the process.

Retained: **status 200, 2,027 bytes, sha256, derived verdict `allowed`.** The
evidence reference says `body-not-retained` and fleet health reports BIA as
**degraded** with the gap named. It is **known, non-blocking for this gate, and
permanent for that request** — no refetch, and no fabricated payload row for
bytes that no longer exist.

## 8. Scale, and the rule it produced (171R / 171X)

Mixed fleet, all three adapter shapes interleaved:

| | |
|---|---|
| attempted | 6,000 |
| **landed** | **6,000** |
| rejected / failed / rolled-back batches | 0 / 0 / 0 |
| statements per landed observation | **1.04** |
| observations/sec (landed) | 443 |
| DB growth | 98.43 MB · provenance rows 44,000 · change events 38,000 |
| peak process memory | 102 MB (process, not writer — stated as such) |

**A throughput number is invalid without a landed-row count.** This phase first
reported **3,490 observations/sec** for a run in which *every batch rolled
back and nothing was written* — 108 statements, 0.0 MB growth. The rate was
arithmetically correct and meaningless. The cause was a hand-written fixture
inventing `lifecycle_state: "open"`, which is not in the canonical vocabulary,
and one bad record rolling back its whole batch of 500.

Both defects are permanently covered by tests, and the phase now refuses to
call a rate "write throughput" when nothing landed.

**Gate 170's UNKNOWN is carried forward verbatim**: ~256 obs/sec at 50k against
the 559/sec Gate 168 shipped, with the split between added indexed-row cost and
machine variance **not measured**. No causation is asserted without an A/B.

## 9. Genericity (171Q / 171AD)

`generic_layer_source_leaks = 0`, `identity_branches_in_generic_layers = 0`,
across 16 enumerated generic files, with the scanner proven falsifiable by
planting a leak. Seven in-code mentions survive comment-and-docstring
stripping; each is an explicit allowlist entry naming the clause that permits
it, and a **stale entry fails** — which caught one redundant entry of mine.

Source names live in 17 files that are allowed to name them: adapters,
descriptor tables, attribution modules, fixtures, authorization data.

## 10. Validation

| | |
|---|---|
| `verify_nativeforge_real_multisource_gate171.sh` | `RESULT=PASS`, 118 checks |
| `tests/test_gate171_real_multisource.py` | 38 passed |
| head-pin battery (63, 119, 120, sprint20, 153) | green after artifact regeneration |
| full suite | see gate report |
| 167 · 168 · 169 · 170 · 171 back to back | see gate report |
| Gate 163 evidence | byte-identical **by content hash** |
| funding-source requests after the live phase | **0** |

The Gate 163 evidence check was tightened rather than widened: it asserted
`sizes == [42, 11131]`, which became false the moment Gate 171 collected two
more payloads. It now matches the two original payloads **by sha256** —
strictly stronger than a size comparison — and requires every additional
payload to belong to an operator-approved source.

---

## The campaign lesson

**Correctness tests do not substitute for access-path or sequential-state
invariants.**

The authoritative suite was **green at 13,241 passing** while both of these
were live: an identity lookup that had become a full table scan, and a
lineage assertion that could describe leftover rows. Neither is a wrong
*answer* — a scan returns the right row, and a replayed write leaves a valid
chain. Only a check that asserts **how** the answer was reached, or **what
state** it was reached from, can see either.

The back-to-back battery has now caught a defect in three consecutive gates.
It is load-bearing, and it is worth the wall-clock.

## What this gate did not do

- did not hunt for an overlap, or spend a request looking for one
- did not refetch either source, or repair the BIA robots gap with a request
- did not substitute a source or activate an alternate
- did not manufacture a real change, conflict or corroboration
- did not reopen historical performance archaeology
- did not weaken L1 uniqueness or provisional semantics to make room for L4
