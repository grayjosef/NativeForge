# NativeForge funding source universe — v2

Research date: 2026-08-26. This is a source-discovery and monitoring dossier, not a legal determination of applicant eligibility or cost allowability. Every eligibility and allowable-cost conclusion must be re-checked against the live NOFO and award terms.

**What v2 is.** v1 established the right architecture — a layered registry rather than "Grants.gov is the market." v2 keeps that architecture and adds direct verification: eight parallel research lanes fetched roughly 300 official primary pages across DOI, HHS, USDA, HUD, Commerce, DOE, EPA, DOT, DOJ, DHS/FEMA, ED, DOL, SBA, NSF/NIH/NOAA/NASA/USGS/IMLS/NEH/NEA, Treasury CDFI Fund, the eCFR, and 40+ South Carolina state sources, plus the robots.txt and terms posture of every major API host. The companion registry grew from 55 seed records to **381 records**.

The honest headline: **v1 was structurally right and factually stale in about a dozen places that would have broken a crawler.** Those corrections are in §1.2 and they are the most immediately actionable content here.

---

## 1. Executive summary

### 1.1 The layered model (unchanged, now evidence-backed)

1. **System-of-record layer.** Grants.gov daily XML extract and Search2/fetchOpportunity APIs; SAM.gov Assistance Listings API; Federal Register API; USAspending API.
2. **Native discovery layer.** The BIA/WHCNAA Access to Capital Clearinghouse, agency tribal-affairs pages, Dear Tribal Leader Letters, the NIH Tribal Health Research Office curated NOFO index, and agency GovDelivery bulletins.
3. **Program-owner layer.** Agency program and NOFO pages, which routinely carry better eligibility, deadline, amendment, and allowable-cost detail than any aggregator.
4. **Pass-through layer.** State administering agencies, instantiated only after matching a customer to operating state(s), recognition status, and entity class.
5. **Research layer.** NIH Guide weekly index, NSF RSS, NIFA RFA list, HRSA find-funding, plus institute-specific curated indexes.
6. **Selective philanthropy layer.** Native-led and materially Native-focused funders, handled manually until terms and page structures are reviewed.

Three things now anchor the design rather than being assumed:

- **The Grants.gov daily XML extract is the only unmetered, complete, fully-documented snapshot in the federal ecosystem.** Verified working: `GrantsDBExtract20260825v2.zip`, 78 MB, published ~04:40 ET, **only 7 days retained**. A missed day is unrecoverable, so a fetch failure is a paging-level alert, not a retry.
- **The tribal eligibility codes are known and documented.** Grants.gov "Eligible Applicants" codes: **`07`** = Native American tribal governments (Federally recognized), **`11`** = Native American tribal organizations (other than Federally recognized tribal governments), **`08`** = Public housing authorities/Indian housing authorities. SAM.gov Assistance Listings uses **`ET23010`**, **`ET23020`**, **`ET23030`**, which map 1:1 onto `07`/`11`/`08`. The recall set must also include **`99`** (Unrestricted) and **`25`** (Others — eligibility hidden in a 4,000-character free-text field), and SAM's **`ET12010`** ("determined at NOFO level"). A filter that matches only `07|11` will look clean and silently miss a large share of tribally-eligible money — precisely the failure NativeForge exists to prevent.
- **The software-allowability question has a much better answer than the market assumes**, because the April 2024 Uniform Guidance revision (89 FR 30136) inserted language that did not previously exist. See §5.

### 1.2 Corrections to v1 — apply these before writing any collector

| v1 assumption | Verified reality |
|---|---|
| HUD ONAP at `hud.gov/program_offices/public_indian_housing/ih` | **Dead shell.** Returns HTTP 200 with a valid skeleton, zero body content, and a `<title>` prefixed `25red-`. A monitor here reports "no change" forever. Live hub is **`hud.gov/codetalk`**; programs moved to `hud.gov/helping-americans/public-indian-housing-*`. |
| `cma.sc.gov` is the SC Commission for Minority Affairs | Agency **renamed** to the SC Commission for Community Advancement and Engagement ("Advance SC"), statute changed May 2025, site moved to **`advance.sc.gov`**. Every stored `cma.sc.gov` URL is stale. |
| `scorf.sc.gov` is the SC Office of Resilience | **Wrong agency.** `scorf.sc.gov` is the SC **Opioid Recovery Fund Board** (SC Code 11-58-10). The Office of Resilience is **`scor.sc.gov`** — and its grants page explicitly names "tribal nations… and nonprofits." |
| `schousing.com` | **301s to `schousing.sc.gov`.** |
| USDA FNS | **Renamed to the Food and Nutrition Administration (FNA) effective June 1, 2026**; `fns.usda.gov/*` 302s to `fna.usda.gov/*`. Mid-migration, so redirect coverage is fragile. |
| `energy.gov/indianenergy/funding-opportunities` | Returns empty. Canonical is **`/indianenergy/current-funding-and-technical-assistance-opportunities`** — and monitoring it alone **under-reports DOE tribal funding**, because energy.gov clears closed FOAs fast while **IE-Exchange (`ie-exchange.energy.gov`)** still carried DE-FOA-0003548 "Unleashing Tribal Energy Development," ~$50M, closed 2026-07-24. |
| `energy.gov/scep/*` | **301s to `/cmei/scep/*`.** Audit all stored SCEP URLs. |
| `highways.dot.gov/federal-lands/programs-tribal` | **301s to `/federal-lands/tribal`** (the legacy alias is still emitted in-page, so store the canonical from the response). |
| BIA `/as-ia/ieed`; `bia.gov/bia/ots/tribal-climate-resilience-program` | **301 to `/as-ia/ied`** and **`/bia/ots/descrm/tcr`** respectively. BIA's own sidebars still link the dead paths. Diff `bia.gov/sitemap.xml` to catch renames before collectors break. |
| ED "Forecast of Funding Opportunities" | Path returns empty. Replaced by **`ed.gov/grants-and-programs/apply-grant/available-grants`** — a server-rendered HTML table with a tribal-aware eligibility facet. |
| De minimis indirect rate 10% | **15% of MTDC** (2 CFR 200.414(f)), per the 2024 revision. Single-audit threshold $750K→$1M; equipment threshold $5,000→$10,000. |
| `doi.gov/ibc/services/indirect-cost-services`; `ihs.gov/csc/` | Both wrong. Use `ibc.doi.gov/ICS/indirect-cost`. `ihs.gov/csc/` is the **Clinical Support Center**, not contract support costs. IHS self-governance is **ISDEAA Title V**, not Title IV. |
| SC "no single portal located… operationally use an agency-by-agency map" | Now stated definitively: **there is no central statewide grants clearinghouse in South Carolina.** Four candidates checked and all fail (see §9.6). |
| EPA Environmental Justice grants as a monitorable source | The grants URL returns an empty body and `epa.gov/environmentaljustice` serves a de-templated legacy page whose newest substantive content is the FY17 progress report, listing **no current program, NOFO, or deadline**. Do not carry EJ grants in the active coverage map. |
| Grants.gov RSS feeds as an ingest path | **Documented but broken.** Two of four advertised feeds returned `Content-Type: text/html` — the SPA shell, not XML. Use the daily extract. |

---

## 2. Federal Native funding source map

| Layer | What it contributes | NativeForge treatment |
|---|---|---|
| Grants.gov daily XML extract | The complete opportunity corpus, plus fields no API exposes (Estimated Synopsis Post/Close Date, Fiscal Year, Archive Date, 18,000-char Description, 4,000-char Additional Information on Eligibility) | **Tier 1, corpus of record.** Nightly reconciliation by diff. |
| Grants.gov Search2 / fetchOpportunity | Intra-day deltas; the best amendment-detection surface in the federal ecosystem (`synopsisModifiedFields[]`, `revision`, `synAttChangeComments[]`) | Tier 1 delta accelerator. Never the corpus of record — no documented date filter, no documented rate limit, explicit right to block. |
| Simpler.Grants.gov API | A real, newer, self-service-keyed public API (60/min, 10k/day) with an `applicant_type` filter | Tier 1, but **early development** and the tribal enum value is undocumented — recover it from the live Swagger before coding. |
| SAM.gov Assistance Listings API | Program catalog, ALN semantics, `ET23010/20/30` tribal eligibility codes | Tier 1 catalog normalization. **Rate limit is the binding constraint: 10/day without a SAM role, 1,000/day with one.** Never infer an open deadline from a listing. |
| Federal Register API | Funding-availability notices, tribal consultation notices, program rules; `agencies[]=indian-affairs-bureau` returns 3,313 documents | Tier 1. **Public Inspection endpoints buy a 1–3 business-day head start over publication.** |
| USAspending API v2 | Prior-award intelligence with real tribal recipient flags (`indian_native_american_tribal_government`, `tribally_owned_firm`, `alaskan_native_corporation_owned_firm`, `american_indian_owned_business`, `native_hawaiian_organization_owned_firm`) | Tier 2. Backward-looking only, but it is how you rank an opportunity by realistic win probability. |
| BIA Access to Capital Clearinghouse (`bia.gov/atc`) | Native-scoped, multi-instrument (grants, loans, cost sharing, tax credits, vouchers) cross-agency directory | Tier 1 discovery — and note **EPA formally retired its own Tribal Waste Management Funding Directory and now redirects users here.** Also the closest thing to a direct competitor. Reconcile every record back to the issuing agency. |
| Agency funding and program pages | Amendments, webinars, per-region deadlines, allowable-cost language | Tier 1/2 HTML and PDF monitoring. |
| Tribal affairs / DTLL pages | Funding announcements that never appear in a grants index | Tier 1/2. IHS Tribal Leader Letters verifiably surfaced Small Ambulatory Program, Joint Venture Construction, Sanitation Facilities Construction, and CHEF — none of which appear in the IHS DGM grants index. |
| GovDelivery bulletins | The real subscription infrastructure across DOE, DOJ/OJP, USDA RD, ED, DOT/FHWA, DOT/FTA, HRSA, Treasury CDFI | Tier 1/2. **Archived bulletins are publicly readable without subscribing** at `content.govdelivery.com/accounts/{ACCT}/bulletins/{id}` — proven for `USDOEIE`. |
| State administering agencies | Formula and competitive pass-through | Instantiate per customer state only. |
| Native-led philanthropy | The only funders that routinely admit state-recognized tribes, 7871 organizations, fiscally-sponsored groups, and unincorporated groups | Tier 1–3, manual-first. |

**Notable absence.** Across every DOE, EPA, and DOT page fetched, **zero RSS/Atom feeds were found**. RSS exists at USDA FNA (8 feeds, including `policy-memo-fdp` which explicitly covers FDPIR), USDA RD (`rss.xml` — a general news feed, not a funding feed), NIH Guide (thin and lagging), NSF (two working feeds), and Reclamation. Plan email-bulletin ingest as a first-class path, not a fallback.

---

## 3. Federal agency and subagency monitoring targets

### 3.1 Interior

- **BIA Office of Indian Economic Development** — `bia.gov/topic/grants` is a consolidated seven-program index (NABDI, NTBG, LLGP, EMDP, TEDC, IBIP, TTGP) and the densest single BIA monitor. **EMDP** verified: ALN **15.038**, annual ~August close, eligibility extends to Tribal Energy Development Organizations "completely owned by individuals of AI/AN descent," so `native-owned-business` is genuinely in scope. **NABDI is dormant, not dead** — the page states no future offerings are planned — and is exactly the program a naive scraper shows forever. NABDI's FY22 award table is the best allowability evidence in DOI: it funded an "ITKN GIS Business Plan" and an "Information Technology (IT) Feasibility Study and Business Plan."
- **BIA Branch of Tribal Community Resilience** (renamed from Tribal Climate Resilience) — competitive, annual, open to federally recognized Tribes **and Tribal organizations**. Since 2011: 280+ funded adaptation plans, vulnerability assessments and risk assessments; 900+ awards totalling $119M+. Planning is the product, not an incidental cost.
- **BIA news** (`bia.gov/news`) is a genuine solicitation channel, not just awards — the Tribal Tourism Cooperative Agreement solicitation appeared there and nowhere else. Lower-noise variants at `/news/service-page/{id}`; applicant webinars at `/events/service/{id}` are a leading indicator.
- **BIE lives on a separate host, `bie.edu`** — treat as two hosts. No NOFO index exists there; GAOA facilities work and Johnson O'Malley are the funding-relevant pages. Note BIE already operates NASIS and Native Star, so a school-facing NativeForge module enters occupied ground.
- **NPS** — Tribal Heritage Grants (ALN **15.904**, FY26 NOFO **P25AS00501**, closed 2026-07-27, ~$900K, **no non-federal match**) is the best-documented DOI program in scope, and its stated purposes expressly include "enabling the establishment of tribal historic preservation offices," i.e. standing up administrative capacity. NAGPRA grants (ALN **15.922**) include **museums** alongside Tribes and NHOs — a native-only eligibility filter mis-tags it.
- **FWS Tribal Wildlife Grants** — reliable annual summer cycle (FY26: 2026-06-12 to 2026-08-14), **federally recognized Tribal governments only, state-recognized excluded explicitly**, and unusually explicit allowable costs: salaries, equipment, consultant services, subcontracts, acquisitions of goods and services, travel; land acquisition not allowed; planning and habitat mapping eligible.
- **Reclamation** Native American Affairs TAP is tribal-only, funds water needs assessments and **water quality data collection**, and its current opportunity (`R26AS00021`, $6M, closes 2026-09-28) is restricted to **30 named Colorado River Basin Tribes** — proof that eligibility sometimes has to be stored as an enumerated set, not a class. Geographic scope: 17 Western States.
- **USGS** — no tribal funding opportunity was verified in any lane. Value is relationship intelligence (named regional liaisons). Do not create CASC tribal-funding rows without verification.

