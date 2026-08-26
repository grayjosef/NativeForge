# NativeForge — build brief for the coding agent

## 0. Before you write code: read the research

A full source-discovery pass has already been done (research date 2026-08-26, ~300 official primary pages fetched and verified). **Do not re-derive it, do not guess at anything it marks UNKNOWN, and do not "fix" its URLs from memory — several correct URLs look wrong and several familiar URLs are dead.**

Copy these files into the repo (suggested `docs/research/`) and read them in this order:

| File | Read it for |
|---|---|
| `nativeforge-funding-source-dossier-v2.md` | **Start here.** The whole map: federal/state/private source universe, the pass-through model, the eligibility matrix, the scraper architecture, priority tiers, and the open questions. Sections 11 and 14 are the engineering spec. |
| `nativeforge-source-registry-v2.csv` | The 381-row machine-readable registry you will load as seed data. 26 columns, schema documented in dossier §14. |
| `ext-apis-monitoring.md` | **The most important file for you.** Endpoint-level detail: exact URLs, request/response fields, auth, rate limits, pagination caps, robots.txt findings per host, dedup key design, polling cadences, forecast→posted and amendment detection. Every claim is tagged `[DOC]` (read in official docs), `[TESTED]` (live call made), or `[INFER]` (engineering judgment). **Respect those tags — do not promote an `[INFER]` to a contract.** |
| `nativeforge-research-funding-and-cost-allowability.md` | 2 CFR 200 analysis with exact citations, the cost-category × allowability table, and the research-funding source list. This is what the product tells customers about paying for the platform. |
| `ext-doi-hhs` content inside `ext-extra-tables.md`, plus `ext-doe-epa-dot.md`, `ext-usda-hud-commerce.md`, `ext-doj-dhs-ed-dol-sba.md` | Per-agency backup evidence and verification logs. Go here when a registry row's `notes` field isn't enough. |

