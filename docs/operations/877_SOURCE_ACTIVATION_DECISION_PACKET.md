# 877 — Source Activation Decision Packet

Reconciled from repository code and committed evidence on **2026-10-02** at
`HEAD = ORIGIN_MAIN = LIVE_SHA = 6d50e01d`.

**Zero sources were activated to produce this packet.** No warrant was minted,
no collector was enabled, no production customer state was mutated, no live
publisher request was issued by this reconciliation. Every measurement quoted
below is a dated measurement someone else already took and committed; where a
number is a sample it is labelled a sample, and where a thing is unknown it is
written UNKNOWN rather than estimated.

This packet does not rank publishers and does not recommend authorization.

---

## 0. A correction to the roster before anything else

The instruction names **twelve** contract-proven publishers. The repository
does not evidence twelve. It evidences:

| Close | Claim in the document | Publishers enumerated with a commit |
| --- | --- | --- |
| Wave 1 (`868`) | "has met **six** real publishers" | 5 surfaces / 4 distinct publishers |
| Tranche 2 (`873`) | "**Five** publishers are contract-proven" | 5 |

Six plus five is **eleven**, and neither document enumerates a twelfth. The
Wave 1 count of six is itself unreconciled: its own section headings name
Grants.gov (two lanes), USAspending, Denali Commission and the California
statewide feed — four publishers across five surfaces.

Rather than invent a twelfth or silently deliver eleven, this packet covers
the **ten publisher surfaces that carry a commit and dated live evidence**,
and records the discrepancy as the first decision item. If the intended twelve
includes SAM.gov assistance listings and the Grants.gov daily extract — both
named in `PHASE1_SOURCE_IDS` but never contract-proven against a live
publisher — say so and they will be added as NOT PROVEN rows.

---

## 1. HUMAN SOURCE AUTHORIZATION REGISTER

What each row needs from a human, without reconstructing engineering history.

| # | Publisher surface | Class | Native-specific | Evidence | Activation state | Blocking item |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Grants.gov — eligibility facet | Federal aggregator | Broadly eligible, facet-filtered | REAL 2026-09-24 | **COLLECTING** via operator cron | none — running |
| 2 | Grants.gov — forecasts | Federal aggregator | Broadly eligible, facet-filtered | REAL contract / FIXTURE transition | NOT ACTIVATED | AUTHORIZATION + CODE |
| 3 | USAspending | Prior-award evidence | Broadly eligible | REAL 2026-09-25 | NOT ACTIVATED | **AUTHORIZATION WITHHELD** + classification |
| 4 | Denali Commission | Regional commission | Geographic, not Native | REAL | NOT ACTIVATED | AUTHORIZATION + CODE |
| 5 | California statewide | State portal | Broadly eligible | REAL 2026-09-24/25 | NOT ACTIVATED | AUTHORIZATION + CODE |
| 6 | Federal Register | Policy / early signal | Broadly eligible | REAL | NOT ACTIVATED | **AUTHORIZATION WITHHELD** |
| 7 | HUD ONAP | Programme roster | Native-specific | REAL | NOT ACTIVATED | AUTHORIZATION + CODE |
| 8 | IHS | Eligibility prose | Native-specific | REAL | NOT ACTIVATED | AUTHORIZATION + CODE |
| 9 | EPA | Enrichment / channel | Mixed | REAL | NOT ACTIVATED | AUTHORIZATION + CODE |
| 10 | CDFI Fund | Early signal | Certification axis | REAL | NOT ACTIVATED | AUTHORIZATION + CODE |

### The single fact that shapes every row

`source_collector_capability_service.ADAPTER_CAPABILITIES` contains **one
key**: `grants_gov_search2`. Wave 1 and Tranche 2 added no entries to it.

Authorization alone therefore activates **nothing** for rows 2 and 4–10. A
signed authorization would produce a source the fleet still cannot dispatch,
because capability is checked before a warrant is even considered. Every row
marked `AUTHORIZATION + CODE` needs both, and the code is not a formality:
`canonical_opportunity_normalizer_service` also has a parser only for
`grants_gov_search2` search hits.

