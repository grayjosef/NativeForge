# Tranche 2B — HUD ONAP

**What HUD ONAP actually contributes to NativeForge:** it is the **programme
roster and discovery surface** that makes HUD's Tribal money findable. It is
not a source of opportunity records. Grants.gov owns every ONAP opportunity
record that exists, and ONAP publishes none of its own.

That sounds like a demotion. It is the opposite: without ONAP's roster,
NativeForge cannot find ONAP's opportunities on Grants.gov at all.

---

## 1. Why the roster is load-bearing

Grants.gov exposes ONAP only as `agencyCode: "HUD"`. There is no ONAP filter,
no PIH filter, no Native programme filter. "Show me ONAP's opportunities" is a
question the canonical source cannot answer about itself.

What *can* answer it is the assistance listing — and the assistance listings
are exactly what ONAP's own programme pages establish.

Measured, 2026-09-25:

| Filter | Records |
|---|---|
| All posted Grants.gov opportunities | 941 |
| `agencies=HUD`, posted | 6 |
| `agencies=HUD`, posted, eligibility 07 | 2 |
| All HUD records, every status, all time | 637 |
| …whose title carries Native entity language | 51 |

Neither of the two HUD records open to Tribal governments is an ONAP
programme. One is ROSS (resident self-sufficiency), one is a Continuum of Care
homelessness competition.

The filter was falsified before being trusted: a nonsense agency code returns
0, and the agency facet independently reports HUD = 6.

---

## 2. The finding that justifies the whole tranche

**A posted, open, Tribes-only ICDBG opportunity is invisible to every Tribal
eligibility code.**

`FR-6900-N-74`, "Application Instructions for the Indian Community Development
Block Grant (ICDBG) Imminent Threat":

- estimated funding **$5,000,000**, award ceiling **$1,500,000**, no cost share
- closes **2026-09-30**
- eligibility prose: *"Eligible applicants are Tribes and Tribal organizations
  as described in the ICDBG regulations at 24 CFR §1003.5"*
- **declared applicant type: `25` — "Others". Nothing else.**

Searching eligibility codes 07, 08 and 11 returns it **zero times out of
three**. Searching assistance listing 14.862 returns it immediately.

Code 25 was already known to return irrelevant rows — the Wave 1A mistake
where it produced 693 plausible NIH clinical trials. What is new is that code
25 also **hides relevant ones**. The eligibility facet is necessary and is not
sufficient, and the gap is one-directional: it costs a Tribe money it never
saw.

Verified end-to-end through the real adapter:

```
found by eligibility        : 106   (union of the first page of each of 07/08/11)
found by assistance listing : 1
found by both               : 0
MISSED by eligibility facet : ['FR-6900-N-74']
```

The 106 is the union of three first pages (totals 460 / 379 / 416), so it is a
floor on the eligibility universe, not its size. The relevant number is
`found_by_both = 0`.

---

## 3. What ONAP publishes

Eight programmes, classified from live pages:

| Programme | Vehicle | Route |
|---|---|---|
| Indian Housing Block Grant | FORMULA_ALLOCATION | formula intelligence |
| IHBG Formula portal | FORMULA_ALLOCATION | formula intelligence |
| IHBG Competitive | COMPETITIVE_GRANT | canonical referral |
| ICDBG | COMPETITIVE_GRANT | canonical referral |
| Native Hawaiian Programs | COMPETITIVE_GRANT | canonical referral |
| Section 184 Loan Guarantee | LOAN_GUARANTEE | financial assistance lane |
| Title VI Loan Guarantee | LOAN_GUARANTEE | financial assistance lane |
| Tribal HUD-VASH | POLICY_GUIDANCE | intelligence only |

**Three of eight can bear an opportunity. None of eight is one.**

Fifteen hub announcements were classified and **zero** bear an opportunity:
4 policy guidance, 3 training events, 3 programme information, 2 technical
assistance, 2 loan guarantee, 1 formula allocation.

**Title VI and Section 184 return zero Grants.gov records, ever.** They are
loan guarantees, not grants. Modelling them as grant opportunities would
invent a pipeline out of a mortgage product.

---

## 4. The stale-link trap, measured

ONAP's own programme pages link to Grants.gov opportunity records. Those links
are **out of date, in the direction that costs money**.

