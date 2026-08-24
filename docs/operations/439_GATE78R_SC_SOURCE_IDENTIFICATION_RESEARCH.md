# 439 — Gate 78R: South Carolina source identification research pack

**Research only. No code changed. Nothing here is monitorable, live, or fresh.**

Every source below carries a citation. Where a claim could not be verified it is
marked UNKNOWN rather than filled in. Access was ordinary reading of public
pages; nothing was scraped and no `robots.txt` was evaluated, so **every**
robots/terms status is `unresolved`.

---

## 1. Executive summary

**Five findings, in order of consequence.**

**1. South Carolina has no central state grants portal.** Confirmed from the
state's own authority: the SC State Library's grants research guide lists five
separate agency resources and presents no unified system. The closest thing to a
central state feed is **SCBO**, which carries procurement solicitations only —
explicitly not grants. Gate 78's decision to seed SC as per-agency categories
rather than one portal was correct.

**2. The recognition split in SC is severe, and it is the whole ballgame.** One
federally recognized tribe (the Catawba Nation) and **ten** state-recognized
tribes, plus three Indian Groups and three Special Interest Organizations.

**3. South Carolina's own Native American Affairs division points
state-recognized tribes at a list of federal programs that mostly require
federal recognition.** The page `advance.sc.gov/grants-state-tribes` is titled
"Grants for State Tribes" and every program on it is federal. Where eligibility
is stated it frequently reads *"Federally recognized Indian tribes..."*. The page
never says whether any program is open to state-recognized tribes.

For SC's ten state-recognized tribes, that list is largely not actionable. This
is the clearest product-relevant gap surfaced by this research, and it is exactly
the kind of thing NativeForge must **not** turn into an eligibility claim.

**4. The agency was renamed, and search indexes are stale.** SC Commission for
Minority Affairs → **SC Commission for Community Advancement and Engagement**;
`cma.sc.gov` → `advance.sc.gov`. The old deep link
`cma.sc.gov/grants-state-tribes` 301-redirects to the new **homepage**, losing
the page. The equivalent path on the new domain does work. Any seeding must use
`advance.sc.gov`.

**5. A geography trap.** The **Catawba Nation Foundation** is funded by an
SC-based tribe but its verbatim scope is *"the Catawba Nation, Cleveland County
and the surrounding region, and Native American Tribal Nations and Native
organizations located within North Carolina."* Cleveland County is in North
Carolina. Eligible: the Catawba Nation itself, and NC Native organizations. **Not
SC Native organizations generally.** Listing it as an SC funder would be wrong.

---

## 2. SC central-source finding

**Answer: no.** There is no single statewide SC grants portal.

Evidence — the SC State Library's grants research guide names only:

| Named resource | URL given |
| --- | --- |
| SC Dept. of Education – Grants Office | `http://ed.sc.gov/finance/grants/` |
| South Carolina Humanities | `https://schumanities.org/` |
| South Carolina Arts Commission | `https://www.southcarolinaarts.com/` |
| SC Dept. of Parks, Recreation & Tourism | `https://www.scprt.com/grants` |
| SC Commission on Higher Education | `https://www.che.sc.gov/students-families-and-military/scholarships-and-grants-sc-residents` |

The guide contains **no** overarching statement about where SC state grant
opportunities are found, and **no** Native American or tribal funding source.

The nearest central artifact is procurement, not grants:

> SCBO is "a live database for goods, services, information technology and
> construction needs of state and local government." — `scbo.sc.gov`, run by the
> Division of Procurement Services

A third-party blog asserted a "South Carolina Grants Portal". **Rejected** — not
corroborated by any `.sc.gov` source. See §9.

---

## 3. SC agency source table

Schema per the gate. `monitoring_allowed: no`, `coverage_claimed: no`,
`freshness_claimed: no` for **every** row without exception.

### SC-001 — SC Business Opportunities (SCBO)

```text
source_id:                  sc-001-scbo
source_name:                South Carolina Business Opportunities (SCBO)
source_url:                 https://scbo.sc.gov/
source_owner:               SC Division of Procurement Services (MMO)
source_family:              sc_procurement_or_contracting_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none)
recognition_relevance:      unknown
native_sector_relevance:    economic_development, infrastructure, general_government
evidence_url:               https://scbo.sc.gov/
evidence_quote_or_summary:  "a live database for goods, services, information
                             technology and construction needs of state and local
                             government"; publishes bids/RFPs, NOT grants
robots_terms_status:        unresolved
access_method:              unknown (no API or data feed stated; page mentions an
                             "online edition" and "advertisement search")
confidence:                 high (exists, ownership and purpose verified)
recommended_status:         robots_terms_review_needed
notes:                      Closest thing SC has to a central feed, but it is
                             CONTRACTS not grants. Relevant to Native business /
                             economic development pursuit. Contract eligibility
                             rules differ from grant eligibility — do not merge.
source_is_real:             yes
source_is_grant_source:     no (procurement)
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-002 — SC Rural Infrastructure Authority

```text
source_id:                  sc-002-ria
source_name:                SC Rural Infrastructure Authority — State Grants
source_url:                 https://ria.sc.gov/grants/
source_owner:               SC Rural Infrastructure Authority
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none)
recognition_relevance:      unknown
native_sector_relevance:    infrastructure, economic_development
evidence_url:               https://ria.sc.gov/grants/
evidence_quote_or_summary:  State-funded infrastructure grant programs; financial
                             assistance in two competitive rounds annually
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         robots_terms_review_needed
notes:                      One of the clearest genuinely STATE-funded SC grant
                             programs found. Eligibility appears oriented to local
                             governments / political subdivisions — whether a
                             tribal entity qualifies is UNKNOWN and must not be
                             assumed.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-003 — SC Department of Education, Grants Office

