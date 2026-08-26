# 489 — Gate 87A: the `2026-12-31` deadline cluster

Audit of the 40 records carrying the identical deadline `2026-12-31`, using
committed and local data only. Nothing was fetched.

## Verdict

**`suspected_placeholder`, for all 40.**

Not "fake". The evidence is strong and entirely circumstantial: it shows the
dates do not behave like fetched deadlines, not that they are wrong. No local
source establishes the real deadline for any of the 40, so none can be called
false and none can be called verified.

The classification blocks these dates from producing freshness and excludes them
from `verified_deadlines`. It does not delete, hide, or rewrite anything.

## Which records

All 40 are `nf13-real-fed-001` through `nf13-real-fed-041` (039 is absent), from
`fixtures/real_grants_corpus/nf13_real_ingested_grants.json`, carrying
`source_seed_id` values `nf-seed-2026-fed-001` … `-041`.

**Every dated record in that batch is in the cluster.** There is no
`nf13-real-fed` record with a different deadline — the batch has 40 dated
records and exactly 1 distinct date.

## The corpus contains its own control group

The decisive evidence is not the cluster on its own. It is the contrast with a
comparable batch in the same corpus:

| batch | records | dated | distinct dates | with `ingested_at` |
| --- | --- | --- | --- | --- |
| `la-real` (la_scale_federal) | 36 | 19 | **15** | **19 / 19** |
| `nf13-real-fed` | 40 | **40** | **1** | **0 / 40** |

Both claim to be real federal opportunities. `la-real` behaves the way fetched
deadlines behave — 15 distinct dates across 19 records, every one with a fetch
timestamp. `nf13-real-fed` shows a single date across 40 records and not one
fetch timestamp.

Forty independently fetched federal opportunities do not all close on the same
day, and the same corpus demonstrates what it looks like when they do not.

## Evidence for `suspected_placeholder`

| # | Evidence | Cluster | Control (`la-real` dated) |
| --- | --- | --- | --- |
| 1 | distinct deadline values | 1 of 40 | 15 of 19 |
| 2 | records with `ingested_at` | 0 / 40 | 19 / 19 |
| 3 | records with `source_url` | 1 / 40 | 19 / 19 |
| 4 | records with `grants_gov_opportunity_id` | 1 / 40 | 19 / 19 |
| 5 | records with a `provenance` block | 0 / 40 | 19 / 19 |

Plus, within the cluster itself:

6. **Templated opportunity numbers.** 39 of 40 are `FED-001` … `FED-041`,
   sequential and synthetic-looking. Real federal numbers in this same corpus
   look like `BIA-IBIP-OIED-2026`, `O-OVW-2026-173049`, `PA-27-100`.
7. **Templated synopses.** 39 of 40 read
   `Federal grant program: {agency} — {title}`, machine-generated from two other
   fields. Only 19 of the other 145 records use that shape.
8. **Short eligibility text.** Median 74 characters against 303 for the rest of
   the corpus — consistent with a generated one-liner rather than a fetched
   eligibility section.
9. **The value is a proven fallback idiom in this repository.**
   `sc_pilot_fixture_loader_service.build_sc_pilot_rule_reference_grants`
   assigns the literal `"application_deadline": "2026-12-31"` to every row it
   builds. That is a different generator producing different records, so it is
   not the origin of these 40 — but it establishes that this project has used
   this exact date as a stand-in when it had none.
10. **December 31 is a year-end sentinel**, the conventional "far future"
    placeholder.

## Evidence against, stated fairly

1. **The records assert a real fetch.** All 40 carry `real_fetch: true`,
   `search_live: true`, `never_synthesized: true`, and 39 carry
   `detail_live: true`. Those flags directly contradict the placeholder reading.
   They are also unaccompanied by any of the artefacts a real fetch leaves
   behind — no timestamp, no URL, no upstream id — which is why the audit weighs
   them as an unsupported assertion rather than as evidence.

2. **One record has a matching recorded transport, and the corroboration is
   circular.** `nf13-real-fed-021` is SAMHSA `SM-26-024`, and
   `tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json`
   records `closeDate: "12/31/2026"` — which normalizes to the same
   `2026-12-31`.

   That fixture's own `_meta` disposes of it as independent evidence:

   > `source_of_values: fixtures/real_grants_corpus/nf13_real_ingested_grants.json`
   >
   > "Every field below is transcribed from committed corpus evidence for grant
   > nf13-real-fed-021 … It is a record of what the repo already asserts, not a
   > claim about what api.grants.gov returns today."

   The fixture's close date was copied *from the row under audit*. It confirms
   the repo is internally consistent, not that the date is real. Gate 77B was
   right to label it, and the label is what makes the circle visible.

   `nf13-real-fed-021` is classified with the other 39. Exempting one record on
   corroboration that declares itself circular would be precisely the unearned
   exemption these rules exist to prevent.

3. **No committed document says these are placeholders.** Nothing in `docs/`,
   no fixture note, and no generator comment identifies the nf13 deadlines as
   defaults. The suspicion is inferred from the data's shape, not read off a
   label.

4. **A real NOFO can close on December 31.** Some certainly do. The finding is
   about 40 of them doing so with no fetch evidence, not about the date being
   implausible.

## Deadline field origin

Not traceable. No committed generator produces `nf13-real-fed-*` rows — the
records exist only as committed JSON. `nf15_eligibility_reingest_pulls.json`
re-ingests two of them (`-021` and `-025`) but carries no deadline field, so it
neither confirms nor corrects the value.

No record in the cluster has a second deadline-like field. There is nothing to
conflict with: no `close_date`, `due_date`, `closing_date`, `archive_date`, or
`posted_date` anywhere in the corpus.

## Answers to the survey questions

- **All 40 from the same corpus/source family?** Yes — one file, one batch, one
  contiguous seed range.
- **Do all 40 share other suspicious defaults?** Yes — templated opportunity
  numbers, templated synopses, short eligibility text, and a complete absence of
  fetch artefacts.
- **Real-looking titles with default-looking deadlines?** Yes, and this is the
  point of the finding. The titles are entirely plausible ("Aid to Tribal
  Governments (Categorical Grants – 15.020)", "Tribal Behavioral Health: Suicide
  Prevention"). Plausible titles are what make an unverified deadline dangerous
  rather than obviously wrong.
- **Does generation code assign `2026-12-31` as a fallback?** Yes, in
  `sc_pilot_fixture_loader_service` — for different records. Corroborating the
  idiom, not the origin.
- **Does any committed fixture or document call it a placeholder?** No.
- **How should Baseline X classify these?** `suspected_placeholder`.

## Effect

None on freshness. All 40 already lacked `ingested_at`, so all 40 already
resolved to `unknown` freshness and contributed nothing to the 19. Classifying
them cannot reduce a number they never contributed to.

What changes is honesty about the deadline count: 59 raw deadlines, of which
only 19 have the evidence to be called verified. The other 40 remain visible,
counted as raw, and marked.
