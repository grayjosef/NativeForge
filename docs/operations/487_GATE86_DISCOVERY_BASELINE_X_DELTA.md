# 487 — Gate 86C/86D: Discovery Baseline X delta

What changed in the baseline, and what did not.


> **Superseded in part by Gate 87.** This page is preserved as the
> post-normalization freshness-recovery baseline. Its numbers are not edited.
>
> Gate 86 established that all 59 deadlines normalize. Gate 87 asked the
> next question - whether they can be *trusted* - and found that only 19 can.
> The other 40 are `suspected_placeholder`: a single identical date across a
> whole batch, with no record in it ever having been checked.
>
> Freshness is unaffected and still reads 19 (16 expired, 3 stale, 0 fresh),
> because those 40 never produced a freshness state to begin with. Nothing was
> deleted, hidden, or rewritten. See docs 489, 490, 491.
>
> **Also superseded in part by Gate 88**, which audited corpus provenance
> rather than deadlines. Nothing on this page changes: 59 raw deadlines,
> 59 normalized, 19 resolvable freshness states. See docs 493, 494, 495.
>
> The sequence to read these in: 483 is the pre-normalization baseline, 487
> (this page) is the post-normalization one, and 491 carries the current
> deadline picture.

## The delta

| Metric | Gate 85 | Gate 86 | Note |
| --- | --- | --- | --- |
| total_records | 185 | 185 | unchanged |
| records_with_raw_deadline | 59 | 59 | **unchanged, and must be** |
| records_with_normalized_deadline | not measured | 59 | new |
| records_with_unparseable_deadline | 19 | 0 | metric redefined, see below |
| records_with_ambiguous_deadline | not measured | 0 | new |
| deadline_normalization_rate | not measured | 1.0 | of records that have a deadline |
| **records_with_resolvable_freshness** | **0** | **19** | the gate's purpose |
| records_never_checked | 79 | 79 | unchanged; parsing cannot help |
| live_records | 0 | 0 | unchanged |
| monitored_sources | 0 | 0 | unchanged |
| baseline_quality_score | 0.0865 | **0.0865** | unchanged, see below |
| improvement_claim_allowed | false | false | unchanged |

## Freshness before and after

```text
             Gate 85    Gate 86
fresh              0          0
amended            0          0
expired            0         16
stale              0          3
superseded         0          0
unknown          185        166
```

**Zero fresh, before and after.** The 19 states recovered are 16 expired and 3
stale. Gate 86 did not make the corpus look better; it showed that the only
deadlines anyone can check have all passed or gone stale. Those records stay
visible and counted — `test_expired_and_stale_records_are_not_hidden` pins it.

## Why 19 and not 59

59 records carry a deadline and all 59 normalize. Only 19 resolve to a freshness
state, because a state requires **both** a normalized deadline and a timestamp
saying somebody looked:

| | has checked-at | records | can resolve |
| --- | --- | --- | --- |
| `MM/DD/YYYY` deadline | yes | 19 | **yes** |
| `YYYY-MM-DD` deadline | no | 40 | no |
| no deadline | yes | 87 | no |
| no deadline | no | 39 | no |

The 40 ISO-deadline records were never a parsing problem — they are already ISO.
They have no `ingested_at` at all, so they stay `never_checked` until monitoring
exists. Giving them a freshness state would be inventing the fact that somebody
looked.

Two invariants hold that line. In the contract,
`resolvable_freshness_exceeds_normalized_deadlines` and
`normalized_deadlines_exceed_raw_deadlines` bound the aggregate. In the baseline
service, every record is checked individually, because an aggregate bound would
still pass if one record borrowed another's entitlement.

## How the 59 normalized

| Route | Records | What settled the format |
| --- | --- | --- |
| `exact` | 40 | already ISO |
| `structural` | 13 | a field over 12 cannot be a month |
| `convention_declared` | 6 | Grants.gov convention, declared by the caller |

The 6 are the both-halves-≤12 dates: `07/01`, `07/07`, `08/03`, `08/07`, and
`09/01` twice. They carry no structural proof of their own and normalize only
because the caller declared the source's convention — which doc 485 shows the
corpus earns, since 10 values in the same batch are structurally month-first.

## Why this is not fabricated freshness

- Every normalized date is a rearrangement of digits already in the committed
  record. An invariant checks that the year, month and day each appear as a
  number in the raw string.
- Raw and normalized deadline counts are reported separately and are both 59.
  Normalization cannot make the corpus appear to have gained a deadline.
- No record gained a `checked-at`. The 79 never-checked records are still 79.
- No committed fixture changed. The fixture hash is identical before and after
  a full run, checked by both the test suite and the generator script.
- `opportunity_freshness_service` is unchanged. The states come from the same
  evaluator Gate 85 used, given dates it can read.

## Why this is not live coverage

Nothing was fetched. `network_access_performed` is `false`,
`live_coverage_claimed` is `false`, `live_records` is 0, and
`monitored_sources` is 0. The parser reads strings that were already committed
to the repository; it has no network access and imports no HTTP client.

That the recovered states are mostly `expired` is itself evidence of the
absence of live coverage: a monitored corpus would not be six weeks stale.

## Impact on the quality score

**None. It stays at 0.0865.**

`baseline_quality_score` is the share of records for which the machinery can
produce a cited eligibility or exclusion verdict — 16 of 185. Deadlines are not
part of that calculation, so a deadline gate cannot move it, and
`test_gate86_does_not_touch_eligibility_or_source_coverage` asserts the exact
value so a future change cannot quietly slip it upward.

This is worth stating plainly: Gate 86 fixed a real defect and the headline
number did not move. That is what it looks like when a metric measures the thing
it claims to measure.

## Why 65% improvement is still not claimed

There is no improvement figure here at all, and there is nothing to compute one
from.

The only number that moved is `records_with_resolvable_freshness`, 0 → 19. That
is 19 of 185 records, all of them expired or stale, and it reflects a parser
being written rather than the corpus becoming more current. Expressing it as a
percentage improvement would take a fix to a formatting bug and dress it as
progress in coverage.

`improvement_claim_allowed` remains `false`. The artifact writer still refuses
to emit any document containing `65% improvement`, `improvement over`, or
`live coverage`, and the generator script re-scans the written JSON, Markdown
and CSV on disk.