**This is the most consequential finding in the packet.** A decision to
authorize is not a decision that makes opportunities appear.

### Rows carrying a standing refusal

- **USAspending (3)** — carries zero NOFOs. `PRIOR_AWARD_ONLY_SOURCES`
  classifies it so its records can never be surfaced as open opportunities.
  Standing instruction: unauthorized unless newer explicit evidence proves
  otherwise. Technical readiness is not authorization.
- **Federal Register (6)** — same standing instruction. It is an early-signal
  and policy surface, explicitly "not an opportunity feed".

---

## 2. What activation actually requires

`source_live_warrant_service` refuses a `source_collection` warrant unless all
of the following hold. Each is a separate recorded fact, and the absence of a
check is treated as a failure rather than as a pass:

```text
live-fetch opt-in        REQUIRED  (not required for robots preflight)
terms signed             REQUIRED
review signed            REQUIRED
activation signed        REQUIRED
attribution satisfied    REQUIRED
robots preflight         REQUIRED, exactly /robots.txt, GET
```

Beyond the warrant, `phase1_collector_activation_policy_service` requires
per-source preconditions, and holds three answers apart because they fail
independently:

```text
may_fetch_live_now        may a request go out right now
may_schedule_monitor      may a recurring check be scheduled
may_surface_customer_data may results reach a customer
```

### Current registry state

All **381** registry rows remain `registry_status=seed_imported`,
`monitoring_status=not_started`, and the committed artifact records
`collector_activated: false` (Tranche 2 close, `873`).

### Why Grants.gov collects while `collectors_live` is 0

Not a contradiction, and worth stating precisely because it looks like one.
`collectors_live` is "derived from fleet gate evidence". The Railway cron does
not use the fleet: it invokes the warrant-gated operator script directly.

```bash
python scripts/run_gate163_grants_gov_bounded_corpus_collection.py \
    --apply --pass 1 --rows 200
```

Observed working on 2026-10-02: the Railway cron service reported **"Last run
succeeded / Next in 3 hours"**, and the customer Workspace moved from
**80 to 280 opportunities tracked** between two observations the same day.
Per standing instruction this cron was not modified and must not be absent an
evidenced defect.

---

## 3. Per-publisher evidence

Fields are UNKNOWN where the repository does not evidence them. Nothing here
is inferred from a plausible-sounding neighbour.

### 3.1 Grants.gov — eligibility-facet discovery · `91d008c` · REAL

- **Identity / surface**: `POST api.grants.gov/v1/api/search2`, public, no key
- **Class**: federal aggregator · **Native-specific**: no, facet-filtered
- **Evidence**: live contract verified 2026-09-24, re-verified at
  implementation. Evidence location: `868` §Grants.gov
- **Proposes to collect**: posted opportunities filtered on the publisher's
  eligibility facet, not on title keywords
- **Mechanism**: `grants_gov_search_api_adapter_service`, the only entry in
  `ADAPTER_CAPABILITIES`
- **Technical readiness**: READY — the only surface that is
- **Activation state**: COLLECTING via operator cron (see §2)
- **Measured yield (2026-09-24)**: 946 posted; code `07` federally recognized
  Tribal governments **464**; code `11` tribal organizations other **418**;
  code `08` Indian housing authorities **379**; keyword `tribal` 276
- **Measured Native-relevant yield**: of the first **100 sampled** elig-07
  titles, **4** contained Native wording. *This is a sample, not a population
  rate.* No percentage is asserted anywhere in the code
- **Agency distribution of the 464**: HHS 375, Justice 35, Commerce 15,
  Interior 11, Agriculture 8, Transportation 3, Energy 3, Housing 2 — solves
  federal health and social services, does **not** solve infrastructure
