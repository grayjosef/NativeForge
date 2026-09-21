# Gate 169 — Cross-Source Opportunity Identity / Dedupe Engine

**Verifier:** `scripts/verify_nativeforge_cross_source_identity.sh` → `RESULT=PASS`, `gate169_ready=true` (77 checks)
**Network requests during Gate 169: 0** (measured) · **fixture residue: 0** · live Gate 163 evidence byte-identical
**Migration:** `0054_cross_source_identity` (alembic head `0053` → `0054`)

---

## 1. Survey first (169A)

| primitive | classification |
|---|---|
| `opportunity_identity_versioning_service` | **AUTHORITATIVE** — L1–L4, now with 1 production caller |
| `opportunity_deadline_and_amendment_model_service` | **AUTHORITATIVE** |
| `canonical_opportunity_normalizer_service` | REUSABLE |
| `notice_ingestion_pipeline_service` | REUSABLE |
| `opportunity_discovery_service` | REUSABLE |
| `discovery_intake_dedupe_fingerprint_service` | **ADVISORY** (declares itself so) |

Two findings decided the design: **L2 and L3 were declared by the identity
service but the store admitted only L1 and L4**, and there were **zero
relationship tables**. No second identity system was built — the layered model
is sound and this gate widened and wired it.

## 2. Identity layers (169B)

```text
L1  a published identifier            (number + doc_type)   settleable
L2  a declared code, corroborated                           settleable
L3  a structured composite            (funder + year + title) provisional
L4  fuzzy fallback                                           provisional
```

Migration 0054 widens the vocabulary to all four and extends the provisional
rule from L4 to **L3 as well**. Both rest on composites nobody publishes, and
the identity service is explicit that agency identity spans three non-aligned
namespaces and **refuses to match agencies by name string**.

**The load-bearing constraint:**

```sql
CHECK (relationship <> 'SAME_AS'
       OR identity_layer IN ('L1','L2')
       OR decided_by = 'human_review')
```

"L4 can never silently create a settled canonical merge" is not a convention
here — a fuzzy SAME_AS with no human decision has **no representation at
rest**. The attempt is proven refused: `a_same_as_at_L3_requires_a_human_decision`.

## 3. Normalization (169C)

Every normalized value carries its own strength: `AUTHORITATIVE` (a published
number, reshaped only), `CORROBORATING` (a declared code), `WEAK` (any
human-written name or title). Weak values may generate *candidates*; they may
never settle a merge.

**The year is extracted before comparison and stripped from the title key.**
FY26 and FY27 titles are word-for-word identical, so they band together for
candidate generation while the year difference makes a merge impossible. A
normalizer that smoothed the year away would merge a Tribe's FY27 opportunity
into last year's closed one.

## 4. Match decisions (169D) and the hard negatives (169F)

Twelve cases, **each asserted individually** in the verifier — a summary
boolean would let one regression hide behind eleven passes.

| case | decision | layer | settleable |
|---|---|---|---|
| same number, same doc type | EXACT_MATCH | L1 | **yes** |
| forecast then posted | FORECAST_OF | L1 | no |
| aggregator republished, no number | REPUBLISHED_FROM | L3 | no |
| republished, funder name only | REVIEW_REQUIRED | L4 | no |
| two unnumbered, shared funder code | PROVISIONAL_MATCH | L3 | no |
| **same title, different year** | RECURRENCE_OF | L2 | no |
| same agency + title, different number | DISTINCT | L1 | no |
| same program, different number | DISTINCT | L1 | no |
| same deadline, unrelated | DISTINCT | L1 | no |
| same title, different funder | DISTINCT | L2 | no |
| unnumbered recurrence | RECURRENCE_OF | L3 | no |
| nothing in common | DISTINCT | L4 | no |

**The strongest guard is the simplest:** two different published opportunity
numbers mean two different solicitations. That refuses four of the negatives
before any title comparison runs.

Confidence is a **declared policy table**, not a calibrated probability —
inventing 0.83 would be fabrication wearing a decimal point. It orders a
review queue and nothing reads it to decide anything.

## 5. Two real rule gaps the negatives exposed

Both were false *negatives* — safer than false merges, but they defeated the
purpose:

1. **Exact title equality is too brittle for the republish case.** An
   aggregator dropping the agency prefix produced a different key, so the
   republish rule never fired. Fixed with a **strict-subset** relation —
   deterministic, no similarity score, no tuned cutoff — reported as weaker
   than equality.