```text
source_id:                  sc-003-scde
source_name:                SC Department of Education — Office of Grant Services
source_url:                 https://ed.sc.gov/finance/grants/
source_owner:               SC Department of Education
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (mixed — see notes)
recognition_relevance:      unknown
native_sector_relevance:    education
evidence_url:               https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
evidence_quote_or_summary:  Named by the SC State Library guide as "SC Dept. of
                             Education – Grants Office"; SCDE describes a page of
                             open opportunities "(federal, state, and privately
                             funded)"
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         robots_terms_review_needed
notes:                      SCDE MIXES federal, state and private opportunities on
                             one page. Lane assignment must be per-opportunity,
                             not per-source, or federal money will be miscounted
                             as SC state.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-004 — SC Arts Commission

```text
source_id:                  sc-004-arts
source_name:                SC Arts Commission — Grants
source_url:                 https://www.southcarolinaarts.com/community-development/grants/
source_owner:               SC Arts Commission
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none stated)
recognition_relevance:      unknown
native_sector_relevance:    culture, education
evidence_url:               https://www.southcarolinaarts.com/community-development/grants/
evidence_quote_or_summary:  Multiple named programs incl. Arts Project Support,
                             Public Art, Emerging Artist, District/School Arts
                             Support; "Folklife and Traditional Arts Projects"
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         triage_needed
notes:                      Highest-priority Native-relevance INVESTIGATION target
                             in the culture sector: a folklife/traditional-arts
                             programme is the kind that may name tribal or
                             traditional practitioners. Relevance NOT yet
                             evidenced — must read the guidelines.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-005 — SC Parks, Recreation & Tourism

```text
source_id:                  sc-005-scprt
source_name:                SC Dept. of Parks, Recreation & Tourism — Grants
source_url:                 https://www.scprt.com/grants
source_owner:               SC Dept. of Parks, Recreation & Tourism
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (unknown mix)
recognition_relevance:      unknown
native_sector_relevance:    culture, infrastructure, economic_development
evidence_url:               https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
evidence_quote_or_summary:  Named by the SC State Library guide with this URL
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 medium (URL from an authoritative index; page not
                             independently opened in this pass)
recommended_status:         triage_needed
notes:                      Heritage/tourism grants can carry cultural-site
                             relevance. Unverified.
source_is_real:             unknown (URL cited by a .sc.gov index, not opened)
source_is_grant_source:     yes (per index)
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-006 — South Carolina Humanities

```text
source_id:                  sc-006-schumanities
source_name:                South Carolina Humanities
source_url:                 https://schumanities.org/
source_owner:               South Carolina Humanities (private nonprofit affiliate)
source_family:              sc_foundation
funding_lane:               foundation
state:                      SC
federal_agency:             (NEH affiliate — see notes)
recognition_relevance:      unknown
native_sector_relevance:    culture, education
evidence_url:               https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
evidence_quote_or_summary:  Named by the SC State Library guide as an SC grant
                             resource
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 medium
recommended_status:         triage_needed
notes:                      NOT a state agency despite appearing in a state guide;
                             state humanities councils are typically NEH
                             affiliates, so lane may be foundation rather than
                             sc_state. Verify before seeding. Cultural/heritage
                             programming is a plausible Native-relevance target.
source_is_real:             unknown (not opened)
source_is_grant_source:     yes (per index)
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-007 — SC Housing (development / Housing Trust Fund)

```text
source_id:                  sc-007-schousing
source_name:                SC State Housing Finance & Development Authority
source_url:                 https://schousing.sc.gov/development
source_owner:               SC Housing
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (LIHTC is federal — see notes)
recognition_relevance:      unknown
native_sector_relevance:    housing
evidence_url:               https://schousing.sc.gov/development/south-carolina-housing-trust-fund-htf
evidence_quote_or_summary:  SC Housing Trust Fund described as state-funded;
                             also administers LIHTC, Housing Preservation
                             Initiative, Supportive Housing Program
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         robots_terms_review_needed
notes:                      DOMAIN MIGRATION: schousing.com → schousing.sc.gov.
                             Both resolve in search results; seed the .sc.gov
                             form. Housing Trust Fund appears genuinely state —
                             LIHTC is a federal tax credit administered by the
                             state, so per-opportunity lane assignment is
                             required.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-008 — SC Department of Environmental Services

```text
source_id:                  sc-008-scdes
source_name:                SC DES — Environmental Loans & Grants
source_url:                 https://des.sc.gov/business/businesses-and-communities-go-green/environmental-loans-grants-businesses-communities
source_owner:               SC Department of Environmental Services
source_family:              sc_agency_grant_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (EPA §319 is federal — see notes)
recognition_relevance:      unknown
native_sector_relevance:    environment, infrastructure
evidence_url:               https://des.sc.gov/business/businesses-and-communities-go-green/environmental-loans-grants-businesses-communities
evidence_quote_or_summary:  Named programs: 319 Nonpoint Source Pollution Grants,
                             Clean Up Assistance, Diesel Emissions Reduction
                             Grant, Drinking Water Fluoridation Grant
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         robots_terms_review_needed
notes:                      SCDES is a successor agency to DHEC (reorganised
                             c.2024). §319 is EPA Clean Water Act money passed
                             through the state — federal pass-through, see §7.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-009 — SC Emergency Management Division (Mitigation)