- **Terms / attribution**: attribution REQUIRED before results are surfaced
  (`ATTRIBUTION_GATED_SOURCES`)
- **Known failure mode**: a renamed facet label returns
  `facet_contract_changed` with zero hits — distinguishable from genuinely
  empty. An earlier pass assumed codes `24`/`25`, got a plausible 693 hits
  from `25`, and they were NIH clinical-trial notices. `25` means "Others"
- **UNKNOWN**: whether publisher eligibility coding is itself reliable; the
  fix moves trust from our heuristic to the publisher's coding, which is a
  better place for it and not zero-risk

### 3.2 Grants.gov — forecasts · `6f00600` · REAL contract / FIXTURE transition

- **Measured**: 431 forecasted elig-07 reported; 100 sampled; `docType:
  "forecast"` and `oppStatus: "forecasted"` confirmed on the wire
- **`REAL_FORECAST_TO_POSTED_PAIR_OBSERVED = false`** — zero overlap between
  100 sampled forecast numbers and 100 sampled posted numbers. A bounded
  sample of 431 and 464: it does **not** prove no pair exists
- **Technical readiness**: adapter lane exists; **not in
  `ADAPTER_CAPABILITIES`**
- **Blocking**: AUTHORIZATION + CODE

### 3.3 USAspending · `86e15ce` · REAL evidence, UNKNOWN filter

- **Surface**: USAspending API v2, public, no key, verified 2026-09-25
- **Class**: prior-award evidence — **carries zero NOFOs**
- **Observed real Tribal awards** (bounded examples, not a survey):
  Navajo Nation / HHS $15,362,285.65 · Navajo Nation / Interior $3,333,334.00
  · Cherokee Nation / DOT $4,796,507.00
- **`recipient_type_names` is not proven**: it silently accepts values it does
  not recognise — `"utter_nonsense_not_a_category_xyz"` returns `results: []`
  with no error while `nonprofit` returns rows. Twelve plausible tribal
  category names all returned zero on an instrument re-verified as working.
  Evidence the vocabulary is **unknown**, not that no Tribal awards exist
- **`recognition_class` stays UNKNOWN** — the awards were found by
  `recipient_search_text`, and name matching cannot distinguish a federally
  recognized Tribal government from a state-recognized one
- **`REAL_EXACT_SOLICITATION_LINKS_PROVEN = false`**;
  `real_award_evidence_available_for_miss_detection` remains FALSE
- **Linkage discipline**: a shared assistance listing is `PROGRAM_LEVEL_ONLY`,
  never a link. Same listing *and* same agency is still `PROGRAM_LEVEL_ONLY` —
  two agreeing weak signals are not one strong one. Only a publisher-named
  opportunity number is `CONFIRMED_LINK`
- **Blocking**: **AUTHORIZATION WITHHELD** by standing instruction, plus the
  `prior_award_only_classification` precondition

### 3.4 Denali Commission · `cdf8063` · REAL

- **Surface**: `denali.gov/wp-json/wp/v2/` — WordPress REST, public. Stable
  integer ids, `modified` timestamp, pagination in headers (`x-wp-total: 18`)
- **Research baseline was wrong twice**: it said HTML (the publisher offers
  JSON) and named the wrong pages (`/funding-requests/` is an interactive
  database and link list; `/grants/` is policy guidance; the actual notices
  are posts)
- **robots.txt**: `User-Agent: * / Disallow:` — empty Disallow, everything
  permitted. Checked **before** anything was collected
- **Native-specific**: **no — Alaska is not Native**, proven on live record
  4048: `native=[]`, `geo=['alaska','rural']`,
  `has_geography_only_signal=true`. The tribal victim services notice returns
  `native=['tribal']` because the publisher said so. The adapter returns
  evidence, never a verdict
- **Mechanism**: `wordpress_rest_listing_adapter_service` — generic. ARC and
  NBRC would be configuration rows, not new code
- **Blocking**: AUTHORIZATION + CODE (generic adapter is not in
  `ADAPTER_CAPABILITIES`)

