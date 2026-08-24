# 436 — Gate 78D: SC source seed status

## Status

```text
SC seed entries:          7
Monitoring allowed:       0
With a check timestamp:   0
With a URL:               0
Native relevance expected: 0
Coverage claimed:         NO
Live ingestion claimed:   NO
SC coverage complete:     NOT CLAIMED
```

Every seed is `discovered`, `unreviewed`, and built through `build_sc_source` so
it inherits the monitoring gate rather than bypassing it.

## The seeds

| Key | Family | Scope |
| --- | --- | --- |
| `sc.state_portal.to_research` | `sc_state_grant_portal` | statewide |
| `sc.agency_grant_pages.to_enumerate` | `sc_agency_grant_page` | agency-wide |
| `sc.agency_program_pages.to_enumerate` | `sc_agency_program_page` | single program |
| `sc.procurement.to_research` | `sc_procurement_or_contracting_page` | statewide |
| `sc.foundations.to_enumerate` | `sc_community_foundation` | regional |
| `sc.regional_local.to_enumerate` | `sc_regional_council` | regional |
| `sc.native_intermediary.to_research` | `native_intermediary` | unknown |

Note the key suffixes: `to_research` where it is not yet known whether the thing
exists, `to_enumerate` where the category certainly exists but its members have
not been listed. The distinction is real — South Carolina may or may not have a
central grant portal, and asserting one would be a claim.

## Why no seed carries a URL

The federal catalog names grants.gov, federalregister.gov and sam.gov, because
those are canonical public entry points and a matter of public record. Naming
them asserts nothing about any particular program.

**There is no equivalent South Carolina address this repo can assert without
research.** A plausible-looking state portal URL would fabricate a source, and
`source_seed_real_url_guard_service` exists in this codebase because that has
been a problem before.

An invariant enforces it: `seed_claims_a_url_without_research`, plus a catalog-
level check that `with_url_count == 0`.

This leaves the catalog visibly thin, and thin is the honest state. A catalog of
invented URLs would look like progress and would send a tribal grant office to
pages that do not exist — a failure that costs them time they do not have and
credibility we would not get back.

## Why `native_relevance_expected` is False throughout

Whether an SC source tends to carry Native-relevant opportunities is a
**finding**, not an assumption. Nothing here has been examined. Marking a source
as Native-relevant before looking would seed the discovery quality score with a
guess, and the Gate 54 scorer exists precisely to prevent guesses counting as
coverage.

The `native_relevance_rationale` field carries *why the category is worth
investigating*, which is a plan rather than a claim. For example, the community
foundation seed records that regional philanthropic funders are often the only
lane open to a Native nonprofit that is not a federally recognized tribal
government — a reason to look, not a finding about any specific funder.

## Why monitoring is not claimed

No robots/terms review has been performed, because no SC source has been
identified to review. `robots_terms_status` is `unreviewed` on every seed, which
is one of the four values that block monitoring.

The registry will refuse to monitor anything in this lane. That is the correct
state, not a limitation to work around.

## What unblocks this catalog

Research, not engineering:

1. Does South Carolina have a central state grant portal, and where?
2. Which SC agencies publish grant opportunities on their own pages?
3. Which SC community foundations and regional councils fund Native-serving
   work?
4. Which Native intermediaries operate in or fund into South Carolina?
5. For each identified source: robots/terms review.

Until then the SC lane is a contract with no contents. That is stated plainly
rather than disguised by placeholder URLs.

## Invariants

```text
seed_is_monitorable:<key>
seed_not_in_discovered_state:<key>
seed_claims_terms_review:<key>
seed_claims_a_check_timestamp:<key>
seed_claims_freshness:<key>
seed_claims_a_url_without_research:<key>
seed_left_the_sc_state_lane:<key>
sc_seed_carries_a_federal_agency:<key>
catalog_reports_monitorable_sources
catalog_reports_seed_urls_without_research
forbidden_claim:coverage_claimed
forbidden_claim:live_ingestion_claimed
forbidden_claim:sc_coverage_complete_claimed
```
