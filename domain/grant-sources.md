# Grant Sources

Distilled from source report Section 5. M0 ingests from one source (Grants.gov, seeded only). M1 expands. M2 adds foundations.

## Tier 1 — MVP ingestion priority

| Source | URL | Type | API/Feed | Priority |
|---|---|---|---|---|
| Grants.gov | grants.gov | Federal discretionary | REST API (public) | **M0 seeded, M1 live** |
| SAM.gov Assistance Listings | sam.gov | Federal programs catalog | API (public) | M0 seeded, M1 live |
| Federal Register | federalregister.gov | NOFAs, NOFOs, rules | API + RSS | M1 |
| BIA Grants | bia.gov/topic/grants | Tribal trust, education, enterprise | Web scrape (no API) | M1 |
| IHS Grants | ihs.gov/dgm/funding | Tribal health | Web scrape | M1 |
| Administration for Native Americans (ANA) | acf.hhs.gov/ana | Social, language, environment | Web scrape | M1 |
| CTAS / DOJ | cops.usdoj.gov/ctas | Justice, public safety | Web scrape | M1 |
| DOE Office of Indian Energy | energy.gov/indianenergy | Tribal energy | Web scrape | M1 |
| HUD ONAP | hud.gov/codetalk | Tribal housing, IHBG | Web scrape | M1 |
| USDA Rural Development | rd.usda.gov | Housing, community facilities, broadband | Web scrape | M1 |
| EPA Tribal Grants | epa.gov | Environmental capacity | EPA Grants API | M1 |
| NTIA Tribal Broadband | ntia.gov | Broadband, digital equity | Web scrape | M1 |
| USAspending.gov | usaspending.gov | Award history | API (public) | M1 |

## Tier 2 — M1/M2 addition priority

| Source | Type | Tribal Relevance |
|---|---|---|
| FEMA Tribal Grants | Disaster preparedness, hazard mitigation | Direct tribal eligibility |
| DOT / FHWA Tribal Transportation | Infrastructure, highways, planning | Tribal Transportation Program |
| DOL Tribal Workforce | Employment, workforce development | WARN Act, tribal workforce grants |
| EDA Indigenous Communities | Economic development | IRC program |
| NEH / NEA Cultural Preservation | Language and culture | Tribal language, arts |
| IMLS Native Programs | Libraries, museums | Native American Library Services |
| NPS Historic Preservation | Tribal historic preservation | THPO grants |

## Tier 3 — Foundation/philanthropic (manual or email monitoring in MVP)

| Source | Focus | Priority |
|---|---|---|
| Native Americans in Philanthropy | Equitable Indigenous philanthropy | M2 |
| First Nations Development Institute | Financial capacity, asset building | M2 |
| NDN Collective | Self-determination, land, climate | M2 |
| Bush Foundation | Native nation building | M2 |
| Robert Wood Johnson Foundation | Health equity | M2 |
| Ford Foundation | Indigenous rights, racial equity | M2 |

Foundation ingestion approach: M1 = saved-search links + email alerts parsed; M2 = structured monitoring.

## Implications for M0

Only Grants.gov matters for the demo, and only with seeded data. Every other source is M1.

The demo's tribal Sparks should still feel diverse — IHS, ANA, BIA, DOE, EPA at minimum — even though all 12 are seeded. The seed file will manually include opportunities from those agencies (sourced from real Grants.gov listings) so the demo passes the smell test.

## Implications for M1

The architecture for ingestion has to handle the agency mix from day one. That means:

- A pluggable source adapter pattern.
- Web scraping fallbacks with rate limiting and robots.txt compliance.
- Amendment/version detection per source.
- Deduplication by `(source, source_id)`.
- Confidence scoring on every extracted field per source (web scrapes are messier than API responses).
