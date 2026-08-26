# 490 — Gate 87B: deadline provenance contract

`deadline_provenance_service` (`nf_deadline_provenance_v1`) answers a different
question from Gate 86. Gate 86 asked *can this deadline be parsed*. This asks
*can it be trusted*.

Conflating the two is how 40 records carrying an identical year-end sentinel
came to be counted alongside 19 fetched deadlines as though they were the same
kind of thing.

## Statuses

| Status | Meaning | Freshness |
| --- | --- | --- |
| `verified_deadline` | normalized, with a check timestamp **and** a source URL or upstream id | allowed |
| `unverified_deadline` | normalized, evidence incomplete | only if checked |
| `suspected_placeholder` | normalized, but does not behave like a fetched deadline | blocked |
| `missing_deadline` | no raw value | blocked |
| `unknown_deadline` | a raw value that does not resolve to a date | blocked |

## Evidence levels

```text
none            nothing
self_asserted   the record claims a fetch, with none of a fetch's artefacts
checked         a timestamp: somebody looked, at a known time
corroborated    a timestamp plus something to point at
```

Only `corroborated` reaches `verified_deadline`, and an invariant fails if a
verified status appears at any lower level.

## The two failures this guards

**Over-claiming.** Calling a date verified because it parsed. `verified_deadline`
requires artefacts a fetch actually leaves behind, and a bare `real_fetch: true`
is explicitly not one of them — it is recorded as `self_asserted` and warned
about via `fetch_asserted_without_fetch_artefacts`.

**Under-claiming.** Calling a date a placeholder because it looks like one. A
suspicion drawn from a value alone is an accusation the corpus cannot answer.
`suspected_placeholder` therefore requires **cluster evidence**, and the
invariant rejects any suspicion whose reasons do not include a `shared_by_N`
line.

`SENTINEL_DATE_SUFFIXES` (`-12-31`, `-01-01`, `-06-30`, `-09-30`) is a
*supporting* signal only. It is recorded as a warning when a cluster already
fired, and can never trigger one. Real notices do close on December 31.

## Why cluster context is an argument

Placeholder detection cannot work one record at a time. One `2026-12-31` says
nothing. Forty identical ones, in a batch where no record carries a fetch
timestamp, say a great deal — especially when a comparable batch in the same
corpus shows fifteen distinct dates across nineteen records with a timestamp on
every one.

So `build_deadline_cluster_context` counts, over records the caller already
holds, how many share each raw value and how many of those have been checked.
The classifier does no I/O, opens no file, and loads no corpus — a test greps
the module source for `open(`, `Path(`, and every HTTP client to keep it that
way.

## The suspicion rule

Both conditions, together:

```text
cluster_size >= PLACEHOLDER_CLUSTER_MIN (10)
AND no record sharing that value has a check timestamp
```

Ten is set well above the largest innocent repeat in the corpus — two records
legitimately sharing a close date — so ordinary coincidence cannot trip it. And
the second condition means a large cluster of genuinely fetched notices stays
`verified_deadline`, which a test pins directly.

## What a verdict may not do

```text
records_removed      always 0
records_hidden       always 0
deadlines_rewritten  always 0
fabricated           always False
```

A `suspected_placeholder` record keeps its raw value, keeps its normalized
value, stays counted in `records_with_raw_deadline`, and stays in `per_record`.
What the status blocks is a freshness state, not the record. The invariant
`raw_deadline_dropped_by_classification` fails if a verdict ever costs a record
its raw deadline.

## Invariants

`provenance_invariant_failures` enforces:

- `fabricated` is `False`, and both vocabularies are closed
- a blocking status can never carry `freshness_allowed`
- `verified_deadline` requires `corroborated` evidence and a normalized date
- `deadline_counts_as_verified` only ever accompanies `verified_deadline`
- a suspicion states its reasons and includes cluster evidence
- a raw value survives every verdict except `missing_deadline`
