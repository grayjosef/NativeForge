# NativeForge funding source universe

Research date: 2026-08-26. This is a source-discovery and monitoring dossier, not a legal determination of applicant eligibility or cost allowability. Eligibility and allowable-cost conclusions must be re-checked against each live NOFO and award terms.

## 1. Executive summary

NativeForge should use a layered registry rather than treating Grants.gov as the whole market:

1. **System-of-record layer:** Grants.gov opportunities/API, SAM.gov Assistance Listings, Federal Register, and USAspending award data.
2. **Native discovery layer:** the BIA/White House Council on Native American Affairs (WHCNAA) Access to Capital Clearinghouse, Indian Affairs grant pages, agency tribal-affairs pages, Dear Tribal Leader Letters (DTLLs), and agency newsletters.
3. **Program-owner layer:** agency program and NOFO pages, which often contain better eligibility, deadline, webinar, amendment, and allowable-cost detail than aggregators.
4. **Pass-through layer:** state administering agencies selected only after matching a customer to operating state(s), recognition status, and entity type.
5. **Research layer:** NIH Guide/RePORTER, NSF funding/search and awards, NIFA, CDC, NOAA, USGS and NASA solicitations.
6. **Selective philanthropy layer:** Native-led or materially Native-focused funders, handled manually until their terms and page structures are reviewed.

