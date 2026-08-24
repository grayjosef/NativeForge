# 424 — Gate 77B: Federal source lane contract

## Scope

`src/nativeforge/services/federal_source_lane_service.py`. The federal lane is
built first because it is the most uniform: a small number of canonical entry
points, a consistent applicant-type vocabulary, and an authoritative amendment
channel.

Nothing here fetches. `coverage_claimed` and `live_ingestion_claimed` are `False`
on every record.

## Source families

| Family | Role |
| --- | --- |
| `grants_gov` | Government-wide index. Structured applicant eligibility codes |
| `federal_register` | Authoritative notices, extensions, amendments |
| `sam_gov_assistance_listing` | Program-level applicant types |
| `agency_nofo_page` | One operating division's own NOFO listings |
| `agency_program_page` | One program's description and recurring terms |
| `native_specific_federal_program_page` | Statutory tribal set-aside / Native authority programs |
| `agency_rss_feed` | Per-agency feed where offered |
| `unknown` | Blocks monitoring |

### The three canonical entry points

**Grants.gov** is the index, and the reason eligibility can be *evidenced* here
rather than inferred: it carries applicant eligibility codes that name tribal
governments and tribal organizations as distinct types.

**Federal Register** is the evidence channel the Gate 76 freshness rules depend
on. Extension and supersession claims need a citable notice, and this is where
they live.

**SAM.gov assistance listings** carry program-level applicant detail. Program
level, not opportunity level — which is why the eligibility service requires a
listing or opportunity binding before crediting a listing-derived applicant type.

## Agency vs subagency

The distinction this gate exists to encode.

```text
agency     = department            HHS
subagency  = operating division    SAMHSA, IHS
bureau     = further subdivision   optional
```

`split_agency_identifier` parses both shapes the repo actually contains —
`"SAMHSA / HHS"` and `"HHS-IHS"` — into the same structure.

`federal_agencies_align` compares at the **most specific level both sides
declare**:

| Case | Aligned | Reason |
| --- | --- | --- |
| SAMHSA vs SAMHSA | yes | `subagency_match` |
| **SAMHSA vs IHS (both HHS)** | **no** | `different_subagency_same_department` |
| SAMHSA vs EPA | no | `different_subagency` |
| HHS vs HHS-IHS | no | `subagency_required_but_only_department_supplied` |
| HHS vs HHS | yes | `department_match` |
| EPA vs HHS | no | `different_department` |
| anything vs missing | no | `missing_agency_identifier` |

Two decisions worth their own line:

**A department cannot confirm a program.** If one side names an operating
division and the other only names the department, that is not a match. The
department-level identifier simply does not contain the information needed to
agree.

**Absent never aligns.** An empty identifier returns `missing_agency_identifier`
rather than defaulting to permissive. Aligning on absence is precisely how a
proxy substitution slips through, and the NF-16 guard's own `_agencies_align`
returns `True` when either side is empty — a looseness this contract does not
inherit.

## The IHS/SAMHSA case

Not hypothetical. Gate 77's triage (doc 423) found the live Grants.gov search for
seed `SAMHSA / HHS — AI/AN Zero Suicide & Suicide Prevention` returning
`HHS-2027-IHS-SPIP-0001` from `HHS-IHS`.

IHS and SAMHSA are separate operating divisions with separate appropriations,
separate NOFOs and separate applicant rules. Treating "both are HHS" as alignment
would have attributed one agency's grant to another agency's source silently.

The NF-16 `assert_source_program_ownership` guard refuses it, and **Gate 77 did
not weaken that guard** — a test asserts `CrossProgramProxyError` still exists and
still raises.

## Completeness rules

**Incomplete is incomplete, not approximately complete.** Separate from blocked,
so a reviewer can tell "we lack information" from "we are not permitted".

Incomplete when:

```text
no_agency                                     no agency and no subagency
subagency_required_for_agency_specific_source agency_nofo_page, agency_program_page,
                                              native_specific_federal_program_page,
                                              agency_rss_feed
no_source_url
no_provenance_url
```

Government-wide families (`grants_gov`, `federal_register`,
`sam_gov_assistance_listing`) do **not** require a subagency — they span every
department, and demanding one would be wrong.

## Monitoring rules

`monitoring_allowed` requires all three:

1. `promotion_status` in `{approved_for_monitoring, monitoring}`
2. Robots/terms cleared — only `reviewed_allowed` and
   `reviewed_allowed_with_rate_limit` qualify
3. The record is complete

A source marked `monitoring` that fails any of these gets an explicit
`marked_monitoring_but_not_eligible` blocker rather than a silent downgrade.

## Coverage and freshness rules

`counts_toward_coverage` requires completeness **and** provenance.

`freshness_claimable` is simply whether `last_checked_at` exists. An invariant
fails any record claiming freshness without a check timestamp — the same rule as
Gate 76, restated here because a federal source is exactly the kind of thing
someone would assume is fresh because the agency is reliable.

## Invariants

```text
federal_source_left_the_federal_lane
monitoring_from_non_monitoring_status
monitoring_without_cleared_terms
monitoring_an_incomplete_source
coverage_credit_without_provenance
freshness_claimable_without_a_check_timestamp
agency_specific_source_complete_without_a_subagency
forbidden_claim:coverage_claimed
forbidden_claim:live_ingestion_claimed
```

## Not done here

No fetching, no persistence, no migration. The registry contract from Gate 76
supplies robots/terms vocabulary; this module reuses it rather than forking it.