```text
source_id:                  sc-009-scemd
source_name:                SCEMD — Mitigation (HMGP)
source_url:                 https://www.scemd.org/recover/mitigation/
source_owner:               SC Emergency Management Division
source_family:              sc_agency_program_page
funding_lane:               sc_state (administering federal money — see §7)
state:                      SC
federal_agency:             FEMA (HMGP)
recognition_relevance:      unknown
native_sector_relevance:    infrastructure, public_safety
evidence_url:               https://www.scemd.org/recover/mitigation/
evidence_quote_or_summary:  SCEMD "administers Hazard Mitigation Grant Program
                             (HMGP) projects funded on a 75% federal, 25%
                             non-federal cost share basis"
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         triage_needed
notes:                      LANE PROBLEM. State agency page, federal money, state
                             administration. Note scemd.ORG not .sc.gov. Federally
                             recognized tribes are commonly direct FEMA
                             applicants, which may put the Catawba Nation on a
                             different path from SC state subrecipients — UNKNOWN,
                             needs verification.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-010 — SC Office of Resilience

```text
source_id:                  sc-010-scor
source_name:                SC Office of Resilience
source_url:                 https://scor.sc.gov/
source_owner:               SC Office of Resilience
source_family:              sc_agency_program_page
funding_lane:               sc_state (administering federal money — see §7)
state:                      SC
federal_agency:             HUD (CDBG-MIT), EPA (Solar for All)
recognition_relevance:      unknown
native_sector_relevance:    infrastructure, housing, environment
evidence_url:               https://scor.sc.gov/resilience-main/sc-disaster-relief-resilience-act
evidence_quote_or_summary:  SCOR "manages the Community Development Block Grant –
                             Mitigation, a Federal HUD grant"; also EPA Solar for
                             All
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         triage_needed
notes:                      Same federal pass-through lane problem as SCEMD.
                             Distinct from SCORF (below) — scor.sc.gov is the
                             office; scorf.sc.gov is a grant management system.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-011 — SCORF Grant Management System

```text
source_id:                  sc-011-scorf-gms
source_name:                SCORF Grant Management System
source_url:                 https://scorf.sc.gov/gms
source_owner:               SC (SCORF)
source_family:              sc_state_grant_portal
funding_lane:               sc_state
state:                      SC
federal_agency:             unknown
recognition_relevance:      unknown
native_sector_relevance:    unknown
evidence_url:               https://scorf.sc.gov/gms
evidence_quote_or_summary:  "Each political subdivision registered in South
                             Carolina is provided with a unique username"
robots_terms_status:        unresolved
access_method:              manual_operator_check (appears authenticated)
confidence:                 medium
recommended_status:         reject_not_grant_source
notes:                      REJECTED as a discovery source: it is an authenticated
                             grant MANAGEMENT system for registered political
                             subdivisions, not a public opportunity listing. A
                             tribal entity is likely not a "political
                             subdivision" — UNKNOWN. Do not attempt access.
source_is_real:             yes
source_is_grant_source:     no (management system, not a listing)
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-012 — SC Commission for Community Advancement and Engagement

```text
source_id:                  sc-012-advance
source_name:                SC Commission for Community Advancement and Engagement
                             — Native American Affairs
source_url:                 https://advance.sc.gov/community-engagement/native-american-affairs
source_owner:               SC Commission for Community Advancement and Engagement
source_family:              sc_agency_program_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none)
recognition_relevance:      state_recognized_relevant, federally_recognized_relevant,
                             native_community_relevant
native_sector_relevance:    general_government, culture
evidence_url:               https://advance.sc.gov/community-engagement/native-american-affairs
evidence_quote_or_summary:  Division carries out duties under SC law including
                             "state recognition of Native American entities";
                             maintains an Advisory Committee; links to
                             "Grants for State Tribes"
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high
recommended_status:         triage_needed
notes:                      THE most important SC Native routing source, and NOT a
                             grant source itself. Formerly SC Commission for
                             Minority Affairs; renamed c. May 2025; cma.sc.gov →
                             advance.sc.gov. The homepage has no grants section.
source_is_real:             yes
source_is_grant_source:     no (recognition/engagement; links out to federal
                             programs)
source_is_native_relevant:  YES — explicit Native American Affairs mandate
eligibility_proven:         no
```

### SC-013 — "Grants for State Tribes" listing

```text
source_id:                  sc-013-advance-grants-state-tribes
source_name:                Grants for State Tribes (SC Commission for Community
                             Advancement and Engagement)