| Page links to | Status | Live record not linked |
|---|---|---|
| `FR-6900-N-48` IHBG-COMP FY2025 | closed 2026-01-15 | `PIH-2600-DC-0048` FY2026 forecast, $125M |
| `FR-6800-N-48` IHBG-COMP FY2024 | closed 2024-08-29 | — |
| `FR-6900-N-23` ICDBG FY2025 | closed 2025-12-10 | `PIH-2600-DC-0034` FY2026 forecast, $90M |

Following those links and calling them current would show a Tribe **two closed
competitions** and hide **two live forecasts worth $215M combined**.

So a page link is a *reference*, resolved against the canonical source before
anyone may call it current. `classify_opportunity_reference` defaults to
UNKNOWN, never to current.

---

## 5. Programme identity is not opportunity identity

The same competitive programme across three cycles:

```
FR-6800-N-48      FY2024   closed
FR-6900-N-48      FY2025   closed
PIH-2600-DC-0048  FY2026   forecast
```

The numbering *scheme* changed. What did not change is assistance listing
**14.867**. The listing is the programme key; the opportunity number is the
cycle key. This is the same defect the campaign has now met five times, and
here both halves are visible in one programme.

Dedupe therefore keys on the opportunity number, never the programme. The
Codetalk announcement *"HUD still has some remaining FY26 ICDBG Imminent
Threat funding"* refers to the same money as `FR-6900-N-74` — and is correctly
non-bearing, so no duplicate is created.

---

## 6. Access posture — three states that all look like 404

| Host | NativeForge UA | Browser UA | Reading |
|---|---|---|---|
| `hud.gov` | 200 / honest 404 | same | healthy, collectable |
| `hud.gov/hud-partners/*` | 404 | 404 | genuinely dead |
| `hudexchange.info` | **404** | **200** | **UA-conditional refusal** |

`hudexchange.info` refuses non-browser clients and disguises the refusal as a
404. A browser user agent was sent **once, as a diagnostic**, to distinguish
"dead" from "blocked" — and never to collect. Spoofing a browser string to
collect would circumvent an anti-automation control.

**HUD Exchange is therefore out of scope for automated collection.** Its five
registry rows record it as a live source; it is not one, and it is not dead
either.

`hud.gov/robots.txt` is a stock Drupal file. It disallows `/core/`,
`/profiles/`, `/admin/`, `/search/` and `/user/*`. **No ONAP path is
disallowed.** There is no JSON:API, no sitemap and no RSS.

---

## 7. Registry health — 9 of 19 HUD rows are not usable

Every registered HUD row was checked live. A 200 is not health: the dead
legacy ONAP path returns **HTTP 200 with 43 characters of visible text**
wrapped in 105KB of inline CSS.

| State | Rows |
|---|---|
| CONTENT | 10 |
| HTTP_ERROR | 7 |
| REACHABLE_BUT_EMPTY | 2 |

The registry's own `HUD-DEAD-LEGACY-PATHS-NEGATI-F77A25` negative-control row
already flagged the dead path, and the live check independently confirmed it.
That row worked exactly as intended.

**Requires MAYHEM's decision — not changed here, because terms status is a
governance flag:**

- `HUD-ONAP` — Tier 1, "Very high", **`terms_status: NO_REVIEW_REQUIRED`**,
  URL `hud.gov/hud-partners/codetalk` → **404**
- `HUD-IHBG` — Tier 1, "Very high", **`NO_REVIEW_REQUIRED`**,
  URL `hud.gov/hud-partners/codetalk-ihbg` → **404**

These are the two most activation-ready rows in the HUD set and both point at
dead URLs. The live hub is `hud.gov/codetalk`, already registered separately
as `HUD-ONAP-CODETALK-HUB-5CA7C5`.

One open research question in the registry is now answered: row
`HUD-IHBG-COMPETITIVE-IHBG-CO-AB76ED` recorded *"NOFO number inconsistent
on-page (N-43 vs N-48) — verify via Grants.gov"*. **It is `FR-6900-N-48`.**

---

## 8. Implementation

No new adapter. No new collection framework. No migration.

**`program_office_roster_service.py`** (new, generic) — funding-vehicle
classification, programme identity, and the stale-reference guard.

**`grants_gov_search_api_adapter_service.py`** (extended) —
`search_grants_gov_by_assistance_listing`, its request-body builder, and
`eligibility_facet_coverage_gap`. The `cfda` filter and `alnist` reading
already existed; this makes programme discovery a first-class path alongside
eligibility discovery rather than something bound to a seed id.

### Bugs caught by the work, not by luck

