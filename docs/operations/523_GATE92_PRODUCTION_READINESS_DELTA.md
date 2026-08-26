# 523 — Gate 92: production readiness delta

Supersedes doc 515 (Gate 91) as the current readiness position.

## Readiness is unchanged

| | Gate 91 | Gate 92 |
| --- | --- | --- |
| controlled customer pilot | NO_GO | NO_GO |
| production rollout | NO_GO | NO_GO |
| login live | no | no |
| production storage | no | no |
| customer persistence | no | no |
| pen-test passed | no | no |
| live source coverage | none | none |
| sources monitored | 0 | 0 |
| collectors built | 0 | 0 |

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

A test asserts all of it after Gate 92. This gate is the one most likely to be
mistaken for corpus improvement — 381 researched sources landed in the
repository — so the assertion matters more here than it did after Gate 91.

**381 sources in a registry is not 381 sources monitored, and it is not one
additional opportunity in the corpus.** The corpus is the same 185 records it
was at Gate 85.

## What Gate 92 built

Seven contract services and their invariants:

```text
external_source_registry_v2_reconciliation_service   v2 supersedes v1, nothing deleted
source_spine_build_plan_service                      Phase 1 spine, no collector built
opportunity_identity_versioning_service              L1-L4 identity, immutable versions
native_eligibility_code_classification_service       graded recall over 07|11|08|99|25
opportunity_deadline_and_amendment_model_service     5 deadline shapes, 7 amendment categories
source_crawler_governance_service                    UA, pacing, blacklist, dead shells
sc_native_recognition_and_geography_service          3 SC sets, deny-by-default geography
```

Plus additive extensions to the Gate 90 importer and seed service, which fixed
two real defects (doc 516).

130 tests in `tests/test_gate92_v2_source_registry_spine.py`.

## What is still not true

Everything in this gate is a contract over data that already exists in the
repository. Specifically, none of the following happened:

- No URL was fetched. `urls_fetched` is 0 across every service in the gate.
- No collector was built. All five spine sources read `collector_status:
  not_built` with at least one activation blocker each.
- No monitoring started. `monitoring_started` is False everywhere.
- No free text was screened. The `requires_reading` backlog is counted, not
  resolved.
- No customer eligibility was determined. Classification says what an
  opportunity allows, never who qualifies.

## Blockers before Phase 1 collection can begin

Ordered by what blocks soonest:

1. **SAM.gov role.** 10 requests/day without one makes the ALN lane unusable.
   Obtaining the role is a prerequisite, not an optimization.
2. **Grants.gov attribution surface.** The verbatim notice must appear on any UI
   using the API. Listed as an activation blocker on both Grants.gov sources.
3. **Legal sign-off on 148 `TERMS_REVIEW_REQUIRED` and 10 `HUMAN_REVIEW_ONLY`
   sources.** Enforced by flag, not convention — those seeds cannot be
   activated while the flag stands.
4. **Four SPA terms pages** (grants.gov, regulations.gov, usaspending.gov,
   reporter.nih.gov) whose policy text could not be retrieved automatically. "No
   terms found" is not "no terms exist"; a human must open them in a browser.
5. **The Simpler.Grants.gov tribal `applicant_type` enum**, undocumented and
   recoverable only from the live Swagger. Also: keys auto-disable after 30 days
   unused, so a heartbeat is required before provisioning one.

Items 3–5 are decisions to escalate, not engineering work.

## One item carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design, still awaiting approval of a filled attestation.
Gate 92 did not touch it.