### 3.5 California statewide feed · `ef868a4` · REAL

- **Surface**: CKAN, California State Library, **Public Domain**,
  `metadata_modified` 2026-09-24
- **Lifecycle, measured 2026-09-25**: total rows **2,010** · closed **1,838** ·
  active **170** · forecasted **2**
- **2,010 rows is not 2,010 open opportunities** — quoting the row count would
  overstate the open pipeline by 1,838 records, and the overstatement would be
  invisible because every row is real, well-formed and correctly published
- **Native-relevant, measured**: **109 of the 170 open rows** name "Tribal
  Government" in `ApplicantType` — publisher-declared, California's analogue
  of Grants.gov code 07. 28 mention tribal in description or purpose
- **Also measured**: 37 fields · 170 carry a deadline and grant URL · 31 carry
  a match requirement · **26 open rows are Loans, not grants**
- **Identity hazard**: `distinct PortalID = 2,010` (one per row);
  `distinct GrantID = 403` (shared across rounds); **GrantID is nullable**.
  Keying on the programme id would fuse five years of rounds into one record,
  lose four in five, and crash on the nulls
- **Blocking**: AUTHORIZATION + CODE

### 3.6 Federal Register · `62a71b3` · REAL

- **Role**: early signal, policy, consultation and intelligence — **not an
  opportunity feed**
- **The adapter already existed** and its own descriptor said
  `"PROPOSED_NOT_VERIFIED_BY_THIS_REPOSITORY"`. It was verified live; no second
  adapter was written
- **`count` is capped at 10000** — an unfiltered query returns exactly 10000
  and an absurd term returns 0, so **any measurement equal to the cap is a
  floor**. No capped number is quoted as a population
- **Bounded 2026-07-01..09-25**: 6,295 documents · 989 matching *tribal* ·
  461 funding-opportunity · 305 repatriation
- **100 real tribal-matching documents classified**: 47 POLICY_RULEMAKING →
  early signal; 22 ADMINISTRATIVE → not routed (remainder in `873` §2A)
- **Blocking**: **AUTHORIZATION WITHHELD** by standing instruction
- **UNKNOWN**: Federal Register document-host access

### 3.7 HUD ONAP · `8b49182` · REAL

- **Role**: programme roster and discovery surface. **Grants.gov owns the
  records**
- **Why the surface is needed**: Grants.gov exposes ONAP only as
  `agencyCode: HUD` — there is no ONAP filter, so *"show me ONAP's
  opportunities"* is a question the canonical source cannot answer about
  itself. The assistance listing can
- **The finding that justified the tranche**: `FR-6900-N-74`, ICDBG Imminent
  Threat — **$5,000,000 estimated / $1,500,000 ceiling**, no cost share,
  closing 2026-09-30, eligibility text *"Eligible applicants are Tribes and
  Tribal organizations as described in the ICDBG regulations at 24 CFR
  §1003.5"* — declares applicant type **25 only**. Codes 07, 08 and 11 return
  it **zero times out of three**; ALN 14.862 returns it immediately
- **Measured**: found by eligibility 106 (floor: first page of each code) ·
  found by assistance listing 1 · found by both **0**
- **Freshness failure**: IHBG-COMP links FY2025 and FY2024 (both closed);
  ICDBG links FY2025 (closed). Live FY2026 forecasts — **$125M and $90M** —
  are linked from neither. **3 of 3 stale**
- **Known failure mode**: **HUD Exchange returns 404 to this user agent and
  200 to a browser one** — a refusal disguised as absence. A browser string was
  sent **once, as a diagnostic, never to collect**. HUD Exchange is out of
  scope; its five registry rows describe a source neither live nor dead
- **Blocking**: AUTHORIZATION + CODE

### 3.8 IHS · `5f423d3` · REAL

- **Role**: eligibility prose and documents. **Grants.gov owns the records**
- **Complete corpus pulled uncapped**: **245 records**. **18 current
  opportunities, and the eligibility facet found all 18** — the exact opposite
  of HUD, which is why the brief forbade generalising