source_url:                 https://advance.sc.gov/grants-state-tribes
source_owner:               SC Commission for Community Advancement and Engagement
source_family:              sc_agency_program_page
funding_lane:               federal_sc_relevant  ← NOT sc_state
state:                      SC (host page only)
federal_agency:             ED, VA, HHS/IHS, HUD, DOI, DOL (multiple)
recognition_relevance:      federally_recognized_relevant (predominantly);
                             state_recognized_relevant UNKNOWN
native_sector_relevance:    education, housing, health, workforce, culture,
                             environment, economic_development
evidence_url:               https://advance.sc.gov/grants-state-tribes
evidence_quote_or_summary:  12 programs listed, ALL FEDERAL. NACTEP eligibility
                             quoted on the page as "Federally recognized Indian
                             tribes, tribal organizations, Alaska Native entities,
                             and eligible BIE-funded schools". Direct Home Loans
                             limited to homes "on Federal Trust land".
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 high (page opened and contents enumerated)
recommended_status:         triage_needed
notes:                      CRITICAL. Titled "Grants for State Tribes" but every
                             program is federal and the ones with stated
                             eligibility require FEDERAL recognition. The page
                             never states whether any program is open to
                             state-recognized tribes. For SC's ten
                             state-recognized tribes this list is largely NOT
                             actionable. Useful as a federal-program index; must
                             NOT be treated as evidence that SC state-recognized
                             tribes are eligible for anything on it.
                             Stale-link hazard: cma.sc.gov/grants-state-tribes
                             301s to advance.sc.gov root, losing the page.
source_is_real:             yes
source_is_grant_source:     yes (an index of federal programs)
source_is_native_relevant:  YES — explicitly Native-targeted programs
eligibility_proven:         no — and mostly evidence AGAINST eligibility for
                             state-recognized tribes
```

### SC-014 — SC Commission on Higher Education

```text
source_id:                  sc-014-che
source_name:                SC Commission on Higher Education — Scholarships & Grants
source_url:                 https://www.che.sc.gov/students-families-and-military/scholarships-and-grants-sc-residents
source_owner:               SC Commission on Higher Education
source_family:              sc_agency_program_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none stated)
recognition_relevance:      unknown
native_sector_relevance:    education
evidence_url:               https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
evidence_quote_or_summary:  Named by the SC State Library guide; described as
                             scholarships and grants for SC residents
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 medium
recommended_status:         reject_not_grant_source
notes:                      REJECTED for the organizational discovery engine:
                             these are student/individual awards, not
                             organizational grants. NativeForge serves tribal
                             organizations and grant offices. Could be
                             re-scoped later if individual scholarships become a
                             product surface.
source_is_real:             unknown (not opened)
source_is_grant_source:     yes, but for individuals
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-015 — SC Dept. of Archives and History (recognition reference)

```text
source_id:                  sc-015-scdah
source_name:                SCDAH — Federal and State Recognized Native American
                             Indian Tribes
source_url:                 https://scdah.sc.gov/historic-preservation/resources/native-american-heritage/federal-and-state-recognized-native
source_owner:               SC Department of Archives and History
source_family:              sc_agency_program_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none)
recognition_relevance:      state_recognized_relevant, federally_recognized_relevant
native_sector_relevance:    culture
evidence_url:               https://scdah.sc.gov/historic-preservation/resources/native-american-heritage/federal-and-state-recognized-native
evidence_quote_or_summary:  Page title indicates a listing distinguishing federal
                             and state recognized tribes
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 medium (URL from search result; not opened)
recommended_status:         reject_not_grant_source
notes:                      Not a funding source. Valuable as a SECOND
                             independent state reference for the recognition
                             split, useful for cross-checking advance.sc.gov.
                             SCDAH also administers historic-preservation
                             programmes worth a separate look.
source_is_real:             unknown (not opened)
source_is_grant_source:     no
source_is_native_relevant:  yes (recognition reference)
eligibility_proven:         no
```

### SC-016 — SC State Library grants research guide

```text
source_id:                  sc-016-statelibrary-guide
source_name:                SC State Library — Grants Research Assistance
source_url:                 https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
source_owner:               SC State Library
source_family:              sc_agency_program_page
funding_lane:               sc_state
state:                      SC
federal_agency:             (none)
recognition_relevance:      unknown
native_sector_relevance:    unknown
evidence_url:               https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources
evidence_quote_or_summary:  Enumerates five SC agency grant resources; contains NO
                             central-portal statement and NO Native/tribal source
robots_terms_status:        unresolved
access_method:              manual_operator_check
confidence:                 high (opened and enumerated)
recommended_status:         reject_not_grant_source
notes:                      Not a funding source — it is the AUTHORITY for finding
                             (a) that no central SC portal exists and (b) which
                             agencies the state itself points at. Its silence on
                             Native funding is itself a finding.
source_is_real:             yes
source_is_grant_source:     no (research aid)
source_is_native_relevant:  no
eligibility_proven:         no
```

---

## 4. SC regional / foundation source table

### SC-017 — Central Carolina Community Foundation