The official Grants.gov API supports unauthenticated opportunity search and fetch endpoints; its terms permit searching, displaying, analyzing, and retrieving data but require attribution and prohibit false representation ([API guide](https://www.grants.gov/api/api-guide), [API terms](https://www.grants.gov/api/terms-conditions)). SAM.gov Assistance Listings is the official catalog of federal assistance program descriptions, but a listing is not itself a currently open competition ([SAM.gov](https://sam.gov/content/assistance-listings)). The WHCNAA/BIA clearinghouse is a searchable Native-specific aggregation of grants, loans and tax credits and therefore deserves Tier 1 status, but NativeForge should reconcile records back to the issuing agency and Grants.gov ([Access to Capital Clearinghouse](https://www.bia.gov/atc)).

## 2. Federal Native funding source map

| Layer | What it contributes | NativeForge treatment |
|---|---|---|
| Grants.gov | Forecasted and posted discretionary opportunities | Tier 1 API ingest; full-text and structured eligibility filters |
| SAM.gov Assistance Listings | Stable program catalog/assistance numbers | Tier 1 catalog normalization; never infer an open deadline |
| Federal Register | Rules, funding notices, consultations and program changes | Tier 1 API/feed monitor; link notices to programs |
| USAspending | Historical awards, recipients and assistance numbers | Tier 2 API; recurring-program and award-pattern intelligence |
| WHCNAA/BIA clearinghouse | Native-specific federal discovery | Tier 1 search/page monitor; deduplicate to primary record |
| Agency funding pages | Amendments, webinars, program guidance, owner-specific notices | Tier 1/2 HTML/PDF monitoring |
| Tribal affairs / DTLL pages | Funding announcements and consultations missed by keyword searches | Tier 2 page/email monitoring |
| State administering agencies | Formula and competitive pass-through opportunities | Instantiate only for customer state(s) |
| Research portals | Calls, notices, awards and institute-specific solicitations | Tier 1/2 API, RSS and search monitors |

## 3. Federal agency/subagency monitoring targets

The machine-readable table contains the operational registry. The minimum department coverage is:

- **Interior:** Indian Affairs/BIA and BIE; Office of Indian Economic Development; Office of Indian Energy and Economic Development; NPS Tribal Heritage and NAGPRA grants; FWS Tribal Wildlife Grants; Reclamation Native American Affairs; USGS Tribal Relations and cooperative science notices. Indian Affairs identifies NABDI, National Tribal Broadband, Living Languages, EMDP, TEDC, Indian Business Incubators and Tribal Tourism as grant programs ([Indian Affairs grants](https://www.bia.gov/topic/grants)).
- **HHS:** IHS, ACF/Administration for Native Americans, SAMHSA, CDC, HRSA, CMS, ACL and NIH. ANA’s Social and Economic Development Strategies (SEDS) program is a recurring capacity-building channel; eligibility must be read from the current NOFO ([ANA funding opportunities](https://www.acf.hhs.gov/ana/grants/funding-opportunities)).
- **USDA:** Rural Development (Community Facilities, ReConnect, Distance Learning and Telemedicine), NIFA, NRCS, FSA, Forest Service and FNS. ReConnect applicant and eligible-cost rules are round-specific ([ReConnect](https://www.rd.usda.gov/programs-services/telecommunications-programs/reconnect-program)).
- **HUD:** Office of Native American Programs (IHBG, ICDBG and related notices), homelessness programs and relevant CDBG channels. IHBG is formula funding for eligible Indian tribes and tribally designated housing entities; state-recognized entities should not be assumed eligible ([IHBG](https://www.hud.gov/hud-partners/codetalk-ihbg)).
- **Commerce:** EDA, NTIA, NOAA, NIST and MBDA. NTIA programs often flow through states or named eligible entities; NativeForge must preserve applicant-type and subrecipient distinctions ([Internet for All funding programs](https://www.internetforall.gov/funding-programs)).
- **Energy:** Office of Indian Energy, Grid Deployment Office, EERE, Weatherization and state energy channels. Office of Indian Energy maintains current opportunities specific to tribal energy deployment and planning ([DOE Indian Energy funding](https://www.energy.gov/indianenergy/funding)).
- **EPA:** American Indian Environmental Office, GAP, Tribal Environmental Exchange Network, Brownfields, water infrastructure, environmental justice, Section 319 and EPA regional tribal pages. GAP supports tribal environmental program capacity; recognition and eligible-entity rules are statutory/program-specific ([EPA GAP](https://www.epa.gov/tribal/indian-environmental-general-assistance-program-gap)).
- **Justice:** OJP/BJA, OVW, COPS, OJJDP and OVC, including Coordinated Tribal Assistance Solicitation (CTAS) ([DOJ Tribal Justice and Safety](https://www.justice.gov/tribal/open-solicitations)).
- **DHS:** FEMA tribal and preparedness grants, hazard mitigation, public assistance and cybersecurity programs. Federally recognized tribes may apply directly for certain FEMA programs, while other entities may need a state pass-through ([FEMA tribal affairs](https://www.fema.gov/about/organization/tribes)).
- **Transportation:** FHWA Tribal Transportation Program, FTA Tribal Transit, RAISE and Safe Streets and Roads for All. Eligibility varies by program and round ([DOT grants](https://www.transportation.gov/grants)).
- **Education:** Office of Indian Education, Native Hawaiian/Alaska Native programs, TCU and BIE-school channels, CTE and higher-education programs ([Office of Indian Education](https://oese.ed.gov/offices/office-of-indian-education/)).
- **Labor:** Division of Indian and Native American Programs and broader workforce/apprenticeship programs ([DOL DINAP](https://www.dol.gov/agencies/eta/dinap)).
- **SBA:** Office of Native American Affairs and technical-assistance ecosystems. 8(a) is a contracting/business-development program, not a customer grant and should not be represented as funding for software ([SBA Native American-owned businesses](https://www.sba.gov/business-guide/grow-your-business/native-american-owned-businesses)).
- **Independent/research:** NSF, NASA, Denali Commission, Appalachian Regional Commission where geographically applicable, AmeriCorps, Institute of Museum and Library Services, National Endowment for the Humanities, and FCC programs.

## 4. Recurring Native/tribal programs

High-value recurring families include ANA SEDS and language programs; BIA NABDI, EMDP, TEDC, Tribal Tourism, Living Languages and National Tribal Broadband; HUD IHBG and ICDBG; EPA GAP and Tribal Wildlife/Section 319-related channels; DOJ CTAS and OVW tribal programs; FEMA Tribal Homeland Security Grant Program; FTA Tribal Transit; DOL Indian and Native American Programs; NPS Tribal Heritage and NAGPRA grants; FWS Tribal Wildlife Grants; DOE Office of Indian Energy solicitations; USDA NIFA Tribal Colleges programs; and IHS discretionary cooperative agreements. “Recurring” means the program/channel has repeated historically, not that a competition or identical eligibility exists every year.

Recognition warning: programs grounded in a government-to-government relationship frequently restrict direct eligibility to federally recognized tribes or their authorized organizations. State recognition alone must never be mapped to “tribe eligible” unless the current authority/NOFO expressly says so. Native nonprofits, Native-serving nonprofits, TCUs/BIE schools, businesses and consortia require separate flags.

## 5. Funding streams likely to pay for software/capability development

| Stream | Plausible NativeForge-supported use | Conservative allowability | Evidence / caveat |
|---|---|---|---|
| ANA SEDS | organizational systems, planning, data/evaluation tied to project outcomes | Sometimes allowable | Project-specific, reasonable and allocable costs only; verify NOFO and federal cost principles ([ANA opportunities](https://www.acf.hhs.gov/ana/grants/funding-opportunities)) |
| EPA GAP | environmental program capacity, data/reporting systems | Likely allowable when integral | GAP is capacity funding; equipment/services still require work-plan and award approval ([EPA GAP](https://www.epa.gov/tribal/indian-environmental-general-assistance-program-gap)) |
| EPA Environmental Information Exchange Network | environmental data exchange and interoperable systems | Clearly/likely allowable for scoped data work | Program is specifically oriented to environmental information exchange ([Exchange Network grants](https://www.epa.gov/exchangenetwork/exchange-network-grant-program)) |
| DOJ CTAS purpose areas | case management, records, court/public-safety technology | Sometimes allowable | Purpose-area and budget-specific; never generalize across CTAS ([DOJ solicitations](https://www.justice.gov/tribal/open-solicitations)) |
| FEMA THSGP | preparedness planning, cybersecurity and approved management/admin | Sometimes allowable | Must fit investment justification and preparedness core capabilities ([FEMA THSGP](https://www.fema.gov/grants/preparedness/tribal-homeland-security)) |
| State and Local Cybersecurity Grant Program | cybersecurity planning, services, tools | Likely allowable for approved cyber plan/project | Usually state-administered; direct/subrecipient route varies ([CISA SLCGP](https://www.cisa.gov/cybergrants/slcgp)) |
| NTIA Digital Equity/BEAD subgrants | digital inclusion systems, workforce and approved program administration | Sometimes allowable | State plan and subgrant rules control; generic grant software is not automatically eligible ([Internet for All](https://www.internetforall.gov/funding-programs)) |
| USDA Community Facilities | eligible public-service facility equipment/technology | Sometimes allowable | Must be essential to eligible facility/project in rural area ([USDA Community Facilities](https://www.rd.usda.gov/programs-services/community-facilities/community-facilities-direct-loan-grant-program)) |
| USDA ReConnect | network-management and broadband project costs | Sometimes allowable | Only costs within approved broadband project/round ([ReConnect](https://www.rd.usda.gov/programs-services/telecommunications-programs/reconnect-program)) |
| EDA programs | planning, feasibility, economic-development systems | Sometimes allowable | Must advance the specific EDA scope; round and award terms control ([EDA funding](https://www.eda.gov/funding/funding-opportunities)) |
| BIA NABDI | feasibility studies/business planning | Likely allowable for consulting/planning; software unclear | BIA describes feasibility/business opportunity assessment; SaaS is not inherently established ([BIA grants](https://www.bia.gov/topic/grants)) |
| BIA TEDC | energy business/capacity development | Sometimes allowable | Federally recognized tribes; current approved budget governs ([TEDC](https://www.bia.gov/service/grants/tedc/apply-tedc-grant)) |
| HUD ICDBG | community facilities/economic development, possibly integral systems | Sometimes allowable | Benefit and activity eligibility tests apply ([HUD ICDBG](https://www.hud.gov/hud-partners/codetalk-icdbg)) |
| HUD IHBG | housing management/data systems as eligible administration or program cost | Sometimes allowable | TDHE/tribe and Indian Housing Plan/eligible-activity rules control ([IHBG](https://www.hud.gov/hud-partners/codetalk-ihbg)) |
| IHS/HRSA/CDC cooperative agreements | EHR, surveillance, evaluation, telehealth or reporting tied to health scope | Sometimes allowable | Only where the NOFO and approved budget support it; privacy/security requirements apply |
| Education/Workforce grants | student/workforce case management and reporting | Sometimes allowable | Must be necessary, reasonable, allocable and permitted by program terms |

Across federal awards, 2 CFR 200 permits necessary, reasonable and allocable costs but does not make a product allowable merely because it is useful ([eCFR 2 CFR Part 200](https://www.ecfr.gov/current/title-2/subtitle-A/chapter-II/part-200)). NativeForge should store allowability at the **opportunity + budget-category** level, with program-family defaults no stronger than “sometimes allowable.”

## 6. Research funding sources

- **NIH Guide for Grants and Contracts:** RSS/search monitoring for notices and funding opportunities; pair with NIH RePORTER for prior awards and institute/center patterns ([NIH Guide](https://grants.nih.gov/funding/searchguide/index.html), [RePORTER API](https://api.reporter.nih.gov/)). Search concepts should include AI/AN, Native American, Alaska Native, tribal, Indigenous, rural health, health disparities, data sovereignty and community-engaged research.
- **NSF:** funding-opportunity search plus NSF Award Search/API; monitor TCUP, EPSCoR, STEM education, cyberinfrastructure and community-engaged research ([NSF funding](https://www.nsf.gov/funding), [NSF award search](https://www.nsf.gov/awardsearch/)). Tribal eligibility often depends on institution type or partnership structure.
- **USDA NIFA:** competitive RFA pages and Grants.gov; prioritize Tribal Colleges programs, Extension, food systems and agriculture research ([NIFA grants](https://www.nifa.usda.gov/grants)).
- **CDC:** Grants.gov plus CDC funding and tribal pages; cooperative agreements may target tribal public health capacity or permit tribal applicants ([CDC grants](https://www.cdc.gov/grants-funding/)).
- **NOAA:** funding opportunities, Sea Grant and climate/resilience/fisheries programs; eligibility varies ([NOAA funding](https://www.noaa.gov/organization/information-technology/funding-opportunities)).
- **USGS:** cooperative research notices and Tribal Relations; many opportunities are institution/partner dependent ([USGS grants](https://www.usgs.gov/office-of-acquisition-and-grants/grants-and-cooperative-agreements)).
- **NASA:** NSPIRES is the principal research solicitation system; monitor ROSES and STEM engagement, but do not infer direct tribal eligibility ([NSPIRES](https://nspires.nasaprs.com/)).

Research governance fields should include tribal resolution/authorization, community engagement requirement, data ownership/sovereignty, publication and specimen/data-sharing terms, indirect costs, and whether the tribe is applicant, subawardee, consultant, participant or merely a population studied.

## 7. Pass-through funding model

For each federal program, store `distribution_mode = direct | state_formula | state_competitive | either | unknown`, the state administering agency, prime-recipient type, subrecipient types, and whether a tribe can bypass the state. Do not advertise a federal listing to a customer when the live route is only a closed state allocation. Track state plan, public-comment notices, subgrant NOFO, amendments, awards and closeout separately.

Pass-through families requiring state instantiation include BEAD/digital equity, FEMA preparedness and mitigation, Drinking Water/Clean Water state revolving funds and set-asides, Weatherization and State Energy Program, CDBG, workforce/WIOA, education formula grants, public-health block/cooperative funding, highway safety, victim services and homeland-security grants.

## 8. State-opportunity filtering model

1. Resolve customer operating state(s), service area and lands; do not use mailing address alone.
2. Resolve legal/eligibility class and recognition status independently.
3. Join federal pass-through families to each state’s administering agency and named program.
4. Monitor the state procurement/grant portal only as a discovery aid; also monitor agency pages and email bulletins.
5. Apply hard geography filters before ranking.
6. Distinguish applicant, subrecipient, partner, beneficiary and vendor roles.
7. Store the source text supporting tribal/nonprofit/business eligibility; otherwise mark `UNKNOWN`.
8. Re-evaluate every live NOFO because state definitions of “tribe,” “local government,” and “political subdivision” differ.

## 9. South Carolina source map

No single official portal located in this review provided complete statewide competitive-grant coverage; operationally, NativeForge should use an agency-by-agency map. That is an evidence-bounded observation, not a claim that no state system exists.

| SC source | What to monitor | Eligibility caution |
|---|---|---|
| SC Broadband Office / Office of Regulatory Staff | BEAD, digital opportunity, guidance, FAQs, datasets and notification list | SCBBO administers BEAD and publishes updates/data; eligible applicant types are round-specific. Do not equate “community served” with applicant eligibility ([SC BEAD](https://ors.sc.gov/broadband/office/investments/state/bead)) |
| SC Emergency Management Division | HMGP, Public Assistance and preparedness/mitigation notices | SCEMD states HMGP may include Indian tribes/tribal organizations and certain nonprofits; PA includes tribal governments and certain PNPs. State-recognized tribe status still requires live-program review ([HMGP](https://www.scemd.org/recover/hazard-mitigation/), [public agencies](https://www.scemd.org/recover/get-help/help-for-public-agencies/)) |
| SC Department of Education | Current and archived SCDE-administered grant opportunities | Tribal schools, Native nonprofits and Native-serving entities only when the specific notice permits their entity class ([SCDE grants](https://www.ed.sc.gov/finance/grants/office-of-grant-services/scde-grant-opportunities/)) |
| SC Department of Health and Human Services | Health delivery, crisis, digital infrastructure and special initiatives | Applicant class is initiative-specific. The 2026 Connections to Care description expressly includes EHR, remote monitoring, telehealth and a statewide resource database, making it a strong capability watch channel ([SCDHHS grants](https://www.scdhhs.gov/resources/grants)) |
| SC Housing | HOME, housing trust, homelessness and community-development channels | Monitor SC Housing and administering entities; tribal/native status alone does not confer eligibility ([SC Housing programs](https://www.schousing.com/home/Resources-for/Developers)) |
| SC Department of Commerce | economic/community development and federal pass-through notices | Many programs route through local governments or development entities; partnership may be required ([SC Commerce grants](https://www.sccommerce.com/communities/grants-incentives)) |
| SC Department of Environmental Services / DPH | water, waste, air, public health and federal pass-through notices | Agency structure changed from former DHEC; monitor both current pages and migrated documents. Eligibility is program-specific ([SC DES grants and loans](https://des.sc.gov/programs/bureau-water/grants-loans)) |
| SC Energy Office / ORS | energy planning, efficiency and federal program notices | Applicant and subrecipient rules vary; monitor Energy Office funding pages ([SC Energy Office](https://energy.sc.gov/)) |
| SC Department of Employment and Workforce | WIOA/workforce notices and local workforce-board channels | Native organizations may be partners/providers; direct applicant eligibility is notice-specific ([SCDEW](https://dew.sc.gov/)) |
| SC Office of Resilience | disaster recovery, mitigation and resilience programs | SCORF’s grant management portal requires credentials and is oriented to named political subdivisions for some programs; use public pages/manual intake first ([SCORF GMS](https://scorf.sc.gov/gms)) |
| SC Arts Commission / Humanities | arts, culture, heritage and nonprofit opportunities | Potentially relevant to Native cultural work when applicant/category rules fit; not Native-specific ([SC Arts grants](https://www.southcarolinaarts.com/grants/)) |

For South Carolina customers, maintain a special recognition mapping: the federally recognized Catawba Indian Nation must be distinct from state-recognized tribes/groups and Native nonprofits. Never inherit federal-tribe eligibility from the word “tribe” in an organization’s name.

## 10. Eligibility-class matrix

Codes: **Y** generally contemplated by the program family; **V** varies by NOFO/route; **N** generally not direct; **U** unknown without live notice.

| Program family | Fed. tribe | State-recognized tribe | Tribal org | Native nonprofit | Native business | Native-serving nonprofit | TCU/BIE school | Individual | Consortium | State/local serving Native communities |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BIA OIED tribal grants | Y | N | V | N | V | N | N | N | V | N |
| ANA discretionary | Y | V | Y | Y | N | V | V | N | V | V |
| HUD IHBG | Y | N | Y/TDHE | N | N | N | N | N | V | N |
| EPA GAP | Y | N | V | N | N | N | N | N | V | N |
| DOJ CTAS | Y | N | V | V | N | V | V | N | V | V |
| FEMA tribal direct | Y | N | V | N | N | N | N | N | V | N |
| General Grants.gov opportunities | V | V | V | V | V | V | V | V | V | V |
| State pass-through | V | V | V | V | V | V | V | V | V | Y/V |
| NIH/NSF research | V | V | V | Y/V | V | Y | Y | V | Y | Y |
| Native-focused philanthropy | Y/V | Y/V | Y | Y | V | V | Y/V | V | V | V |

## 11. Scraper/monitoring recommendations

- Use the Grants.gov `search2` and `fetchOpportunity` endpoints as the canonical opportunity ingest. Save raw payloads, retrieved time and source hashes. Display the required API attribution ([guide](https://www.grants.gov/api/api-guide), [terms](https://www.grants.gov/api/terms-conditions)).
- Use the Federal Register API for tribal consultation, proposed/final rules, notices and funding announcements; it is an official public API ([API](https://www.federalregister.gov/developers/documentation/api/v1)).
- Use USAspending API for historical awards and recipient intelligence, not current-deadline discovery ([API](https://api.usaspending.gov/)).
- Treat agency HTML as amendment detection. Extract links to PDFs, compare document hashes/text, and retain prior versions.
- Prefer official RSS/email where offered. Email bulletins should enter a review queue with original headers and source URL.
- Do not automate authenticated state portals (including SCORF GMS) until terms, authorization and account ownership are reviewed.
- Score every match using explicit eligibility evidence plus geography; keyword “tribal” is not enough.
- Add a human gate before publishing `federal_recognition_required`, `state_recognition_supported`, or `clearly allowable` when derived only from a summary page.

## 12. Source priority tiers

- **Tier 1:** Grants.gov API, WHCNAA/BIA clearinghouse, SAM Assistance Listings, Federal Register API, Indian Affairs grants, ANA, HUD ONAP, DOE Indian Energy, EPA tribal/GAP, DOJ tribal solicitations/CTAS, FEMA tribal/preparedness, USDA RD/NIFA, NTIA, NIH Guide, NSF funding, and customer-state pass-through hubs.
- **Tier 2:** USAspending, agency newsletters/DTLLs, IHS/CDC/HRSA/ACL, NPS/FWS/Reclamation, DOT modal pages, DOL DINAP, EDA, NOAA/USGS/NASA and state agency pages.
- **Tier 3:** broader cross-cutting federal programs, regional commissions, arts/humanities/museum programs and selected philanthropy.
- **Tier 4:** authenticated portals, unstable search apps, sources with unclear reuse terms and manual-only philanthropy.

## 13. Unknowns and legal/terms review needs

1. WHCNAA clearinghouse data endpoint, rate limits, reuse terms and whether its JavaScript application exposes a supported API.
2. SAM.gov public API coverage for Assistance Listings versus HTML/data extracts and applicable API-key/terms requirements.
3. Each agency site’s robots.txt, terms, acceptable polling rate and PDF redistribution rules.
4. Authenticated portal automation, especially state systems, GrantSolutions and SCORF.
5. Whether email-bulletin archiving and content display complies with sender terms and copyright.
6. Customer authority to access account-specific portals and store documents.
7. Treatment of tribal-sensitive information, data sovereignty and research data.
8. Whether NativeForge is providing legal/eligibility advice; product language should preserve NOFO primacy.
9. Accessibility and source-attribution requirements.
10. Retention and update policy when agencies revise or remove notices.

## 14. Machine-readable source table

The companion [CSV registry](nativeforge-source-registry.csv) contains the requested columns and starter records. `UNKNOWN` is intentional. URLs point to official sources. The table is a seed registry, not an assertion that every listed program currently has an open competition.

## Final prioritized lists

### Top 25 sources NativeForge should monitor first

1. Grants.gov API
2. WHCNAA/BIA Access to Capital Clearinghouse
3. SAM.gov Assistance Listings
4. Federal Register API
5. Indian Affairs grants
6. ANA funding opportunities
7. HUD ONAP CodeTalk/grants
8. DOE Office of Indian Energy funding
9. EPA tribal grants/GAP
10. DOJ Tribal Justice/open solicitations and CTAS
11. FEMA Tribal Affairs and preparedness grants
12. USDA Rural Development
13. USDA NIFA
14. NTIA Internet for All
15. NIH Guide
16. NSF funding opportunities
17. IHS funding opportunities
18. CDC grants
19. HRSA funding
20. EDA funding opportunities
21. DOT grants and modal tribal pages
22. DOL DINAP
23. NPS Tribal Heritage/NAGPRA grants
24. FWS Tribal Wildlife Grants
25. Customer-state pass-through agency bundle (SC bundle for initial customers)

### Top 10 sources likely to help customers pay for NativeForge

1. ANA SEDS
2. EPA GAP
3. EPA Exchange Network grants
4. DOJ CTAS purpose areas
5. FEMA THSGP
6. CISA State and Local Cybersecurity Grant Program pass-throughs
7. NTIA/state digital equity programs
8. HUD IHBG/ICDBG where integral and approved
9. Health cooperative agreements (IHS/HRSA/CDC) with data/EHR/evaluation scopes
10. Workforce/education grants with case-management, data and reporting scopes

### Top 10 sources requiring legal/terms review before scraping

1. WHCNAA/BIA Access to Capital Clearinghouse application endpoints
2. SAM.gov non-documented page/search endpoints
3. SCORF authenticated GMS
4. GrantSolutions authenticated content
5. NSPIRES authenticated/search behavior
6. State grant portals requiring accounts
7. Foundation portals (Fluxx/Foundant/Blackbaud and similar)
8. Agency email bulletins intended for subscribers
9. JavaScript-only agency search applications without a documented API
10. Third-party philanthropic aggregators

### Top 10 state-specific source categories to instantiate per customer state

1. Central state grants/procurement discovery portal
2. Emergency management/preparedness/mitigation
3. Broadband and digital equity
4. Housing and community development
5. Energy office and utility/efficiency programs
6. Environmental/water/SRF programs
7. Workforce and economic development
8. Education and tribal-school-relevant programs
9. Public health/Medicaid/behavioral health
10. Justice, victim services and public safety

### Open questions before crawler implementation

- Which customer eligibility attributes are verified, by whom, and how often?
- Will NativeForge show opportunities, make eligibility recommendations, or both?
- What confidence/evidence threshold is required before a source is labeled eligible?
- How will amendments, cancellations, forecast-to-posted transitions and duplicate records be versioned?
- What polling budgets and attribution are required by each API/website?
- Will authenticated customer portals be in scope, and what consent/security model applies?
- How will state-pass-through parent/child records be represented?
- How will Tribal data sovereignty, sensitive locations and research governance be enforced?
- Who performs final legal/terms review and maintains decisions?
- What is the human-review SLA for unknown eligibility, PDF-only notices and email intake?
