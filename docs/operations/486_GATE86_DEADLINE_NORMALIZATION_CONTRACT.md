# 486 — Gate 86B: deadline normalization contract

`deadline_normalization_service` (`nf_deadline_normalization_v1`) turns a raw
deadline string from a committed record into an ISO date — but only when the raw
string actually determines one.

The rule the module exists to enforce: **a normalized date must be derivable
from the characters already in the raw string.** `fabricated` is always `False`,
and an invariant fails if it is ever anything else.

## Formats that normalize

| Input | Output | `parse_confidence` | Why |
| --- | --- | --- | --- |
| `2026-12-31` | `2026-12-31` | `exact` | already ISO |
| `2026-06-29T21:38:46+00:00` | `2026-06-29` | `exact` | ISO datetime; warns `time_component_discarded` |
| `07/24/2026` | `2026-07-24` | `structural` | 24 cannot be a month |
| `31/12/2026` | `2026-12-31` | `structural` | 31 cannot be a month |
| `7/4/2026` (convention declared) | `2026-07-04` | `convention_declared` | source convention |
| `07/01/2026` (convention declared) | `2026-07-01` | `convention_declared` | source convention |

## Formats that do not normalize

| Input | `parse_status` | Why |
| --- | --- | --- |
| `07/01/2026` (no convention) | `ambiguous` | both readings are valid dates |
| `02/30/2026`, `2026-02-29` | `impossible` | not a calendar date |
| `2026-07`, `07/2026` | `insufficient_precision` | no day, and one is not invented |
| `2026` | `insufficient_precision` | no month and no day |
| `07/24` | `insufficient_precision` | no year, and one is not inferred |
| `next Tuesday`, `TBD`, `rolling` | `unparseable` | not a date |
| `""`, `None`, whitespace | `absent` | nothing there |
| `20261231` (int) | `unparseable` | non-string, not coerced |

A record with no deadline is `absent`, not a failure, and is excluded from the
denominator of `normalization_rate`. A record that has no deadline has not
failed to have one parsed.

## The ambiguity decision

`07/24/2026` proves its own format — 24 is not a month, so month-first is the
only reading. `07/01/2026` proves nothing on its own.

Rather than flatten these into one answer, the parser keeps them apart:

- self-proving date → normalized at `parse_confidence: structural`
- ambiguous date → normalized **only** if the caller declares a convention, at
  `parse_confidence: convention_declared`
- ambiguous date with no declared convention → `parse_status: ambiguous`,
  no date produced

`source_convention` takes `month_first`, `day_first`, or `unknown` (the
default). An unrecognised value degrades to `unknown` and adds a warning rather
than being trusted. A caller that does not know its source's convention
therefore cannot accidentally receive a guess.

Baseline X declares `month_first` only for records carrying a
`grants_gov_opportunity_id`. Doc 485 records why that is earned rather than
assumed: all 19 slash-format deadlines come from the one `la_scale_federal`
batch, and 10 of that batch's distinct values have a second field over 12.

## Why this is not inside the freshness evaluator

`opportunity_freshness_service._days_between` calls `date.fromisoformat` and its
docstring is explicit that the module avoids owning a timezone policy. A slash
date needs a *locale* policy on top of that. Teaching the evaluator to guess
would make a module that correctly refuses to guess start guessing.

Normalization sits upstream. **`opportunity_freshness_service.py` is unchanged
by this gate.**

## Output fields

```text
raw_value           the input, verbatim, always
normalized_date     ISO date or None
date_precision      day | month | year | none
parse_status        one of seven, listed above
parse_confidence    exact | structural | convention_declared | none
source_format       iso_8601_date | iso_8601_datetime | slash_numeric |
                    partial_date | unrecognised | absent
warnings            non-blocking notes
blocked_reasons     why no date was produced
fabricated          always False
```

## Invariants

`normalization_invariant_failures` enforces, on every result:

- `fabricated` is `False`
- every vocabulary field is in its frozenset
- a produced date implies day precision, a confidence other than `none`, a
  status of `normalized` or `already_iso`, and no blocked reasons
- **every component of a produced date appears as a number in the raw string**
- no produced date implies at least one blocked reason and no asserted
  confidence

The anti-fabrication check compares integers, not characters. Zero-padding
legitimately adds a digit — `7/4/2026` yields `2026-07-04`, whose characters are
not a subset of the raw ones but whose year, month and day are each literally
present. A character-level check would reject correct output, and a rejected
correct output is what tempts someone to weaken the check later.