```text
source_id:                  sc-017-cccf
source_name:                Central Carolina Community Foundation
source_url:                 https://www.yourfoundation.org/grants-scholarships/grant-opportunities/
source_owner:               Central Carolina Community Foundation
source_family:              sc_community_foundation
funding_lane:               foundation
state:                      SC
federal_agency:             (none)
recognition_relevance:      unknown
native_sector_relevance:    unknown
evidence_url:               https://www.yourfoundation.org/grants-scholarships/grant-opportunities/
evidence_quote_or_summary:  Serves Calhoun, Clarendon, Fairfield, Kershaw, Lee,
                             Lexington, Newberry, Orangeburg, Richland, Saluda and
                             Sumter Counties. Community Impact Grants across four
                             focus areas. Applications via a grant portal.
robots_terms_status:        unresolved
access_method:              manual_operator_check (portal-gated applications)
confidence:                 high
recommended_status:         triage_needed
notes:                      NO evidence of Native-specific eligibility. Its
                             service area is a research LEAD only — whether any
                             SC state-recognized entity sits in these counties is
                             UNKNOWN here and must be verified, not assumed.
                             Funding SC generally is NOT Native relevance.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-018 — Coastal Community Foundation of South Carolina

```text
source_id:                  sc-018-ccf
source_name:                Coastal Community Foundation of South Carolina
source_url:                 https://coastalcommunityfoundation.org/competitive-grants/open-grants/
source_owner:               Coastal Community Foundation
source_family:              sc_community_foundation
funding_lane:               foundation
state:                      SC
federal_agency:             (none)
recognition_relevance:      unknown
native_sector_relevance:    unknown
evidence_url:               https://coastalcommunityfoundation.org/competitive-grants/open-grants/
evidence_quote_or_summary:  "officially serves nine coastal counties - Beaufort,
                             Berkeley, Charleston, Colleton, Dorchester,
                             Georgetown, Hampton, Horry, and Jasper"; two
                             competitive cycles per year, applications due January
                             and June
robots_terms_status:        unresolved
access_method:              manual_operator_check (grantee portal)
confidence:                 high
recommended_status:         triage_needed
notes:                      Same caution as SC-017: no Native-specific eligibility
                             evidence. Also hosts grantmaking for the Jewish
                             Endowment Foundation of SC and the Saul Alexander
                             Foundation — a portal serving multiple funders, which
                             affects how a source record should be modelled.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  unknown
eligibility_proven:         no
```

### SC-019 — Catawba Nation Foundation

```text
source_id:                  sc-019-catawba-foundation
source_name:                Catawba Nation Foundation
source_url:                 https://catawbanationfoundation.org/
source_owner:               Catawba Nation Foundation
source_family:              native_intermediary
funding_lane:               foundation
state:                      NC  ← not SC, despite an SC-based funder
federal_agency:             (none)
recognition_relevance:      federally_recognized_relevant, native_community_relevant
native_sector_relevance:    culture, general_government, unknown
evidence_url:               https://catawbanationfoundation.org/
evidence_quote_or_summary:  VERBATIM: "We fund projects for the Catawba Nation,
                             Cleveland County and the surrounding region, and
                             Native American Tribal Nations and Native
                             organizations located within North Carolina."
robots_terms_status:        unresolved
access_method:              manual_operator_check
confidence:                 high (verbatim scope statement)
recommended_status:         triage_needed
notes:                      GEOGRAPHY TRAP. Funded by an SC-based tribe (per
                             reporting, from Catawba Two Kings Casino proceeds
                             under a 2021 compact with North Carolina), but the
                             stated grantmaking geography is NORTH CAROLINA.
                             Eligible: the Catawba Nation itself, and NC Native
                             organizations. NOT SC Native organizations generally.
                             Listing this as an SC funder would be a fabrication
                             of eligibility.
source_is_real:             yes
source_is_grant_source:     yes
source_is_native_relevant:  YES — explicitly Native-targeted
eligibility_proven:         no for SC organizations; the scope statement is
                             evidence AGAINST general SC eligibility
```

### SC-020 / SC-021 — local-government aggregators

```text
source_id:                  sc-020-masc / sc-021-sccounties
source_name:                Municipal Association of SC — Grants /
                             SC Association of Counties — Grants
source_url:                 https://www.masc.sc/research-tools/grants
                             https://www.sccounties.org/grants
source_owner:               MASC / SCAC (membership associations, not agencies)
source_family:              sc_regional_council
funding_lane:               unknown
state:                      SC
recognition_relevance:      unknown
native_sector_relevance:    infrastructure, general_government
evidence_url:               (both URLs appeared in search results)
evidence_quote_or_summary:  Grant listing pages maintained for member
                             municipalities / counties
robots_terms_status:        unresolved
access_method:              html_page_scheduled_check
confidence:                 medium (URLs seen, pages not opened)
recommended_status:         triage_needed
notes:                      SECONDARY aggregators oriented to local governments,
                             not tribes. Useful as a discovery LEAD for finding
                             primary SC sources; should not become monitored
                             sources themselves without deciding whether
                             aggregators belong in the registry at all.
