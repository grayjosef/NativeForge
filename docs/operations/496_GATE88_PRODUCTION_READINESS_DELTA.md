# 496 — Gate 88: production readiness delta

## Readiness is unchanged

| Gate | Gate 87 | Gate 88 |
| --- | --- | --- |
| production_usable | false | false |
| controlled_pilot_usable | false | false |
| customer_demo_usable | true | true |
| improvement_claim_allowed | false | false |
| confidence_level | `recorded_pre_live` | `recorded_pre_live` |

Pinned by invariant, not by judgement.

A new figure sits alongside it: `provenance_confidence_level`, reading
`predominantly_asserted`. The corpus-level confidence label and the
record-level one now agree, which they did not before — `recorded_pre_live`
implied a corpus of recordings, and 90% of it turns out to be assertions.

## What Gate 88 changed

It lowered evidential standing. That is the whole delta.

```text
before   162 records reported as recorded, treated alike
after     18 verified by artifact
         166 asserted, of which 38 rest on booleans alone
           1 circular
```

Nothing was deleted, hidden, or rewritten. No record was declared fake, and
`synthetic_declared_records` is 0. Every record keeps its flags, its content and
its place in the corpus. What changed is that a boolean no longer passes for
evidence.

## What it did not change

- **Corpus composition: still 162 / 23 / 0 / 0.** Gate 85's axis is untouched.
- **Deadlines: still 59 raw, 19 verified.** Gate 87's findings stand.
- **Freshness: still 19** — 16 expired, 3 stale, 0 fresh.
- **Quality score: still 0.0865.**
- **Coverage: still 0 live records, 0 monitored sources.**

## An inversion worth recording

The 17 `nf14-mixed-*` records carry `real_fetch: false` and `fixture: true` —
the weakest self-assertion in the corpus. They are also the best-evidenced
records in it, because somebody committed the 466 KB transport alongside them.

Meanwhile 38 records asserting `real_fetch: true` have no artefact at all.

**Self-assertion and evidence run in opposite directions here.** Any future
work that ranks corpus quality by what records claim about themselves will get
this exactly backwards.

## The direction of travel

Four gates in sequence:

```text
Gate 85   0 of 185 records had a resolvable freshness state
Gate 86   19 recovered - all expired or stale, none fresh
Gate 87   of the 59 deadlines behind that, only 19 can be trusted
Gate 88   of the 162 records reported as recorded, only 18 are evidenced
```

Each gate made the picture more accurate and less flattering. That is the
correct direction for a baseline, and it is worth stating plainly that four
consecutive audits have found the previous number optimistic. The pattern is
consistent: every figure that rested on a self-describing flag turned out to
mean less than it appeared to.

## The blocker is unchanged and better evidenced again

```text
167 of 185 records have no independent recording artefact
 38 of those rest on booleans alone
 79 of 185 records have never been checked
 40 of  59 deadlines cannot be verified
  0 of  27 seed sources are monitored
  0 of  27 seed sources are terms-cleared
 22 of  27 seed sources have no URL
```

A pilot needs opportunities a customer can rely on. The corpus has 18 records
with an evidenced recording, 19 verified deadlines, and every one of those
deadlines is expired or stale.

Freshness needs monitoring. Monitoring needs terms clearance. Terms clearance is
legal review, not engineering. Unchanged, and still the binding constraint.

## What would actually resolve the 166

Not more analysis of committed data — Gate 88 has taken that as far as it goes,
as Gate 87 did for deadlines. It needs one of:

1. **A transport artefact per record** — a recording carrying data the row
   cannot supply. Requires a fetch, blocked behind terms clearance.
2. **A committed provenance record** from whoever produced
   `nf13_real_ingested_grants.json`, `la_scaled_federal_grants.json` and the
   tier-2/tier-3 batches, stating how each was populated.

Option 2 costs nothing and is not blocked. For 38 records it would settle the
question either way, and it is the cheapest honest move available.

## Status

```text
controlled customer pilot   NO_GO
production rollout          NO_GO
login live                  no
production storage          no
customer persistence        no
pen-test passed             no
live SC coverage            none
live federal coverage       none
sources monitored           0
real live notices parsed    0
65% improvement claimed     no
```

Unchanged from Gate 87.
