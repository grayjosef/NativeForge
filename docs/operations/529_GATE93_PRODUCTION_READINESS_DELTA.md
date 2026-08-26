# 529 — Gate 93: production readiness delta

Supersedes doc 523 (Gate 92) as the current readiness position.

## Readiness is unchanged

| | Gate 92 | Gate 93 |
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
| collectors active | 0 | 0 |

**No collectors were activated. No URLs were fetched. No live coverage is
claimed. SAM.gov scraping remains prohibited. Phase 1 collection remains blocked
until preflight passes.**

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

## What Gate 93 built

Six contract services, and one runtime wiring:

```text
source_activation_preflight_service        deny-by-default activation decision
grants_gov_attribution_service             verbatim notice, customer-visible
phase1_collector_activation_policy_service five sources, all not_active
raw_payload_store_contract_service         16 fields, store not implemented
source_terms_review_queue_service          185-item work list, all pending
phase1_readiness_artifact_service          six artifacts, refuses false claims

trust_surface_service + TrustCenterCard    the attribution, actually rendered
```

120 tests in `tests/test_gate93_phase1_collector_readiness.py`.

## Phase 1 activation matrix

Every source is `not_active` and every source is missing preconditions — the raw
payload store does not exist, so nothing can pass yet:

```text
grants_gov_daily_extract      preflight, attribution, payload store, retention alert
grants_gov_search2_fetch      preflight, attribution, payload store, amendment materiality
federal_register_api          preflight, payload store, cadence, public inspection
sam_assistance_listings_api   preflight, payload store, api key, role+rate limit, no-scraping ack
usaspending_api_v2            preflight, payload store, prior-award-only classification
```

## One defect found and fixed

**A collector type could exempt itself from its own requirement.** The first
preflight implementation let `not_required` satisfy any requirement, so a
`public_api_with_key` collector declaring `credential_status: not_required` and
an `html_crawler` declaring `user_agent_status: not_required` both reached
`activation_allowed`. Caught by the service's own smoke test before any test
file existed. Fixed so a mandated requirement accepts only its affirmative
value, with two invariants added.

## The survey's most important finding, and what it means

**Three of four live-HTTP call sites in `src/` bypass every gate.** Gate 77B
built a real deny-by-default choke point and wired it to the Grants.gov path
only:

```text
GUARDED    grants_gov_search_api_adapter_service.py:51
UNGUARDED  polite_http_fetch_service.py:49  (robots.txt)
UNGUARDED  polite_http_fetch_service.py:90  (polite_http_get, 5 live callers)
UNGUARDED  real_url_resolver_service.py:82
```

`polite_http_get` also predates Gate 92 and contradicts its governance in four
ways: a 2.0s interval against a 5.0s floor, a second user-agent string, a
**robots fail-open** (missing robots.txt reads as permissive), and no host
blacklist or circuit breaker.

Gate 93 did **not** close these. That is a code change to shared modules with
five live callers and its own regression surface, and folding it into a
contracts gate would mean shipping it with less scrutiny than it warrants. It is
recorded as survey finding #5 and is the top-ranked follow-up below.

This is worth stating plainly: **Gate 93 makes it impossible to activate a Phase
1 collector accidentally, but it does not make it impossible to issue an HTTP
request from this codebase.** Those are different claims and only the first one
is true today.

## Blockers before Phase 1 collection can begin

```text
1  raw payload store implementation      required by all five sources
2  close the three unguarded fetch paths route them through one choke point
3  SAM.gov API key + role                10/day without it is unusable
4  185 queue items reviewed              148 terms + 62 human-only + 4 SPA + 1 SAM
5  four SPA terms pages read by a human  "no terms found" is not "no terms exist"
6  Simpler.Grants.gov tribal enum        undocumented; needs the live Swagger
7  scheduler + breaker wiring            columns exist, nothing reads them
```

Items 3–6 are decisions and human work, not engineering.

## Carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design, still awaiting approval of a filled attestation.
Gate 93 did not touch it.
