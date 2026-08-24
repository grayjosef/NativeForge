# 447 — Gate 79B-D: Exclusion evidence in discovery scoring

## The mismatch doc 445 found

**Exclusion is per applicant class. The Gate 54 scorer was per opportunity.**

`opportunity_discovery_quality_service` is the only one of the seven quality
services that scores opportunity coverage, and it asked one question per
opportunity: is eligibility evidenced? An opportunity that requires federal
recognition answers yes — and then counted as eligible coverage for a
state-recognized tribe it excludes.

That is the failure mode Gate 79 was built to stop, still live in the scorer.

## What changed

`build_discovery_quality_score` gained a keyword-only `applicant_class`.

```python
def _excluded_for_class(o: dict[str, Any]) -> bool:
    if not applicant_class:
        return False
    return applicant_class in (o.get("excluded_classes") or [])
```

`eligibility_evidenced` gained `and not _excluded_for_class(o)`. Nothing else in
the count changed.

Same opportunity, three views:

```text
applicant_class=None                        eligibility score 1.0   (unchanged)
applicant_class=state_recognized_tribe      eligibility score 0.0   + 1 negative intelligence
applicant_class=federally_recognized_tribe  eligibility score 1.0
```

One opportunity, two correct and different answers for two customers in the same
state. A model that collapsed the recognition tiers could not produce that.

## Excluded is not deleted

The instruction was explicit, and it is the right call: an excluded opportunity
is the **most actionable** thing this product can currently tell an SC
state-recognized tribe — *this programme requires federal recognition, here is
the sentence, do not spend a week on it.* Deleting it would throw that away and
leave the customer to rediscover the exclusion themselves.

So:

| Field | Effect of exclusion |
| --- | --- |
| `opportunity_count_raw` | unchanged |
| `opportunity_count_unique` | unchanged |
| `eligibility_evidence_score` | **reduced** |
| `excluded_for_class_count` | +1 |
| `negative_intelligence_count` | +1 |
| record `visible` | stays `True` |

Only *eligible coverage* moves. The corpus does not shrink, and the discovery
record stays visible with its excluded classes and citation attached.

## Invariants

```text
excluded_for_class_count_invalid
negative_intelligence_count_disagrees_with_exclusions
exclusions_counted_without_an_applicant_class
forbidden_claim:excluded_counted_as_eligible_coverage
```

The third is the deny-by-default one: a result that reports exclusions without
naming the class it excluded them for is incoherent and fails.

`excluded_counted_as_eligible_coverage: False` is a hardcoded published claim,
matching the existing `unknown_eligibility_counted_as_eligible` pattern. It
cannot silently become true — flipping it fails the invariant check.

## Boundaries this does not cross

- **No ineligibility is invented.** Only classes that
  `eligibility_exclusion_evidence_service` excluded *with a citation* reach
  `excluded_classes`. An uncited exclusion produces none, so it cannot reach the
  scorer at all.
- **`not_supported_by_evidence` is not exclusion.** Absent evidence lowers
  confidence; it does not exclude, and does not reduce coverage.
- **The class must be named.** No class supplied means no exclusion applied, so
  no existing call site changes behaviour.

## Still to do

`applicant_class` is threaded no further than the call. Scoring per *customer*
means resolving the class from an org profile at the call site, which is
engineering-blocked and recorded in doc 448.

And the exclusions themselves are only as good as their sources: the Gate 78R
eligibility strings are still `eligibility_verified: false`, read from index
pages rather than primary notices. The machinery to publish an exclusion now
exists; no customer-facing exclusion should rest on that evidence until it is
verified against the primary notice.
