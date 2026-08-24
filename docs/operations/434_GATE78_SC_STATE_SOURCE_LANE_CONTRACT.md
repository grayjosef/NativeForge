# 434 — Gate 78B: SC state source lane contract

## Scope

`src/nativeforge/services/sc_state_source_lane_service.py`. What a South
Carolina state source **is**, and — more load-bearing — what it is not.

Nothing here fetches. `coverage_claimed` and `live_ingestion_claimed` are False
on every record.

## What the SC lane covers

Sources **owned and administered by South Carolina or by SC-based private and
sub-state funders**:

| Family | Needs a state agency? |
| --- | --- |
| `sc_state_grant_portal` | no — statewide aggregation |
| `sc_agency_grant_page` | **yes** |
| `sc_agency_program_page` | **yes** |
| `sc_procurement_or_contracting_page` | **yes** |
| `sc_foundation` | no |
| `sc_community_foundation` | no |
| `sc_regional_council` | no |
| `sc_local_government` | no |
| `native_intermediary` | no |
| `unknown` | blocks monitoring |

Procurement is a separate family on purpose: a contract is not a grant, its
eligibility rules differ, and folding it into grant families would blur a
distinction that matters for Native business and economic-development pursuit.

## What the SC lane does not cover

**Federal opportunities, however relevant to South Carolina.** This is the rule
most likely to be got wrong and the one with the worst consequence.

`build_sc_source` accepts `federal_agency` **so it can reject it**:

```text
federally_owned_source_not_sc_state:<agency>
```

The value is recorded as `rejected_federal_agency`; the record's own
`federal_agency` is always `None`, and an invariant fails any SC record carrying
one. Taking the field and refusing it makes the boundary visible in the data
rather than depending on callers to know it.

### Why this matters concretely

Collapsing federal into state would undercount federal coverage and overcount
state coverage. For a tribal organization in a state with few state-administered
Native programs, that misstates their funding landscape as smaller and more
local than it is — and the federal lane is where most tribal eligibility
actually lives.

`sc_state_source_adapter_config_service` already stated the principle as
`organization_geography_must_not_filter_federal`. This module enforces it at the
record level; `sc_native_routing_service` (doc 435) enforces it at the
opportunity level.

## Recognition relevance

A **set**, not a single value, with no inference between members:

```text
state_recognized_relevant      federally_recognized_relevant
native_nonprofit_relevant      native_business_relevant
native_community_relevant      unknown
```

`recognition_routing_contract_service` (Block 27) already says *"State-recognized
status is never treated as federally recognized"*. Gate 78 makes that
operational for SC, where it is the local case: **South Carolina has
state-recognized tribes**, and a federal program open to federally recognized
tribal governments may be closed to them.

Both directions are tested. `normalize_recognition_relevance` performs no
inference in either direction, and both tiers can be held together when both are
supplied.

Tags bridge onto the existing Gate 56 `RECOGNITION_ROUTES` via
`RECOGNITION_ROUTE_MAP`. `native_community_relevant` maps to `unknown` rather
than borrowing a route — it describes a community served, not an applicant type.
A test asserts every tag projects into the existing vocabulary.

### Relevance is not eligibility

`recognition_relevance` is a source-level **expectation** of who a source tends
to serve. A source that often carries tribal opportunities does not make any
particular opportunity open to any particular applicant. The record carries
`eligibility_determined: False` and an invariant enforces it.

## Monitoring rules

`monitoring_allowed` requires all three:

1. `promotion_status` in `{approved_for_monitoring, monitoring}`
2. Robots/terms cleared — only `reviewed_allowed` and
   `reviewed_allowed_with_rate_limit`, reusing the Gate 76 registry vocabulary
3. The record is complete

A source marked `monitoring` that fails any of these gets
`marked_monitoring_but_not_eligible` rather than a silent downgrade.

## Completeness rules

Separate from blocked, so "we lack information" is distinguishable from "we are
not permitted":

```text
state_agency_required_for_agency_specific_source
no_source_url
no_provenance_url
unrecognised_recognition_relevance_tags
```

## Coverage and freshness rules

`counts_toward_coverage` requires completeness, provenance and no blockers.
`freshness_claimable` is simply whether `last_checked_at` exists — an invariant
fails any record claiming freshness without one.

## Invariants

```text
sc_source_left_the_sc_state_lane
sc_state_source_carries_a_federal_agency
monitoring_from_non_monitoring_status
monitoring_without_cleared_terms
monitoring_an_incomplete_source
coverage_credit_without_provenance
freshness_claimable_without_a_check_timestamp
agency_specific_source_complete_without_a_state_agency
forbidden_claim:eligibility_determined
forbidden_claim:coverage_claimed
forbidden_claim:live_ingestion_claimed
```

## Not done here

No SC source has been identified. The lane is a contract with no contents —
see doc 436. No fetching, no persistence, no migration.