- **Four are missed by codes 07/08/11 and do not fail the same way**: Tribal
  Epidemiology Centers ($7,000,000, Tribe named) · Urban Indian 4-in-1
  ($9,707,858) · Urban Indian Educ. & Research ($1,450,000) · National Urban
  Indian BH ($200,000, Tribe **not** eligible)
- **Code 25 contains both Tribe-eligible and Tribe-ineligible Native-serving
  money.** Collapsing to `tribal = true` would show a Tribe **$11.36M it
  cannot apply for** and still be wrong about the $7M it can
- **Recognition is a separate field from entity class**: across all 18, 14
  name a Tribe, 3 UNKNOWN, 1 NO — and only **8 of 18** state a federal
  recognition requirement. Never inferred in either direction
- **Freshness failure**: **26 of 26** first-party Grants.gov links are closed
  rounds while 17 live FY2027 forecasts go unlinked
- **Fixed in this tranche**: ALN alphabetic suffixes (`93.00K`, `93.00E`,
  `93.00F`, `93.00G`, `93.00L`, `93.00P`) were real listings the 2B validation
  regex refused outright
- **Blocking**: AUTHORIZATION + CODE

### 3.9 EPA · `3221b36` · REAL

- **Role**: enrichment and channel intelligence. **Its structured records
  contain no eligibility at all**
- **Complete corpus**: **1,491 records**
- **Deferral measured across the complete current-and-closed set**: EPA
  sampled 5, defers to document 5, states 0 → **100%**. IHS sampled 32, defers
  0, states 30 → 0%. HUD sampled 40, defers 0, states 40 → 0%
- **Document intelligence is therefore load-bearing for EPA**, not optional
- **Flagship**: `EPA-OW-OWOW-26-01` (id 363611), ALN 66.460, **$3,500,000 /
  $175,000 ceiling / cost share true**, closing 2026-11-09, one attachment —
  *its only machine-readable Native evidence is its title*
- **The channel question**: the wastewater set-aside reads *"Tribes must
  identify their wastewater needs to the IHS Sanitation Deficiency System"* —
  **EPA holds the money; another agency holds the queue.** 2 of 5 measured
  programmes are directly applicable; **3 are real money nobody applies for at
  EPA**
- **Only publisher whose first-party link is current**: 1 link, 0 stale (the
  complete set, stated as such) — and the inverse of IHS: its own DWIG-TSA
  page supplies *"Any federally recognized Tribe is eligible"*, the
  eligibility Grants.gov omits
- **Found by codes 07/08/11**: **0 of 4**; rescue path is code 25 only
- **UNKNOWN**: whether EPA's deferred-eligibility documents parse cleanly —
  the documents were identified, **not ingested**
- **Blocking**: AUTHORIZATION + CODE

### 3.10 CDFI Fund · `3deb1f7` · REAL

- **Role**: early signal and programme intelligence. **Zero open
  opportunities — and that is the correct answer**
- **Complete corpus**: **63 records, every one archived**, 2007→2026
  continuous including FY2026 opened 2026-06-30
- **The zero is real**: negative control `USDOT-NONSENSE` returns 0. **No
  false source-health failure — a quiet publisher is not a broken one**
- **Certification is not identity**: NACA's gate is *"Certified CDFIs,
  Emerging CDFIs, and Sponsoring Entities"* — three certification states,
  **zero** statutory Native entity classes. The entity reader returns `[]`
  here, which is correct and incomplete. Certification is now an orthogonal
  axis (`CERTIFICATION_HELD_REQUIRED` / `EMERGING_CERTIFICATION_PATH` /
  `SPONSORING_ENTITY` / `NOT_MENTIONED`), verified orthogonal on live prose
