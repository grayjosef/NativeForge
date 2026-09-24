# 863 — Gate 176: early signals, recurrence, and backward-error coverage

## Why this gate exists

By the time a NOFO is published, a Tribe with one grant writer has already
lost weeks it did not have. Every gate up to here made NativeForge better at
seeing what has been published. This one asks the two harder questions:

- **Forward:** can we see funding coming *before* the solicitation?
- **Backward:** can we tell what we *missed*?

The second question is the uncomfortable one, and it is the one that makes the
first trustworthy. A system that only reports what it found has no way to be
wrong. A system that looks at awards and asks "did we ever see the
solicitation that produced this?" can be shown to have failed.

## What was built

| Concern | Module |
| --- | --- |
| Signals, lifecycle, correlation | `early_funding_signal_service.py` |
| Backward-error detection, scorecard | `award_miss_detection_service.py` |
| Cadence, expectation, absence | `program_recurrence_service.py` |
| 21 adversarial cases | `early_signal_gold_corpus_service.py` |
| 10 named detectors + their proofs | `early_signal_self_health_service.py` |
| The 8 critical access paths | `early_signal_repository_service.py` |
| Durable state and its CHECKs | `alembic/versions/0062_early_signal_intelligence.py` |

## The load-bearing properties

### A signal is evidence, never an opportunity

Thirteen signal types across an eight-state lifecycle. Every row carries
`creates_opportunity = false` and `auto_onboarding_permitted = false` — stated
on the row so nothing downstream can read it as licence, enforced by
`signal_invariant_failures`, and enforced again as CHECK constraints in 0062
so a writer that bypasses the service still cannot store the lie.

This matters because the failure mode is not a crash. A budget line that
quietly became a "funding opportunity" would be a fabrication presented to a
Tribal government as a real programme they could apply for.

Linking requires an opportunity that **already exists**.
`link_signal_to_opportunity` refuses rather than creates. Correlation
*proposes* — corroborates, likely precursor, possible same programme — and
merges nothing; two traces sharing only a funder reach `UNRESOLVED` rather
than a convenient answer.

### The most important measurement in this gate is FALSE

```text
real_award_evidence_available_for_miss_detection=false
```

All 2,757 award rows are Gate 138 demo fixtures on the protected demo
organisation. None carries a `source_opportunity_id`. The backward-error
detector is built, proven, and has nothing real to detect against.

The verifier asserts this **false** deliberately. If it ever flips to true,
either real award data has been ingested or the fixtures have been
contaminated, and both deserve a human's attention.

Left unguarded, running the detector across that table would have produced
2,757 "misses" — every one a fixture for a solicitation that never existed.
So a miss carries the provenance of its award, the scorecard counts REAL and
DEMO separately, and 0062 makes `award_is_demo_fixture = 1` with
`counts_toward_real_metrics = 1` unrepresentable.

### The scorecard refuses to report a percentage

The denominator — how much Native-relevant funding exists — is unknown, and
this system has no way to learn it. A coverage percentage would be a number we
made up, and it would be believed. `build_coverage_scorecard` reports counts,
`coverage_percentage` is always `None`, `denominator_known` is always `false`,
and `why_no_coverage_percentage` says so in the payload.

### Below three cycles, nothing is forecast

Recurrence rests on a decisive identity basis — assistance listing, programme
number, stable source path, programme authority — and **never** on title
similarity, because a cadence derived from a name collision is worse than no
cadence at all. A renamed programme keeps its history; a lookalike gets
`UNKNOWN` and a review flag.

One observation plus an assumption looks exactly like intelligence until the
year it is wrong, so `EXPECTED`/`POSSIBLE` below `MINIMUM_CYCLES_FOR_CADENCE`
is refused in the model and again by
`ck_nf_program_recurrences_expectation_needs_enough_history`.

### An absence cites the history that justifies it

`EXPECTED_RECURRING_PROGRAM_ABSENT` is derived from something *not* happening,
so there are no payload bytes to point at. The gate's own evidence invariant
rejected every one of them as `signal_has_no_evidence` — correctly, because a
claim about the world with nothing behind it is not evidence.

