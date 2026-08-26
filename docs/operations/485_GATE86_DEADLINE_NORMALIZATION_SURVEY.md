# 485 — Gate 86A: deadline and freshness surface survey

Surveyed before patching. The headline finding changes what this gate can
honestly claim, so it goes first.

## Headline: normalization can recover at most 19 of 185 records

Gate 85 reported `records_with_resolvable_freshness = 0` with three causes:

```text
79   never checked            no ingested_at at all
87   no close date            checked, but no application_deadline
19   unparseable close date   checked, has a deadline, in MM/DD/YYYY
```

Only the third group is a parsing problem. Cross-tabulating deadline format
against whether a record has ever been checked:

| deadline format | has checked-at | records |
| --- | --- | --- |
| `MM/DD/YYYY` | yes | **19** |
| `YYYY-MM-DD` | **no** | 40 |
| none / empty | yes | 87 |
| none / empty | no | 39 |

**Every record with both a deadline and a checked-at timestamp is in the 19.**
The 40 ISO-format deadlines have no `ingested_at` at all, so they stay
`never_checked` no matter what the parser does — for them this was never a
parsing problem, and normalization is a no-op because they are already ISO.

So the ceiling for this gate is 19 records, not 59. Anything above 19 would mean
freshness was invented for a record nobody has checked.

## The recovered states are 16 expired and 3 stale. Zero fresh.

Running the existing evaluator over the 19 with their dates normalized, at
`now = 2026-08-25`:

```text
expired  16   close dates from 2026-07-01 to 2026-08-14, 11 to 55 days past
stale     3   close dates 2026-08-31 and 2026-09-01, not checked for 57 days
fresh     0
```

Gate 86 does not make the corpus look better. It reveals that the only records
whose deadlines can be checked have all either closed or gone stale. That is a
worse-looking and more honest number, and it is the whole reason
"do not hide expired/stale records" is a rule.

## Date formats present

`application_deadline` is the only deadline field in the corpus. Every distinct
shape, across all 185 records:

```text
74   None                       key present, null
30   ''                         key present, empty string
40   '2026-12-31'               ISO YYYY-MM-DD
19   '07/24/2026'               MM/DD/YYYY, zero-padded
22   (key absent)
```

`ingested_at` is the only other date field: 106 records, all full ISO-8601
timestamps with offset (`2026-06-29T21:38:46.776483+00:00`). All parse already.

No `M/D/YYYY` (single-digit) value exists in the committed corpus. The contract
supports it anyway, because the next batch may carry one and a parser that
silently fails on it would recreate exactly this gap.

## Why the current freshness count is zero

`opportunity_freshness_service._days_between` calls `date.fromisoformat` on the
first 10 characters and returns `None` on `ValueError`. `07/24/2026` raises,
`_days_between` returns `None`, and the evaluator records
`close_date_or_now_unparseable` and leaves the state `unknown`.

The evaluator is not wrong. Its docstring is explicit that it takes ISO strings
and that it deliberately avoids owning a timezone or locale policy. Teaching it
to guess at slash dates would push a locale decision into a module that
correctly refuses to make one.

**So normalization belongs upstream of the evaluator, not inside it.** Nothing
in `opportunity_freshness_service.py` changes in this gate.

## Is `07/01/2026` July 1 or January 7?

This is the real design question, and the corpus answers it rather than leaving
it to assumption.

All 19 slash-format records come from one homogeneous batch:

```text
batch_block              la_scale_federal   19/19
fetch_mode               live               19/19
grants_gov_opportunity_id present           19/19
```

Within that batch, 10 of the distinct values have a second field greater than
12:

```text
07/14  07/15  07/16  07/17  07/22  07/23  07/24  07/27  08/14  08/31
```

A second field of 31 cannot be a month, so those are structurally `MM/DD/YYYY`
and cannot be read any other way. The same field, in the same batch, from the
same source, is therefore `MM/DD/YYYY` for the remaining values too. Grants.gov
emits `MM/DD/YYYY`, which agrees.

Five distinct values have both halves ≤ 12 and so carry no structural proof of
their own:

```text
07/01  07/07  08/03  08/07  09/01
```

The parser distinguishes these two situations rather than flattening them.
A date that proves its own format is normalized at `parse_confidence:
structural`. A date that needs the batch convention is normalized only when a
convention is **explicitly declared by the caller**, at `parse_confidence:
convention_declared`. With no declared convention, a both-halves-≤12 slash date
stays unnormalized and is reported as ambiguous.

That keeps "ambiguous dates must remain unnormalized" true in the general case
without throwing away five records whose format is actually known.

## Existing date utilities

There is no shared date parser. `_days_between` is a private helper inside the
freshness service; `nofo_text_extraction_service` and
`nofo_amendment_detector_service` handle spans and statuses, not dates. Gate 86
introduces the first one, as a pure-function contract service consistent with
the rest of the campaign.

## A finding this gate does not act on

All 40 ISO deadlines carry the identical value `2026-12-31`, none has ever been
checked, and none has a `batch_block`. Forty records sharing one year-end date
reads like a placeholder rather than forty real deadlines.

Gate 86 does not touch them. They are already ISO, so they are outside a
normalization gate, and reclassifying them would be changing committed data on
suspicion. Recorded here so a later gate can look at it deliberately.

## What this gate must not do

- Not invent a deadline for the 126 records that have none.
- Not infer a year, a day, or a month that the raw string does not contain.
- Not give freshness to any of the 79 records nobody has checked.
- Not hide the 16 expired and 3 stale results that normalization exposes.
- Not modify `opportunity_freshness_service`.
- Not mutate a committed fixture.
- Not touch eligibility or source coverage.
- Not claim improvement. `baseline_quality_score` is the share of records with a
  cited eligibility or exclusion verdict; deadlines are not part of it, so the
  score is expected to stay at 0.0865.