- **Recurrence is IRREGULAR, not annual**: seven real rounds, no FY2023 round,
  344-day spread. The human read them as "annual, December–February";
  `program_recurrence_service` graded IRREGULAR with no expected window.
  **The detector was right and the eyeball was wrong**
- **Agency code hazard**: `TREAS`, `TREAS-CDFI` and `CDFI` all returned
  exactly what `NONSENSE` returned. The real code is `USDOT-CDFI`, found only
  by reading records
- **Blocking**: AUTHORIZATION + CODE

---

## 4. Coverage language

Kept separate on purpose, because collapsing them is how a product starts
lying.

- **SOURCE COVERAGE** — coverage of the explicitly defined authoritative
  source universe. Ten surfaces proven; one collecting.
- **INTELLIGENCE COVERAGE** — completeness of source-backed relevance,
  eligibility, monetary value, requirements and provenance among opportunities
  already in the corpus.
- **Overall Native funding-market coverage remains UNKNOWN.** There is no
  defensible denominator. The historical ~14.29% known-dollar-value figure is
  **not** market coverage and is not used as one anywhere in this packet.

### The discovery invariant this packet must not erode

```text
ELIGIBILITY != VISIBILITY
ELIGIBILITY != RELEVANCE
ELIGIBILITY != STRATEGIC VALUE
```

Eligibility and downstream intelligence must never silently remove a relevant
opportunity from discovery. The IHS and HUD findings are the evidence for why:
an eligibility facet that looks authoritative missed a $5M ICDBG award
entirely, and code 25 mixes money a Tribe can win with money it cannot.

---

## 5. Decisions required from Mayhem

1. **Roster** — confirm the intended twelve, or accept these ten. SAM.gov
   assistance listings and the Grants.gov daily extract are named in
   `PHASE1_SOURCE_IDS` but are not contract-proven; SAM.gov additionally
   carries a `no_scraping_ack` precondition because its terms prohibit the
   obvious implementation outright.
2. **USAspending (3) and Federal Register (6)** — both remain unauthorized by
   standing instruction. Neither is blocked by engineering.
3. **Rows 2, 4, 5, 7, 8, 9, 10** — authorization is necessary but **not
   sufficient**. Each additionally needs an `ADAPTER_CAPABILITIES` entry and a
   canonical parser. Authorizing them today switches nothing on.
4. **Whether to fund the code work at all**, and in what order — this packet
   deliberately does not rank them.

---

## 6. Carried forward, unresolved

- **Gate 170 `j_reopened_seen`** — root cause remains **UNKNOWN**. This
  investigation produced no evidence resolving it and it is not relabelled.
- EPA deferred-eligibility document parsing — identified, not ingested.
- USAspending Tribal recipient-category vocabulary — UNKNOWN.
- Real applicant-class coverage for publishers whose eligibility lives only in
  PDFs.
- Whether any real forecast→posted pair exists in current publisher data.

---

## 7. Provenance of this packet

Every claim above is sourced from one of:

```text
docs/operations/868_WAVE1_SOURCE_EXPANSION_INTEGRATED_CLOSE.md
docs/operations/873_TRANCHE2_INTEGRATED_CLOSE.md
src/nativeforge/services/source_collector_capability_service.py
src/nativeforge/services/phase1_collector_activation_policy_service.py
src/nativeforge/services/source_live_warrant_service.py
src/nativeforge/services/backend_health_readiness_service.py
scripts/run_gate163_grants_gov_bounded_corpus_collection.py
docs/operations/grants_gov_scheduled_collection_railway.md
```

plus two first-hand observations on 2026-10-02: the Railway cron service
reporting "Last run succeeded / Next in 3 hours", and the customer Workspace
moving from 80 to 280 opportunities tracked.

`docs/operations/SOURCE_INGESTION_COVERAGE_INVENTORY.md` is dated 2026-09-28
and **predates Wave 1 and Tranche 2**. It was read and deliberately not relied
on for adapter state; `ADAPTER_CAPABILITIES` was read from code instead. Its
central claim happens to still hold: one adapter key.
