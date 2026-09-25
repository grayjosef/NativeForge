# Wave 1 Source Expansion — Integrated Close Report

Wave 1 took NativeForge from a fabric with three demo-scoped sources to one that
has met six real publishers and knows precisely what each of them does and does
not prove.

This report separates what was proven against live data from what was proven
against publisher-shaped fixtures, what is built but unproven in the world, and
what remains unknown. Every count is a dated measurement, not a constant.

---

## Evidence classes used below

| Class | Meaning |
| --- | --- |
| **REAL** | verified against the live publisher on the date stated |
| **FIXTURE** | proven offline against publisher-shaped records |
| **BUILT** | implemented and tested, never run against the world |
| **NOT ACTIVATED** | deliberately not collecting |
| **UNKNOWN** | not established |

---

## Grants.gov — eligibility-facet discovery

**REAL.** Live contract verified 2026-09-24 and re-verified at implementation.
`POST api.grants.gov/v1/api/search2`, public, no key.

Discovery previously built its query from the *source row's own name* as a
keyword and asked for five rows. With forty Native-named programme rows, the
system searched for the programmes it already knew the names of.

Measured snapshot, 2026-09-24:

| Measure | Count |
| --- | --- |
| Posted opportunities | 946 |
| Open to federally recognized Tribal governments (code `07`) | 464 |
| Open to tribal organizations, other (code `11`) | 418 |
| Open to Indian housing authorities (code `08`) | 379 |
| Keyword `tribal` | 276 |
| **Of the first 100 sampled elig-07 titles, containing Native wording** | **4** |

**State this carefully.** Four of one hundred *sampled* titles is a sample, not
a proven population rate. It is strong evidence that keyword discovery
undercounts substantially; it is not a proof that exactly 96% of the 464 lack
Native wording, and nothing in the code asserts a percentage.

`verify_eligibility_facet_contract` reads the facet back and compares each code
against the publisher's own label, because an earlier research pass assumed
codes `24`/`25`, got a plausible 693 hits from `25`, and those hits were NIH
clinical-trial notices — `25` means "Others". A renamed label now returns
`facet_contract_changed` with zero hits, distinguishable from empty.

Agency distribution of the 464: HHS 375, Justice 35, Commerce 15, Interior 11,
Agriculture 8, and **Transportation 3, Energy 3, Housing 2**. Grants.gov used
correctly solves federal health and social-services discovery. It does not
solve infrastructure, and that gap is why Denali and the state feeds matter.

## Grants.gov — forecasts

**REAL** contract, **FIXTURE** transition. 431 forecasted elig-07 opportunities
reported; 100 sampled; `docType: "forecast"` and `oppStatus: "forecasted"`
confirmed on the wire.

**`REAL_FORECAST_TO_POSTED_PAIR_OBSERVED = false`.** Zero overlap between 100
sampled forecast numbers and 100 sampled posted numbers — a bounded sample of
431 and 464, so it does not prove no pair exists, only that none appeared in
what was sampled. The transition is proven offline instead.

---

## Logical opportunity identity

**FIXTURE**, and the most consequential defect Wave 1 found.

A forecast and the posting it becomes produce two L1 rows, because
`composite_key` is `<number>|<doc_type>`. That split is correct and stays:
overwriting the forecast would destroy the answer to "what did we know before
this was posted?". What was wrong is that the product counted both.

Proven by probe, not by reading:

```
canonical_rows_created: 2
forecast: L1:ONF181B1|forecast
posted:   L1:ONF181B1|synopsis
same_canonical_id: false
```

`decide_match` already returned `FORECAST_OF` for "one published number, two
document kinds", migration 0054 already permitted a machine to settle it at L1,
and `primary_canonical_id` already existed. `grep` found `FORECAST_OF` wired to
nothing. **No migration was required for any of Wave 1B.**

Now true across the product: feed returns one card with the forecast as
history; counts report `logical_opportunity_count` and `representation_count`
separately; customer decisions bind to logical identity so watching a forecast
and pursuing its posting is one decision; relevance, eligibility, documents and
change history aggregate logically; conflicts return CONFLICT with both
histories preserved rather than a silent winner.

`RECURRENCE_OF`, `VERSION_OF`, `RELATED_TO` and `REPUBLISHED_FROM` deliberately
do **not** collapse — last year's cycle is a different grant with a different
deadline.

**Lifecycle evidence survives the dedupe.** One opportunity, and still visible
that the early signal was missed. Without that separation the product would
report perfect coverage of a lifecycle it only caught the end of.

Resolution is batched: `query_count = 1` at 10, 100 and 1000 pairs.

