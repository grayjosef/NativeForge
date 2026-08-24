# 435 — Gate 78C: SC Native routing contract

`src/nativeforge/services/sc_native_routing_service.py`. Routes an opportunity
for a South Carolina Native organization while keeping three things apart that
are easy to collapse.

## Lane: distinct but joinable

```text
funding_lane: sc_state | federal_sc_relevant | local_regional | foundation | unknown
```

`STATE_LANES` and `FEDERAL_LANES` are disjoint sets, and an invariant fails an
opportunity claiming both.

**A federal opportunity relevant to SC keeps `funding_lane="federal_sc_relevant"`
and its federal agency, and still sets `sc_relevant=True`.** That flag is the
join: the customer sees one list spanning both lanes, while the coverage counts
stay separable.

Enforced:

- `sc_state` lane + a federal agency → **blocked**
- `sc_state` lane + a non-SC state → **blocked**
- `federal_sc_relevant` naming a state agency but no federal agency → flagged for
  review

## Recognition tier: independent

```text
federally_recognized | state_recognized | native_nonprofit | native_business | unknown
```

A set, preserved as supplied, with no inference between members. Bridged onto
Gate 56's `RECOGNITION_ROUTES`; only `native_business` differs in name
(`native_business_economic_development`), and a test asserts every tier projects
into the existing vocabulary.

South Carolina has state-recognized tribes. A federal program open to federally
recognized tribal governments may be closed to them, and an SC state program may
be the reverse. Treating the tiers as interchangeable would produce confident
wrong answers in both directions.

## Sector: many, not one

```text
housing health education workforce culture infrastructure
economic_development environment public_safety general_government unknown
```

An opportunity may carry several — a tribal housing programme with a workforce
component is both, and forcing a single value would discard whichever lost.

Bridged onto Gate 56's `SC_CATEGORIES`: `culture` → `culture_language`,
`environment` → `environment_natural_resources`. `general_government` has no
Gate 56 category and maps to `unknown` rather than being forced into a
neighbour.

Unrecognised sectors and tiers are surfaced for review rather than dropped.

## Eligibility: neither location nor relevance

The two facts this module is best at establishing are explicitly **not**
eligibility:

| Input | Recorded as |
| --- | --- |
| `sc_location_relevant=True` | `sc_location_relevance_is_not_eligibility` |
| `native_relevance_evidenced=True` | `native_relevance_evidence_is_not_eligibility_by_itself` |

Both are accepted as inputs specifically so the refusal appears in the output. A
grant can be located in South Carolina, be unmistakably about Native
communities, and still restrict applicants to state agencies or universities.

### Resolution

```text
tier-mapped explicit evidence           → that tier: eligible
general applicant list / funder /
  operator confirmation, no tier named  → possibly_eligible + human review
otherwise                               → unknown
```

Evidence needs a recognised kind **and** a non-empty reference. Each tier is
credited only by evidence mapped to it — an invariant fails
`tier_eligible_without_tier_evidence`.

`unknown` stays `unknown`. This module never asserts ineligibility.

**Why this rule is strict.** Telling a tribal organization they are eligible for
something they are not costs them weeks of unpaid application work, and a grant
office that learns the product overstates eligibility stops trusting all of it.

## Invariants

```text
funding_lane_invalid
opportunity_in_both_state_and_federal_lanes
state_lane_carries_a_federal_agency
sector_invalid:<sector>
recognition_tier_invalid:<tier>
tier_eligible_without_tier_evidence:<tier>
eligible_without_any_evidence
eligibility_asserted_without_evidence
opportunity_hidden_instead_of_marked
forbidden_claim:coverage_claimed
```

## Visibility

`visible: True` always, including blocked records. A blocked opportunity is
still a record of something found, and hiding it would make the gaps invisible.

## Not done here

No opportunity data. This routes records it is given; nothing fetches or parses
them. The NOFO parser is Gate 81.