### 3.2 HHS

- **IHS DGM Funding Opportunities index** (`ihs.gov/dgm/funding/index.cfm`) is the single highest-value source in the DOI/HHS scope: year-sectioned Open/Closed archive 2021–2026 with stable PDF paths. FY26 open at fetch: Dementia Models of Care, Tribal Management Grant, Tribal Self-Governance **Planning** and **Negotiation** cooperative agreements. Two structural facts change design: the NOFO publication policy **changed** (2022–23 via Federal Register, 2024+ via self-hosted PDFs — handle both), and **`/dgm/forecast/` is a trap page** containing no forecast data at all.
- **IHS Tribal Leader Letters** and the parallel **Urban Leader Letters** are funding channels. Stable pattern `.../{YYYY}_Letters/DTLL[_DUIOLL]_MMDDYYYY.pdf`, archives to 2000.
- **SDPI** — $150M/year, +$41M for FY2026, guided by the Tribal Leaders Diabetes Committee, behaving closer to formula than competition. It runs its own SDPI Outcomes System reporting platform: direct competitive-adjacent signal.
- **HRSA `find-funding`** is the best-structured funding search found at any agency: server-rendered, filterable, with per-opportunity number, deadline, bureau, status **and a full "Who can apply" paragraph on the listing page**. And HRSA's policy page contains the single most important eligibility sentence in this entire engagement: applicants include *"Native American tribal (whether the U.S. government recognizes your organization or not)"* — the only affirmative federal statement found that non-federally-recognized tribal organizations may apply. Model it as a **default that each NOFO overrides**; both currently-open HRSA NOFOs are far narrower.
- **NIH** — the **Tribal Health Research Office curated index** (`dpcpsi.nih.gov/thro/programs`, note `/thro/funding` 404s) is irreplaceable: hand-split into "AI/AN-Specific" and "AI/AN-Relevant" NOFOs, a relevance signal no keyword search reconstructs. **NARCH** (now titled "Health Research Programs for Federally-Recognized Tribes or Tribal Entities" — do not match on "NARCH" alone) lets Tribes apply **directly**, no university pass-through: PAR-23-166 (S06), PAR-25-441 (R34), PAR-24-260 (TIRBEE R24). Discovery runs through the **weekly index** at `WeeklyIndexMobile.cfm`, never the Guide search UI (a React SPA).
- **CDC** — use the `/healthy-tribes/*` namespace (`/healthytribes/` and several variants return empty) and **blocklist `/tribal/*`, which serves 2016 Zika content**. GHWIC reaches 115+ federally recognized tribes and notably admits Urban Indian Organizations and Tribal Epidemiology Centers. The CDC/ATSDR Tribal Advisory Committee page is a **leading indicator** — materials precede Grants.gov postings by weeks to months. **Terms risk:** CDC states redistribution of syndicated content is not allowed, citing 42 U.S.C. 1320b-10 on reproducing content *for a fee* — which directly implicates a paid product. Store facts and metadata, not CDC prose, and get counsel.
- **ACF/ANA** is the weakest-scraping HHS host: pages return thin extracts with navigation and dynamic listings stripped, `/grants` is stamped "Last Reviewed: April 7, 2016," and roughly ten ANA path attempts failed. ANA's three program areas (SEDS, Native Languages, Environmental Regulatory Enhancement — the last funding "legal, technical and organizational capacities") are real, but **source ACF tribal set-asides (Tribal CCDF, Tribal TANF, LIHEAP tribal, AIAN Head Start) from SAM.gov Assistance Listings and Grants.gov, not from ACF HTML.** "Native Language P&M" and "Esther Martinez Immersion" could not be verified as current program names.
- **CMS** is a coverage gap (empty bodies on every path) and is largely reimbursement policy, not grantmaking. **ACL Title VI** is reachable but yielded only navigation — grant character believed formula-ish, unverified.

### 3.3 USDA

- **Rural Development** is the most scraper-friendly agency in scope: server-rendered Drupal, `?page=0..5` pagination on `/programs-services/all-programs`, real server-side filters (State, Program Area, keyword). `/about-rd/tribal-relations` is effectively a pre-built Native relevance map naming Tribal College Initiative Grants, Water and Waste Facility Loans and Grants to Alleviate Health Risks **on Tribal Lands** (a separate line from Colonias), Grants for Rural and Native Alaskan Villages, the **Native CDFI Relending Demonstration Program**, IRP, RBDG, and ReConnect — plus a **dedicated tribal GovDelivery category, `USDARD_C148`**. **SUTA** (Substantially Underserved Trust Area) is not a program but a statutory flexibility — discounted rates and waived matches across RUS programs on trust land — and is high practical leverage. RCDI eligibility verified as including "federally recognized tribes." Note ReConnect is linked at **`usda.gov/reconnect`**, not the `rd.usda.gov` path.
- **NIFA** is the highest scraper ROI anywhere in this engagement: program pages emit Funding Opportunity Number, **Assistance Listing Number**, posted date, closing date, total funding, award range, cost-sharing, eligibility, contact, and a Grants.gov deep link. Verified: **TCRGP** ALN **10.227**, FON `USDA-NIFA-TCRGP-011697`, posted 2026-04-22, closing 2026-12-31, $11,574,000, awards $150K–$2.5M, no match — and its text expressly solicits "artificial intelligence (AI), data science, robotics, and other cutting edge digital tools." **TCEG** funds recipients to "invest in technology to reach more students on remote reservation communities." Two eligibility inversions must be modeled: **NBTS** (ALN 10.527) admits 1994, 1862 **and** 1890 land-grants; **FRTEP** applicants are 1890/1862 universities serving federally recognized Tribes, not Tribes themselves. TCEP-CA and TCEP-SE are two distinct programs — do not merge them. `robots.txt` on nifa.usda.gov carries **`Disallow: /*?*`**, which kills all faceted and paginated query-string URLs; the clean-URL RFA index is both the compliant and the better path.
- **FNA (ex-FNS)** — FDPIR distributes "both food **and administrative funds**" to Indian Tribal Organizations and state agencies. The **FDPIR Self-Determination Demonstration Project** (2018 Farm Bill, ISDEAA §4 contracts) ran Round 1 ~$7.0M and Round 2 $4.4M, both winding down through 2026; **a Round 3 is UNKNOWN — do not present it as open.** Bonus: the page names ~20 Native-owned vendors, usable as seed data for a `native-owned-business` registry. FNA publishes the best structured feed set found: 8 RSS feeds at `/rss-feeds`, including `policy-memo-fdp` which explicitly covers FDPIR.
- **NRCS, FSA, Forest Service** — **not verified in any lane.** Tribal Forest Protection Act and the Highly Fractionated Indian Land program have **no confirming page** in this research; assert nothing. Start from `usda.gov/tribalrelations` and `farmers.gov`.

### 3.4 HUD

`hud.gov/codetalk` is the highest-value HUD target and carried eight distinct notices on the fetch date (FY26 IHBG/NHHBG income limits ONAP-PG-2026-01/-02, a June 2026 Federal Register disaster-waiver notice, the FY2027 IHBG formula allocation DTL, the P.L. 119-70 income exclusion, and two radon-notice extensions).

- **IHBG** carries the most consequential eligibility sentence in the federal set: *"Eligible IHBG recipients are federally recognized Tribes, Tribally Designated Housing Entities (TDHEs), and **a limited number of State-recognized Tribes**."* This is one of very few federal programs where state recognition is not categorically disqualifying — but the set is closed and grandfathered, not open. Reporting runs through **GEMS** (which replaced EPIC, now live in all ONAP regions).
- **IHBG-Competitive** is limited to existing IHBG Formula recipients; FY25 due 2026-01-15; the application package includes **HUD-426 "Indirect Costs Information"** — formal recognition of indirect cost structures in the award.
- **ICDBG** has two tracks that must be modeled separately: Single Purpose (annual competitive; FY25 deadline **revised** to 2025-12-10 and labelled "New Deadline" — deadline revision is a real event class) and **Imminent Threat (noncompetitive, rolling, first-come-first-served, up to $5M/yr, governed by PIH 2025-09)**.
- **The IHBG formula process runs on a non-.gov domain, `ihbgformula.com`** (FY2027 Formula Response Form corrections due 2026-08-01; FY2028 census challenges due 2027-03-30). Flag for terms review.
- **HUD Exchange** is a useful secondary but **not** the ONAP notice channel — for tribal programs it links out to hud.gov. Its `/news/` list is server-rendered and scrapeable; its facet layer is AngularJS serving raw `{{t.name}}` placeholders. There is a real tribal hub at `/programs/priority-tribal/`, and **Community Compass TA explicitly names "tribe or tribally-designated entity" as eligible to request assistance** while excluding subrecipients.
- **`hud.gov/robots.txt` names `ClaudeBot`, `GPTBot`, `CCBot` and others with `Disallow: /`** and asserts `ai-train=no` as a condition of access, invoking Article 4 of EU Directive 2019/790. NativeForge's crawler must not present an AI-crawler user-agent on hud.gov, and this needs counsel before production.

### 3.5 Commerce

- **EDA** site health is **page-by-page, not site-wide**: `/funding` carries an appropriations-lapse banner and literal `test` placeholder text, while `/funding/programs` is fully current (Drupal 11, links a 2026-02-12 document). Monitor `/funding/programs`. The **Planning Program** names "Indian Tribes" as eligible verbatim, and its deliverable is a CEDS — so planning and data costs are on-mission by construction. EDA's reauthorization in the **Thomas R. Carper WRDA of 2024** created new tribal authorities and an **Office of Tribal Economic Development**. Critically: the tribal set-aside **"Assistance to Indigenous Communities" exists only as page 37 of a combined PWEAA/AI-Upskill NOFO PDF** — page-level HTML monitoring will miss it entirely. PDF section extraction is required, not optional. Open-opportunity facet endpoint verified: `?f[0]=funding_status:6565`.
- **NTIA/internetforall.gov are human-review-only for funding status.** TBCP's page reads "Status: Open" for a round that closed in January 2023 and credits a prior administration prospectively; `ntia.gov/funding-programs/tribal-broadband-connectivity-program` returns an empty body. **BEAD's structural fact is decisive: Tribes are not BEAD eligible entities** — only the 56 states/territories are, and tribal participation is via mandated coordination and subgrantee selection, making BEAD a state-pass-through watchlist item. The **Digital Equity Act "Native Entity Capacity & Planning Grant Program"** is a genuine Native set-aside, but its 2026 status is **UNKNOWN** and must be flagged prominently. Route NTIA through Grants.gov and the Federal Register.
- **NOAA and MBDA** — not reached in any lane. Nothing asserted. NOAA's research side surfaced one important structural finding (§6).

### 3.6 Energy

