# 503 — Gate 90A: external source registry intake survey

Survey of the Perplexity source-discovery dossier and its companion CSV, before
any code was written. **No URL in the CSV was fetched.**

Doc number: the gate suggested 502, which is already taken by the untracked
Gate 89 provenance draft. This survey is 503 and the rest of Gate 90's docs
follow from 504.

## Inputs, and where they now live

```text
docs/reference/nativeforge-funding-source-dossier.md        29,239 bytes
fixtures/external_source_registry/nativeforge-source-registry.csv  22,458 bytes
```

Copied verbatim from the user-supplied files. No existing corpus fixture was
touched — the fixture-cleanliness verifier passes unchanged, and this is a new
directory.

## Shape

```text
data rows        55
columns          26
source_id        unique across all 55
```

The column set matches the gate's specification exactly, in order:
`source_id, source_name, source_type, agency_or_org, subagency, jurisdiction,
federal_or_state_or_private, state_if_applicable, url, monitoring_method,
scraper_difficulty, robots_or_terms_risk, native_relevance, eligibility_classes,
federal_recognition_required, state_recognition_supported,
software_cost_allowability, program_examples, deadline_pattern,
update_frequency, data_format, has_api, has_rss_or_email, requires_login, notes,
priority_tier`.

## Priority tiers

| Tier | Rows |
| --- | --- |
| Tier 1 | 33 |
| Tier 2 | 19 |
| Tier 3 | 2 |
| Tier 4 | 1 |

## Federal / state / private split

| Jurisdiction class | Rows |
| --- | --- |
| federal | 43 |
| state | 10 (all South Carolina) |
| private | 2 |

**Every state row is `SC`.** There are no other states in the registry, which
matters for the filtering model: a non-SC customer sees zero state sources from
this seed, not a different state's sources.

## Monitoring methods

| Method | Rows |
| --- | --- |
| static HTML page monitor | 33 |
| PDF/NOFO page monitor | 8 |
| API monitor | 5 |
| search endpoint monitor | 5 |
| email bulletin/manual intake | 2 |
| RSS/feed monitor | 1 |
| human review only | 1 |

## Robots / terms risk

| Risk | Rows |
| --- | --- |
| low | 42 |
| TERMS_REVIEW_REQUIRED | 8 |
| API_TERMS | 4 |
| HUMAN_REVIEW_ONLY | 1 |

**13 of 55 rows carry a non-`low` risk.** None of them may be activated before
legal review, and the one `HUMAN_REVIEW_ONLY` row (SCORF GMS) may not be
automated at all.

## API and feed availability

| Field | Yes | No | UNKNOWN |
| --- | --- | --- | --- |
| `has_api` | 5 | 45 | 5 |
| `has_rss_or_email` | 43 | 4 | 8 |

`requires_login`: 50 No, 3 Varies, 1 API key, 1 Yes.

**`has_api: Yes` is a capability claim, not an approval.** Of the 5 API-capable
rows, 4 carry `API_TERMS` risk. Gate 90's model keeps those two facts in
separate fields so one can never be read as the other.

## Source types

23 distinct values, led by `agency_grant_page` (18) and `program_page` (6), with
a long tail of one-offs (`opportunity_aggregator`, `program_catalog`,
`notice_feed`, `capacity_program`, `data_system_program`, `formula_program`,
`pass_through_program`, `authenticated_portal`, three research types, four
state-scoped types, two Native-specific types).

The tail is not noise — `authenticated_portal` and `Native_philanthropy` carry
different activation rules from `agency_grant_page`, and the import preserves
the value verbatim rather than bucketing it.

## Scraper difficulty and Native relevance

`scraper_difficulty`: 36 low, 16 medium, 3 high.
`native_relevance`: 23 Very high, 24 High, 8 Medium.

## Top Tier 1 sources

The 33 Tier 1 rows, in registry order:

