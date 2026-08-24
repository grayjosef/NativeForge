# 426 — Gate 77D: Federal source seed status

## Status

```text
Federal seed entries:      6
Monitoring allowed:        0
With a check timestamp:    0
With a URL:                3
Coverage claimed:          NO
Live ingestion claimed:    NO
Federal coverage complete: NOT CLAIMED
```

Every seed is `discovered`, `unreviewed`, `last_checked_at=None`, and comes back
`monitoring_allowed=False`. Each is built through `build_federal_source`, so it
inherits the monitoring gate rather than bypassing it — a test asserts none is
monitorable.

## The seeds

| Key | Family | URL | Scope |
| --- | --- | --- | --- |
| `fed.grants_gov.search` | `grants_gov` | https://www.grants.gov/ | government-wide |
| `fed.federal_register.notices` | `federal_register` | https://www.federalregister.gov/ | government-wide |
| `fed.sam_gov.assistance_listings` | `sam_gov_assistance_listing` | https://sam.gov/ | government-wide |
| `fed.agency_nofo_pages.to_enumerate` | `agency_nofo_page` | — | operating division |
| `fed.agency_program_pages.to_enumerate` | `agency_program_page` | — | operating division |
| `fed.native_specific_program_pages.to_enumerate` | `native_specific_federal_program_page` | — | single program |

## Why only three have URLs

Those three are canonical public entry points and a matter of public record.
Their addresses are not a claim about any particular program.

The other three are **categories awaiting enumeration**. Writing a plausible
agency NOFO URL would fabricate a federal source, and this repo already carries
`source_seed_real_url_guard_service` because that has been a problem before.

## Why the Native-specific lane is deliberately the emptiest

It is the highest-value lane — programs with statutory tribal set-asides or
Native-specific authority are where evidenced Native relevance actually lives —
and it contains exactly one placeholder with no URL.

Naming a specific Native program page would assert three things at once: that the
program exists, that it lives at that address, and that it serves a particular
applicant type. All three are factual claims about real federal programs serving
real tribal communities, and none is derivable from repo data. Getting any of
them wrong sends a tribal grant office to a program that will not fund them.

Gate 77's triage is the argument for that caution: a live federal API returned an
IHS opportunity for a SAMHSA seed. If the live source can be wrong about agency
attribution, a hand-written placeholder certainly can.

A test asserts every Native-specific seed has `source_url is None`.

## What each seed is for

**Grants.gov** — the index, and why eligibility can be evidenced rather than
inferred: structured applicant codes name tribal governments and tribal
organizations as distinct types.

**Federal Register** — the evidence channel the Gate 76 extension and
supersession rules depend on.

**SAM.gov assistance listings** — program-level applicant types. Evidence only
when bound to a specific listing or opportunity (doc 425).

**Agency NOFO pages** — agencies publish ahead of or instead of Grants.gov. Each
needs its operating division named, not just its department.

**Agency program pages** — recurring program terms. Context, not
opportunity-level eligibility.

**Native-specific program pages** — see above.

## Why monitoring is not claimed

No robots/terms review has been performed for any federal source. That review is
a legal and policy judgement, not an engineering task, and it is the gate
standing between this registry and any fetching at all.

Until it happens, `robots_terms_status` stays `unreviewed`, which is one of the
four values that block monitoring. The registry will refuse to monitor anything —
by design, and that is the correct state, not a limitation to work around.

## Invariants

```text
seed_is_monitorable:<key>
seed_not_in_discovered_state:<key>
seed_claims_terms_review:<key>
seed_claims_a_check_timestamp:<key>
seed_claims_freshness:<key>
seed_left_the_federal_lane:<key>
catalog_reports_monitorable_sources
forbidden_claim:coverage_claimed
forbidden_claim:live_ingestion_claimed
forbidden_claim:federal_coverage_complete_claimed
```
