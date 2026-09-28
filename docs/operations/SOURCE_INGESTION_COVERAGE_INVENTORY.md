# Source ingestion and coverage inventory

Verified from repository code on 2026-09-28. This is not a roadmap.
A name in a seed CSV, a fixture, or a planning document is not a collector.

No production collector was activated to produce this inventory.
`collectors_live` remains 0. No warrant was minted.

## How a source enters NativeForge

1. A registry or seed row names a source and an `adapter_key`.
2. Gate 163 measures whether that adapter is in
   `ADAPTER_CAPABILITIES` (`source_collector_capability_service`).
   Today that map contains one key: `grants_gov_search2`.
3. A live request is minted only by `source_live_warrant_service`.
   A collection warrant requires a signed authorization, terms review,
   attribution where required, robots preflight, and the live-fetch opt-in.
   The transport builder calls that check itself.
4. Bytes are normalized by `canonical_opportunity_normalizer_service`,
   which currently has a parser only for `grants_gov_search2` search hits.
5. Identity is decided by `cross_source_identity_service` (exact number,
   strong match, recurrence, distinct). It does not boolean-merge.
6. Freshness rules exist (`source_freshness_service`,
   `opportunity_freshness_service`, Gate 32). Nothing in production is
   scheduled to run them. Phase 1 invariants refuse `may_fetch_live_now`
   and refuse `collector_status` other than `not_active`.
7. Readiness (`backend_health_readiness_service`) hard-fails if
   `collectors_live` is not 0.

Manual entry is separate: `create_grant_spark` / Add Opportunity.
That is an operator-entered record, not a collector.

## What counts as implemented

