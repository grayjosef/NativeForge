# 491 — Gate 87C/87D: Discovery Baseline X deadline provenance delta


> **Superseded in part by Gate 88.** This page is preserved as the deadline
> provenance baseline. Its numbers are not edited and all still stand: 59 raw
> deadlines, 19 verified, 40 suspected placeholder, 19 resolvable freshness
> states.
>
> Gate 88 applied the same question to the records themselves rather than their
> deadlines, and found the same shape: 18 of 185 records have an independent
> recording artifact, 166 rest on assertion, and 38 of those rest on booleans
> alone. `corpus_summary.recorded_records` stays at 162 and is unchanged; the
> gap between it and the 18 is reported as its own metric. See docs 493, 494,
> 495.
>
> The reading order across the sequence: 483 is the original baseline, 487 the
> post-normalization one, 491 (this page) the deadline provenance one, and 495
> carries the current corpus provenance picture.

## The delta

| Metric | Gate 86 | Gate 87 | Note |
| --- | --- | --- | --- |
| total_records | 185 | 185 | unchanged |
| records_with_raw_deadline | 59 | 59 | **unchanged — nothing was removed** |
| records_with_normalized_deadline | 59 | 59 | unchanged |
| **verified_deadlines** | not measured | **19** | new |
| **suspected_placeholder_deadlines** | not measured | **40** | new |
| unverified_deadlines | not measured | 0 | new |
| unknown_deadlines | not measured | 0 | new |
| missing_deadlines | not measured | 126 | new |
| raw_deadline_count_overstated_by | not measured | **40** | new |
| deadline_verification_rate | not measured | 0.322 | of dated records |
| placeholder_suspicion_rate | not measured | 0.678 | of dated records |
| freshness_blocked_by_deadline_provenance | not measured | 40 | new |
| records_with_resolvable_freshness | 19 | **19** | **unchanged** |
| freshness split | 16 expired / 3 stale / 0 fresh | **identical** | unchanged |
| baseline_quality_score | 0.0865 | **0.0865** | unchanged |
| live_records | 0 | 0 | unchanged |
| monitored_sources | 0 | 0 | unchanged |
| improvement_claim_allowed | false | false | unchanged |

## Are the 40 identical dates verified, unverified, suspected, or unknown?

**`suspected_placeholder`.** All 40, consistently, because they share the same
evidence.

Not "fake". The evidence shows the dates do not behave like fetched deadlines;
it does not show they are wrong. No local source establishes the real deadline
for any of the 40 — which is precisely why none can be called verified either.

## What evidence supports the classification

The decisive evidence is a control group inside the same corpus:

| | `nf13-real-fed` (the cluster) | `la-real` (dated) |
| --- | --- | --- |
| records | 40 | 19 |
| distinct deadline values | **1** | **15** |
| with `ingested_at` | **0** | **19** |
| with `source_url` | 1 | 19 |
| with `grants_gov_opportunity_id` | 1 | 19 |

Both batches claim to be real federal opportunities. One behaves the way fetched
deadlines behave. The other does not.

Supporting signals within the cluster: 39 of 40 carry templated opportunity
numbers (`FED-001`…`FED-041`), 39 of 40 carry a templated synopsis
(`Federal grant program: {agency} — {title}`), median eligibility text is 74
characters against 303 for the rest of the corpus, and `2026-12-31` is a proven
fallback idiom elsewhere in this repository
(`sc_pilot_fixture_loader_service.build_sc_pilot_rule_reference_grants` assigns
that exact literal).

## What evidence is missing

- **No independent source.** Nothing local establishes what the real deadline
  for any of the 40 is. That gap is why the status is a suspicion.
- **No generator.** No committed code produces `nf13-real-fed-*` rows; they
  exist only as committed JSON, so the deadline's origin is not traceable.
- **No label.** No doc, fixture note, or comment identifies these as
  placeholders. The suspicion is inferred from the data's shape.
- **The one apparent corroboration is circular.** `nf13-real-fed-021` is SAMHSA
  `SM-26-024`, and its recorded transport fixture carries
  `closeDate: "12/31/2026"` — but that fixture's `_meta` names
  `nf13_real_ingested_grants.json` as its `source_of_values` and states it is "a
  record of what the repo already asserts, not a claim about what api.grants.gov
  returns today". The close date was copied from the row under audit. It shows
  the repo is internally consistent, not that the date is real.

  `nf13-real-fed-021` is classified with the other 39. Exempting one record on
  corroboration that declares itself circular would be an unearned exemption.

Against all of that, the 40 records do carry `real_fetch: true`,
`search_live: true` and `never_synthesized: true`. Those flags contradict the
placeholder reading directly. They are also unaccompanied by any artefact a
fetch leaves behind, which is why the classifier records them as
`evidence_level: self_asserted` and warns
`fetch_asserted_without_fetch_artefacts` rather than treating them as evidence.

## Effect on the raw deadline count

**None.** It stays at 59. No record was removed, hidden, or rewritten —
`records_removed`, `records_hidden` and `deadlines_rewritten` are all 0 and
invariants fail if any becomes non-zero.

What changed is that the baseline now says out loud that the 59 overstates what
can be trusted, and by how much: `raw_deadline_count_overstated_by = 40`. That
is its own metric rather than an inference from two others, so somebody has to
read it.

## Effect on the verified deadline count

New, at 19 — the `la-real` records that carry a check timestamp and something to
point at. `deadline_verification_rate` is 0.322: under a third of the corpus's
deadlines stand up.

## Effect on freshness

**None. Still 19 — 16 expired, 3 stale, 0 fresh.**

This is the important part and it is not a coincidence. All 40 suspected records
already lacked `ingested_at`, so all 40 already resolved to `unknown` freshness
under Gate 86. Classifying them cannot remove a contribution they never made.

`freshness_blocked_by_deadline_provenance` is 40, and a test asserts freshness
stays at exactly 19 — if it ever drops, the audit has begun blocking dates that
were genuinely supported.

## Why no deadlines were fabricated

Nothing was written, and no date was produced. This gate reads and classifies.
`fabricated` is `False` on every classification and on the summary;
`deadlines_rewritten` is 0; the fixture hash is identical before and after a
full build, checked by the suite and by the generator script.

The Gate 86 guarantee still holds underneath: every normalized date's year,
month and day appear as numbers in the raw string.

## Why no live coverage is claimed

Nothing was fetched. `network_access_performed` is `false`,
`live_coverage_claimed` is `false`, `live_records` is 0, `monitored_sources` is
0. The provenance service performs no I/O at all — a test greps its source for
`open(`, `Path(`, and every HTTP client.

The finding itself is further evidence of the absence of live coverage: a
monitored corpus would not contain 40 unverifiable deadlines.

## Why 65% improvement is still not claimed

Nothing improved. This gate lowered the confidence attached to two-thirds of the
corpus's deadlines and moved no number upward. `verified_deadlines` at 19 is not
an increase on anything — before this gate the count did not exist, and the
number it replaces in practice is the 59 that was being read as though it were
trustworthy.

If anything, the honest summary of Gate 87 is that the deadline picture is worse
than Gate 86 reported. `improvement_claim_allowed` remains `false`, and the
artifact writer still refuses to emit any document containing `65% improvement`,
`improvement over`, or `live coverage`.