The claim does have evidence: the recurrence record, its observed cycles and
its projected window. The signal simply was not pointing at it. It now carries
`document_ref = "recurrence:<id>"`, so a reviewer asking "why do you think
this is missing" gets the history.

## What the instruments found

Roughly a third of this gate's defects were in **measurements**, not in the
system. Recorded here because the pattern keeps repeating.

**The open-queue query was wrong, and the query plan was right.**
`WHERE signal_state IN (4 of 8) LIMIT 200` with no ordering asks for "any 200
open signals". Half the table qualifies, so a scan genuinely *is* the cheapest
plan. Adding an index would have been cargo cult. The defect was that a triage
queue returning an arbitrary 200 rows is not a queue — a human working it
cannot tell progress from a fresh random sample. With `ORDER BY observed_at`
and a **partial** index over the four open states, the same path became an
ordered index walk.

**The scan detector could not read a query plan.** SQLite prints
`SCAN <table>` for a full scan and `SCAN <table> USING INDEX <name>` for an
ordered index walk. The check tested for the substring `SCAN <table>`, which
the second form contains — so it reported the *fastest* query in the set as a
table scan. The module's own comment stated the correct rule while the code
beneath it did the opposite; the comment was not the thing being executed.
`plan_is_a_table_scan` now distinguishes them, and `explain_is_falsifiable`
proves the detector still fires against a control query nothing can serve.

**A self-health fixture broke two things at once.** Zeroing a recurrence's
history while leaving `EXPECTED` standing is *both* zero-history and
expected-from-insufficient-history. Both detectors fired, so the fixture
proved neither cleanly. The specificity check — `no_other_detector_fired` — is
what caught it, and it is the check that stops a fire-on-everything detector
from scoring perfectly.

**A corpus case was wrong, not the model.** `GRANTEE_ANNOUNCEMENT` was
expected to be forward-looking. It means "a grantee describes money from a
programme we never saw" — backward-looking miss evidence. The model was right.

**The miss trace dropped the evidence it was handed.** The caller supplies
`evidence_ref`, the miss row recorded it, and `build_signal` never received
it — so the trace failed its own evidence invariant while the row beside it
happily recorded the reference.

## Scale

120,000 historical programme instances, 120,000 signals, 20,000 misses.

| Path | Plan | ms |
| --- | --- | --- |
| signals by programme | `SEARCH ... USING INDEX ix_..._program` | 0.33 |
| signals by source | `SEARCH ... USING INDEX ix_..._source` | 1.13 |
| unresolved signals | `SCAN ... USING INDEX ix_..._open` (partial, ordered) | 1.14 |
| award misses | `SEARCH ... USING INDEX ix_..._queue` | 1.01 |
| recurrence history | `SEARCH ... USING INDEX ix_..._history` | 0.21 |
| expected but absent | `SEARCH ... USING INDEX ix_..._absent` | 0.94 |
| coverage gap linkage | `SEARCH ... USING INDEX ix_..._gap` | 0.32 |
| signals linked to opportunity | `SEARCH ... USING INDEX ix_..._linked` | 0.20 |

Every query returns rows: a query returning nothing has a beautiful plan and
proves nothing. `CRITICAL_QUERIES` is the single registry both the service and
the scale proof read, so the plans cannot drift from the SQL that runs.

## What this gate does NOT claim

- **The corpus is not the world.** Twenty-one cases we thought of. Recall and
  precision are measured against them and stay `INFO` in the verifier.
  Promoting them to structural claims would turn "we handled the situations we
  imagined" into "our coverage is perfect".
- **No real NOFO or award has been evaluated.** Every byte is a synthetic
  fixture; the socket count is zero.
- **No source was onboarded**, no real organisation touched, no network call
  made.

## Running it

```bash
bash scripts/verify_nativeforge_early_signal_gate176.sh
```

Every temporal case pins its own `now`. Gate 172 shipped a verifier asserting
a state that was true the day it was written and false a week later; a corpus
whose answers depend on the wall clock is a time bomb with a test suite
wrapped around it.
