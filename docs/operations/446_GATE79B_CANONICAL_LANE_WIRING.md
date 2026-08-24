# 446 — Gate 79B-B/C: Canonical lane wiring

## What was wired

Two services now consume `opportunity_funding_lane_service` as the canonical
source of an opportunity's funding lane.

| Service | Parameter added | Effect |
| --- | --- | --- |
| `sc_native_routing_service.route_sc_opportunity` | `canonical_funding_lane` | overrides the caller's `funding_lane`; projects via `sc_routing_lane()` |
| `native_opportunity_discovery_service.build_native_opportunity_record` | `canonical_funding_lane` | overrides `lane`; projects via `discovery_lane()` |

**The canonical lane overrides the caller's.** A lane derived from
funding-origin evidence outranks one passed in — that is the entire Gate 79
correction, and honouring the caller instead would leave the defect in place.

Both parameters are keyword-only and optional. Omitted, behaviour is exactly as
before: asserted by explicit backward-compatibility tests and by 343 pre-existing
gate tests passing unchanged.

## Which old vocabularies remain

Both, as compatibility projections. Neither deleted.

```text
opportunity_funding_lane_service.FUNDING_LANES   8 values   CANONICAL
sc_native_routing_service.FUNDING_LANES          5 values   projection target
native_opportunity_discovery_service.LANES       5 values   projection target
source-level "lane" strings                                 correct as-is
```

The source-level strings are **not** a defect. An SC agency page is an SC
source; a federal agency page is a federal source. Gate 79's correction was that
an *opportunity* must not inherit its source's lane, and it does not.

Deleting either projection target would break tests that pin their exact
membership. That is a separate breaking change and is recorded as
engineering-blocked in doc 448.

## Where the projection is lossy

`federal_pass_through` has no member in either older vocabulary:

```text
federal_pass_through → sc_native_routing_service:            federal_sc_relevant
federal_pass_through → native_opportunity_discovery_service: federal
```

Both land on federal. **Neither lands on a state value**, which is the property
that matters and the one under test in both directions:

- no lane in `FEDERALLY_FUNDED_LANES` projects to `sc_state` or `state`;
- **only** `sc_state` projects to a state value in either vocabulary.

The loss is recorded rather than hidden. Each record carries:

```python
"canonical_funding_lane": "federal_pass_through",
"lane_projection": {"canonical_funding_lane": ..., "projected_lane": ...,
                    "lossy": True},
"lane_projection_lossy": True,
```

and the routing service adds a review reason
`lossy_lane_projection:federal_pass_through->federal_sc_relevant`. Someone
reading an old view is told the distinction existed upstream.

## Invariants added

```text
sc_native_routing_service:
  federal_canonical_lane_projected_onto_a_state_lane
  federal_pass_through_projected_to_sc_state

native_opportunity_discovery_service:
  federal_canonical_lane_projected_onto_state
  class_both_eligible_and_excluded:<classes>
  excluded_opportunity_hidden_instead_of_marked
```

An unrecognised canonical lane is refused (`unknown` + a review reason), never
guessed at.

## Exclusion evidence in the discovery record

`build_native_opportunity_record(..., exclusion_result=...)` accepts the output
of `evaluate_all_applicant_classes` and surfaces:

```python
"excluded_classes": [...], "eligible_classes": [...],
"has_exclusion_evidence": bool,
```

with a review reason `excluded_by_evidence_for:<classes>`.

Three properties are enforced:

- **Per class.** A state-recognized exclusion leaves
  `federally_recognized_tribe` in `eligible_classes`.
- **Never hidden.** `visible` stays `True`; an invariant fails a hidden excluded
  record.
- **Citation-required.** An exclusion evaluated without a reference yields no
  excluded classes at all, so an uncited exclusion cannot reach the record.

Gate 76's rules survive the wiring, and are re-tested here: Native relevance
still does not imply eligibility, and a keyword-only match still earns no
relevance credit.

## Drift guards

A test scans every service for a `FUNDING_LANES` declaration and asserts exactly
two files declare one. A third fails the suite by name.

### A naming collision found by that guard

The first version of the guard also matched bare `LANES` and immediately caught
a fourth file — `source_seed_catalog.LANES`. That turned out **not** to be lane
drift:

```python
source_seed_catalog.LANES = ("federal", "south_carolina", "expansion")
```

Those are **seed catalog groupings**, not funding lanes. `south_carolina` and
`expansion` are not funding classifications at all, and only the word `federal`
overlaps.

The guard was split rather than loosened: one test pins the funding-lane
vocabularies, a second pins the two unrelated users of the bare name `LANES` and
asserts the seed groupings stay disjoint from `FUNDING_LANES`. A genuinely new
declaration of either still fails.

The collision is worth knowing about: two constants named `LANES` in the same
package meaning entirely different things is a trap for the next reader.

## What still needs primary-source verification

Nothing in this wiring verifies any SC claim. The machinery to classify a lane
and publish an exclusion now exists and is in the path; the Gate 78R eligibility
strings remain `eligibility_verified: false`, and the pass-through
classifications rest on evidence captured from index pages rather than primary
notices.

No source is seeded, monitored or fetched. See doc 448.