| Mechanism | State | Method | Live-capable code | Production enabled | Warrant | Normalization | Provenance | Dedup | Freshness | Retry | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Grants.gov search2 (`api.grants.gov/v1/api/search2`) | PARTIAL | API | Yes. Only adapter in `ADAPTER_CAPABILITIES`. Also `fetchOpportunity`. | No | Yes, for collection | Search-hit fields only. Eligibility text, amounts, and source URL are declared unsupported on a search hit. | Parser version recorded on observations | Yes, when a number exists (`cross_source_identity_service`) | Policy exists; no running monitor | Fetch errors are an outcome. First-collection adapters retry 0 times. | AUTHORIZATION. Also CODE if the goal is to flip `collectors_live` or Phase 1 `collector_status`: those invariants reject a live claim. |
| Grants.gov daily extract | NOT IMPLEMENTED | — | No fetch module | No | Would be required | No | — | — | Retention-alert precondition named only | — | CODE |
| Federal Register documents JSON | SCAFFOLD ONLY | API (proposed) | `PROPOSED_PATH` is explicitly unverified. `read_records` is a hypothesis. | No | Would be required | Not in `OPPORTUNITY_PARSERS` | Adapter contract only | Document-level helper only | Not running | `max_attempts: 1` | CODE. Envelope not confirmed. |
| SAM.gov assistance listings | NOT IMPLEMENTED | — | Policy row only. Scraping prohibited. API key named as a precondition. | No | Would be required | No | — | — | — | — | CODE, then an API key |
| USAspending API v2 | NOT IMPLEMENTED | — | Policy row only. Classified prior-award, not open opportunities. | No | Would be required | No | — | — | — | — | CODE. Must not be surfaced as open opportunities. |
| BIA program-page HTML | SCAFFOLD ONLY | document | One GET, depth 0, shallow title/headings. Dates and amounts are intentionally not extracted. Shape unverified. | No | HTML path uses `polite_http_get`, live off by default | Not in the canonical parser map | Page hash only | Link list deduped; links are not fetched | Not running | One attempt | CODE |
| Foundation HTML listing | PARTIAL | scrape/document | `polite_http_get` plus link extraction. Not in `ADAPTER_CAPABILITIES`. | No | Live network guard, default deny | Tier-3 parse of supplied rows; operator activation required | Fetch result labeling | URL dedup inside a page | Not running | Guard refuses; no fleet retry | CODE for fleet collection. AUTHORIZATION for any live GET. |
| Foundation Fluxx embed | PARTIAL | scrape | Same polite fetch, Fluxx URL detection. Not a fleet capability. | No | Same guard | Cluster match against a seed | Fetch labeling | Page-level | Not running | Same | CODE + AUTHORIZATION |
| State tribal-affairs HTML | PARTIAL | scrape | Polite fetch, tribal-hint filter, one same-domain hop. Not a fleet capability. | No | Same guard | Tier-2 parse requires supplied listing rows | Fetch labeling | URL dedup | Not running | Same | CODE + AUTHORIZATION |
| WordPress REST listing | PARTIAL | API | Generic `/wp-json/wp/v2/` parser. No publisher is wired as a fleet source. | No | Caller-injected transport | Listing records, not the canonical opportunity parser | Outcome field distinguishes empty vs parse failure | Not the cross-source graph | `modified` is read; nothing schedules it | Blocked is distinct from empty | CODE to bind a publisher. AUTHORIZATION to fetch. |
| Tier-1 federal parser (`grants_gov_federal`, `simpler_grants_gov`, `grant_solutions`) | SCAFFOLD ONLY | other | Normalizes a payload already in hand. `grants_gov_like_to_fixture_row`. Does not fetch. | No | n/a | Fixture-shaped row | Canonical id from Grants.gov id when present | Idempotent upsert by that id | No | No | CODE. 60 seed rows use `grants_gov_federal` and are not 60 collectors. |
| Manual opportunity (`create_grant_spark`, Add Opportunity) | COMPLETE for manual entry | manual | Writes an org-scoped opportunity the operator typed. | Yes, as data entry. Not a collector. | No | Application record, not source normalization | Operator entry | Not cross-source identity | No source refresh | n/a | None for the write path. It does not create coverage. |
| Customer live federal search | PARTIAL query, not a collector | API | Calls search2 for three publisher eligibility classes. Returns `collectors_live: false`. | No. Hermetic guard blocks live network in tests. Production readiness still reports no live fetch. | Transport refusals are surfaced, not treated as empty results. | Row labels are the publisher class, not a NativeForge verdict. | Source URL when Grants.gov returns an id | Unique by opportunity number inside one response | No | Errors recorded per class | AUTHORIZATION for a live call. The query itself is limited to three tribal applicant classes. |

## Seed catalog is not coverage

`fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv` has 179 rows:

- tier 1: 63 (60 `grants_gov_federal`, 1 `grants_gov_search2`, 1 `federal_register_documents_json`, 1 `bia_program_page_html`)
- tier 2: 51 `state_portal_generic`
- tier 3: 65 `foundation_org_page`

`catalog_accounting_bucket=activatable` (124 rows) is a seed health label.
It is not production activation. `source_seed_catalog.py` and
`federal_source_seed_catalog.py` state that their entries are discovered,
unreviewed, and not monitoring. `opportunity_source_catalog.py` is
illustrative (`example.gov` / `example.org`).

Named in that seed, and not a functioning collector:

- BIA, IHS, ANA, SAMHSA, HUD, EPA, DOJ, DOT, USDA, DOE, NPS, IMLS, NEA, FWS,
  FEMA, Treasury CDFI, DOL, Reclamation, NIH, NSF, ACL — program names on
  `grants_gov_federal` rows.
- State tribal-affairs pages, one per state-shaped row, on `state_portal_generic`.
- Foundation and intermediary pages on `foundation_org_page`.

Phase 1 ids with no fetch implementation: `grants_gov_daily_extract`,
`sam_assistance_listings_api`, `usaspending_api_v2`.
`federal_register_api` in the Phase 1 policy is the same unverified Federal
Register adapter, not a second collector.