---

## USAspending

**REAL** evidence, **UNKNOWN** filter, **NOT ACTIVATED**.

Public, no key, verified 2026-09-25. Real Tribal-government awards observed:

```
NAVAJO NATION TRIBAL GOVERNMENT   HHS        $15,362,285.65
NAVAJO NATION TRIBAL GOVERNMENT   Interior    $3,333,334.00
CHEROKEE NATION                   DOT         $4,796,507.00
```

Those are bounded examples, not a survey.

**`recipient_type_names` is not proven.** It silently accepts values it does not
recognise — `"utter_nonsense_not_a_category_xyz"` returns `results: []` with no
error, while `nonprofit` returns rows. Twelve plausible tribal category names
all returned zero on an instrument re-verified as working. That is not evidence
that no Tribal awards exist; there demonstrably are. It is evidence the
vocabulary is unknown.

The awards above were found by `recipient_search_text`, which is name matching,
and name matching cannot distinguish a federally recognized Tribal government
from a state-recognized one. **`recognition_class` stays UNKNOWN.**

**`REAL_EXACT_SOLICITATION_LINKS_PROVEN = false`.**
**`real_award_evidence_available_for_miss_detection` remains FALSE.** Nothing
was ingested.

The linkage grades refuse the attractive merge: a shared assistance listing is
`PROGRAM_LEVEL_ONLY`, never a link, because one listing produces annual
competitions, discretionary rounds and supplements. Same listing *and* same
agency is still `PROGRAM_LEVEL_ONLY` — two agreeing weak signals are not one
strong one. Only a publisher-named opportunity number is `CONFIRMED_LINK`, and
only that grade is machine-actionable.

Miss detection is graded so programme evidence cannot inflate: only "award
names a solicitation absent from the graph" sets `is_confirmed_miss`.

---

## Denali Commission

**REAL.** And the research baseline was wrong in two ways that only live
reconnaissance caught.

**The research said HTML; the publisher offers JSON.** denali.gov runs
WordPress and exposes `/wp-json/wp/v2/` publicly — stable integer ids, a
`modified` timestamp, pagination in headers (`x-wp-total: 18`).

**The research named the wrong pages.** `/funding-requests/` contains
"Interactive Project Database" and "Additional Links"; `/grants/` is policy
guidance. Actual funding notices are posts — *FUNDING ASSISTANCE FOR TRIBAL
VICTIM SERVICES*, *FY2023 Funding Opportunity*, and others.

`robots.txt` is `User-Agent: * / Disallow:` — empty Disallow, everything
permitted. Checked before anything was collected.

**Alaska is not Native**, proven on a live record. Record 4048, a genuine Denali
funding opportunity, returns `native=[]`, `geo=['alaska','rural']`,
`has_geography_only_signal=true`. The tribal victim services notice returns
`native=['tribal']`, because the publisher said so. The adapter returns evidence
and never a verdict.

The adapter is generic: ARC and NBRC are configuration rows, not new code.

---

## California statewide feed

**REAL.** CKAN, California State Library, Public Domain, `metadata_modified`
2026-09-24.

Measured 2026-09-25:

| Lifecycle | Count |
| --- | --- |
| Total rows | **2,010** |
| closed | **1,838** |
| active | **170** |
| forecasted | **2** |

**2,010 dataset rows is not 2,010 open opportunities.** Quoting the row count
would overstate the open pipeline by 1,838 records — and the overstatement
would be invisible, because every row is real, well-formed and correctly
published.

Also measured at that time: 37 fields; **109 of the 170 open rows name "Tribal
Government" in `ApplicantType`**; 28 mention tribal in description or purpose;
170 carry a deadline and a grant URL; 31 carry a match requirement; **26 open
rows are Loans, not grants**.

The 109 is publisher-declared applicant-type evidence — the state's own
statement of who may apply — and is California's analogue of Grants.gov
eligibility code 07.

**Program identity is not opportunity identity, again.** `distinct PortalID =
2,010` (one per row); `distinct GrantID = 403` (shared across rounds); and
**GrantID is nullable**. Keying on the programme id would fuse five years of
rounds into one record, lose four in five, and crash on the nulls. This is the
USAspending assistance-listing mistake wearing different field names.

The classifier prefers what the publisher says over what a date implies: a row
marked closed with a 2027 deadline stays closed; rolling wording stops a past
deadline closing a row. Hedged match wording — "a match may be required" —
stays UNKNOWN rather than becoming a requirement the publisher never imposed.

None of these counts are constants. They are a snapshot.

---

