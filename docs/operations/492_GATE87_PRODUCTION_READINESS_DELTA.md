# 492 — Gate 87: production readiness delta

## Readiness is unchanged

| Gate | Gate 86 | Gate 87 |
| --- | --- | --- |
| production_usable | false | false |
| controlled_pilot_usable | false | false |
| customer_demo_usable | true | true |
| improvement_claim_allowed | false | false |
| confidence_level | `recorded_pre_live` | `recorded_pre_live` |

Pinned by invariant, not by judgement.

## What Gate 87 changed

It lowered confidence. That is the whole delta.

```text
before   59 deadlines, treated alike
after    19 verified, 40 suspected placeholder, 0 unverified, 0 unknown
```

Two-thirds of the corpus's deadlines will not stand up. Nothing was deleted,
nothing was hidden, and no date was declared false — the records are all still
there with their raw values intact. What changed is that the baseline no longer
lets a parsed date pass for a trusted one.

## What it did not change

- **Freshness: still 19** — 16 expired, 3 stale, 0 fresh. The 40 never produced
  a freshness state, so classifying them removed nothing.
- **Quality score: still 0.0865.** It counts cited eligibility and exclusion
  verdicts; deadlines are not part of it.
- **Coverage: still 0 live records, 0 monitored sources.**
- **Corpus: still 185 records.**

## The direction of travel is worth stating

Three gates in sequence:

```text
Gate 85   0 of 185 records had a resolvable freshness state
Gate 86   19 recovered - all of them expired or stale, none fresh
Gate 87   of the 59 deadlines behind that, only 19 can be trusted at all
```

Each gate made the picture more accurate and less flattering. That is the
correct direction for a baseline. A campaign whose measurements only ever
improve is a campaign measuring the wrong things.

## The blocker is unchanged and now better evidenced

```text
79 of 185 records have never been checked
40 of 59 deadlines cannot be verified
 0 of 27 seed sources are monitored
 0 of 27 seed sources are terms-cleared
22 of 27 seed sources have no URL
```

A pilot needs current opportunities with deadlines a customer can rely on. The
corpus has 19 verified deadlines, every one of them expired or stale.

Freshness needs monitoring. Monitoring needs terms clearance. Terms clearance is
legal review, not engineering. That chain is untouched by this gate and remains
the binding constraint.

## What would actually resolve the 40

Not more analysis of the committed data — Gate 87 has taken that as far as it
goes. Resolving them needs one of:

1. **A live or recorded fetch** of the 39 records lacking an upstream id,
   producing a real close date to compare against. Out of scope for every gate
   so far, and blocked behind terms clearance.
2. **A committed provenance record** from whoever generated
   `nf13_real_ingested_grants.json`, stating whether the deadline field was
   populated or defaulted.

Until one exists, `suspected_placeholder` is the most precise status the
evidence supports, and the 40 records stay visible and counted with their
reasons attached.

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

Unchanged from Gate 86.