source_is_real:             unknown (not opened)
source_is_grant_source:     aggregator
source_is_native_relevant:  unknown
eligibility_proven:         no
```

---

## 5. Federal-SC-relevant source notes

**Kept federal. Nothing here becomes an SC state source.**

The only substantive federal-SC finding this pass is **SC-013**, the
`advance.sc.gov/grants-state-tribes` index. It is hosted on an SC state domain,
which makes it exactly the kind of source that would be mis-lane-assigned:
`funding_lane: federal_sc_relevant`, host state SC, twelve federal programmes
across at least six federal departments.

The Gate 77 federal lane already covers grants.gov, the Federal Register and
SAM.gov. This research adds no new canonical federal entry point and should not
duplicate them.

**The federal pass-through problem** — the sharpest unresolved modelling
question from this research. Three SC agencies administer federal money:

| Source | Federal programme | Federal funder |
| --- | --- | --- |
| SCEMD (SC-009) | HMGP, 75/25 cost share | FEMA |
| SCOR (SC-010) | CDBG-MIT; Solar for All | HUD; EPA |
| SCDES (SC-008) | §319 Nonpoint Source | EPA |
| SC Housing (SC-007) | LIHTC | Treasury/IRS |
| SCDE (SC-003) | mixed federal/state/private on one page | various |

The **source** is an SC state agency page. The **money** is federal. Gate 78's
contract assigns lane by ownership, which puts these in `sc_state` — but the
opportunity a customer sees is federal money with federal strings.

This matters for recognition routing: federally recognized tribes are frequently
*direct* applicants to federal programmes, bypassing the state, while
state-recognized tribes are not eligible for many federal tribal programmes at
all and may only reach the money as a state subrecipient — if at all. Getting
the lane wrong here would misroute the highest-value opportunities for both
groups in opposite directions.

**Recommendation:** lane must be assigned **per opportunity**, not inherited from
the source, and a `federal_pass_through` flag should be added. See §11.

---

## 6. Native relevance notes

Evidence-backed Native relevance found in exactly **three** sources:

| Source | Basis |
| --- | --- |
| SC-012 advance.sc.gov Native American Affairs | explicit statutory Native American Affairs mandate incl. state recognition |
| SC-013 Grants for State Tribes | twelve explicitly Native-targeted federal programmes |
| SC-019 Catawba Nation Foundation | verbatim scope naming Native Tribal Nations and Native organizations |

**Everything else is `unknown`.** No SC state agency grant page examined in this
pass carried Native-specific eligibility language, and the SC State Library's
grants guide names no Native funding source at all.

Two named entities are worth flagging as leads rather than findings:

- The **American Indian Chamber of Commerce** appears among SC's recognised
  Special Interest Organizations (advance.sc.gov) — relevant to
  `native_business_relevant` routing, though whether it grants funds is UNKNOWN.
- The **Pine Hill Indian Community Development Initiative** likewise appears as a
  recognised Special Interest Organization; funding role UNKNOWN.

Neither was researched further and neither should be seeded as a funder without
evidence.

**A caution that must survive into code.** A foundation that funds South Carolina
is not thereby Native-relevant. A programme in a Native-relevant *sector*
(housing, health, culture) is not thereby Native-relevant. Relevance requires the
source or opportunity to say something about Native applicants or communities.
Gate 78's contract already enforces this; this research supplies no reason to
relax it.

---

## 7. State-recognized vs federally recognized routing implications

**The single most consequential finding of this research.**

South Carolina's recognition landscape, per `advance.sc.gov`:

```text
Federally recognized tribes:            1   (Catawba Nation)
State recognized tribes:               10
Indian Groups:                          3
Special Interest Organizations:         3
```

*(A secondary source said nine state-recognized tribes; the agency page
enumerates ten. The agency page is treated as authoritative and the discrepancy
is recorded rather than resolved.)*

The state's own definition, quoted from the page:

> "Federally Recognized Tribe: an American Indian or Alaska Native tribal entity
> that is recognized as having a government-to-government relationship with the
> United States."

State recognition confers no such relationship. Reporting on SC recognition
describes state recognition as acknowledging cultural and historical presence
without the sovereign rights federal recognition carries.

### Why this breaks naive routing

The `advance.sc.gov/grants-state-tribes` page is the state's own resource *for
state tribes*, and:

- all twelve programmes on it are **federal**;
- where eligibility is stated it commonly requires **federal recognition**
  (NACTEP: *"Federally recognized Indian tribes, tribal organizations, Alaska
  Native entities, and eligible BIE-funded schools"*);
- one is limited to homes **"on Federal Trust land"**;
- the page **never states** whether a state-recognized tribe qualifies for any of
  them.

So the practical position for SC:

| Applicant | Federal Native programmes | SC state grant programmes |
| --- | --- | --- |
| Catawba Nation (federally recognized) | frequently eligible | UNKNOWN |
| 10 state-recognized tribes | frequently **not** eligible | UNKNOWN |
| Native nonprofits | depends on programme | UNKNOWN |
| Native businesses | depends on programme | UNKNOWN |

Every "UNKNOWN" above is genuinely unknown from this research. No SC state
programme examined stated tribal eligibility either way.

### Consequences for the product

1. **Collapsing the two tiers would produce confident wrong answers in both
   directions** — telling ten state-recognized tribes they can apply for
   federally-recognized-only programmes, and potentially hiding state programmes
   from them. Gate 78's refusal to infer between tiers is vindicated.
2. **The most valuable honest thing NativeForge could tell an SC
   state-recognized tribe is which programmes exclude them and why.** That is a
   negative result, and it is more useful than a padded list.
3. **`eligibility_proven` is `no` everywhere in this pack.** Nothing here
   licenses an eligibility claim.

---

## 8. Robots / terms / access review queue

**No `robots.txt` was evaluated for any source. Nothing is cleared. Nothing is
monitorable.** Access in this research was ordinary reading of public pages.

Queue, ordered by likely value:

| Priority | Source | Why | Access shape |
| --- | --- | --- | --- |
| 1 | SC-013 advance.sc.gov/grants-state-tribes | highest Native relevance | static page |
| 2 | SC-012 advance.sc.gov Native American Affairs | recognition routing | static page |
| 3 | SC-002 ria.sc.gov/grants | clearest state-funded programme | static page |
| 4 | SC-003 ed.sc.gov/finance/grants | large mixed listing | listing page |
| 5 | SC-007 schousing.sc.gov/development | housing sector | static + PDF |
| 6 | SC-004 southcarolinaarts.com grants | culture sector lead | static page |
| 7 | SC-008 des.sc.gov env. loans & grants | environment sector | static page |
| 8 | SC-001 scbo.sc.gov | procurement; no API stated | search UI |
| 9 | SC-009 scemd.org mitigation | .org domain, federal pass-through | static page |
| 10 | SC-010 scor.sc.gov | federal pass-through | static page |
| 11–14 | SC-005, SC-006, SC-017, SC-018 | unopened / portal-gated | mixed |

**Do not queue:** SC-011 SCORF GMS (authenticated system — do not attempt
access), SC-017/SC-018 application portals (grantee-authenticated; only the
public listing pages are candidates).

Two specific questions for review:

- **SCBO** states no API or data feed. Whether its "advertisement search" may be
  queried programmatically is unresolved and must be asked, not assumed —
  `scbo@mmo.sc.gov` is the published contact.
- **scemd.org** is a `.org`, not `.sc.gov`. Confirm it is the official SCEMD
  domain before seeding.

---

## 9. Sources rejected and why

| Source | Reason |
| --- | --- |
| "South Carolina Grants Portal" (asserted by a third-party blog) | **reject** — no `.sc.gov` corroboration; the SC State Library guide names no central portal. Treated as a third-party claim, not a source. |
| grantwatch.com, instrumentl.com, thegrantportal.com, grantsights.com, grantexec.com, insidephilanthropy.com | **reject_not_grant_source** — commercial aggregators/lead-gen. Not primary sources; provenance unverifiable; terms likely prohibit automated use. |
| bidedgehq.com, contractradar.io | **reject_not_grant_source** — commercial resellers of SCBO data. Use SCBO directly. |
| fconline.foundationcenter.org (Candid), grantforward.com | **reject_not_grant_source** — subscription databases. |
| che.sc.gov (SC-014) | **reject_not_grant_source** for this product — individual scholarships, not organizational grants. |
| scorf.sc.gov/gms (SC-011) | **reject_not_grant_source** — authenticated management system for political subdivisions, not an opportunity listing. |
| guides.statelibrary.sc.gov (SC-016) | **reject_not_grant_source** — research aid. Retained as the *authority* for the no-central-portal finding. |
| scdah.sc.gov (SC-015) | **reject_not_grant_source** — recognition reference. Retained for cross-checking. |
| cma.sc.gov/* | **reject** — dead domain; 301s to advance.sc.gov root. Any seed using it would rot. |
| Wikipedia, news outlets (Post & Courier, SC Daily Gazette, hoodline, pmg-sc, shelbyindependent) | **not sources** — used only as corroborating context for the Catawba Foundation's funding origin and the recognition landscape. Never as eligibility evidence. |

---

## 10. UNKNOWNs

Stated plainly, because each is a place a later gate could fabricate.

1. **Whether any SC state grant programme is open to tribal entities.** Not one
   page examined said so either way. This is the biggest gap.
2. **Whether SC state-recognized tribes qualify for any programme on
   `advance.sc.gov/grants-state-tribes`.** The page is silent; several
   programmes' stated eligibility suggests not.
3. **Which counties SC's state-recognized entities are located in**, and
   therefore whether the two community foundations' service areas overlap them.
   Not verified here and deliberately not guessed.
4. **Whether a tribal entity counts as a "political subdivision"** for RIA or
   SCORF eligibility. Likely not, but unverified.
5. **Whether the Catawba Nation applies to FEMA/HUD directly** rather than as an
   SC subrecipient.
6. **Whether SC-005 (SCPRT), SC-006 (SC Humanities), SC-015 (SCDAH), SC-020
   (MASC) and SC-021 (SCAC) pages exist as cited** — URLs came from an
   authoritative index or search results but were not opened.
7. **Whether SC Humanities is a state agency or an NEH affiliate**, which decides
   its lane.
8. **Nine or ten state-recognized tribes** — the agency page says ten, a
   secondary source said nine.
9. **Whether SCBO permits programmatic access.**
10. **Whether SC Commerce publishes any grant or incentive opportunity page** —
    searched, nothing confirmed.
11. **Whether aggregators (MASC, SCAC) belong in a source registry at all**, or
    only as human research leads.

---

## 11. Recommended Gate 79/80 code actions

Ordered. The first two are corrections that this research makes necessary; the
rest are build steps.

**1. Add a `federal_pass_through` flag and assign lane per opportunity, not per
source.** Five SC agency sources carry federal money (§5). Gate 78 assigns lane
by source ownership, which would file FEMA HMGP as `sc_state`. The source is
state-owned; the opportunity is federal. Without this the state/federal counts —
the thing Gate 78 worked hardest to protect — go wrong on the highest-value
opportunities.

**2. Model a source whose eligibility evidence argues *against* an applicant
type.** `advance.sc.gov/grants-state-tribes` is the case: a Native-targeted index
whose stated eligibility excludes most SC state-recognized tribes. Today the
contract can record `unknown`; it cannot record *"evidence suggests this
applicant type is excluded"*, which is more useful to a grant office than
silence. Suggest an `exclusion_evidence` concept alongside eligibility evidence —
still never asserting `not_eligible` without an explicit statement.

**3. Seed SC-001 through SC-018 as `discovered` / `triage_needed` only.** URLs
now exist, so the Gate 78 invariant `seed_claims_a_url_without_research` can be
relaxed to permit *researched* URLs — but only with the citation recorded.
Recommend a `citation_url` field required whenever `source_url` is non-null, so a
URL can never appear again without provenance. Keep
`monitoring_allowed: False` and `robots_terms_status: unreviewed` throughout.

**4. Do not build the scheduler (Gate 80) yet.** Zero sources are terms-cleared.
The registry will correctly refuse to monitor all of them, so a scheduler would
have nothing to schedule. Robots/terms review (§8) is the true next gate, and it
is a legal/policy judgement, not code.

**5. Record the recognition landscape as data, not prose.** 1 federally
recognized, 10 state-recognized, 3 groups, 3 special-interest organizations, from
`advance.sc.gov`, cross-checkable against SCDAH. This is the routing table the SC
lane needs, and it is the one thing in this research that is settled fact rather
than lead.

**6. Leave the Catawba Nation Foundation out of any SC coverage count.** Its
verbatim geography is North Carolina. Seed it, if at all, with `state: NC` and a
note that the Catawba Nation itself is an eligible SC-resident applicant.

---

## Claim boundaries for this document

```text
monitoring_allowed:      no   (every source)
coverage_claimed:        no
freshness_claimed:       no
eligibility_proven:      no   (every source)
live SC coverage:        NONE
65% improvement:         NOT CLAIMED
sources scraped:         none
robots.txt evaluated:    none
```

## Sources

- [SC Recognized Native American Indian Entities](https://advance.sc.gov/south-carolinas-recognized-native-american-indian-entities)
- [SC Native American Affairs](https://advance.sc.gov/community-engagement/native-american-affairs)
- [Grants for State Tribes](https://advance.sc.gov/grants-state-tribes)
- [SC Commission for Community Advancement and Engagement](https://advance.sc.gov/)
- [SC State Library — SC grant resources](https://guides.statelibrary.sc.gov/grants-research-assistance/scgrantresources)
- [SCBO](https://scbo.sc.gov/)
- [SC Rural Infrastructure Authority — State Grants](https://ria.sc.gov/grants/)
- [SC Dept. of Education — Grants](https://ed.sc.gov/finance/grants/)
- [SC Arts Commission — Grants](https://www.southcarolinaarts.com/community-development/grants/)
- [SC PRT — Grants](https://www.scprt.com/grants)
- [SC Humanities](https://schumanities.org/)
- [SC Housing — Housing Trust Fund](https://schousing.sc.gov/development/south-carolina-housing-trust-fund-htf)
- [SC DES — Environmental Loans & Grants](https://des.sc.gov/business/businesses-and-communities-go-green/environmental-loans-grants-businesses-communities)
- [SCEMD — Mitigation](https://www.scemd.org/recover/mitigation/)
- [SC Office of Resilience](https://scor.sc.gov/resilience-main/sc-disaster-relief-resilience-act)
- [SCORF Grant Management System](https://scorf.sc.gov/gms)
- [SC Commission on Higher Education](https://www.che.sc.gov/students-families-and-military/scholarships-and-grants-sc-residents)
- [SCDAH — Federal and State Recognized Native American Indian Tribes](https://scdah.sc.gov/historic-preservation/resources/native-american-heritage/federal-and-state-recognized-native)
- [Central Carolina Community Foundation — Grant Opportunities](https://www.yourfoundation.org/grants-scholarships/grant-opportunities/)
- [Coastal Community Foundation — Open Grants](https://coastalcommunityfoundation.org/competitive-grants/open-grants/)
- [Catawba Nation Foundation](https://catawbanationfoundation.org/)
- [Municipal Association of SC — Grants](https://www.masc.sc/research-tools/grants)
- [SC Association of Counties — Grants](https://www.sccounties.org/grants)