## Totals

Counted as an implemented collector only when this repository contains code
that can request that source and read a response. Seed rows are not counted.

| Question | Count |
|---|---|
| Actual implemented collectors (request + read) | 1 fleet-capable: Grants.gov search2. 4 additional fetch-shaped adapters that are not fleet capabilities: foundation HTML, Fluxx, state tribal-affairs HTML, WordPress REST. |
| Production-capable | 0. Readiness rejects a nonzero `collectors_live`. Phase 1 rejects `collector_status != not_active`. |
| Currently enabled | 0 |
| Requiring only authorization or configuration | 1: Grants.gov search2, for a warranted fetch. Claiming the collector live is still code-blocked by the invariants above. |
| Requiring additional code | Federal Register confirmation, BIA page confirmation, SAM.gov, USAspending, daily extract, per-publisher WordPress binding, fleet registration of the HTML adapters, and every seed row that is only a name. |
| Scaffolded but incomplete | Federal Register documents JSON, BIA program-page HTML, tier-1/2/3 parsers, Phase 1 policy rows for daily extract, SAM, USAspending. |
| Source-class coverage with a real fetch path | Federal: Grants.gov search2 (broad index). Foundation: HTML/Fluxx adapters, not enabled. State: HTML adapter, not enabled. |
| Source classes with no implementation | Local, Tribal (as a publisher), Corporate, University, Nonprofit, Private — placeholders or illustrative catalog rows only. |
| Federal-agency coverage | UNKNOWN as ingested inventory. The only federal fetch implementation is the government-wide Grants.gov index, not a per-agency collector. Agency names in the seed are not agency collectors. |
| Native-specific source coverage | 0 enabled. BIA page adapter is a scaffold. IHS and ANA appear only as seed program names. |
| Broad-eligibility source coverage | Grants.gov search2 can query posted and forecasted opportunities without a tribal facet (`search_grants_gov_opportunities`). That path is not production-enabled. The customer search helper currently queries only eligibility codes 07, 08, and 11. |

## Activation

A. Best next source: Grants.gov search2. It is the only adapter the collector
capability registry can execute, it is a public API, and normalization and
cross-source identity already know its search hits.

B. Activatable immediately with no new code and no new authorization: none.
No warrant is present, and this inventory does not create one.

C. Authorization / configuration, code already able to fetch: Grants.gov search2.

D. Small adapter work: confirm the Federal Register documents envelope
(the path in code is marked proposed); register foundation, Fluxx, state HTML,
and WordPress adapters in `ADAPTER_CAPABILITIES` only after a warrant exists
for a specific host.

E. High-value classes with no implementation: State (as administered grant
portals, distinct from tribal-affairs HTML), Local, Tribal publishers,
Philanthropic programs beyond page scraping, Corporate, University.

F. Blind spots: no per-agency collector for BIA, IHS, or ANA; customer live
search is tribal-class only, which misses broadly eligible opportunities and
misses tribal-eligible notices Grants.gov files under other facet codes
(the adapter documents code 25 "Others" hiding tribal-restricted programs);
USAspending must not be treated as an open-opportunity source; 179 seed names
are not inventory.

G. Architectural blockers: Phase 1 and readiness invariants forbid reporting
collectors live; fleet capability is a one-entry map; canonical normalization
has one parser; HTML fetch defaults to deny and is outside that map.

H. The normalization model is general enough to add parsers by `adapter_key`
without new product tables. It is not general enough today: only
`grants_gov_search2` is registered, and several canonical fields are
unsupported on a search hit until `fetchOpportunity` is authorized.

## Doctrine

Source coverage and Native relevance are separate.
Grants.gov is a broad-eligibility index. NativeForge qualifies rows after
ingestion. A collector that searches only for the words "tribal grants" is
the wrong ingestion strategy. The three eligibility codes are a publisher
facet, not the discovery universe.