1. **The trailing word boundary, a third time.** `\bnofo\b` cannot match
   "NOFOs", and a real page reads *"in all applicable program NOFOs"*. This is
   the identical bug that classified two Federal Register funding notices as
   OTHER. Caught before shipping; the closing boundary is gone and the reason
   is written above the pattern.

2. **A 700-character truncation in my own probe** classified ICDBG — a
   programme with a live $90M forecast — as PROGRAM_INFORMATION, because
   "Notice of Funding Opportunity" sits at character 718. The instrument was
   the bug. A regression test now pads the description.

3. **`declared_applicant_types` returned `[]` when the field was absent.**
   The live search response carries no applicant types, and `[]` reads as
   "declares no applicant types" — the same shape as the real answer for the
   record this path exists to find. It would have recreated the blind spot
   inside the fix for it. Absent is now `None`, with an explicit flag.

4. **A policy notice filed in the financial-assistance lane.** A notice
   telling grantees what to exclude when calculating income matched no policy
   pattern, so its only signal was the "Title VI Loan Guarantee program" it
   lists among the programmes it affects. *A notice about a programme is not
   that programme* — the same error in its fifth costume.

5. **The roster summary counted labels, not verdicts**, so it reported fewer
   opportunity-bearing programmes than its own routes did.

### A page is not a programme

Seven of eight ONAP programme pages carry more than one funding vehicle. One
page covers a block grant *and* a loan guarantee; another describes a
competitive track *and* a "noncompetitive, first come-first served" track.
Returning one confident label for either averages two kinds of money into one
wrong answer, so multi-signal records are flagged
`requires_program_level_split` and `may_bear_opportunity` is deliberately
asymmetric: true if **any** signal is competitive. A false positive costs one
referral that canonical resolution discards. A false negative costs a Tribe
money it never saw.

---

## 9. False positive / false negative review

**False positives — all referred records inspected, not sampled.** One record
would reach the referral path: `FR-6900-N-74`. It has funding, a deadline, an
application, and eligibility prose naming Tribes. **Zero false positives.**

**False negatives.** Fifteen announcements and eight programme pages reviewed
for money language in non-bearing records. Two flagged, both adjudicated
correct: the ICDBG Imminent Threat mention duplicates `FR-6900-N-74`, already
captured canonically; the FY2027 IHBG allocation estimate is formula money,
real and not pursuable.

One known imprecision, stated plainly: **Native Hawaiian Programs** is
classified COMPETITIVE_GRANT on an incidental mention of *"applicable program
NOFOs"*. It is a false positive in the safe direction — canonical resolution
discards it.

---

## 10. Verification

```
78  new tests (44 gate 182B, 34 gate 182C)
994 passed across gates 77, 171, 172, 173, 176, 179, 181, 182,
    source registry and seed corpus
~90 real network requests, bounded
0   migrations
```

**One known failure, pre-existing and deferred:**
`test_gate143_source_monitoring_preflight.py::test_the_committed_artifacts_match_what_the_service_builds`.
The artifact pins `files_scanned: 1281`; Tranche 2A took it to 1282 and 2B to
1283. It was already red at `62a71b3`. Per the Wave 1 pattern, artifacts are
regenerated **once** at tranche-set close, not per tranche.

---

## 11. Activation decision

**CONTRACT_PROVEN: yes** for `hud.gov` ONAP surfaces — robots checked, content
verified reachable by a plain HTTP client, structured alternatives ruled out
by evidence rather than assumption.

**COLLECTOR_ACTIVATED: no.**

**Final state: ACTIVATE AS DISCOVERY / ENRICHMENT SOURCE — pending, not
activated.** Registry rows remain `seed_imported` / `not_started` /
`TERMS_REVIEW_REQUIRED`. No governance flag was changed.

The reason ONAP should never be activated as an *opportunity* source is
measured, not stylistic: it publishes zero opportunity records, and its links
to the ones that exist are a fiscal year out of date.

**HUD Exchange: DO NOT ACTIVATE.** UA-conditional refusal.

---

## 12. The durable lesson, carried forward

Tranche 2A established that **source trust and record routing are separate
decisions**. 2B adds the sharper form:

> A source can be worth activating precisely because of what it is *not*.
> ONAP's value is that it tells you which assistance listings to ask the
> canonical source about — a question the canonical source cannot answer about
> itself.

And the one that cost the most to learn:

> A 404 can be a refusal, a 200 can be an empty page, and a plausible zero can
> be a filter you spelled wrong. Falsify the instrument before believing the
> measurement.
