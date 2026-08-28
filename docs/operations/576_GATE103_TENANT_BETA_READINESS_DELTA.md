# 576 — Gate 103G/H: tenant beta readiness delta

## Two questions, two answers

```text
ready_for_demo              true   contract demo against demo-safe fixtures
ready_for_beta_onboarding   false  four components missing
```

The first is true today. The second is not, and the gap is not small:

```text
live_source_collection_available  false
email_delivery_available          false
customer_auth_live                false
customer_persistence_live         false
```

Conflating them is how a working demo becomes a signed contract for something
that does not exist. They are separately derived, and an invariant fails any
result reaching onboarding readiness without every component behind it.

## Demo readiness is scoped, and the scope travels with it

`demo_scope` is `contract_demo_against_demo_safe_fixtures`. It means the
contracts work against fixtures. It does **not** mean live matching, live
digests, or real tenant data work, because none of those exists.

The scope is a field rather than a footnote so `ready_for_demo: true` cannot be
quoted without it, and an invariant fails a ready result missing its scope.

## What the gate delivered

```text
tenant_profiles_available              true    103B
tenant_feature_entitlements_available  true    103C
tenant_source_priority_available       true    103D
demo_fixtures_available                true    103E
allowability_review_available           true    103F
awarded_grants_contract_available      true    reused from Gate 91-era work
reporting_tracking_contract_available  true    reused
digest_contract_available              false   Gate 104
pursuit_suppression_contract_available false   Gate 104
```

Seven of nine present. The two absent are Gate 104's, and the readiness reports
them as absent rather than anticipating them.

## Boundaries unchanged

```text
source_monitoring_live       false
live_source_coverage         false
collectors_active            0
production_rollout           false
controlled_customer_pilot    false
sources_active               0    (across all 360 in-scope registry rows)
```

Every tenant feature in this gate is fixture-backed. Nothing was activated, no
URL was fetched, no message was sent, and no fact about any real Tribe was
invented.

## 103H artifacts

`artifacts/tenant_beta_feature_contract/`

```text
tenant_beta_feature_contract.json
tenant_beta_feature_matrix.csv          44 rows - 4 tenants x 11 features
tenant_source_priority_matrix.csv       20 rows - 4 tenants x 5 tiers
tenant_beta_demo_profiles.json
software_capacity_allowability_contract.json
tenant_beta_readiness_summary.md
```

Seven declarations on every file and every CSV row:

```text
tenant_beta_contract_available    true
ready_for_demo_contract           true
ready_for_beta_onboarding         false
live_source_collection_available  false
email_delivery_available          false
source_monitoring_live            false
live_source_coverage              false
```

The source matrix is per **tier**, not per source. Four tenants against 360
in-scope sources would be 1,440 rows of near-identical content; 20 rows say the
thing that matters — *this tenant gets 57 SC sources first, that one gets none,
and every tier has zero active collectors.*

The writer refuses rather than annotates. It rejects a forged declaration, a
fixture naming a real Tribe, and a self-assessed allowability example that
escaped the cap. Artifacts regenerate deterministically and a test compares the
committed bytes against a fresh generation.

## Testing

125 tests. **Twenty mutations introduced, twenty caught** — no misses, which
breaks a four-gate run of untestable-conjunct findings. The mutations that
mattered most:

```text
NativeForge self-assessment cap removed        caught
affirmative label without evidence allowed     caught
fixture fabricates recognition status          caught
fixture facts claimed as verified              caught
real-Tribe token list emptied                  caught
SC tier applied regardless of tenant state     caught
enabling the watchlist asserts monitoring      caught
```

## Two gaps found while linting

Ruff surfaced two unused imports that were real gaps rather than tidiness:

- The artifact writer imported `source_priority_invariant_failures` and never
  called it, so source priority results went unvalidated. Fixed by validating
  them in `build_tenant_beta_bundle`, **before** the rows are stripped for the
  summary — checking afterwards would fail on the missing rows and say nothing.
- The review service imported Gate 92's `ALLOWABILITY_CLASSES` without using it.
  Now load-bearing via `bridge_coverage_gaps()`, which distinguishes a Gate 92
  class with no mapping (drift, a bug here) from a string that was never a Gate
  92 class at all.

## Where this leaves the product lane

```text
103  tenant beta feature contract          done
104  digest + pursuit suppression          next - both genuinely greenfield
105  awarded grants requirement tracking   extends existing service
106  Grants.gov scaffold, fixture/dry-run
107  tenant match engine
108  demo tenant seed pack
109  customer-facing demo
110  demo hardening + pricing page
```

Doc 570's three flagged tensions are unchanged and all land in Gate 104:
change detection needs a time series that no amount of contract work supplies;
deadline confidence is uneven and the digest must consume
`deadline_provenance_service` rather than raw dates; and the allowability
self-assessment cap — recommended in 570, implemented here.