- **Office of Indian Energy** is the most tribal-specific federal source in the inventory. Technical assistance is verified-active and rolling, with unusually broad eligibility: *"federally recognized Indian Tribes and Tribal entities, including Alaska Native regional corporations and village corporations,"* covering energy planning, efficiency assessments, resource assessments, project planning, building codes, and utility formation. **IE-Exchange must be a first-class monitor**, and its Topic Areas 2 and 3 are explicitly pre-development, planning, assessment and feasibility. The monthly newsletter covers DOE **and other federal agencies'** tribal energy funding, and its archive is publicly readable at stable GovDelivery URLs.
- **Tribal Energy Loan Guarantee Program** — verified-active, rolling ("Loan Guarantee authority has no expiration"), IRA raised authority $2B→$20B with $75M to administer. Eligible project list is now technology-neutral and includes **mining and fossil energy production** and CCUS — a policy shift worth surfacing to users. It is a debt instrument, so software and admin costs are not a fit. ALN renders blank on the page: UNKNOWN.
- **Grid Deployment Office status is UNKNOWN for 2026.** The landing page confirms the program existed (its own news archive references the FY22 40101(d) State and Tribal Formula deadline extension) but all news items are 2022 and both `/gdo/grid-resilience-state-and-tribal-formula-grants` and `/gdo/funding-opportunities` return empty. Do not represent 40101(d) or GRIP as active or inactive.
- **SCEP** portfolio verified (WAP, SEP + EE Revolving Loan Fund, EECBG, Communities LEAP, Local Government Energy Program, Energy Future Grants, Renew America's Schools/Non-Profits), and SCEP's own text names "Tribal Nations" and "local and tribal governments." But the **WAP tribal/direct-grant pathway, SEP tribal pass-through, and EECBG tribal allocation are all UNVERIFIED.** "Energy Transitions Initiative" was not found on any DOE page and should not be carried forward.

### 3.7 EPA

- **GAP is the single most important EPA row and is fully verified from the FY26 NOFA PDF.** ALN **66.926**, FON **EPA-CEP-02** (Performance Partnership Grants: **66.605**, EPA-CEP-01). Eligibility is restrictive: *"Federally recognized Indian Tribal government. Intertribal consortia"* only, per 40 CFR 35.502 — **state-recognized Tribes are excluded with no alternate pathway.** Intertribal consortia require majority-GAP-eligible membership plus **unanimous** authorizing resolutions. Not competitive; regionally allocated; ~520+ awards; $75,000 floor; project periods up to 4 years (5 in a PPG); no cost share; 15% de minimis indirect available. **Deadlines are per-EPA-Region, not national** — verified FY26: R9 Feb 6, R10 Feb 13, R8 Feb 26, R6 Feb 27, R4 Apr 17, R3 May 29, R1 Jul 3 (45 days from allocation letter), R5 60 days from allocation letter, R2 Feb/Mar, R7 Tribe-specific. **This is a product requirement: model deadlines per region, and parse the "Application Submittal Schedule" table every November.** Allowability language is exceptionally favourable (§5).
- **Water** is verified and detailed. **CWA §106 tribal grants**: formula, $65,167 base per TAS-eligible Tribe plus a variable allotment, >$25M/year, match waived, **two-gate eligibility (federal recognition AND Treatment-as-State)**, and a verbatim eligible use of *"Developing water quality and geographic information system databases to track changes in water quality and ensure consistency in data management."* **CWA §319 tribal base grants**: noncompetitive, formula by land area ($50K/$55K/$60K/$75K bands), requires TAS plus an approved NPS assessment and management program. **§319 tribal competitive is OPEN**: NOFO `epa-ow-owow-26-01`, Grants.gov opportunity 363611, **deadline 2026-11-09**, $175K cap, ~$3.5M/year, with a **New Applicant Set-Aside** for those not awarded FY21–FY25; recurring pattern is NOFO ~August, close ~November, selections ~spring; grantees must submit to **GRTS** within 90 days. **CWISA's real intake is the IHS Sanitation Deficiency System, not an EPA competition** — monitoring EPA alone misses the actionable step. DWIG-TSA is allotment-based (FY25 tribal infrastructure total >$262M).
- **Brownfields** is freshly funded: FY2026 $248M to Multipurpose/Assessment/Cleanup plus $22.5M RLF supplemental, and $12M in Job Training to 25 communities; IIJA provided $1.5B. Reporting runs through **ACRES**. A Constant Contact listserv exists.
- **EPA retired its Tribal Waste Management Funding Directory and now points users to `bia.gov/atc/search`** — a strong signal about where Native-scoped discovery is consolidating.
- **Two software-relevant EPA programs deserve a dedicated pass:** the **Environmental Information Exchange Network Grant Program** (funds "electronic collection, exchange, and integration of high-quality data" — the most software-relevant EPA program found) and the **Pollution Prevention Grant Program** ("matching funds to state and tribal programs"). Neither was individually fetched; terms UNKNOWN.
- EPA emits `meta-DC.date.modified` and `article:modified_time` on every page — build change detection on the meta tags, not HTML diffs.
- **CPRG is closed to new applications** (>$4.3B awarded under the General Competition; $300M to 34 applicants under the **Tribes and Territories Competition**). Monitoring value is deliverable tracking (CCAP now due 2026-06-01), not discovery.

### 3.8 Transportation

- **FHWA Office of Tribal Transportation** is the strongest DOT cluster. TTP formula: 23 U.S.C. 202, 25 CFR 170, **135 Tribes hold direct FHWA funding agreements**, formula based on tribal population, road mileage and historic TTAM shares, and eligibility keyed explicitly to the BIA Federal Register recognition list — **no state-recognized pathway**. Tribal shares and planning funds are published as **annual PDFs only** (Excel by emailing a named contact) — high-value per-Tribe dollar data at medium-high parsing cost. **TTPSF** is a clean annual cycle (4% TTP set-aside; 2026 deadline Jan 15; FY2025 awards announced 2026-03-19) but its operating NOFO is a **multi-year 2022–2026 document currently at Amendment No. 2**, so monitor for new amendment numbers rather than new NOFOs — and applications go by emailing `TTPSF@dot.gov` for an upload link, **not Grants.gov**. **§202(a)(9)** is the real state-pass-through mechanism on the highway side, and it is small and agreement-driven: "approximately 20 transfers across 8 different states" to date. **GovDelivery topic `USDOTFHWA_83` is the highest-signal, lowest-cost DOT tribal monitor available.**
- **FTA Tribal Transit** has the best-documented eligibility model in the whole set — and **the clearest state-recognition pathway found anywhere**: *"Tribal governments that are not federally recognized remain eligible to apply to the state as a subrecipient for funding under the state's apportionment."* Structure: 5% takedown of §5311, 20% competitive / 80% formula, ~$36M formula + ~$9M competitive, **no local match on either**, funds available 3 fiscal years. FY26 competitive: ~$19M announced 2026-05-27, applications due 2026-08-25. The **formula program has a hard gate** — you must have reported to the National Transit Database in the most recent report year, typically meaning two consecutive years of NTD reporting before a first allocation. That is a concrete, high-value alert NativeForge can generate. Allowability is verbatim favourable: "capital, operating, planning, and administrative expenses," and non-operating Tribes may apply for "a planning project or start-up costs." Also verified: the **Tribal Transportation Self-Governance Program** includes tribal **organizations**, broader than most DOT programs.
- **SS4A** is tribal-eligible (federally recognized only), FY26 closed 2026-05-26, with "approximately $1 billion still available for the next funding round" — expected but unannounced. FY25 awarded $982,231,998 to 521 communities, of which "over $340,904,546… benefits communities in rural and Tribal areas." Implementation Grants require an existing eligible Action Plan.
- **`transportation.gov/tribal` — DOT's own department-level tribal portal — is abandoned**, last updated 2017-01-20, with links to dead `dot.dev` paths. Do not use it as a coverage anchor.
- **RAISE, Bridge Investment, Rural Surface Transportation, PROTECT, FAA AIP, Thriving Communities, and state HSIP pass-through were not verified.** They are carried as explicit gap rows, not as characterized programs.

### 3.9 Justice

- **Highest-priority change signal in the entire federal map:** `justice.gov/tribal` carries an active consultation notice on *"the Department's plan to consolidate the Office of Community Oriented Policing Services, the Office of Justice Programs, and the Office on Violence Against Women into a single grantmaking component named the Bureau of Justice Grants."* **Build DOJ collectors behind an abstraction layer** — URL structures and NOFO publishing patterns will change.
- **OJP is the cleanest scrape target in the federal set**: fully server-rendered Drupal, complete opportunity list in static HTML grouped by bureau, individual pages with a clean field block, stable NOFO PDFs at `ojp.gov/funding/docs/<opp-id>.pdf`, and a `Date Modified` footer for cheap change detection. **No search/filter API exists.** Every opportunity carries **two deadlines** (Grants.gov 11:59 p.m. ET and JustGrants 8:59 p.m. ET) — a data-model requirement, not a display detail.
- **CTAS FY26** verified: opportunity `O-BJA-2026-172662`, posted 2026-07-24, Grants.gov 2026-10-15, JustGrants 2026-10-22, ALNs **16.710, 16.596, 16.583, 16.585, 16.731, 16.043**, eligibility "federally recognized tribes and tribal consortia" only (**state-recognized excluded**), and **no Purpose Area 7 in FY26**. CTAS must not be modeled as one policy — its cost rules differ by purpose area (§5.3).
- **OVW Tribal Affairs Division** administers six tribal-specific programs and states that *"Tribal entities are generally eligible to apply for any OVW grant program for which a comparable non-Tribal entity is eligible."* **TSASP has the broadest tribal-nonprofit eligibility in DOJ**: "Indian Tribes, Tribal consortia, Tribal organizations, and nonprofit Tribal organizations." Tribal Governments Program and TSASP both closed 2026-09-03; Tribal Jurisdiction Program closed for FY26. A **court-ordered stay on a certification requirement** is flagged on the OVW funding page — monitor that banner.
- **OVC Tribal Victim Services Set-Aside is a formula program**, not competitive, and its verbatim allowable uses lead with *"community needs assessment and strategic planning."*
- **Tribal Access Program is a services program, not a grant** — no money flows to the Tribe; DOJ provides CJIS access, hardware, training and auditing to selected federally recognized Tribes (152 Tribes, 500+ agencies). High strategic relevance as an adjacent system; zero relevance as a funding source.

### 3.10 Homeland Security

**fema.gov serves degraded and stale content to non-browser clients** — `/grants` returned a near-empty stub whose newest item was a 2014 press release; the AFG and FEMA GO pages rendered 2020 content; the tribal-cybersecurity and state-local-cybersecurity pages returned **completely empty bodies**. Do not scrape fema.gov as primary; use Grants.gov as the authoritative FEMA NOFO source.

**OpenFEMA is verified, free, keyless — and verified NOT to cover NOFOs.** All 50 datasets were enumerated and a live filter on title substrings "Funding", "Opportunit", "NOFO" returned zero matches; FEMA's own dataset description says FOAs "may be found online at www.fema.gov/grants." Its real value is eligibility and competitive intelligence — above all **`HazardMitigationPlanStatuses`, which tells you which Tribes hold an approved mitigation plan**, a hard gate on HMA project funding. Warning: OpenFEMA `id` is regenerated each refresh; key on the `DataSetFields` `primaryKey` flags and sync on `lastRefresh`.

- **THSGP** is tribal-specific and direct (not state pass-through). Latest published NOFO is **FY2025 at $13.5M** (FY24 $13.5M, FY23 $15M, FY22 $15M, FY21 $15M); no FY2026 NOFO on the page. The rendered page does **not** state the federal-recognition test — the statutory term of art is "directly eligible tribe" — so verify against the FY25 NOFO PDF before shipping eligibility logic.
- **HSGP** (SHSP/UASI/OPSG, FY25 $1.008B) reaches Tribes only as **subrecipients of State Administering Agencies** — a 50-state monitoring surface. **EMPG is not part of HSGP**; its tribal pathway is UNKNOWN.
- **HMGP** confirms the tribal direct-recipient option ("32 tribes are working directly with FEMA") and a hard gate: *"All state, local, tribal and territorial governments must develop and adopt hazard mitigation plans to receive funding for hazard mitigation project application."* Planning grants are an eligible activity.
- **BRIC status is UNKNOWN for FY26.** The page describes BRIC in the present tense, its newest content is FY23 selections announced 2024-07-02 (~$1B including a **Tribal Set-Aside** and a **Tribal Building Code Plus-Up**), and it neither announces a current competition nor states termination. Do not place BRIC in the MVP pipeline on an assumption of activity. BRIC Direct Technical Assistance is non-financial and requires no prior award and no approved mitigation plan.
- **Tribal Cybersecurity Grant Program and SLCGP status: UNKNOWN** (empty bodies). Both would be extremely high-relevance if active, given their software and IT scope. Re-verify via Grants.gov before making any claim to users.
- **AFG/SAFER tribal eligibility: UNKNOWN — do not assert.** Tribal fire departments are not named on the page as fetched.

### 3.11 Education

No reorganization or program-transfer notice appeared on any ED page fetched. The Office of Indian Education is live under OESE.

**Title VI Indian Education Formula Grants carry the sharpest eligibility contrast in the federal set and must be encoded as a distinct rule.** "Indian" for child-count purposes includes a member of a tribe *as membership is defined by the tribe*, plus *"Any tribe or band terminated since 1940,"* *"Any tribe or band recognized by the State in which the tribe or band resides,"* and *"A descendant, in the first or second degree"* of such an individual, plus Alaska Natives and certain 1988-grant organized groups. **So members of state-recognized Tribes count, and so do terminated tribes and first/second-degree descendants** — the opposite of CTAS, GAP, and TTP. Whether a state-recognized Tribe may itself be the *applicant* is UNKNOWN. The program also requires **written approval of an Indian Parent Committee** and consultation with nearby Tribes, and its equipment test is narrow and purpose-tied.

ED's **Available Grants** table has the richest native-eligibility facet vocabulary of any agency site found: "Indian Tribes and Tribal Organizations," "Indian Tribe or Consortia Located on a Reservation," "Tribal Education Agencies (TEAs)," "Tribally Controlled Colleges and Universities (TCCUs)," "Minority Serving Institutions (MSIs)." CFDA numbers are embedded in program titles — a free ALN join key. **Material finding: as of 2026-08-26 only five competitions were open, all IES research-training, and zero Indian Education competitions.** The 17-program Native index page is the best seed page for the ED registry; note **DEMO and NALRC eligibility expressly includes "a nontribal for-profit organization"** — relevant if NativeForge ever applies directly. **Perkins CTE tribal/BIE set-aside mechanics: UNKNOWN** (routed to `cte.ed.gov`, not fetched).

### 3.12 Labor and SBA

- **DINAP** is the best DOL target; its Announcements block carried the live FOA. The multi-year designation cycle is confirmed and closed: **FOA-ETA-26-20**, issued 2026-04-02, closed 2026-05-22, with **two separate Grants.gov postings applicants must choose between** — `-IA` Comprehensive Services (361739) and `-IY` Supplemental Youth (361740). Covered entities verbatim: "tribes, tribal organizations, Alaska Native entities, Indian controlled organizations and Native Hawaiian organizations." State WIOA Title I is an entirely separate 50-state-plus-local-board surface.
- **SBA is thin and should be represented as thin.** Verbatim: *"SBA does not provide grants for starting and expanding a business"* and *"SBA provides grants to nonprofits, Resource Partners, and educational organizations."* **ONAA runs no grant program** — it offers free technical assistance. 8(a) is a **certification**, confirmed by site architecture (it appears only under `/certifications/`). **PRIME is the one genuinely tribe-eligible SBA grant**: "nonprofit microenterprise development organizations run either privately, or by state, local, tribal governments, or Indian tribes," posted to Grants.gov "in either April or May of each year." STEP goes to states only. **7(j) status UNKNOWN** (empty body post-migration, unmentioned on the grants page). **APEX Accelerators' current administrator UNKNOWN** — do not state that SBA administers it.

### 3.13 Treasury — the source v1 missed entirely

**The CDFI Fund's Native American CDFI Assistance (NACA) program is the strongest Native capacity-funding source outside the grant agencies**, and it belongs in Tier 1. More than $220M awarded to date. Financial Assistance requires a **Certified CDFI with at least 50% of activities serving Native American, Alaska Native and/or Native Hawaiian communities**; FY2025 also offered roughly $100M in Housing Production Financial Assistance. **Technical Assistance is the relevant vehicle here** and is open to Certified CDFIs, **Emerging CDFIs** (must certify within 3 years) and **Sponsoring Entities** (organizations primarily serving Native communities that will create a Certified CDFI within 4 years), and may be used "to increase their capacity to serve their communities."

The limit must be stated plainly: **tribal governments are not eligible as such** — the applicant is a financial institution or an entity becoming one. Every document on the application-materials page carries an "Updated - `<date>`" stamp, which is ideal free change detection, and the FY TA Application Guidance PDF is the authoritative unread artifact on whether software is a line-item allowable cost.

---

## 4. Recurring Native and tribal programs

"Recurring" means the channel has repeated historically — not that a competition or identical eligibility exists every year. Verified recurring cycles, with the ones that have a *checkable* pattern marked:

| Program | Verified cycle |
|---|---|
| EPA GAP | National NOFA ~November; work-plan/Grants.gov deadlines **per EPA Region**, Feb–July |
| EPA CWA §319 tribal competitive | NOFO ~mid-August, close ~early November, selections ~spring |
| FWS Tribal Wildlife Grants | Opens ~June, closes ~mid-August |
| NPS Tribal Heritage Grants | Annual, ~July close |
| BIA EMDP | Annual, ~August close |
| DOJ CTAS | Annual; FY26 posted July, Grants.gov mid-October |
| OVW Tribal Governments Program / TSASP | Annual; FY26 closed early September |
| FHWA TTP Safety Fund | Deadline ~mid-January; awards announced ~March |
| FTA Tribal Transit competitive | Annual; FY26 announced late May, due late August |
| DOL WIOA §166 INA | Multi-year designation cycle; PY26 FOA issued April, closed May |
| SBA PRIME | Grants.gov posting in April or May |
| USDA NIFA TCRGP | Posted April, closes December (phased) |
| HUD IHBG-COMP | NOFO ~September, due ~January |
| HUD ICDBG Single Purpose | Annual competitive; **ICDBG Imminent Threat is rolling** |
| Treasury NACA | FY2025 pattern: opened mid-January, closed late March, TA awards announced end of September |
| IHS SDPI | Recurring appropriation, formula-like distribution |
| Cherokee Preservation Foundation | First Monday of December and first Monday of June |
| American Indian College Fund scholarships | Opens February 1; May 31 priority review |

**Recognition warning, restated with evidence.** Programs grounded in the government-to-government relationship restrict direct eligibility to federally recognized Tribes: EPA GAP (40 CFR 35.502), FWS TWG (explicit), FHWA TTP (keyed to the BIA Federal Register list), DOJ CTAS (explicit), DOE Tribal Energy Loan Guarantee, NPS Tribal Heritage Grants. Three verified exceptions run the other way and are commercially important: **HUD IHBG** admits a limited, grandfathered set of state-recognized Tribes; **ED Title VI** counts members of state-recognized tribes, terminated tribes, and first/second-degree descendants; **FTA** expressly routes non-federally-recognized tribal governments to state §5311 subrecipient status. And **HRSA** states agency-wide that recognition is not required.

---

## 5. Funding streams likely to pay for software and capability development

### 5.1 The governing authorities (verified in the eCFR)

The 2024 Uniform Guidance revision changed the answer materially:

- **2 CFR 200.455(c)** — *"The costs related to data and evaluation are allowable,"* expressly including expenditures needed to gather, store, track, manage, analyze, secure, share or publish data to administer or improve the program, *"such as data systems, personnel, data dashboards, cybersecurity, and related items,"* and naming *"feasibility assessment"* and *"conducting evaluations."*
- **2 CFR 200.413(b)** — costs otherwise indirect may be direct if directly related to a specific award, expressly listing *"cybersecurity, integrated data systems, asset management systems, performance management costs, program evaluation costs."*
- **2 CFR 200.414(f)** — the de minimis indirect rate is **15% of MTDC**, and once elected it must be used for all federal awards until a negotiated rate is obtained. MTDC excludes equipment, capital expenditures, rental costs, and each subaward above $50,000, so 15% recovers less than customers expect.
- **SaaS classification.** §200.1 names *"software subscriptions or licenses"* as **intangible property**, and *Capital assets*(2) excludes intangible right-to-use and right-to-use operating lease assets; §200.465(e) allows right-to-use lease payments. Reading those together, **a SaaS subscription is best characterized as a service / intangible right-to-use cost, escaping both the equipment regime and §200.439 prior approval.** Present that as a well-supported reading, not settled law. **The corollary is a real trap: a perpetual license capitalized under GAAP becomes a capital asset, triggering prior approval and becoming unallowable as an indirect cost. Subscription pricing is regulatorily cleaner than perpetual licensing.**
- **⚠ The tribal-specific limitation.** **§200.444(a)** makes general costs of government unallowable for Tribes — the exact objection an auditor raises against a tribe-wide platform. The counter is **§200.444(b)**, which lets Tribes book up to **50% of executive-office costs** for "managing and operating Federal programs" into indirect **without documentation**. Framing matters materially.
- **§200.460** — proposal costs *"normally should be treated as indirect costs,"* and *"No proposal costs of past accounting periods may be allocated to the current period."*
- **§200.413(c)** — administrative and clerical salaries are presumed **indirect**; direct-charging requires all three conditions (integral to the award, specifically identifiable, not also recovered as indirect) and is a documentation burden, not a formality.

**Currency caveat:** the eCFR pages read display as current to 2026-08-24 with Title 2 last amended 2026-08-17, and that amendment was **not diffed** against the quoted text. Re-verify §§200.413, 200.414, 200.455 before any client deliverable.

### 5.2 Summary table

| Cost category | Allowability | Best supporting authority | Caveats |
|---|---|---|---|
| Cybersecurity tooling | **clearly allowable** | 2 CFR 200.455(c) and 200.413(b) — named in both | Direct vs. indirect placement still fact-dependent; no double-charging |
| Data systems | **clearly allowable** | 200.455(c) "data systems, personnel, data dashboards"; 200.413(b) "integrated data systems" | The "integrated data systems" sentence in §200.455(c) references State/local agencies, **not Tribes** — rest the tribal case on the first two sentences |
| Program evaluation | **clearly allowable** | 200.455(c); 200.413(b); 24 CFR 1000.236(a) | — |
| Compliance system | likely allowable | **24 CFR 1003.206(a)(1)(iii)** "Developing systems for assuring compliance with program requirements" | Strongest program-level hook found; ICDBG-specific and inside a combined 20% cap |
| Grant management software | likely allowable | 200.455(c); 200.413(b) "asset management systems, performance management costs"; 200.444(b) 50% safe harbor | Not named as such anywhere. Enterprise-wide deployment belongs in the **indirect pool**, not a direct charge. §200.444(a) objection applies |
| Financial reporting system | likely allowable | 200.455(c); 200.413(b); 24 CFR 1000.236(a) | Consistency rule §200.413(a); IHBG within its admin cap |
| Cloud/SaaS subscription | likely allowable | §200.1 *Intangible property*; *Capital assets*(2); **200.465(e)** | Classification is an inference from three definitions, not one OMB sentence — expect some awarding officials to disagree. Period-of-performance limits. Pre-award timing |
| Needs assessment | likely allowable | 200.455(c) "evidence reviews, evaluation planning and feasibility assessment"; 24 CFR 1003.205(a) "data gathering, studies, analysis" | ICDBG combined 20% cap; §1003.205(b) excludes plan *implementation* |
| Feasibility study | likely allowable | 200.455(c) names "feasibility assessment" verbatim; BIA NABDI FY22 awards funded an IT feasibility study | Same caps |
| Grant writing | likely allowable **as indirect**; unlikely as a direct charge | 200.460; **24 CFR 1003.206(d)** for direct (ICDBG only) | **⚠ DOJ COPS expressly bars "Contractor/consultant expenses for grant writing purposes." Always present both sides.** No carry-forward of prior-period proposal costs |
| Records management | sometimes allowable, NOFO-dependent | **DOJ COPS PA1: "Records management systems (RMS)"** expressly allowable | PA1 only; program-purpose RMS, not administrative recordkeeping |
| Workforce case-management system | sometimes allowable, NOFO-dependent | **DOJ CTAS PA5: "Data management systems for record keeping and case management"** | Purpose-Area-specific; PA2 forbids budgeting equipment at all |
| IT modernization | sometimes allowable, NOFO-dependent | §200.1 *Information technology systems*; §200.439(b)(1) | **⚠ Biggest threshold trap: IT counts as general purpose equipment, so prior written approval attaches at ANY dollar amount if capitalized;** §200.439(b)(7) bars it from the indirect pool |
| Administrative capacity/staff | sometimes allowable, NOFO-dependent | 200.413(c) three conditions; **200.444(b)** 50% tribal safe harbor; 24 CFR 1000.236(a) | Presumed indirect. **⚠ DOJ bars "administrative assistant" salaries.** HUD and FEMA caps apply |
| Broadband/digital-equity planning | **unclear** | NTIA TBCP page status only — NOFO unverified; a Digital Equity planning program could not be located | Program status itself unverified. **Do not advise on this** |
| Procurement modernization | **unclear** | No authority found. 24 CFR 1003.206(a)(4) is the nearest reach | **Weakest category — do not represent as supported** |

### 5.3 The program-level hooks worth quoting to customers

- **⭐ 24 CFR 1003.206(d) (ICDBG)** — *"ICDBG funds may be used to prepare applications for other Federal programs where the grantee determines that such activities are necessary or appropriate to achieve its community development objectives."* This is explicit federal authority to spend a grant on grant-seeking capacity. It sits inside a combined §1003.205 + §1003.206 cap of **20% of grant plus program income**, and §1003.206(c) permits indirect costs under a 2 CFR 200 subpart E cost allocation plan.
- **EPA GAP** — supports *"core environmental program capacities, such as administrative, financial management, information management,"* with budget categories expressly including contracts and consultants and a 15% de minimis indirect. Constraint to encode: costs must map to an approved **work plan component** and an **ETEP** priority; if no ETEP exists, developing one must be a work plan commitment.
- **EPA CWA §106** — *"Developing water quality and geographic information system databases to track changes in water quality and ensure consistency in data management."*
- **DOJ CTAS, by purpose area** — PA1 (COPS/TRGP): *"Computer hardware and software, mobile data terminals, radios,"* indirect costs allowable. PA5 (treatment courts): *"Computer hardware and software for internet access and email capability"* and *"Data management systems for record keeping and case management"* (same language in PA8 and PA9). PA2 (strategic planning): computing devices go under Supplies or Other, but *"Costs for outside TTA providers, planners, or outside organizations to create a strategic plan for the tribe are not an allowable expense,"* and PA2 is once-per-tribe. PA8/PA9 bar additional consultants.
- **BIA TCR** — 280+ funded adaptation plans, vulnerability and risk assessments; planning is the program.
- **FWS TWG** — salaries, equipment, consultant services, subcontracts, acquisitions of goods and services; planning and habitat mapping eligible.
- **FTA Tribal Transit** — "capital, operating, planning, and administrative expenses"; planning projects and start-up costs for non-operating Tribes.
- **USDA NIFA TCEG** — recipients "invest in technology to reach more students on remote reservation communities." TCRGP solicits AI, data science and digital tools by name.
- **Treasury NACA TA** — capacity funding for Native CDFIs, the canonical vehicle for technology, systems, staffing and consulting in that segment. Rated *likely* rather than *clearly* allowable because the TA Application Guidance PDF was not opened.
- **SC Rural Health Transformation Program (Connections to Care)** — the state pass-through that most directly funds the category: verified to expand *"electronic health records, remote patient monitoring, telehealth services and a statewide resource database platform."*

### 5.4 The traps to state to every customer

Pre-award costs need written agency approval (§200.458). Capital-expenditure prior approval attaches to **general purpose equipment — which includes information technology systems — at any dollar value**; the $10,000 threshold applies only to *special* purpose equipment. No program read permits charging a subscription beyond its period of performance, and **DOJ additionally bars "service agreements, or prepaid voice and data plans"** — structure as annual, in-period charges. One platform cannot be both an indirect cost and a line item on multiple awards (§200.413(c)(3), §200.414(f)). ICDBG's 20% cap covers planning **plus** administration together. Supplanting rules are uneven and must be checked program by program (DOJ PA1 uniquely tests against BIA funds; ANA has maintenance of effort at 45 CFR 1336.50(c); EPA GAP has a no-reduction rule) — with real exposure if the Tribe was already paying for the tool from its own funds. ANA's 20% non-federal match means charging a subscription there also consumes match capacity. And **FY26 DOJ content restrictions** on funds used "to promote gender ideology" or advance "diversity, equity, and inclusion" could reach a platform's features, content, or marketing claims.

**Two claims were deliberately not made.** No 15% FEMA HMGP management cost rate exists in 44 CFR 207 (only 4.89% was found); the commonly cited DRRA figure is UNVERIFIED. And 25 U.S.C. 5325(a)(2)–(3) was not read, so "ISDEAA contract support costs cover administrative overhead" remains UNVERIFIED rather than a selling point.

---

## 6. Research funding sources

- **NIH.** Discovery via the **weekly index** (`WeeklyIndexMobile.cfm`, server-rendered) plus the `fundingopps.xml` RSS — but the RSS returned only one item while the index showed different content, so it is **lagging and not a sole ingest**. The **THRO curated index** and **NARCH** are the two irreplaceable tribal-specific assets; Tribes apply to NARCH directly. RePORTER API v2 is real and keyless with documented pacing (1 request/second; large jobs on weekends or 21:00–05:00 EST, with IP-blocking risk) and contradictory limit documentation (docs say 500, swagger says 50 — handle 400s).
- **NSF.** Two verified working RSS feeds (`rss_www_funding_pgm_annc_inf.xml` and `rss_www_funding_upcoming.xml`, the latter with only a **30-day horizon**). **TCUP** is institution-only — not Tribes-as-governments, not Native nonprofits — with six verified recurring dates across strands, so model deadlines as (strand, type, recurrence). **AISL is archived** with no named successor but carries the best tribal/Native-nonprofit eligibility language at NSF; worth a standing watch. **EPSCoR eligibility is jurisdictional, not tribal** — 28 named jurisdictions, and **South Carolina is one of them**. There is **no NSF funding-opportunity API**, only an awards API; `nsf.gov/funding/opportunities` returns an empty shell, and `robots.txt` disallows query-string funding URLs and CSV export.
- **USDA NIFA.** Covered in §3.3; the phased TCRGP deadlines appear **only** in the "Upcoming Program Events" block on program pages.
- **HRSA and CDC.** Covered in §3.2. HRSA is bursty but structurally excellent; CDC carries genuine terms risk.
- **IMLS.** FY26 Native NOFOs (`fy26-ols-nab`, `-nae`, `-nh`, `fy26-oms-nanh`) **are posted**, but the `/grants/available/*` program pages **still show FY2025 deadlines** — parse the PDFs, do not scrape those pages. Eligibility inverts NIFA's: *"Indian tribes and Alaska Native villages and corporations are eligible… libraries, museums, schools, tribal colleges… are not eligible applicants."* Native Hawaiian Library Services runs on 20 U.S.C. 7517(2) and requires a **nonprofit, not a government**.
- **NEH / NEA.** A Native or Indigenous-focused NEH line **could not be verified**; `/grants/listing` claims 41 results but renders four with due dates stale to 2020, and robots disallows that path. DEL is confirmed joint NSF/NEH but **monitor it on NSF**. NEA's Grants for Arts Projects has verified twice-yearly two-part deadlines and explicit eligibility for *"Federally recognized tribal communities or tribes"* — but hard bars for small Native nonprofits (five years of prior arts programming, $20,000 minimum operating expenses, 1:1 cost share, **fiscal-sponsor applications ineligible**) and a two-part application trap (Grants.gov Part 1, then a separate portal Part 2 a week later). **NEA's robots.txt carries an explicit `ClaudeBot` full-site `Disallow` and a Crawl-delay of 300 — source NEA from Grants.gov.**
- **NOAA.** The key structural finding: the **national Sea Grant office had zero open opportunities while linking 34 state and consortium programs running their own RFPs on `.edu`/`.org` domains**, one of which had explicit "tribal entity" eligibility. **Grants.gov-only ingestion misses this entire tier.** NOAA CPO had no open opportunities and states no tribal eligibility. An unresolved high-value lead: `cpo.noaa.gov/noaa-aihec-mou/` (a NOAA–American Indian Higher Education Consortium MOU).
- **NASA.** **No tribal or TCU-specific MUREP element was found** — MAIANSE survives only in image alt-text and should be treated as unverified or likely discontinued. The OSTEM forecast has three rows, none MUREP, and carries a verbatim disclaimer that none of the listed solicitations has been formally approved for release. NSPIRES gave conflicting evidence across two fetches and served 2024-dated rows in August 2026: Grants.gov primary, browser automation only if business-critical.
- **USGS.** Cooperative Research Units is not a grant program; the CASCs name Tribes as partners but **no page states whether a Tribe can be a direct applicant** — do not assert either way.

Research governance fields the registry should carry: tribal resolution/authorization required, community engagement requirement, data ownership and sovereignty terms, publication and specimen/data-sharing terms, indirect cost treatment, and whether the Tribe is applicant, subawardee, consultant, participant, or merely a studied population.

---

## 7. Pass-through funding model

For every federal program store `distribution_mode = direct | state_formula | state_competitive | either | unknown`, plus the state administering agency, prime-recipient type, subrecipient classes, and whether a Tribe can bypass the state. Never advertise a federal listing to a customer when the live route is a closed state allocation. Track state plan, public-comment notice, subgrant NOFO, amendments, awards and closeout as separate records.

**Verified pass-through mechanics worth encoding as first-class patterns:**

- **FTA §5311/§5310** — the cleanest documented state-subrecipient route for a non-federally-recognized tribal government, with FTA itself linking the DOT state-contacts directory.
- **FHWA §202(a)(9) + §104(f)(3)** — allows a State's title-23 apportionment to be credited to TTP for a specified Tribe. Real but small: ~20 transfers across 8 states. Agreement-driven, never posted as an opportunity → human review.
- **FEMA HSGP/SHSP** — State Administering Agencies subaward; OJP maintains the SAA directory. A 50-state surface.
- **FEMA HMGP** — state-administered, but with a **tribal direct-recipient option** and a mitigation-plan gate.
- **EPA Alaska Native Villages** — flows through the Alaska DEC Village Safe Water Program.
- **EPA CWISA** — intake is the **IHS Sanitation Deficiency System**, not an EPA competition.
- **NTIA BEAD** — Tribes are not eligible entities; participation is via state coordination and subgrantee selection.
- **DOL WIOA Title I** — state workforce agencies then Local Workforce Development Boards; §166 INA is a separate direct channel.
- **State CDBG** — in many states, including South Carolina, only units of general local government may apply, making the nonprofit route a subrecipient relationship.

**Archetypes to instantiate per state:** emergency management; broadband/digital opportunity; housing finance and community development; environmental/SRF; energy office; workforce/WIOA; education; public health; justice assistance (Byrne/JAG); victim services (VOCA/VAWA STOP); arts; humanities; historic preservation; transportation/DOT; aging; agriculture; resilience/disaster recovery. Note that **the justice-assistance and victim-services administrators are frequently different agencies within the same state** — in South Carolina, SCDPS holds Byrne/JAG while the Attorney General's office holds crime victim assistance.

---

## 8. State-opportunity filtering model

1. Resolve operating state(s), service area, and lands — **never from mailing address alone**.
2. Resolve legal/eligibility class and recognition status **independently** of state.
3. Join federal pass-through families to each state's administering agency and named program.
4. Monitor state portals as a discovery aid only; monitor agency pages and email bulletins as the substance.
5. Apply hard geography filters **before** ranking. Potlatch Fund (ID/MT/OR/WA), Bush Foundation (MN/ND/SD), Cherokee Preservation Foundation (EBCI/western NC) and Reclamation (17 Western States) are clean test cases for the gate.
6. Distinguish applicant, subrecipient, partner, beneficiary and vendor roles.
7. Store the source text supporting tribal/nonprofit/business eligibility; otherwise mark `UNKNOWN`.
8. Re-evaluate every live NOFO, because state definitions of "tribe," "local government," and "political subdivision" differ.

**Suggested fields on a state-source record:** state code; county or service-area scope; administering agency and division; parent federal program ALN; eligible applicant classes; eligible **subrecipient** classes; announcement channel (page, PDF, portal, email list); portal vendor and whether login-gated; page-date reliability flag; render mode (static / needs headless).

**Multi-state and urban Native cases.** A Tribe with land or service population in more than one state needs the union of state registries plus a per-state recognition record. Native nonprofits serving urban Native populations often have no reservation nexus at all — for them the productive classes are `native-nonprofit`, `native-serving-nonprofit`, and general nonprofit eligibility, and the productive sources are HRSA, IHS urban Indian programs, ED Title VI/DEMO, state pass-through, and Native-led philanthropy. Federal tribal set-asides will mostly be dead ends, and the product should say so rather than showing them.

---

## 9. South Carolina source map

### 9.1 The recognition picture — the foundation of everything else

South Carolina recognizes Native American entities under **SC Code §1-31-40(A)(10)** and **SC Code of Regulations Chapter 139**, administered by the **SC Commission for Community Advancement and Engagement ("Advance SC")**, renamed from the Commission for Minority Affairs in May 2025. Three categories exist: **Native American Indian Tribes, Native American Indian Groups, and Native American Indian Special Interest Organizations**.

The published list at `advance.sc.gov/south-carolinas-recognized-native-american-indian-entities` contains **16 entities**: 1 federally recognized (Catawba Nation), 10 state-recognized Tribes, 3 Indian Groups, and 3 Special Interest Organizations. **It carries no publication or last-revised date anywhere** — so monitor it by content hash, not by date. The **recognition application process is not published** as a findable page: mark UNKNOWN and contact the Commission.

Three distinct sets must be tracked separately, because conflating them produces wrong eligibility:

1. **SC state-recognized entities** (16, per Advance SC).
2. **Federally recognized Tribes resident in SC** — exactly one, **Catawba Nation**, confirmed against Federal Register document **2026-01899** published 2026-01-30, which lists 575 federally recognized entities nationally.
3. **Federally recognized Tribes with historic SC affiliation for Section 106 consultation** — 16, per SCDAH, including Catawba plus fifteen non-resident Tribes. This is **not** a recognition list.

Note also that Advance SC's **Native American Advisory Committee membership is broader than the recognized list** and must not be conflated with it.

**The operational consequence, stated plainly.** A state-recognized-only SC entity is **ineligible** for BIA/Interior programs, IHS, HUD ICDBG and Section 184, DOL WIOA §166, ED Title VII/STEP as an applicant, EPA GAP, FHWA TTP, DOJ CTAS, FEMA THSGP, and THPO status under NHPA. What remains open is real but different: the **Special Interest Organization** route via SC nonprofit incorporation; FEMA HMGP via SCEMD (which names "Indian tribes or other tribal organizations, and certain private non-profits"); SCOR grants (which name "tribal nations… and nonprofits"); HOME/CHDO via SC Housing; SCDHHS RHTP subawards; subrecipient status under a local government for CDBG and effectively BEAD; **FTA §5311 subrecipient status via SCDOT**; **HRSA**, whose agency-wide policy does not require recognition; **ED Title VI child counts**, which expressly include state-recognized tribes' members; and **Native-led philanthropy** — First Nations Development Institute and Potlatch Fund both admit state-recognized tribes explicitly, though Potlatch's geography excludes SC.

**Also verified:** Advance SC's page titled "Grants for State Tribes" is a **static curated list of roughly 25 federal programs the Commission does not administer**, most of which require federal recognition. It has no application, deadline, or dollar figure. Treat it as human lead-generation, never as an opportunity feed — ingesting it would systematically surface programs SC's state-recognized entities cannot win.

### 9.2 Emergency management, resilience, mitigation

- **SCEMD Mitigation / HMGP** (`scemd.org/recover/mitigation`) names eligible applicants verbatim as *"state and local governments, Indian tribes or other tribal organizations, and certain private non-profits,"* 75/25 cost share with in-kind match allowed. Open disasters: HMGP 4829 Helene, 4835 Debby, 4858 Edisto Flooding. Applications run through the "South Carolina Recovery Grants system," **whose URL is not exposed on the page and is almost certainly login-gated (UNKNOWN)**. BRIC must go through FEMA GO, not the state. **FMA is not at SCEMD — SCEMD states it is managed by SC DNR.**
- **Major negative finding: SCEMD's site has no grants section at all.** The full sitemap was retrieved and there is no HSGP, SHSP, EMPG or NOFO page anywhere in navigation. This is absence of content, not link rot. Likely non-web channel: the county emergency-management network.
- **SC Office of Resilience (`scor.sc.gov`)** — established under SC Code §48-62-10, grants hub at `/grants-activities`, explicitly naming *"tribal nations, traditional communities, and nonprofits."* Not login-gated; publishes a public Google Calendar of hearings. Programs: Disaster Relief and Resilience Reserve Fund, SC Resilience Revolving Fund, HUD CDBG-MIT, Helene CDBG-DR Mitigation, ARPA Stormwater, Voluntary Buyouts.

### 9.3 Housing, community development, CDBG

- **SC CDBG is unambiguous and restrictive:** *"only units of general local government —towns, cities and counties— are eligible for CDBG funds."* Administered by SC Commerce's Division of Grants Administration. A Native-serving nonprofit or tribal government must partner with a non-entitlement town or county — and **the explicit subrecipient provision was not verified** because the Implementation Manual was not fetched. The entitlement exclusion list is stamped "For FY 2018" and is stale; it excludes **Rock Hill**, Catawba Nation's home city, which runs its own HUD allocation.
- **Consolidated Plan administration map for SC:** CDBG → Commerce; HOME and National Housing Trust Fund → SC Housing; ESG → SC Department of Administration; HOPWA → SC Department of Public Health. The annual cycle is public notice mid-January, hearing late January, comment close mid-February, program year April 1–March 31.
- **SC Housing CHDO certification** is a real nonprofit developer pathway: 15% of HOME funds are set aside for CHDOs acting as owner, developer or sponsor, and 2026-27 application materials are live. **Flag for legal review:** the CHDO tests require a board with at least one-third low-income representation and a *"lack of for-profit or public control,"* which may block a tribally-controlled nonprofit.

### 9.4 Health, behavioral health, aging

- **SCDHHS Grants is the richest single SC grants page found**, and the v1 claim about Connections to Care is **verified essentially verbatim**: it expands *"electronic health records, remote patient monitoring, telehealth services and a statewide resource database platform."* It sits under the federal **Rural Health Transformation Program** led by CMS. Five initiatives: Connections to Care (SCDHHS-26-001), Leveling Up (-002), Wellness Within Reach (-003), Shoring Up to Sustainability (-004), and the **Tech Catalyst Fund administered by the SC Research Authority, not SCDHHS**. The 2026 window is **closed** (posted 2026-04-02, due 2026-06-01, awards 2026-07-31), which makes it precedent — except the **Tech Catalyst Fund, described as announced through a future stage: the one live thread.** An "Example Standard Subrecipient Agreement" dated 2026-07-31 plus a full SF-424 package confirms a genuine subrecipient regime. Eligible applicant classes live inside four unfetched application PDFs: UNKNOWN.
- **SC DPH** (successor to SCDHEC's health functions after the 2024 reorganization) has dedicated Procurement Services and Subrecipient Monitoring pages, confirming a real subaward regime for Title V MCH and Hospital Preparedness — but eligibility is entirely unknown because of a rendering defect (§9.7).
- **SC BHDD** (formerly DAODAS; `daodas.sc.gov` 301s to `bhdd.sc.gov`) references a **July 2026–June 2029 nonprofit Mental Health Block Grant solicitation** on-page with no document attached and stale instructions — chase it directly. Behavioral health is one of the strongest Native-need domains in SC.
- **SC Department on Aging** runs Eldercare Trust Fund and senior-center grants. Note OAA **Title VI** Native American programs are a direct federal channel to tribal organizations and do not flow through the state unit on aging, while Title III services do — so an SC Native elder program may be reachable both ways.

### 9.5 Environment, water, land, agriculture, energy, broadband, workforce, transportation, education, culture

- **SC DES** (successor to SCDHEC's environmental functions) runs the SRF programs and **Section 319 nonpoint source subawards** — confirmed to exist as a subaward pipeline, eligibility UNKNOWN. **SC Rural Infrastructure Authority** publishes a consolidated "Funding Resources 2026" guide that doubles as an SC funder map. **SC Forestry Commission** publishes real NOFO PDFs (Urban and Community Forestry, Hurricane Supplemental, cost-share, Hurricane Helene Timber Block Grant). **SC Conservation Bank** funds land protection through a login-gated application portal. **SC Department of Agriculture** administers the USDA **Specialty Crop Block Grant** — the most plausible SC food-sovereignty entry point for a Native-serving nonprofit.
- **Broadband: there is no open SC state broadband program.** BEAD was restructured per an NTIA Policy Notice dated 2025-06-10 and SCBBO's Initial Proposal Modification Letter dated 2025-06-19; SC's Final Proposal was filed 2025-09-30 and every state broadband program is Awarded or Closed. Tribal/nonprofit subgrantee eligibility is not established on any fetched page; the realistic Native role is as a **Community Anchor Institution**, verifiable in the published `SC BEAD CAIs.csv`. The authoritative announcement channel is a **Survey123 notification list** which SCBBO names twice — subscribe rather than scrape. Tier 4 watchlist, not a pipeline.
- **Workforce:** SCDEW administers WIOA, but real access is through **12 local workforce development boards** and `scworks.org`, each with its own procurement — a 12-board surface inside one state. The SC WIOA Combined State Plan PY2026-2027 modification is published.
- **Transportation — the most important SC pass-through finding.** SCDOT's Public Transit Division runs the §5310 Enhanced Mobility Call for Projects and §5311 Rural, and **names §5311(c) Tribal Transit on paper with zero detail; it appears dormant in SC.** Combined with FTA's own statement that non-federally-recognized tribal governments may apply to the state as a subrecipient, this is a direct, apparently unclaimed opening — and a concrete question to put to SCDOT. The SCDOT State Management Plan would resolve §5311 and §5311(c) eligibility and was not fetched.
- **Justice and victim services:** SCDPS's Office of Highway Safety and Justice Programs is the SC home of **Byrne/JAG** and NHTSA highway safety, with FFY 2027 solicitation PDFs published and a login-gated IntelliGrants portal. **VOCA crime victim assistance sits with the SC Attorney General's Crime Victim Services Division**, not SCDPS, with 2026-2027 Program Guidelines published. The legacy `sova.sc.gov` is a frozen 2015 shell. **SC's VAWA STOP/SASP administrator was not identified — an open question.**
- **Culture — the highest-priority SC open question.** **SCDAH's grants program is the only SC program family found that names state-recognized tribes**, with a cycle deadline observed at 2026-09-02. Whether a tribal government can satisfy the Charities-registration, incorporation and deed tests is unresolved, and this decides whether it is a real pathway or a paper one. Contact `sgf@scdah.sc.gov`. **SC Humanities** is an NEH state affiliate that regrants federal humanities money to SC nonprofits — reachable by a Native-serving SC nonprofit that could not compete nationally at NEH. **SC Arts Commission** uses Foundant.
- **Education:** SCDE maintains current and archived opportunity lists; **21st Century Community Learning Centers** is the most plausible route for an out-of-school Native youth program. CHE is institution-oriented.
- **SC-local philanthropy:** Coastal Community Foundation and Central Carolina Community Foundation both accept applications from in-geography SC nonprofits and neither has a Native-specific program. Two features matter anyway: **Coastal explicitly offers capacity-building and technical assistance, and operates fiscal sponsorships** — a real path for a Native-serving group without its own 501(c)(3). Central Carolina's portal vendor is verified as **Foundant**.

### 9.6 There is no central SC grants portal

Stated definitively. Four candidates were checked and all fail:

- **SC Department of Administration "Managing Grants"** is inward-facing compliance under **SC Code §2-65-30** (Form GR-100 notification to the Executive Budget Office before spending unanticipated federal awards, exempting grants under $200,000 and research/student aid). **Filings are not published — a FOIA target, not a scrape target.**
- **State Clearinghouse Intergovernmental Review** is an E.O. 12372 single-point-of-contact review function, not an opportunity board. (Worth one follow-up fetch: DOJ CTAS PA1 expressly triggers E.O. 12372, so this office sits in the CTAS path for SC applicants.)
- **SCBO / procurement.sc.gov** is **procurement, not grants** — keep it in a separate data stream. It is relevant as a sales channel into SC agencies, not as a Native funding source.
- **SC Office of the State Auditor** publishes no single-audit resource, no Uniform Guidance page, and no subrecipient-monitoring resource.

**SC coverage must therefore be built agency-by-agency.** That is not a limitation of this research; it is the shape of the state.

### 9.7 SC engineering hazards found the hard way

Domain churn is the top data-integrity risk: `cma.sc.gov`→`advance.sc.gov`, `schousing.com`→`schousing.sc.gov`, `daodas.sc.gov`→`bhdd.sc.gov`, and the `scorf`/`scor` near-miss. Several key pages carry **no revision date** (the recognized-entities list, the CDBG entitlement list, the SCEMD mitigation page), requiring content-hash diffing. **Every `des.sc.gov` and `dph.sc.gov` HTML page emits an identical ~103–104 KB mega-navigation before any body content**, exhausting a fetch budget — these need a headless render with a `#main-content` selector, and `des.sc.gov/sitemap.xml` is a usable URL inventory. Two domains must be **blacklisted in the ingestion layer before any crawl runs**: the legacy `scdhec.gov`, and **`scdmh.net`, which was fetched and found to be a hijacked casino site**. SC runs mostly Drupal 10, with exceptions: SCEMD custom, `cdbgsc.com` WordPress, `scbo.sc.gov` Backdrop, `osa.sc.gov` WordPress.

---

## 10. Eligibility-class matrix

Codes: **Y** generally contemplated; **V** varies by NOFO/route; **N** generally not direct; **U** unknown without a live notice.

| Program family | Fed. tribe | State-recog. tribe | Tribal org | Native nonprofit | Native business | Native-serving nonprofit | TCU/BIE school | Individual | Consortium | State/local serving Natives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BIA OIED tribal grants | Y | N | V | N | V (TEDO/IBIP) | N | N | N | V | N |
| BIA TCR | Y | N | Y | N | N | N | N | N | V | N |
| IHS DGM competitive | Y | N | Y | V | N | V | N | N | V | N |
| IHS urban Indian programs | N | N | V | Y | N | Y | N | N | V | N |
| ANA discretionary | Y | U | Y | Y | N | V | V | N | V | V |
| HRSA (agency default) | Y | **Y** | Y | Y | N | Y | V | N | Y | Y |
| NIH NARCH | Y | N | Y | V | N | N | Y | N | Y | N |
| HUD IHBG | Y | **Y (limited, grandfathered)** | Y (TDHE) | N | N | N | N | N | V | N |
| HUD ICDBG | Y | N | V | N | N | N | N | N | V | N |
| EPA GAP | Y | **N (explicit)** | V (intertribal consortia only) | N | N | N | N | N | V | N |
| EPA CWA §106 / §319 | Y (+TAS gate) | N | V | N | N | N | N | N | V | N |
| DOJ CTAS | Y | **N (explicit)** | V | V | N | V | V | N | Y | N |
| OVW TSASP | Y | U | Y | Y | N | V | N | N | Y | N |
| FEMA tribal direct (THSGP/HMGP) | Y | U | V | V (certain PNPs) | N | V | N | N | V | Y |
| FHWA TTP / TTPSF | Y | **N (explicit)** | V (TTSGP) | N | N | N | N | N | V | V (§202(a)(9)) |
| FTA Tribal Transit | Y | **V — via state §5311 subrecipient** | Y (TTSGP) | V | N | V | N | N | V | Y |
| ED Title VI (child counts) | Y | **Y (members count)** | Y | Y (ICBO) | N | V | V | N | Y | Y (LEA) |
| USDA NIFA 1994 programs | N (institution test) | N | N | N | N | N | Y | N | V | Y (1862/1890) |
| USDA RD | Y | N (RCDI explicit) | V | Y | V | Y | Y | V | V | Y |
| DOL WIOA §166 | Y | U | Y | Y | N | Y | N | N | V | N |
| Treasury NACA | N (as government) | N | V (Sponsoring Entity) | Y (as CDFI) | Y (as CDFI) | V | N | N | V | N |
| General Grants.gov (codes 99/25) | V | V | V | V | V | V | V | V | V | V |
| State pass-through | V | V | V | V | V | V | V | V | V | Y |
| Native-led philanthropy | Y | **Y (FNDI, Potlatch explicit)** | Y | Y | V | Y | V | Y | V | N |

**Two modeling notes the matrix cannot capture.** First, eligibility must be a **graded classification, not a boolean** — `07`/`11`/`08` and `ET23010/20/30` give high-precision positives, but `99`, `25` and `ET12010` push the real answer into free text and the NOFO PDF. Second, the **501(c)(3) trap** is real and the best Native funders already solve it: First Nations Development Institute and Potlatch Fund both enumerate tribal governments, **Native 7871 organizations**, and **fiscally-sponsored** entities as first-class applicants, and Potlatch even lists **"Seeking Recognition."** Build the eligibility taxonomy from those two pages, and carry a distinct **"fiscal sponsorship accepted"** flag.

---

## 11. Scraper and monitoring recommendations

### 11.1 Four lanes

**Tier 1 — authoritative spine, API-first, no HTML.** Grants.gov daily XML extract (corpus of record) + Search2/fetchOpportunity (deltas and amendment forensics) + Federal Register API including **Public Inspection** + SAM.gov Assistance Listings API + USAspending API v2. Design it **extract-primary, API-secondary**: the extract is the only unmetered, complete, fully-documented snapshot, and it is the only source carrying `Estimated Synopsis Post Date`, `Fiscal Year`, `Archive Date`, the 18,000-character description and the 4,000-character eligibility text.

**Tier 2 — change detection on server-rendered HTML** (all confirmed statically scrapeable): OJP current-funding (use its `Date Modified` field), ED Available Grants, HUD Exchange `/news/`, HUD `codetalk`, DOE Office of Indian Energy table 1, NIH `WeeklyIndexMobile.cfm`, HRSA find-funding, NIFA program pages, USDA RD program directory, BIA `/news`, EPA program pages (use the `meta-DC.date.modified` tag), IHS DGM index, FTA `/grants` (a sortable, filterable, paginated table — the cleanest structured surface in DOT). **Hash a normalized content region, not the page** — agency footers and view counters generate pure noise.

**Tier 3 — browser automation, budgeted deliberately.** NSF `/funding/opportunities`, NIH Guide search UI, DOE "Other Funding and Opportunities" cross-agency table, DOE IE-Exchange grid, HUD Exchange facet layer, NSPIRES session search, `sam.gov/data-services`, `des.sc.gov` and `dph.sc.gov`, `apexaccelerators.us`, the BIA Access to Capital Clearinghouse. **Never run browser automation against hud.gov or arts.gov under an AI-crawler user-agent** — both name `ClaudeBot` with `Disallow: /`.

**Tier 4 — email and bulletin ingest, first-class not fallback.** DOE Office of Indian Energy monthly (`USDOEIE`), OJP Funding News weekly (`USDOJOJP_COMMS_25`), FHWA Office of Tribal Transportation (`USDOTFHWA_83`), FTA tribal transit (`USDOTFTA_51`), DOT Navigator (`USDOT_167`), USDA RD tribal (`USDARD_C148`), NIFA (`USDANIFA`), FNA (`USFNS`), ED (`USDE`), HRSA (`USHHSHRSA`), Treasury CDFI (`USTREASCDFI`), CDC (`USCDC_2247`), HUD Codetalk (`CODETALK-L`), HUD Exchange, EPA grants (Mailchimp), EPA Brownfields (Constant Contact). Provision a dedicated ingest mailbox with per-source plus-addressing. **Then try to skip email where possible:** archived GovDelivery bulletins are publicly readable at `content.govdelivery.com/accounts/{ACCT}/bulletins/{id}` without subscribing — proven for `USDOEIE`, and probing the pattern for the other accounts is the highest-leverage unexplored lead in this research.

**PDF extraction lane — where tribal eligibility is actually adjudicated.** Grants.gov `synopsisAttachmentFolders[].synopsisAttachments[]` (`folderType: "Full Announcement"`), the EPA GAP national NOFA (parse the per-Region "Application Submittal Schedule" table every November), the FHWA tribal-shares PDFs, the TTPSF multi-year NOFO amendments, **EDA's combined PWEAA NOFO where the tribal set-aside lives on page 37**, IMLS `fy{NN}-*` NOFO PDFs, DOJ solicitation PDFs at `ojp.gov/funding/docs/<opp-id>.pdf`, and the Treasury NACA TA Application Guidance. Codes `25`/`99` and `ET12010` all push the real answer into this lane.

### 11.2 Polling cadence

| Source | Cadence | Constraint |
|---|---|---|
| Grants.gov XML extract | 1×/day ~05:30 ET | Published ~04:40 ET; **only 7 days retained — a missed day is unrecoverable** |
| Grants.gov Search2 | Hourly in business hours, 4×/day otherwise | No documented rate limit but an explicit right to block |
| Grants.gov fetchOpportunity | Event-driven only | Fire on delta detection |
| Simpler.Grants.gov | ≤60/min, ≤10k/day per key | Search data is **hourly-cached**; keys **auto-disable after 30 days unused** — keep a heartbeat |
| Federal Register documents | 2×/day | Documented **2,000-result pagination ceiling — partition backfills by date range** |
| Federal Register public inspection | 1×/business morning | Buys 1–3 business days of lead time |
| SAM.gov Assistance Listings | 1×/week with `publishedDateFrom` | **10/day without a SAM role, 1,000/day with one** — get a role |
| USAspending | 1×/month plus on demand | Probe `/awards/last_updated/` first |
| Regulations.gov | 1×/day, docket-scoped | GET limit undocumented; commenting API 50/min and 500/hr |
| OpenFEMA | Match `lastDataSetRefresh` | Explicit FEMA rule; `id` is not stable across refreshes |
| NIH RePORTER | ≤1 req/sec; large jobs weekends or 21:00–05:00 EST | Documented, with IP-blocking risk |
| NSF Awards API | 1×/day, avoid Fri 22:00–Sun 12:00 | Documented maintenance window |
| Tier-2 HTML | Daily (OJP, DOE, HUD, ED, IHS, HRSA); weekly (USDA RD, EPA, BIA, NIFA) | Honor ETag/If-Modified-Since; self-impose ~1 req/5s per host, since **no host publishes a Crawl-delay** except NEA and NEH (300s) |
| Tier-3 browser | Weekly, or on a Tier-2 signal | Expensive and brittle; never the primary detector |

**Global posture:** one descriptive user-agent identifying NativeForge with a contact URL; **never an AI-crawler UA**; exponential backoff on 429/5xx; a circuit breaker that halts a source after N consecutive failures and pages a human rather than retrying into a block; per-host concurrency of 1. Note that `energy.gov` timed out twice at 180s on first contact then served fine — build retry-with-backoff and do not treat a single timeout as a dead source.

### 11.3 Deduplication and transition detection

Federal grant data has no single global identifier, so use layers:

- **L1 identity:** normalized `opportunityNumber` (uppercase, strip whitespace and hyphens) as the human-facing key, plus the numeric `opportunityId` as a surrogate. **Composite required:** `(opportunityNumber, docType)` where docType ∈ {forecast, synopsis} — a forecast and its resulting synopsis **share the opportunity number**, and collapsing them destroys the transition you most need to detect. Never key on title.
- **L2 version:** `(opportunityId, docType, revision)`, cross-checked against the extract's `Version` field. A revision change creates a new immutable row; never update in place.
- **L3 cross-source joins:** ALN `NN.XXX` (Grants.gov ↔ SAM Assistance Listings ↔ USAspending `program_numbers` ↔ ED titles) as a **many-to-many** table, never a scalar; Federal Register document number (prefer it over the page-based citation, and treat `correction_of`/`corrections[]` as a version chain); docket ID plus `regulations_dot_gov_url` for consultation tracking; UEI for recipients. **Build an explicit agency crosswalk table** — Grants.gov `agencyCode`, Federal Register `agencies[].slug`/`parent_id`, and SAM's FPDS/AAC codes are three non-matching namespaces. Do not string-match agency names.
- **L4 fuzzy fallback** for sources with no identifier (BIA news, HUD Exchange, DOE tables, SC agency pages): `SHA-256(normalized_agency + normalized_title + earliest_deadline_date)`, with a near-match pass on title similarity plus deadline-within-3-days, resolving up to L1 as soon as an opportunity number appears in the text. BIA's Tribal Tourism Cooperative Agreement is the live example of an agency announcing an opportunity days before, or instead of, a Grants.gov posting.

**Forecasted → posted.** Index every `docType = forecast` record with its `Estimated Synopsis Post Date`; emit a first-class alert when the same opportunity number appears as a synopsis or `oppStatus` moves forecasted→posted. **Handle the silent-death case explicitly:** a forecast whose estimated post date has passed with no synopsis and no archive should age into a "forecast lapsed — never posted" state rather than sitting there looking live. That is the most common failure mode in naive grant trackers.

**Amendments,** in priority order: `synopsisModifiedFields[]`/`forecastModifiedFields[]` from fetchOpportunity — a literal list of what the agency changed, unique in the federal ecosystem, and it should be rendered to users directly ("the close date changed," not "something changed"); then `revision` plus history counts; then `lastUpdatedDate` (**polymorphic — the extract field is "Last Updated Date or Created Date," so a value there does not prove an update occurred**); then `synAttChangeComments[]` and attachment size/filename diffs, which catch **a changed NOFO PDF behind an unchanged synopsis**. Classify materiality: promote deadline, eligibility and award-ceiling changes; suppress contact-name and typo churn. Un-triaged amendment noise is what makes grant alerting unusable.

### 11.4 Failure modes specific to this domain

1. **Dead shells beat 404s.** HUD's old paths and several SC pages return HTTP 200 with valid HTML and zero content. **Content-length and body-hash checks are mandatory; HTTP status is not sufficient.** Add a rule: a title carrying a redesign artifact prefix (e.g. `25red-`) means stale — flag, do not diff.
2. **Shutdown and "not being updated" banners are page-scoped, not site-scoped.** EDA proves it. Detect them per page and suppress that page from user-facing output rather than blacklisting the domain.
3. **Stale-but-live is worse than dead.** internetforall.gov serves "Status: Open" for a window that closed in 2023. **Never surface an agency-authored status field without an independent freshness check** (latest internal date vs. today).
4. **Tribal set-asides hide inside multi-program NOFO PDFs.** EDA page 37. PDF section extraction is required for tribal coverage.
5. **Deadlines get revised.** HUD labelled an ICDBG date "New Deadline." Model deadlines as mutable and version them.
6. **Per-region deadlines are real.** EPA GAP has ten. One national date is wrong.
7. **Dual deadlines are real.** Every DOJ opportunity has a Grants.gov deadline and a JustGrants deadline.
8. **Application portals diverge from marketing pages.** DOE energy.gov vs. IE-Exchange; TTPSF applications by email; FDPIR/CWISA intake through IHS systems.
9. **`Disallow: /search/` is nearly universal** (sam.gov, ojp.gov, hud.gov, epa.gov, energy.gov, grants.nih.gov, rd.usda.gov, bia.gov). A monitor that polls site-search URLs violates robots on almost every agency host. Poll sitemaps, listing pages, feeds, or APIs.
10. **Portal vendors cluster.** Fluxx, Foundant/grantinterface, SM Apply, IntelliGrants, GrantSolutions, JustGrants, FEMA GO, TrAMS, AMIS, RD Apply, GEMS. Building vendor-specific adapters covers a disproportionate share of the field — and none of them should be automated with a customer's credentials without an explicit consent and security model.

---

## 12. Source priority tiers

The companion registry carries a tier on every one of its **381 rows**: Tier 1 = 144, Tier 2 = 133, Tier 3 = 58, Tier 4 = 42, Tier 5 = 4. Those tiers are per-lane research judgments about *importance*, not a build order — 144 collectors is not an MVP. **Use the Top 25 list below as the build sequence and the tier column as the backlog priority.**

- **Tier 1 (must monitor for MVP).** The API spine; the Native discovery layer (BIA ATC, IHS DGM + DTLLs, BIA grants index and news, HUD codetalk, DOE Indian Energy + IE-Exchange, EPA GAP and tribal water, DOJ tribal/OJP/CTAS, FEMA THSGP/HMGP, FHWA TTP + TTPSF, FTA tribal, USDA RD tribal + NIFA tribal, FNA FDPIR, EDA tribal, Treasury NACA, NIH THRO + NARCH, HRSA); and the customer's state bundle.
- **Tier 2 (important soon).** USAspending; OpenFEMA; agency newsletters and DTLL pages; ACF/ANA, SAMHSA, CDC, ACL; NPS/FWS/Reclamation secondary pages; DOT modal pages; DOL DINAP; SBA PRIME; NSF/NIFA/IMLS research; the remaining SC agencies; Native-led philanthropy with open applications.
- **Tier 3 (useful but later).** Broader cross-cutting federal programs; regional commissions; arts, humanities and museum programs; announcement-only intermediaries; SC-local community foundations.
- **Tier 4 (watchlist / manual research).** Authenticated portals; unstable JS search apps; sources with unclear reuse terms; invitation-only philanthropy; programs whose 2026 status is UNKNOWN (BRIC, Tribal Cybersecurity, SLCGP, Digital Equity, GDO 40101(d), TBCP).
- **Tier 5 (documented dead ends).** Recorded so nobody re-attempts them: Grants.gov RSS (serves HTML), NSPIRES as a primary source, USGS Cooperative Research Units, eRA Commons as a discovery surface, third-party aggregators.

---

## 13. Unknowns and legal/terms review needs

### 13.1 Terms and robots posture, verified

- **`sam.gov` prohibits scraping outright**, verbatim: *"Automated data gathering, web scraping tools are prohibited and, if detected, will result in the associated account(s) being denied access to SAM.gov via Login.gov."* API-with-key is the only sanctioned path, and D&B-sourced fields carry their own no-bulk restriction. **HUMAN_REVIEW_ONLY for scraping.**
- **`hud.gov` names `ClaudeBot`, `GPTBot`, `CCBot`, `Bytespider`, `Google-Extended`, `meta-externalagent` and others with `Disallow: /`**, asserts `Content-Signal: ai-train=no` *"as a condition of accessing this website,"* and invokes Article 4 of EU Directive 2019/790. Two hard flags: never present an AI-crawler UA on hud.gov, and get counsel on the access condition. The separate HUD USER API has a real click-through agreement with mandatory attribution and a 60-queries-per-minute limit.
- **`arts.gov` (NEA) robots.txt carries an explicit `# AI Bots` block naming `ClaudeBot` and `ChatGPT-User` with `Disallow: /`, plus `Crawl-delay: 300`.** Source NEA from Grants.gov. `neh.gov` also carries Crawl-delay 300 and disallows `/grants/listing*` — the program listing is off-limits to a compliant crawler.
- **CDC** states redistribution of syndicated content is not allowed, citing 42 U.S.C. 1320b-10 on reproducing content **for a fee** — directly implicating a paid product.
- **Grants.gov** requires a **mandatory attribution string** in any application using the API: *"This product uses the Grants.gov API but is not endorsed or certified by the U.S. Department of Health and Human Services."* This is a build requirement for NativeForge's UI, not optional. Its robots.txt is two lines, `Allow: /`.
- **federalregister.gov** needs no key, disallows the HTML search paths but not `/api/`, and prohibits use of NARA/OFR logos or seals by republishers. It is explicitly **not an official legal edition** — link the govinfo PDF where legal reliance matters.
- **fema.gov robots.txt returned an empty body and the OpenFEMA terms page failed at three URLs — binding terms unread. TERMS_REVIEW_REQUIRED.**
- **⚠ SPA opacity is a legal risk, not just an engineering one.** grants.gov, regulations.gov, usaspending.gov and reporter.nih.gov all serve their terms/policy pages client-side, so automated fetching retrieved no policy text. For those four, "no restrictive terms found" is **not** "no restrictive terms exist." A human must open them in a browser before production launch sign-off.
- **Non-.gov dependencies in critical federal paths** warranting review: `ihbgformula.com` (the IHBG formula process), `naihc.net` (HUD's own National Tribal Housing Summit registration), `apexaccelerators.us`, `tribalselfgov.org`, `eepurl.com` and `lp.constantcontactpages.com` (EPA listservs).
- **Private-sector flags:** Candid's opportunity API is a paid commercial license and redistributing its records inside a SaaS product is a contract negotiation under `candid.org/terms-of-service`; Native CDFI Network's site emitted an active content-protection signal; Native Americans in Philanthropy's Grantwatch feed is a **member benefit**, so scraping it is a permission conversation and ideally a partnership.

### 13.2 Open unknowns

**Eligibility:** whether ANA programs admit state-recognized entities (the single highest-value open eligibility question for SC customers); whether a state-recognized Tribe may be a Title VI *applicant* rather than only a source of countable children; whether SCDAH's grants are practically reachable by a tribal government; whether SC CDBG's Implementation Manual permits nonprofit subrecipients; whether tribal or nonprofit entities can be BEAD subgrantees in SC; whether a tribally-controlled nonprofit can satisfy SC Housing's CHDO control tests; THSGP's federal-recognition test as written in the FY25 NOFO; AFG/SAFER tribal eligibility; whether Tribes can apply directly to the USGS CASCs; SC's VAWA STOP/SASP administrator; whether SCDOT has ever solicited §5311(c).

**Program status as of 2026:** FEMA BRIC; Tribal Cybersecurity Grant Program; SLCGP; NTIA TBCP and the Digital Equity Act Native set-aside; DOE Grid Deployment Office 40101(d) and GRIP; DOE EECBG/WAP/SEP tribal pathways; a FDPIR Self-Determination Round 3; SBA 7(j); APEX Accelerators' administrator; NASA MAIANSE; an NEH Native line; a next DOE Office of Indian Energy FOA cycle.

**Technical:** the Simpler.Grants.gov `applicant_type` enum value for tribal applicants (recover from the live Swagger before writing filter code); whether the BIA Access to Capital Clearinghouse exposes a supported endpoint; whether NCAI's Sanity CMS backend exposes a queryable content API; whether GovDelivery's public bulletin-archive pattern works for accounts beyond `USDOEIE`; the FABS `business_types` letter meanings behind USAspending's `I`/`J`/`K`/`11`; USAspending's `spending_by_award` path (not verified this session); OpenFEMA's true stable primary keys; the FEMA and Treasury PDF artifacts that hold the authoritative allowability answers.

**Product and policy:** whether NativeForge shows opportunities, makes eligibility recommendations, or both — and what evidence threshold is required before a source is labelled eligible; whether authenticated customer portals are in scope, and the consent and security model if so; how tribal data sovereignty, sensitive locations and research governance are enforced; how state-pass-through parent/child records are represented; who performs final legal and terms review and maintains those decisions; and the human-review SLA for unknown eligibility, PDF-only notices and email intake.

---

## 14. Machine-readable source table

The companion registry is **`nativeforge-source-registry-v2.csv`** — **381 records**, carrying the requested 26 columns:

`source_id, source_name, source_type, agency_or_org, subagency, jurisdiction, federal_or_state_or_private, state_if_applicable, url, monitoring_method, scraper_difficulty, robots_or_terms_risk, native_relevance, eligibility_classes, federal_recognition_required, state_recognition_supported, software_cost_allowability, program_examples, deadline_pattern, update_frequency, data_format, has_api, has_rss_or_email, requires_login, notes, priority_tier`

Composition: 303 federal, 57 state (all South Carolina), 21 private. Terms posture: 261 OK, 111 TERMS_REVIEW_REQUIRED, 9 HUMAN_REVIEW_ONLY. Monitoring method normalized to the seven permitted values: 215 static HTML page monitor, 51 PDF/NOFO page monitor, 50 human review only, 30 API monitor, 15 search endpoint monitor, 11 email bulletin/manual intake, 9 RSS/feed monitor.

Note that 381 rows resolve to 346 unique URLs. That is intentional: several distinct fundable things share a page — the eight CTAS purpose areas sit on one solicitation URL with materially different cost rules, and OVW's four tribal programs share one funding-opportunities page. Model the program, not the page.

**Reading conventions a second agent must respect.**

- `UNKNOWN` is deliberate and load-bearing. It means "not verified," not "not applicable." Do not backfill it from priors.
- Every note ends with a `[research lane: …]` provenance tag naming which verification pass produced or merged the row. Rows tagged `seed-v1` came from the prior registry and carry its verification level, not this one's.
- `eligibility_classes`, `federal_recognition_required`, `state_recognition_supported`, `software_cost_allowability` and `deadline_pattern` are properties of **programs**, not of **data sources**. On a pure-infrastructure row (an API, a sitemap, a mailing list) they are `NA` or `UNKNOWN` by design.
- Rows exist that are deliberately negative: known-dead URLs (HUD's `/program_offices/` shell), trap pages (`ihs.gov/dgm/forecast`), absence findings (SCEMD has no grants section; SC has no central portal), and blacklist entries (`scdmh.net`). **Do not prune them** — they are the memory that stops a crawler from silently failing or from being re-pointed at a hijacked domain.
- Several rows are explicit gap markers (DOT unverified programs; USDA NRCS/FSA/Forest Service; Commerce MBDA/NOAA). They assert nothing and exist so the coverage map shows its own holes.
- The registry is a seed for scraper tests and monitoring contracts. **It is not an assertion that any listed program currently has an open competition.**

---

## Final prioritized lists

### Top 25 sources to monitor first — in build order

1. **Grants.gov daily XML extract** — corpus of record; filter on eligibility codes `07|11|08|99|25`
2. **Grants.gov Search2 + fetchOpportunity** — deltas and the only per-field amendment list in the federal ecosystem
3. **Federal Register API**, including the **Public Inspection** endpoints and `agencies[]=indian-affairs-bureau`
4. **SAM.gov Assistance Listings API** — ALN semantics and `ET23010/20/30`; get a SAM role first
5. **BIA Access to Capital Clearinghouse** (`bia.gov/atc`) — Native-scoped, multi-instrument, and where EPA now sends people
6. **IHS DGM Funding Opportunities index** — the densest single tribal NOFO archive
7. **IHS Tribal Leader Letters** — surfaces facilities programs no index carries
8. **BIA grants index** (`bia.gov/topic/grants`) **+ `bia.gov/news` + `sitemap.xml`**
9. **HUD `codetalk`** — replacing the dead `/program_offices/` paths
10. **DOJ OJP current-funding page + CTAS** — cleanest scrape target; dual deadlines; watch the Bureau of Justice Grants consolidation
11. **EPA GAP** — the annual November NOFA PDF plus a per-Region deadline model
12. **EPA tribal water** (§106, §319 base and competitive, CWISA, DWIG-TSA)
13. **DOE Office of Indian Energy page + IE-Exchange + monthly bulletin archive**
14. **FHWA Office of Tribal Transportation + TTPSF + GovDelivery `USDOTFHWA_83`**
15. **FTA tribal-governments hub + Notices index** — and the NTD reporting gate alert
16. **USDA RD tribal-relations + all-programs directory + `USDARD_C148`**
17. **USDA NIFA tribal programs + RFA list** — highest structured-metadata ROI anywhere
18. **USDA FNA FDPIR + the 8 RSS feeds** (`policy-memo-fdp` covers FDPIR)
19. **HRSA find-funding + the Who Can Apply policy page** — the recognition-agnostic default
20. **NIH THRO curated index + NARCH + the Guide weekly index**
21. **Treasury CDFI Fund NACA program + application-materials page**
22. **FEMA THSGP and HMGP via Grants.gov, plus OpenFEMA `HazardMitigationPlanStatuses`** as an eligibility gate
23. **ED Available Grants table + the Native programs index** (tribal eligibility facets; ALNs in titles)
24. **DOL DINAP announcements** (the §166 designation cycle)
25. **The customer's state bundle** — for the first customers, the South Carolina bundle in §9

### Top 10 sources most likely to help customers pay for NativeForge

1. **EPA GAP** — "administrative, financial management, information management" capacity, 4-year periods, no cost share, 15% indirect
2. **HUD ICDBG**, on **24 CFR 1003.206(a)(1)(iii)** compliance systems and **1003.206(d)** preparing applications for other federal programs (within the 20% cap)
3. **DOJ CTAS Purpose Areas 1 and 5** — computer hardware and software, and data management systems for record keeping and case management
4. **Treasury CDFI Fund NACA Technical Assistance** — the canonical technology and systems vehicle for Native CDFIs
5. **BIA Tribal Community Resilience Annual Awards** — planning, vulnerability and risk assessment is the program
6. **EPA CWA §106** — water quality and GIS database development, named verbatim
7. **BIA OIED feasibility programs (NABDI when funded, TEDC, TTGP)** — with the ITKN GIS and IT Feasibility Study awards as precedent
8. **HUD IHBG / IHBG-COMP administration and reporting**, with HUD-426 indirect-cost recognition in the package
9. **State health-IT pass-through — SC's Rural Health Transformation Program is the model**: EHR, remote monitoring, telehealth and a statewide resource database, explicitly funded
10. **The indirect-cost route itself** — 2 CFR 200.455(c) plus §200.444(b)'s 50% tribal executive-office safe harbor. Often the strongest position for an enterprise-wide platform, and the one most customers have never been shown

### Top 10 sources requiring legal or terms review before scraping

1. **SAM.gov** — scraping expressly prohibited with a named enforcement consequence; API-only
2. **hud.gov** — `ClaudeBot`/`GPTBot` disallowed by name; `ai-train=no` asserted as a condition of access; EU Directive 2019/790 invoked
3. **arts.gov (NEA)** and **neh.gov** — explicit AI-bot disallow and Crawl-delay 300
4. **cdc.gov** — redistribution of syndicated content barred, citing reproduction for a fee
5. **fema.gov / OpenFEMA** — robots.txt empty and terms unretrievable at three URLs
6. **Candid** — paid commercial license; redistribution inside a SaaS product is a contract question
7. **Native Americans in Philanthropy Grantwatch** — the feed is a member benefit; seek permission or partnership
8. **Authenticated portals** — SCORF/SC Recovery Grants, SCDPS IntelliGrants, GEMS, JustGrants, FEMA GO, TrAMS, AMIS, RD Apply, GrantSolutions, NSPIRES, Fluxx/Foundant/SM Apply. Never automate with a customer's credentials without a consent and security model
9. **The four SPA terms pages** — grants.gov, regulations.gov, usaspending.gov, reporter.nih.gov: policy text could not be retrieved automatically, so "no terms found" is not "no terms exist"
10. **Non-.gov dependencies in federal paths** — `ihbgformula.com`, `naihc.net`, `apexaccelerators.us`, plus agency Mailchimp and Constant Contact listservs whose content is intended for subscribers

### Top 10 state-specific source categories to instantiate per customer state

1. Emergency management, mitigation and disaster recovery (and note these are often **two** agencies — in SC, SCEMD plus SCOR, with FMA at SC DNR)
2. Housing finance and community development, including the CDBG administrator and the CHDO pathway
3. Health and human services / Medicaid, especially health-IT and rural transformation scopes
4. Behavioral health and substance use block-grant subawards
5. Justice assistance (Byrne/JAG) **and, separately, victim services (VOCA/VAWA STOP)** — frequently different agencies
6. Transportation and public transit, specifically the **FTA §5310/§5311 subrecipient pathway**, which is the documented route for a non-federally-recognized tribe
7. Environment, water and SRF, plus the §319 nonpoint source subaward program
8. Workforce and economic development, including **every local workforce development board** (12 in SC)
9. Education, higher education and out-of-school programs (21st CCLC as the likeliest fit)
10. Arts, humanities and historic preservation — the SHPO is often the only state program that names tribes at all, and the state humanities council regrants federal money to local nonprofits

Plus two per-state prerequisites that are not funding sources: the **state recognition registry and process**, and a **negative-findings record** documenting what does not exist in that state so the product never implies coverage it lacks.

### Open questions before crawler implementation

1. Which customer eligibility attributes are verified, by whom, and how often — and who owns the three distinct recognition sets (state-recognized, federally recognized resident, federally recognized with consultation interest)?
2. Does NativeForge show opportunities, make eligibility recommendations, or both — and what evidence threshold is required before a source is labelled eligible for a given customer?
3. How are `99`, `25` and `ET12010` opportunities handled? They are the recall set, they require NLP over a 4,000-character eligibility field and the NOFO PDF, and they are where the differentiator actually lives.
4. How are amendments, cancellations, forecast-to-posted transitions, forecast lapses and duplicate records versioned and surfaced — and what counts as material enough to notify?
5. What polling budget and attribution obligation applies per source, and where is the mandatory Grants.gov attribution string rendered?
6. Are authenticated customer portals in scope, and if so what is the consent, credential-custody and security model?
7. How are state pass-through parent/child records represented, and how does the geography gate handle multi-state Tribes, off-reservation service areas, and urban Native organizations with no reservation nexus?
8. How are tribal data sovereignty, sensitive locations, and research governance enforced in storage, display and export?
9. Who performs final legal and terms review, maintains those decisions, and signs off before a source moves from research to production?
10. What is the human-review SLA for `UNKNOWN` eligibility, PDF-only notices, email intake, and any source flagged `TERMS_REVIEW_REQUIRED` or `HUMAN_REVIEW_ONLY`?
11. What is the plan for the 42 Tier-4 rows whose 2026 program status is unknown — do they appear to users as "status unverified," or not at all until verified?
12. Is NativeForge willing to be a *supported* consumer where possible — a SAM.gov role, a Simpler.Grants.gov key with a heartbeat, a Grants.gov S2S listserv subscription for breaking-change notice, and a conversation with Native Americans in Philanthropy rather than a scraper?