## What Wave 1 proved about scaling

**Generalized adapters now available**

| Adapter | Instances proven | Future sources it serves |
| --- | --- | --- |
| Grants.gov structured API | 1 | forecast + posted paths on one collector |
| **Generic WordPress REST** | 1 (Denali) | ARC, NBRC, many agencies and foundations |
| **Generic structured funding feed** | 1 (California) | CKAN and Socrata state feeds, custom state REST |
| Logical identity resolver | cross-cutting | any publisher with pre-publication records |
| Award linkage semantics | 1 (USAspending) | foundation grantee databases, state award feeds |

**Configuration-dominant** for the next tranche: CKAN rows (Virginia,
Oklahoma), Socrata rows (Maryland, New Jersey, Connecticut, New York, Oregon,
Texas), and WordPress publishers among the regional commissions.

**New adapter likely required**: HUD ONAP, IHS, EPA and CDFI are agency HTML
listings whose structure has not been inspected; Federal Register has an
existing path but its document hosts are gated.

No throughput timeline is claimed. None was measured.

---

## Launch readiness delta against Gate 180

Gate 180 concluded: *the fabric is trustworthy enough to carry real data; there
is not yet enough real data for it to carry.*

**What improved.** Six publishers verified against live contracts. Real Tribal
award evidence observed. Real open state opportunities measured with lifecycle
truth. Real forecast records observed. Two generic adapters that make the next
tranche configuration rather than engineering. Federal discovery corrected from
a keyword search over forty programme names to an eligibility facet over 464
measured postings.

**What did not change.** No source is activated. `collector_activated` remains
false. The three active sources remain demo-org scoped. All 2,757 award rows
remain Gate 138 fixtures. Production authentication, infrastructure, monitoring
and support runbook remain unproven or absent.

**Launch verdict: still blocked.** The blocker has changed shape — it is no
longer "we do not know what is out there", it is "nothing is switched on, and
production has not been proven". That is a better problem, and it is not a
smaller one.

---

## Known unknowns

1. USAspending Tribal recipient-category vocabulary.
2. Whether any real forecast→posted pair exists in the current publisher data.
3. Exact award→solicitation linkage in real data — none observed.
4. Recognition class for any award recipient.
5. Structure of HUD ONAP, IHS, EPA and CDFI listings.
6. Federal Register document-host access.
7. Whether publisher eligibility coding is itself reliable — the eligibility
   fix moves trust from our heuristic to the publisher's coding, which is a
   better place for it and still not zero-risk.
8. Gate 170's single historical failure. Passed again in this close. Root cause
   remains **UNKNOWN** and is not relabelled.

---

## Verification record

| Step | Result |
| --- | --- |
| Artifact regeneration | 3 files, 6 lines, `network_attempts=0`, 1276 to 1281 |
| Regeneration idempotence | second run rewrote **0** |
| Independent scanner check | `find src/nativeforge -name "*.py"` = **1281** = artifact value |
| Migration head | artifact `0065` = actual `0065` (no migration added in Wave 1) |
| Focused verification | **706 passed** across 19 test files |
| Sequential battery 167-179 | **13/13 GREEN** |
| **Authoritative full suite** | **13,896 passed, 50 skipped, 0 failed - 2:06:29, exit 0** |
| Post-suite tree integrity | **IDENTICAL** to freeze; 11 artifact hashes verified |
| Test delta | 13,695 to 13,896 = **+201**, matching Wave 1 additions exactly |

Ruff reports 699 pre-existing findings across the repository. The identical
count is present at `0879bd2`, the last pushed commit, which passed its own
authoritative suite. All seven files Wave 1 touched report clean.

### Gate 170

Passed again in this close (235s). The single historical failure on
`j_reopened_seen` remains **unexplained**. Cross-gate ordering, seed collision
and phase nondeterminism were each tested and eliminated, and a snapshot showed
its input identical to the passing runs. It is recorded as an unexplained
intermittent and is not relabelled fixed, flaky or resolved, so that a
recurrence reads as a pattern rather than a first.

### Commits in this wave

```
ef868a4  California statewide structured funding ingestion
cdf8063  Denali Commission real-source ingestion
86e15ce  bounded real USAspending award evidence
40191ec  logical opportunity wiring across intelligence layers
2885a82  logical opportunity identity through customer paths
6cd9320  related source records resolve to one logical opportunity
6f00600  Grants.gov forecasts linked to posted opportunities
91d008c  Grants.gov eligibility-facet discovery
ac18028  file-count artifacts re-stamped
```

No source was activated. No migration was added. Nothing is pushed.
