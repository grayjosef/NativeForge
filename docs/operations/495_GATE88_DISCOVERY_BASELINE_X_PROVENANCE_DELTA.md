# 495 — Gate 88C/88D: Discovery Baseline X corpus provenance delta

## The delta

| Metric | Gate 87 | Gate 88 | Note |
| --- | --- | --- | --- |
| total_records | 185 | 185 | unchanged |
| corpus_summary.recorded_records | 162 | **162** | **unchanged — not edited** |
| corpus_summary.synthetic_records | 0 | 0 | unchanged |
| corpus_summary.live_records | 0 | 0 | unchanged |
| **recorded_verified_records** | not measured | **18** | new |
| **recorded_asserted_records** | not measured | **166** | new |
| **recorded_circular_records** | not measured | **1** | new |
| **flags_only_records** | not measured | **38** | new |
| synthetic_declared_records | not measured | 0 | new |
| unknown / missing_provenance | not measured | 0 / 0 | new |
| verified_recorded_rate | not measured | 0.0973 | new |
| asserted_recorded_rate | not measured | 0.8973 | new |
| provenance_confidence_level | not measured | `predominantly_asserted` | new |
| corpus_summary_recorded_overstated_by | not measured | **144** | new |
| verified_deadlines | 19 | 19 | unchanged |
| records_with_resolvable_freshness | 19 | 19 | unchanged |
| baseline_quality_score | 0.0865 | **0.0865** | unchanged |
| improvement_claim_allowed | false | false | unchanged |

## Is `recorded_records` still trustworthy?

**It is accurate for the question it answers, and it was being read as though it
answered a stronger one.**

`recorded_records: 162` counts records whose flags say they were produced by a
fetch rather than synthesised. That is true of all 162. Nothing in this audit
contradicts any record's content, nothing declares itself synthetic, and no
record is fake.

What it does not mean is that 162 recordings can be evidenced. Only **18** can.

Both numbers stay in the baseline, both labelled. `corpus_summary` answers *how
was this record produced*; the new metrics answer *what evidence survives to
show it*. Neither is edited to match the other.

## Which records are verified recorded — 18

All 18 rest on one artefact:
`fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json`, 466 KB of
raw Grants.gov transport, `pulled_at: 2026-05-19`,
`fetch_mode_recorded: live`.

- **17 `nf14-mixed-*` records**, covering all 16 upstream ids the batch carries.
- **1 `la-real` record** — `la-real-014`, upstream id 361742, appears in the
  pull as `HHS-2026-ACF-ANA-NB-0116`, "Native American Language Preservation and
  Maintenance-Esther…", matching the corpus row's number and title. The same
  opportunity was recorded twice and the independent copy backs the asserted one.

Worth noting: the 17 nf14 records carry `real_fetch: false` and `fixture: true`.
The batch with the *weakest* self-assertion turns out to have the *strongest*
evidence, because somebody committed the transport alongside it. That inversion
is the argument for this gate in one line.

## Which records are asserted recorded — 166

Graded by what they actually carry:

| Evidence level | Records | What they have |
| --- | --- | --- |
| `upstream_identified` | 31 | timestamp + an id the repo did not mint |
| `checked_metadata` | 74 | timestamp + provenance block or URL |
| `metadata` | 23 | provenance block or URL, never checked |
| **`flags_only`** | **38** | **booleans and nothing else** |

The 38 are the whole `nf13-real-fed` batch minus its two odd records — the same
batch Gate 87 found carrying 40 identical deadlines. They have no ingestion
timestamp, no provenance block, no upstream identifier and no source URL, and
they assert `real_fetch: true`.

A record at `upstream_identified` is in a different position entirely, and the
evidence level is there so the two are never filed together.

## Which records are circular recorded — 1

`nf13-real-fed-021` (SAMHSA SM-26-024). Its recorded transport names
`nf13_real_ingested_grants.json` as its `source_of_values` and describes itself
as "a record of what the repo already asserts". Covered in Gate 87A; it is the
only artefact in the corpus that declares such derivation.

## What evidence supports each class

```text
recorded_verified   a transport carrying 33 fields the row does not - a row
                    cannot be the source of data it does not contain
recorded_circular   an artefact that names the row as its own source
recorded_asserted   flags, plus timestamps / blocks / URLs in most cases
```

## What evidence is missing

For the 166: a transport artefact per record. Nothing else will move them, and
producing one requires a fetch, which is blocked behind terms clearance.

Two specific gaps worth naming:

- **`never_synthesized: true` proves nothing.** Hardcoded in the fetch adapter,
  set on every record. Any future reasoning that leans on it is leaning on a
  constant.
- **The Sprint 313 guard cannot close this.** It is fail-closed and correct
  within its scope, but it compares flags to flags on the same payload. A
  payload with all four flags and no artefact passes it, and a test pins that.

## Impact on `recorded_records`

None to the figure — it stays at 162 and was not edited.

What changed is that the baseline now states the gap outright:
`corpus_summary_recorded_overstated_by = 144`, its own metric rather than an
inference from two others.

## Impact on the verified recorded count

New, at 18. `verified_recorded_rate` is 0.0973 — under a tenth of the corpus
stands on an artefact, and `provenance_confidence_level` reads
`predominantly_asserted`.

## Why no live coverage is claimed

Nothing was fetched. `network_access_performed` is `false`,
`live_coverage_claimed` is `false`, `live_records` is 0 in both the corpus
summary and the new provenance summary, `monitored_sources` is 0. The classifier
performs no I/O at all, and `live` is not in its status vocabulary — so a live
record is not merely unclaimed, it is unreachable.

## Why 65% improvement is still not claimed

Nothing improved. This gate lowered the evidential standing of 90% of the
corpus and moved no number upward. `recorded_verified_records: 18` is not an
increase on anything — before this gate the count did not exist, and the figure
it qualifies is the 162 that was being read as though every record had a
recording behind it.

The honest summary is that corpus provenance is weaker than Baseline X has been
reporting since Gate 85. `improvement_claim_allowed` remains `false`, and the
artifact writer still refuses to emit any document containing `65% improvement`,
`improvement over`, or `live coverage`.

## The record this gate does not make

None of the above says any record is fake. No record declares itself synthetic,
no evidence contradicts any record's content, and `synthetic_declared_records`
is 0. `recorded_asserted` means uncorroborated, not refuted — and a test asserts
the rendered summary never calls a record fake.