```text
FED-GRANTS      Grants.gov                    FED-SAM-AL      SAM.gov Assistance Listings
FED-FR          Federal Register              NAT-ATC         Access to Capital Clearinghouse
DOI-BIA-GRANTS  Indian Affairs Grants         HHS-ANA         ANA Funding Opportunities
HHS-IHS         IHS Funding Opportunities     HHS-SAMHSA      SAMHSA Grants
NIH-GUIDE       NIH Guide                     USDA-RD         USDA Rural Development
USDA-RECONNECT  ReConnect Program             USDA-NIFA       NIFA Grants
HUD-ONAP        HUD ONAP                      HUD-IHBG        Indian Housing Block Grant
DOC-EDA         EDA Funding Opportunities     DOC-NTIA        Internet for All
DOE-INDIAN      Office of Indian Energy       EPA-TRIBAL      EPA Tribal Grants
EPA-GAP         EPA GAP                       EPA-EN          Exchange Network Grants
DOJ-TRIBAL      DOJ Tribal Solicitations      DOJ-OVW         OVW Open Solicitations
FEMA-THSGP      Tribal Homeland Security      CISA-SLCGP      State/Local Cybersecurity
DOT-GRANTS      DOT Grants                    ED-OIE          Office of Indian Education
DOL-DINAP       DOL DINAP                     NSF-FUNDING     NSF Funding Opportunities
SC-BEAD SC-EMD-HMGP SC-EMD-PA SC-ED SC-DHHS   (5 SC rows, Tier 1)
```

### Which Tier 1 sources are implementable first

Of the 33, **28 are federal and 5 are SC**. Filtering to rows with `low` terms
risk and no login requirement leaves the set that could be built after nothing
more than a robots check:

```text
FED-FR          Federal Register    API monitor, low risk, documented public API
DOI-BIA-GRANTS  Indian Affairs      static HTML, low risk
HHS-ANA / HHS-IHS / HHS-SAMHSA      static HTML, low risk
USDA-RD / USDA-RECONNECT / USDA-NIFA
HUD-ONAP / HUD-IHBG
DOC-EDA / DOC-NTIA / DOE-INDIAN
EPA-TRIBAL / EPA-GAP / EPA-EN
DOJ-TRIBAL / DOJ-OVW / FEMA-THSGP / CISA-SLCGP
DOT-GRANTS / ED-OIE / DOL-DINAP / NIH-GUIDE (RSS)
```

`FED-GRANTS` (Grants.gov) carries `API_TERMS` rather than `low` — its terms
permit search and retrieval but require attribution, so it needs an attribution
decision rather than a full legal review.

**Excluded from "first" despite Tier 1:** `FED-SAM-AL` and `NAT-ATC`, both
`TERMS_REVIEW_REQUIRED`. NAT-ATC is the highest-value Native-specific
aggregator in the whole registry and is `scraper_difficulty: high` with a
JavaScript front end and `has_api: UNKNOWN`. It is the single most valuable
blocked source.

## South Carolina rows

All 10 state rows, and the only state rows in the registry:

| source_id | Tier | Type |
| --- | --- | --- |
| `SC-BEAD` | 1 | state_program_page |
| `SC-EMD-HMGP` | 1 | state_pass_through |
| `SC-EMD-PA` | 1 | state_pass_through |
| `SC-ED` | 1 | state_agency_grants |
| `SC-DHHS` | 1 | state_agency_grants |
| `SC-COMMERCE` | 2 | state_agency_grants |
| `SC-DES-WATER` | 2 | state_agency_grants |
| `SC-ENERGY` | 2 | state_agency_page |
| `SC-DEW` | 2 | state_agency_page |
| `SC-SCORF` | 4 | authenticated_portal |

Every one carries `federal_recognition_required: No` and
`state_recognition_supported: UNKNOWN`. That pairing is important and must
survive import intact: it says the *program* does not require federal
recognition, and says **nothing** about whether a state-recognized tribe
qualifies. Reading `No` + `UNKNOWN` as "state-recognized tribes are eligible"
would be exactly the collapse Gates 78–79 built guards against.

