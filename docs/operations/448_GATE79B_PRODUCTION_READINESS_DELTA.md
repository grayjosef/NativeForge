# 448 — Gate 79B-G: Production readiness delta

Gate 79 built the corrections. Gate 79B wired them into the services that needed
them. Nothing was fetched, nothing seeded, no coverage claimed.

## Canonical funding lane: now

| | Before | After |
| --- | --- | --- |
| Canonical lane used by SC routing | no | **yes**, overrides the caller's lane |
| Canonical lane used by discovery | no | **yes** |
| `federal_pass_through` expressible downstream | no | yes, projected and marked lossy |
| Federal money reachable in a state lane | possible | **impossible**, invariant-enforced in both |
| Source lane overriding opportunity lane | possible | refused |

The three Gate 78R pass-through sources now route end to end without ever
touching a state lane:

```text
SCEMD  + FEMA HMGP  → federal_pass_through → federal_sc_relevant / federal
SCOR   + HUD CDBG   → federal_pass_through → federal_sc_relevant / federal
SCDES  + EPA §319   → federal_pass_through → federal_sc_relevant / federal
```

## Old vocabulary status

**Both retained as compatibility projections. Neither deleted.**

| Vocabulary | Status |
| --- | --- |
| `opportunity_funding_lane_service.FUNDING_LANES` (8) | canonical |
| `sc_native_routing_service.FUNDING_LANES` (5) | compatibility projection |
| `native_opportunity_discovery_service.LANES` (5) | compatibility projection |
| source-level `"lane"` strings | **correct as-is** — a source's lane is not an opportunity's |

Deleting either would break tests that pin their exact membership, and is a
separate breaking change. Doc 445 records why.

A drift guard scans every service for a `FUNDING_LANES` declaration and asserts
exactly two files declare one. A third fails the suite by name.

A second guard pins the bare name `LANES`, which is declared twice for two
unrelated concepts: opportunity funding lanes in
`native_opportunity_discovery_service`, and **seed catalog groupings**
(`federal` / `south_carolina` / `expansion`) in `source_seed_catalog`. The seed
groupings are not funding classifications and the guard asserts they stay
disjoint from `FUNDING_LANES`. Doc 446 records the collision.

### Where the projection is lossy

`federal_pass_through` has no member in either older set and lands on
`federal_sc_relevant` / `federal`. **Neither lands on a state value** — that is
the property under test, in both directions: no federal lane reaches a state
value, and only `sc_state` reaches one.

The loss is recorded on the record (`lane_projection`, `lane_projection_lossy`)
and surfaced as a review reason, so nobody reads an old view and concludes the
distinction was never there.

## Exclusion evidence scoring: now

The structural mismatch doc 445 identified: **exclusion is per applicant class,
the Gate 54 scorer was per opportunity.** An opportunity scored without naming
the class counted as eligible coverage for a customer it excludes.

`build_discovery_quality_score(..., applicant_class=...)` makes coverage
class-aware. Same opportunity, three views:

```text
applicant_class=None                        eligibility score 1.0   (unchanged)
applicant_class=state_recognized_tribe      eligibility score 0.0   + 1 negative intelligence
applicant_class=federally_recognized_tribe  eligibility score 1.0
```

**Excluded opportunities remain visible and remain in the corpus.** Raw and
unique counts are untouched; only *eligible coverage* changes. An excluded
opportunity is negative intelligence — "this one requires federal recognition,
here is the sentence" — which is useful, and deleting it would throw away the
most actionable thing this product can currently tell an SC state-recognized
tribe.

Invariants: `exclusions_counted_without_an_applicant_class`,
`negative_intelligence_count_disagrees_with_exclusions`,
`forbidden_claim:excluded_counted_as_eligible_coverage`.

## Backward compatibility

Every wiring parameter is keyword-only and optional. Omitting it reproduces the
previous behaviour exactly — asserted by three explicit tests, and by 343
pre-existing gate tests passing unchanged.

## Live coverage status

**Unchanged.**

```text
Live SC source coverage:   NONE
Live federal coverage:     NONE
Sources monitored:         0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

Gate 79B wired contracts. It identified no source, fetched nothing, and seeded
nothing. The Gate 77B hermetic guard and the Gate 78E write-back guards are
untouched, asserted by a test.

## Native customer value

The chain now works end to end for the case Gate 78R found:

1. A federal programme published on an SC state domain is classified
   `federal_sc_relevant`, not `sc_state`.
2. Its cited eligibility excludes state-recognized tribes, with the sentence
   attached.
3. It does not count as eligible coverage for a state-recognized tribe.
4. It **does** count as eligible coverage for the Catawba Nation.
5. It stays visible to both, as negative intelligence for one and an opportunity
   for the other.

That is a single opportunity producing two correct, different answers for two
customers in the same state — which is what the recognition split actually
requires and what a collapsed model could never do.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources.
- **Primary-source verification** of the Gate 78R eligibility strings. The
  machinery to publish an exclusion now exists; the SC claims are still
  unverified, and the fixture says so on every line. No customer-facing exclusion
  should rest on a summarised read of an index page.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- Retiring the two compatibility vocabularies once their tests are rewritten.
- Threading `applicant_class` from a customer's org profile into the scorer, so
  coverage is scored per customer rather than per call site.
- NOFO parsing (Gate 81) to extract eligibility text rather than accept it.
- Scheduler (Gate 80) — still correctly blocked; zero sources are terms-cleared.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: the corrections are no longer contracts sitting beside
the code — they are in the path. Federal money administered by an SC agency
cannot reach a state lane through any route, and an opportunity that excludes a
customer's applicant class can no longer be counted as coverage for them.