2. **Conflicting declared funder codes weren't used as a distinguisher.** Two
   different codes are positive evidence of *difference*, not merely absent
   evidence of sameness. `same_title_different_funder` was returning
   REVIEW_REQUIRED; it now returns DISTINCT.

## 6. A merge is a row, so unmerging is deleting a row (169L)

Nothing rewrites a `canonical_id`, moves an observation or deletes a version.
A merge is a **SAME_AS relationship** with a designated primary for display.

| | observations | versions | provenance |
|---|---|---|---|
| before merge | 4 | 4 | 39 |
| during merge | 4 | 4 | 39 |
| after revocation | 4 | 4 | 39 |

**Zero rows deleted by the revocation.** Reversibility is structural, not a
feature somebody has to remember — there was never anywhere for the evidence
to go. The revoked merge stays on record, and both the approval and the
revocation must name a signer.

## 7. Bounded candidate generation (169O/P) — and a trade

Candidate generation is an indexed `(key_kind, key_value)` seek, never a scan.
Measured at three graph sizes with a fixture whose bucket width is **constant
by construction**:

| graph | mean candidates | max | statements/lookup | ms |
|---|---|---|---|---|
| 1,001 | 1.1 | 3 | 2.0 | 1.55 |
| 5,001 | 1.1 | 3 | 2.0 | 1.55 |
| 10,001 | **1.6** | 16 | **2.0** | 1.45 |

Flat across a 10× graph. `no_n_squared_scan = true`.

Getting there required excluding two key kinds from *generation*, both
measured rather than assumed:

```text
funder_and_period   25 -> 125 -> 201 candidates at 1k -> 5k -> 10k
title_band           4 ->  20 ->  40 candidates at 1k -> 5k -> 10k
```

Both grow with the corpus — a fleet has a bounded number of funders, and title
bands collide heavily. **This costs recall**: two records with the same title,
no shared funder code and no number will not become candidates. That is the L4
shape, the weakest and highest-risk match, which could never settle
automatically anyway. Recovering it needs a deliberate rate-limited sweep,
which is **not built here**. Both keys are still written, for reporting and for
that future sweep.

Cross-source identity costs **two statements per new opportunity** (11 → 13) —
a bulk key insert and one existence check that stops an orphaned key from
failing the batch. Neither is per field or per observation.

## 8. Health (169S)

Ten conditions, `identity_resolution_ready = true`, zero named gaps. Three
cannot be read from a row — false-positive controls, bounded candidates,
replay determinism — so they are **passed in from the phases that measured
them** and the report says which. Proven falsifiable: a forged readiness
claim is caught, and an unmeasured condition is named rather than assumed.

## 9. Defects found in my own instruments

Two, both in the scale harness, and the second is the sharpest of the campaign:

1. **The write path only built blocking keys for NEW opportunities**, leaving
   everything created before this gate — including the one real Grants.gov
   opportunity — invisible to candidate generation. Closed with an idempotent
   backfill rather than a per-observation read.
2. **My fixture's key space had collapsed, and I nearly blamed the design.**
   Funder, year and title derived from `index % 40`, `index % 4` and
   `index % 250` — not independent, `lcm(40, 250) = 1000` — so only 1,000 key
   combinations were reachable however many records were generated, and every
   bucket held exactly N/1000. The measurement showed candidates growing
   linearly and pointed at the lookup. The lookup was fine; my arithmetic
   wasn't. The fixture now fixes bucket width by construction, so a rising
   candidate count can only mean a scan.

A third was caught only by running the verifiers **back to back after the
commit**, which is the one sequence nothing earlier exercises:

3. **Cleanup deleted canonical rows but not their blocking keys.** The next
   run re-created the same canonical id, the write path inserted its keys
   again, and the batch died on a primary-key collision — surfacing three
   phases later as "versioning and conflict detection stopped working". Fixed
   in two places: cleanup now removes its own orphans (**before** the canonical
   rows, since the FK points that way — deleting canonical first raises
   IntegrityError, the schema correctly refusing to orphan a key), and the
   writer tolerates a pre-existing key instead of failing the batch.

Also: the Gate 168 profiler flagged my new blocking-key insert **and** its
existence check as **unattributed work**, failing the gate twice until each was
named — which is the profiler doing exactly its job.

## 10. What Gate 169 deliberately did not do

No LLM identity decisions · no silent fuzzy merge · no second identity system ·
no collapsed provenance · no canonical graph rewrite · no live source activated
· no review UI · no rate-limited recall sweep · no network request.