Source location on this machine (copy, don't reference in place):

```
C:\Users\JosefGray\AppData\Roaming\Claude\local-agent-mode-sessions\a9a92ccb-6df5-441f-8858-1c69adf33d67\6ca39871-622f-44fa-bf07-76717a7d6274\local_149805d5-a329-4e35-8cde-bbedaa99a2d6\outputs\
```

---

## 1. What NativeForge is

A grant-intelligence and pursuit platform for Tribes, tribal organizations, Native nonprofits, Native-owned businesses, tribal colleges and BIE schools, and Native-serving entities. First customers are in **South Carolina**, which matters enormously — see §6.

Your job in this phase: **build the source registry, the collectors, and the opportunity store.** Matching/ranking/UI come later, but the data model decisions you make now determine whether they're possible.

---

## 2. Build order — the Top 25, in this sequence

Do not build 381 collectors. The registry's `priority_tier` column is a backlog priority, not a build order. Build order is:

**Phase 1 — the spine (nothing else works without it)**

1. **Grants.gov daily XML extract** — `https://prod-grants-gov-chatbot.s3.amazonaws.com/extracts/GrantsDBExtract<YYYYMMDD>v2.zip`. 78 MB, published ~04:40 ET, **only 7 days retained**. This is the corpus of record. A failed fetch is a paging-level alert, not a retry — a missed day is unrecoverable. It is the only source carrying `Estimated Synopsis Post Date`, `Fiscal Year`, `Archive Date`, the 18,000-char description, and the 4,000-char `Additional Information on Eligibility`.
2. **Grants.gov Search2 + fetchOpportunity** (`POST https://api.grants.gov/v1/api/search2`, no auth) — hourly deltas and amendment forensics. `fetchOpportunity` returns `synopsisModifiedFields[]` / `forecastModifiedFields[]`, a literal list of what the agency changed. Nothing else in the federal ecosystem gives you this. **Render it to users directly** — "the close date changed," not "something changed."
3. **Federal Register API** (`/api/v1/documents.json`, no key) — including the **Public Inspection** endpoints, which surface documents 1–3 business days *before* publication. `conditions[agencies][]=indian-affairs-bureau` returns 3,313 documents and is a better instrument for BIA than bia.gov itself.
4. **SAM.gov Assistance Listings API** — ALN semantics and tribal eligibility codes.
5. **USAspending API v2** — prior-award intelligence, not discovery.

**Phase 2 — Native discovery layer** (items 5–24 of the dossier's Top 25 list): BIA Access to Capital Clearinghouse, IHS DGM index + Tribal Leader Letters, BIA grants index + news + sitemap, HUD `codetalk`, DOJ OJP + CTAS, EPA GAP + tribal water, DOE Indian Energy + IE-Exchange, FHWA TTP + TTPSF, FTA tribal, USDA RD tribal + NIFA, FNA FDPIR, HRSA, NIH THRO + NARCH, Treasury CDFI NACA, FEMA via Grants.gov, ED Available Grants, DOL DINAP.

**Phase 3 — the customer's state bundle.** For the first customers that's South Carolina (§6).

---

## 3. Non-negotiable constraints — get these wrong and we have a legal problem, not a bug

1. **Mandatory attribution.** Any UI surface using the Grants.gov API must display, verbatim: *"This product uses the Grants.gov API but is not endorsed or certified by the U.S. Department of Health and Human Services."* This is a build requirement, not a footer nicety.
2. **SAM.gov prohibits scraping outright** — *"Automated data gathering, web scraping tools are prohibited and, if detected, will result in the associated account(s) being denied access to SAM.gov via Login.gov."* API-with-key only. And **the rate limit is the binding constraint: 10 requests/day for a non-federal user with no SAM role, 1,000/day with a role.** Get a role before building anything on it.
3. **Never present an AI-crawler user-agent.** `hud.gov` robots.txt names `ClaudeBot`, `GPTBot`, `CCBot` and others with `Disallow: /` and asserts `ai-train=no` as a condition of access, invoking Article 4 of EU Directive 2019/790. `arts.gov` (NEA) carries an explicit `ClaudeBot` full-site disallow plus `Crawl-delay: 300`. Use one descriptive user-agent identifying NativeForge with a contact URL.
4. **`Disallow: /search/` is near-universal** (sam.gov, ojp.gov, hud.gov, epa.gov, energy.gov, grants.nih.gov, rd.usda.gov, bia.gov). A monitor polling site-search URLs violates robots on almost every agency host. Poll sitemaps, listing pages, feeds, or APIs. `nifa.usda.gov` additionally carries `Disallow: /*?*`, killing all query-string URLs — use its clean-URL RFA index.
5. **Do not build on any source flagged `HUMAN_REVIEW_ONLY` or `TERMS_REVIEW_REQUIRED`** in the registry until legal signs off. That includes CDC (redistribution of syndicated content barred, citing reproduction *for a fee* — which implicates a paid product), FEMA (robots.txt and OpenFEMA T&C both unretrievable), Candid (paid license), and Native Americans in Philanthropy's Grantwatch (member-benefit feed).
6. **Rate discipline:** exponential backoff on 429/5xx; a circuit breaker that halts a source after N consecutive failures and pages a human rather than retrying into a block; per-host concurrency of 1; self-impose ~1 req/5s per host since almost no host publishes a Crawl-delay. `energy.gov` timed out twice at 180s then served fine — build retry-with-backoff, don't mark it dead.

Per-source cadence table is in dossier §11.2. Follow it.

---

## 4. Data model requirements derived from verified findings

These are not preferences. Each one exists because the research found a case that breaks the naive model.

**Identity and dedup (dossier §11.3, `ext-apis-monitoring.md` Part C):**

- Primary key: normalized `opportunityNumber` (uppercase, strip whitespace/hyphens). Store the numeric `opportunityId` as a surrogate — it's the required input to `fetchOpportunity`. **Never key on title.**
- **Composite key is `(opportunityNumber, docType)`** where `docType ∈ {forecast, synopsis}`. A forecast and its resulting synopsis **share the opportunity number.** Collapsing them destroys the transition you most need to detect.
- Version rows are immutable: `(opportunityId, docType, revision)`. Never update in place.
- **ALN is many-to-many, never a scalar column.** One opportunity can carry several (`alnist[]`).
- **Build an explicit agency crosswalk table.** Grants.gov `agencyCode`, Federal Register `agencies[].slug`/`parent_id`, and SAM's FPDS/AAC codes are three non-matching namespaces. Do not string-match agency names.
- Fuzzy fallback for sources with no identifier: `SHA-256(normalized_agency + normalized_title + earliest_deadline_date)` with a near-match pass, resolving up to the real key as soon as an opportunity number appears. BIA announced a live solicitation *only* as a press release — that's the live case.

**Eligibility must be a graded classification, not a boolean.**

- Grants.gov codes: `07` = federally recognized tribal governments, `11` = tribal organizations other than federally recognized, `08` = Indian housing authorities.
- SAM.gov Assistance Listings: `ET23010` / `ET23020` / `ET23030` map 1:1 onto `07` / `11` / `08`.
- **The recall set must also include `99` (Unrestricted), `25` (Others), and SAM's `ET12010` (determined at NOFO level).** `99` is silently tribe-eligible; `25` and `ET12010` hide eligibility in free text and the NOFO PDF. **A filter matching only `07|11` will look clean and silently miss a large share of tribally-eligible money — that is the exact failure the product exists to prevent.** Model a confidence/precision tier, not a yes/no.
- Eligibility classes are a controlled vocabulary: `federally-recognized-tribe, state-recognized-tribe, tribal-government, tribal-organization, native-nonprofit, native-owned-business, native-serving-nonprofit, tribal-college-or-BIE-school, native-individual, consortium-with-tribal-partner, state-or-local-govt-serving-natives, UNKNOWN`.
- Carry a distinct **`fiscal_sponsorship_accepted`** flag and a **501(c)(3)-not-required** flag. Many tribal governments are not 501(c)(3)s, and the best Native funders (First Nations Development Institute, Potlatch Fund) explicitly admit tribal governments, Native 7871 organizations, fiscally-sponsored groups, and even entities "Seeking Recognition."
- Support **enumerated-set eligibility**, not just class-based. Reclamation's current tribal drought opportunity is restricted to a hard-coded list of 30 named Colorado River Basin Tribes.

**Deadlines are harder than one date field.**

- **Dual deadlines**: every DOJ opportunity has a Grants.gov deadline and a separate JustGrants deadline (11:59 p.m. ET and 8:59 p.m. ET).
- **Per-region deadlines**: EPA GAP has ten different regional deadlines in a single national NOFA. One national date is wrong.
- **Deadlines get revised**: HUD labelled an ICDBG date "New Deadline." Model deadlines as mutable and versioned.
- **Phased deadlines**: USDA NIFA TCRGP has phase deadlines that appear *only* in an "Upcoming Program Events" block on the program page.
- **Multi-year NOFOs**: FHWA TTPSF's operating document spans 2022–2026 and is currently at Amendment No. 2 — monitor for new amendment numbers, not new NOFOs.
- Deadline pattern is `UNKNOWN` unless verified. **Never synthesize a date from a historical pattern and present it as current.**

**Program vs. page.** 381 rows resolve to 346 unique URLs. That's intentional: the eight CTAS purpose areas share one solicitation URL and have materially different cost rules; OVW's four tribal programs share one page. Model the program, not the page.

**State and geography.**

- Store: state code, county/service-area scope, administering agency + division, parent federal program ALN, eligible applicant classes, eligible **subrecipient** classes (separate field), announcement channel, portal vendor, login-gated flag, page-date-reliability flag, render mode (static vs. needs headless).
- **Apply hard geography filters before ranking.** Clean test cases: Potlatch Fund (ID/MT/OR/WA only), Bush Foundation (MN/ND/SD), Cherokee Preservation Foundation (EBCI/western NC), Bureau of Reclamation (17 Western States). An SC customer must never see any of them.
- `distribution_mode = direct | state_formula | state_competitive | either | unknown`. **Never advertise a federal listing when the live route is a closed state allocation.**

---

## 5. Failure modes that are specific to this domain — write tests for these

1. **Dead shells beat 404s.** HUD's old `/program_offices/public_indian_housing/ih` returns **HTTP 200 with valid HTML and zero body content**, titled `25red-Indian Housing`. A monitor there reports "no change" forever. **Content-length and body-hash checks are mandatory; HTTP status is not sufficient.** Add a rule: a title with a redesign-artifact prefix (e.g. `25red-`) means stale — flag, do not diff.
2. **Trap pages.** `ihs.gov/dgm/forecast/` contains no forecast data at all and just defers to Grants.gov. Don't build a collector against it.
3. **Stale-but-live is worse than dead.** `internetforall.gov` serves `Status: Open` for a TBCP round that closed in January 2023. **Never surface an agency-authored status field without an independent freshness check** (latest internal date vs. today).
4. **Banners are page-scoped, not site-scoped.** `eda.gov/funding` carried an appropriations-lapse notice and literal `test` placeholder text while `eda.gov/funding/programs` was fully current. Suppress the page, don't blacklist the domain.
5. **Tribal set-asides hide inside multi-program PDFs.** EDA's "Assistance to Indigenous Communities" exists only as page 37 of a combined PWEAA/AI-Upskill NOFO. **PDF section extraction is required for tribal coverage, not optional.**
6. **Application portals diverge from marketing pages.** `energy.gov` had cleared a $50M tribal FOA that IE-Exchange still carried. FHWA TTPSF applications go by emailing `TTPSF@dot.gov` for an upload link, not Grants.gov. EPA CWISA's real intake is the **IHS Sanitation Deficiency System**. Monitoring the pretty page under-reports.
7. **URL churn is the top operational risk.** Follow redirects, store the canonical URL from the response, compare against `<link rel="canonical">`, and **alert on 301s.** Diff `bia.gov/sitemap.xml` — BIA renames paths without notice.
8. **Polymorphic fields.** The Grants.gov extract field is "Last Updated Date **or** Created Date" — a value there does not prove an update occurred. Guard for it.
9. **Attachment changes with no synopsis change.** Diff attachment `fileLobSize` + filename to catch a re-issued NOFO PDF behind an unchanged record, and re-run extraction when they move.
10. **Forecast silent death.** A forecast whose `Estimated Synopsis Post Date` has passed with no synopsis and no archive must age into an explicit `forecast_lapsed` state — not sit there looking live. This is the most common failure in naive grant trackers.
11. **Amendment noise must be triaged.** Promote deadline, eligibility (`applicantTypes` delta), and award ceiling/floor changes to notifications. Suppress contact-name and typo churn. Un-triaged amendment noise makes grant alerting unusable.
12. **Blacklist before first crawl:** `scdmh.net` (fetched and found to be a **hijacked casino site**), legacy `scdhec.gov`, and CDC's `/tribal/*` namespace (serves 2016 Zika content — use `/healthy-tribes/*`).

---

## 6. South Carolina — the first-customer path

**Read dossier §9 in full before writing a single SC collector.** The short version:

- **South Carolina has no central grants portal.** Four candidates were checked and all fail. SC coverage is agency-by-agency, full stop.
- **Recognition is the foundation of everything.** SC recognizes Native entities under SC Code §1-31-40(A)(10) via **Advance SC** (renamed from the Commission for Minority Affairs, May 2025 — every `cma.sc.gov` URL is stale). The published list has **16 entities: 1 federally recognized (Catawba Nation), 10 state-recognized Tribes, 3 Indian Groups, 3 Special Interest Organizations.** The page carries **no date stamp** — monitor it by content hash.
- **Model three distinct sets, and never conflate them:** (1) SC state-recognized entities; (2) federally recognized Tribes resident in SC — exactly one, Catawba, confirmed against Federal Register doc `2026-01899` published 2026-01-30 (575 entities nationally); (3) federally recognized Tribes with historic SC affiliation for Section 106 consultation — 16, per SCDAH, which is **not** a recognition list.
- **A state-recognized-only SC entity is ineligible** for BIA, IHS, HUD ICDBG, DOL WIOA §166, EPA GAP, FHWA TTP, DOJ CTAS, FEMA THSGP, and THPO status. **The product must say so rather than showing them those programs.**
- **What stays open, and should be ranked highly for them:** the Special Interest Organization / SC-nonprofit route; FEMA HMGP via SCEMD (which names "Indian tribes or other tribal organizations, and certain private non-profits"); SC Office of Resilience at **`scor.sc.gov`** (names "tribal nations… and nonprofits"); HOME/CHDO via SC Housing; SCDHHS Rural Health Transformation subawards; **FTA §5311 subrecipient status via SCDOT**; HRSA (recognition-agnostic agency-wide); ED Title VI (state-recognized members count); and Native-led philanthropy.
- **`scorf.sc.gov` is the Opioid Recovery Fund Board, not the Office of Resilience.** Don't repeat that mistake.
- **`des.sc.gov` and `dph.sc.gov` need headless rendering** — every page emits ~103 KB of navigation before body content. `des.sc.gov/sitemap.xml` works and is a usable URL inventory.

---

## 7. Honesty rules for the registry — these are load-bearing

- **`UNKNOWN` means "not verified," not "not applicable."** Do not backfill it from priors, from an LLM's memory, or from a plausible-looking guess. If you need a value, fetch and verify it, and record what you fetched.
- **Do not prune the negative rows.** The registry deliberately contains known-dead URLs, trap pages, absence findings ("SCEMD has no grants section"), and blacklist entries. They are the memory that stops a crawler from silently failing or being re-pointed at a hijacked domain.
- **Gap rows assert nothing.** DOT's unverified programs, USDA NRCS/FSA/Forest Service, Commerce MBDA/NOAA — including the **Tribal Forest Protection Act**, which no research lane could confirm from a live page. Leave them as gaps; do not populate from memory.
- **Programs whose 2026 status is UNKNOWN** — FEMA BRIC, Tribal Cybersecurity Grant Program, SLCGP, NTIA TBCP, Digital Equity Act Native set-aside, DOE Grid Deployment Office 40101(d) — must not enter the MVP pipeline on an assumption of activity. Decide with the product owner whether they surface as "status unverified" or not at all.
- Every row's `notes` ends with a `[research lane: …]` provenance tag. Rows tagged `seed-v1` carry the *prior* registry's verification level, not this pass's. Treat them as lower confidence.
- **The registry is not an assertion that any listed program currently has an open competition.** Nothing in the UI may imply otherwise.

---

## 8. Definition of done for this phase

- [ ] Registry CSV loads into the source table with the 26-column schema intact, `UNKNOWN` preserved as a distinct value from empty/null, and provenance tags retained.
- [ ] Phase-1 spine ingests daily, with the Grants.gov extract as the reconciliation corpus and Search2 as the delta accelerator — **not the other way around.**
- [ ] Eligibility classification returns a graded result over `07|11|08|99|25`, with the free-text `Additional Information on Eligibility` field screened, not skipped.
- [ ] Forecast→posted transition emits a first-class event; forecast lapse emits a distinct state.
- [ ] Amendment detection uses `synopsisModifiedFields[]` as the primary signal and classifies materiality.
- [ ] Geography gate provably excludes out-of-state sources — test with an SC customer against Potlatch Fund, Bush Foundation, and Reclamation.
- [ ] Recognition model distinguishes the three SC sets and correctly withholds federal-set-aside programs from a state-recognized-only entity.
- [ ] Crawler presents a NativeForge user-agent, honors robots, respects the §11.2 cadence table, and has a circuit breaker.
- [ ] Body-hash/content-length checks catch dead shells; a synthetic test points a collector at HUD's `/program_offices/public_indian_housing/ih` and asserts it is flagged stale rather than "unchanged."
- [ ] Every `TERMS_REVIEW_REQUIRED` and `HUMAN_REVIEW_ONLY` source is inert in code until legal sign-off, enforced by a flag, not by convention.

---

## 9. What to escalate rather than decide yourself

Dossier §13.2 lists the full set. The ones that will block you soonest:

1. The **Simpler.Grants.gov `applicant_type` enum value for tribal applicants** is undocumented — recover it from the live Swagger at `https://api.simpler.grants.gov/docs` in a browser before writing filter code. (Also: keys auto-disable after 30 days unused — build a heartbeat.)
2. Whether **authenticated customer portals** are in scope (JustGrants, GEMS, FEMA GO, TrAMS, AMIS, RD Apply, IntelliGrants, GrantSolutions) — and if so, the consent, credential-custody and security model. **Do not automate anything with a customer's credentials without that decision in writing.**
3. Whether the product **shows opportunities, makes eligibility recommendations, or both**, and the evidence threshold before a source is labelled eligible for a given customer. This determines how much of §4 you build now vs. later.
4. **Legal sign-off on the four SPA terms pages** (grants.gov, regulations.gov, usaspending.gov, reporter.nih.gov) whose policy text could not be retrieved automatically — "no terms found" is not "no terms exist."
5. How **tribal data sovereignty, sensitive locations, and research governance** are enforced in storage, display and export. Get this decided before you design the schema, not after.
