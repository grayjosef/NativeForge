# 488 — Gate 86: production readiness delta

## Readiness is unchanged

| Gate | Gate 85 | Gate 86 |
| --- | --- | --- |
| production_usable | false | false |
| controlled_pilot_usable | false | false |
| customer_demo_usable | true | true |
| improvement_claim_allowed | false | false |
| confidence_level | `recorded_pre_live` | `recorded_pre_live` |

`production_usable` and `controlled_pilot_usable` are pinned `false` by
invariant, not by judgement. Nothing in Gate 86 could have moved them and
nothing did.

## What Gate 86 actually bought

A date parser, and honesty about what the parser reaches.

Before, `records_with_resolvable_freshness` was 0 and the reported cause was
partly wrong: 19 records were counted as having a deadline "the evaluator cannot
read", which was true, but conflated with the far larger group that has no
deadline or has never been checked.

After, the picture is decomposed correctly:

```text
59  records carry a deadline, and all 59 normalize
19  resolve to a freshness state - 16 expired, 3 stale, 0 fresh
40  have a deadline but have never been checked
87  have been checked but have no deadline
39  have neither
```

The product can now say, for 19 opportunities, whether the deadline has passed.
It could not say that before. That is a real capability and a small one.

## What Gate 86 did not buy

- **No currency.** Zero records are fresh. The best the corpus offers is three
  stale records whose deadlines have not yet passed and which nobody has checked
  for 57 days.
- **No coverage.** 0 live records, 0 monitored sources, unchanged.
- **No eligibility change.** The quality score is identical at 0.0865.
- **No pilot readiness.** A pilot needs current opportunities. Recovering
  freshness states proved the corpus has none.

Gate 86 made the staleness *visible* rather than *unknown*. Visible staleness is
better than unknown staleness — you can act on it — but it is not freshness, and
the distinction is the whole point of the gate.

## The blocker this exposes, stated plainly

The corpus cannot support a pilot because nothing refreshes it. That is not a
parsing problem and Gate 86 does not touch it:

```text
79 of 185 records have never been checked at all
0 of 27 seed sources are monitored
0 of 27 seed sources are terms-cleared
22 of 27 seed sources have no URL
```

Freshness needs monitoring. Monitoring needs terms clearance. Terms clearance is
legal review, not engineering. That chain is unchanged by this gate and remains
the binding constraint on pilot readiness.

## A finding logged, not acted on

All 40 ISO-format deadlines carry the identical value `2026-12-31`, none has
ever been checked, and none carries a `batch_block`. Forty records sharing one
year-end date reads like a placeholder rather than forty real deadlines.

Gate 86 does not touch them: they are already ISO, so they are outside a
normalization gate, and reclassifying committed data on suspicion is exactly the
kind of move this campaign's rules exist to prevent. If they are placeholders,
`records_with_raw_deadline` is overstated by up to 40 and a later gate should
establish that deliberately rather than by inference here.

## Status

```text
controlled customer pilot   NO_GO
production rollout          NO_GO
login live                  no
production storage          no
customer persistence        no
pen-test passed             no
```

Unchanged from Gate 85.