## State pass-through rows

Two rows are explicitly typed `state_pass_through` (`SC-EMD-HMGP`,
`SC-EMD-PA`), and one federal row is typed `pass_through_program`
(`CISA-SLCGP`, noted "Instantiate state route"). The dossier's §7 pass-through
model is broader than the CSV encodes — the CSV has no `distribution_mode`
column — so Gate 90 imports what the CSV carries and does not synthesise the
richer model.

## Sources likely to pay for NativeForge

`software_cost_allowability` is dominated by hedged values: **38 of 55** read
"Sometimes allowable depending on NOFO/budget category", plus 6 more
"Sometimes allowable depending on call/incident/program".

Only 3 rows read stronger than "sometimes":

```text
EPA-GAP     Likely allowable   environmental program capacity
EPA-EN      Likely allowable   environmental data exchange systems
CISA-SLCGP  Likely allowable   cybersecurity plans, projects, tools
```

And 8 read weaker or not applicable: 3 `Unclear` (FED-SAM-AL, FED-FR,
PRIV-NDN), 3 `Varies` (NAT-ATC, DOI-BIA-GRANTS, DOI-BIE), 2 `Not applicable`
(FED-USA, NIH-REPORTER — both award databases, not funding sources).

**Zero rows read "Clearly allowable."** The dossier is explicit that program-family
defaults should be no stronger than "sometimes allowable" and that allowability
belongs at the opportunity + budget-category level. The classifier built in
Gate 90E therefore has a `clearly_allowable` bucket that nothing in this seed
reaches — which is the correct outcome, not a gap.

## Sources requiring terms review before activation

10 rows, by the union of non-`low` risk and any login requirement:

```text
SC-SCORF      HUMAN_REVIEW_ONLY      login: Yes      never automate
NASA-NSPIRES  TERMS_REVIEW_REQUIRED  login: Varies
PRIV-NDN      TERMS_REVIEW_REQUIRED  login: Varies
PRIV-FNT      TERMS_REVIEW_REQUIRED  login: Varies
FED-SIMPLER   API_TERMS              login: API key
FED-SAM-AL    TERMS_REVIEW_REQUIRED  login: No
NAT-ATC       TERMS_REVIEW_REQUIRED  login: No
DOI-BIE       TERMS_REVIEW_REQUIRED  login: No
HHS-HRSA      TERMS_REVIEW_REQUIRED  login: No
NSF-FUNDING   TERMS_REVIEW_REQUIRED  login: No
```

Three further rows carry `API_TERMS` without a login (`FED-GRANTS`, `FED-USA`,
`NIH-REPORTER`) — attribution obligations rather than blockers.

## UNKNOWN values, preserved

`UNKNOWN` appears 23 times across three columns and is intentional per the
dossier:

```text
10  state_recognition_supported
 8  has_rss_or_email
 5  has_api
```

The import preserves the literal string. It is not coerced to `False`, `None`,
or a default — an unknown capability is not an absent one, and this campaign has
already been bitten once by a field that meant less than it looked like.

## What this survey establishes for the rest of Gate 90

1. The CSV is well-formed, complete, and internally consistent. No row is
   missing a `source_id`, `source_name`, or `priority_tier`.
2. **10 of 55 rows are blocked** pending terms or human review, and 1 may never
   be automated.
3. **All 10 state rows are SC**, so state filtering has a clean test: an SC
   customer sees 10, a non-SC customer sees 0, and a customer with no declared
   state sees 0.
4. **Nothing in the seed is "clearly allowable"** for paying for software, and
   the honest headline is 3 "likely" against 44 "sometimes".
5. `has_api` and terms risk must stay separate fields, because 4 of the 5
   API-capable rows carry API terms obligations.
