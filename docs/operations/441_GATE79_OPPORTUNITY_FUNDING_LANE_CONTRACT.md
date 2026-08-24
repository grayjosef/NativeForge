
# 441 — Gate 79B: Opportunity funding lane contract

`src/nativeforge/services/opportunity_funding_lane_service.py`

## The rule

**Funding lane follows the money, not the masthead.**

Lane is assigned **per opportunity, from funding-origin evidence** — not
inherited from the source that published it.

## Why the source-level rule was wrong

Gate 78 assigned lane by source ownership. That is right for a source: an SC
agency page is an SC source. It is wrong for an opportunity, and Gate 78R found
five live counterexamples in South Carolina alone:

| Source | Programme | Federal funder | Old lane | New lane |
| --- | --- | --- | --- | --- |
| SCEMD | HMGP, 75/25 cost share | FEMA | `sc_state` | `federal_pass_through` |
| SCOR | CDBG-MIT; Solar for All | HUD; EPA | `sc_state` | `federal_pass_through` |
| SCDES | §319 Nonpoint Source | EPA | `sc_state` | `federal_pass_through` |
| SC Housing | LIHTC | Treasury/IRS | `sc_state` | `federal_pass_through` |
| SCDE | mixed federal/state/private | various | `sc_state` | `unknown` + review |

Gate 78 stopped federal opportunities being relabelled as state ones by
**geography**. Nothing stopped it happening by **administration** — and
`sc_native_routing_service` actively *rejected* an `sc_state` record naming a
federal agency, so the honest representation was invalid.

The consequence was specific: a customer shown federal money, with federal
strings and often federal-recognition eligibility rules, described as a state
programme — and both coverage counts wrong at once.

## Lanes

```text
sc_state              state-funded, cited
federal               federally funded
federal_pass_through  federally funded, state-administered
federal_sc_relevant   federally funded, relevant to SC
local_regional        county / municipal / COG
foundation            private philanthropic
corporate             corporate giving
unknown               no evidence, or mixed
```

Grouped so "is this federal money" is one membership test rather than a string
comparison scattered around — the looseness that let pass-through look like state
funding:

```text
FEDERALLY_FUNDED_LANES = {federal, federal_pass_through, federal_sc_relevant}
STATE_FUNDED_LANES     = {sc_state}
PRIVATE_FUNDED_LANES   = {foundation, corporate}
```

A test asserts these partition `FUNDING_LANES` with `local_regional` and
`unknown`.

## Three things that do not determine the lane

Each is **accepted as input so the refusal appears in the output**, rather than
relying on callers to know it:

| Input | Recorded note |
| --- | --- |
| `.sc.gov` source URL | `sc_gov_source_url_does_not_determine_funding_lane` |
| SC agency administering | `sc_agency_administration_does_not_determine_funding_lane` |
| `source_lane == "sc_state"` | `source_lane_does_not_determine_opportunity_funding_lane` |

## Federal pass-through

`federal_pass_through` = federal funding **and** a state administrator. Both
halves must hold; invariants fail either missing:

```text
pass_through_not_marked_federally_funded
pass_through_without_an_administering_agency
pass_through_flag_without_pass_through_lane
```

Detection is positive: a `federal_agency` field, a `federal_pass_through_to_state`
origin, or a federal-funder token in the evidence text
(`fema`, `hud`, `epa`, `cdbg`, `hmgp`, `lihtc`, `cost share`, `subrecipient`, …).
The token list is deliberately not exhaustive — anything unmatched falls through
to `unknown`, never to `sc_state`.

### Why this matters for recognition routing

Federally recognized tribes are frequently *direct* applicants to federal
programmes, bypassing the state. State-recognized tribes are ineligible for many
federal tribal programmes entirely and may only reach the money as a state
subrecipient, if at all. Mislabelling pass-through money would misroute the
highest-value opportunities for both groups in opposite directions.

## `sc_state` requires a citation

The one lane that cannot be inferred. State-funding tokens
(`state appropriation`, `general assembly`, `state trust fund`, …) plus a
**cited** `evidence_url` are both required. Without the citation the lane is
`unknown` with `state_funding_claimed_without_cited_evidence`.

Invariant: `sc_state_lane_without_cited_evidence`.

Federal money can be recognised from a funder name; state money is the claim
someone would make to inflate local coverage, so it carries the higher bar.

## Mixed funding

`funding_origin="mixed"`, or both federal and state signals present, resolves to
`unknown` with `human_review_required`. Neither origin is discarded and nobody
guesses which dominates.

Invariants: `mixed_funding_origin_resolved_to_a_confident_lane`,
`mixed_funding_origin_without_human_review`.

SCDE is the real case — one page carrying "federal, state, and privately funded"
opportunities.

## Unknown

The default. `no_funding_origin_evidence` sets `unknown` and
`human_review_required`. There is no path from absent evidence to a confident
lane, and specifically none to `sc_state`.

## Bridging, not forking

Doc 440 found the codebase already had **three** disagreeing lane vocabularies.
Gate 79 adds the canonical opportunity-level set and projects onto both existing
ones:

```python
sc_routing_lane(lane)  # → sc_native_routing_service.FUNDING_LANES
discovery_lane(lane)   # → native_opportunity_discovery_service.LANES
```

Tests assert both projections are total over `FUNDING_LANES` and that every
result lands inside the older vocabularies.

**One projection is lossy, and recorded as such.** `federal_pass_through` maps to
`federal_sc_relevant` in the SC routing vocabulary, because that set's only
federal member is the SC-relevant one. It never lands on a state value — a test
asserts that specifically.

## Invariants

```text
federal_money_marked_state_funded
sc_state_lane_marked_federally_funded
sc_state_lane_carries_a_federal_agency
sc_state_lane_with_federal_funder_evidence
sc_state_lane_without_cited_evidence
pass_through_not_marked_federally_funded
pass_through_without_an_administering_agency
mixed_funding_origin_resolved_to_a_confident_lane
sc_routing_lane_projection_invalid
discovery_lane_projection_invalid
forbidden_claim:coverage_claimed
forbidden_claim:live_ingestion_claimed
```

## Not done here

Not yet wired into `sc_native_routing_service` or
`native_opportunity_discovery_service`; their local lane vocabularies remain and
are bridged rather than retired. Recorded as engineering-blocked in doc 444.
Nothing fetched, nothing seeded, no coverage claimed.
