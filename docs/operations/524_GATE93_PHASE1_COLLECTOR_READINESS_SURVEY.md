# 524 — Gate 93A: Phase 1 collector readiness survey

Surveyed before building, because the gate's purpose is to make accidental
activation impossible, and you cannot block a path you have not found.

## The headline finding

**There are four live-HTTP call sites in `src/`. One is guarded. Three are not.**

```text
GUARDED
src/nativeforge/services/grants_gov_search_api_adapter_service.py:51
  default_grants_gov_http_post
  -> calls assert_live_network_allowed() first (Gate 77B)
  -> raises LiveNetworkBlockedError unless
     NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1

UNGUARDED
src/nativeforge/services/polite_http_fetch_service.py:49   robots.txt fetch
src/nativeforge/services/polite_http_fetch_service.py:90   polite_http_get
src/nativeforge/services/real_url_resolver_service.py:82   default_real_http_fetch
```

Gate 77B built a real deny-by-default choke point and wired it to the Grants.gov
path only. Gate 82 found the same three modules in its own survey and responded
by forbidding *Gate 82's* modules from importing them — a local fix that left the
hole open for everything else.

`polite_http_get` has five live callers today:

```text
state_tribal_affairs_html_adapter_service.py:157, 192
tier3_foundation_batch_live_fetch_service.py:73
foundation_fluxx_embed_adapter_service.py:90
foundation_html_listing_adapter_service.py:171
```

None of them consults the hermetic guard, the Gate 92 crawler governance
service, or any activation flag.

## The polite fetcher contradicts Gate 92 governance in four ways

`polite_http_fetch_service` predates Gate 92 and was written to a different, more
permissive standard:

| | polite fetcher | Gate 92 governance |
| --- | --- | --- |
| min request interval | `2.0s` | `5.0s` floor |
| user-agent | `NativeForge/1.0 (+github…)` | `NativeForgeBot/1.0 (+…)` |
| robots.txt unavailable | **returns `True` — fail open** | deny by default |
| host blacklist | none | scdmh.net, scdhec.gov, cdc.gov/tribal |
| circuit breaker | none | 5 failures → halt + page |

The robots fail-open is the sharpest of these. `robots_allows_fetch` returns
`True` when robots.txt is missing, unreachable, or returns >=400 — so a host that
times out reads as permissive.

Both UA strings pass Gate 92's `user_agent_violations` (both identify
NativeForge and carry a URL), so this is a fork rather than a violation — but two
user-agent strings means the one a host sees depends on which module made the
call.

## One default-open parameter

```text
grants_gov_attachment_recoverable_reaudit_service.py:88
    allow_live_fetch: bool = True
```

The call it guards lands on `default_grants_gov_http_post`, so Gate 77B's guard
still stops it. The default is nonetheless backwards: a caller that forgets the
argument opts *into* live fetching.

## Raw payload storage — does not exist

`nf_source_check_runs` records the shape of a check, not its evidence:

```text
check_mode, check_status, started_at, completed_at,
opportunities_seen_count, new_candidates_count, accepted_count,
duplicate_count, rejected_count, review_items_created_count,
error_code, error_message, operator_notes, result_summary_json
```

No raw payload. No payload hash. No response status or headers. No per-payload
`retrieved_at`. No secret-scan status.

The modules that grep for `raw_payload` (`tier1_batch_live_fetch_service`,
`tier2_state_batch_live_fetch_service`, `tier3_foundation_batch_live_fetch_service`,
the three `*_corpus_persist_service` modules) hold response text in local dicts
during a run and persist the *parsed* result. Nothing durable retains the bytes.

This is the same gap Gates 87–89 spent four gates measuring from the other end:
185 corpus records, only 18 with independent transport evidence, because the
evidence was never stored. Building collectors before the payload store repeats
it at 381-source scale.

## Attribution surface — does not exist

The verbatim Grants.gov notice appears in exactly one place in the repository:

```text
src/nativeforge/services/source_spine_build_plan_service.py:45
  GRANTS_GOV_ATTRIBUTION  (Gate 92 constant)
```

`grep -ri "endorsed or certified" frontend/` returns nothing. The string is a
Python constant and a line in three docs. It is not runtime-visible, and it is
not customer-visible.

**The seam that fits.** `trust_surface_service.build_trust_manifest()` produces a
deterministic policy payload, served at `/trust` (`api/trust_routes.py:44,112`)
and rendered by `frontend/src/components/TrustCenterCard.tsx` via `App.tsx:927`.
It already carries `submission_policy`, `ai_training_policy`, `export_policy`.
A `source_attribution` block belongs beside them — that is a runtime payload a
customer's browser actually receives, which is what the requirement means.

## Credential handling — does not exist

No API-key storage, no key rotation, no SAM.gov role model. The only matches for
`api_key` / `credential` in services are prose inside `active_source_activation_m0/m1`
planning packets. SAM.gov needs a key as a query parameter and a role to move
from 10 to 1,000 requests/day, and neither has anywhere to live.

## Scheduler seam — exists, unused for Phase 1

Real and already migrated:

```text
nf_opportunity_sources.check_interval_days
nf_opportunity_sources.next_check_due_at
nf_opportunity_sources.last_check_status / last_check_run_id
nf_opportunity_sources.consecutive_failure_count
nf_opportunity_sources.consecutive_empty_check_count
nf_opportunity_sources.source_health_status
nf_source_check_runs (full table, Alembic 0015)
```

This is where a Phase 1 scheduler attaches later. Nothing populates it for the
v2 registry, and `consecutive_failure_count` exists with no breaker reading it.

## Circuit breaker — contract without a wire

Gate 92's `source_crawler_governance_service.build_circuit_breaker_state` defines
the policy; `nf_opportunity_sources.consecutive_failure_count` is the column that
would feed it. Nothing connects them, and no fetch path increments the column.

## Terms / legal review model — two vocabularies, no queue

```text
Gate 76  source_registry_service.ROBOTS_TERMS_STATUSES
         reviewed_allowed | reviewed_allowed_with_rate_limit |
         reviewed_disallowed | reviewed_requires_agreement |
         unreviewed | unknown

Gate 90  external_source_registry_import_service.terms_status
         NO_REVIEW_REQUIRED | ATTRIBUTION_REQUIRED |
         TERMS_REVIEW_REQUIRED | HUMAN_REVIEW_ONLY
```

Gate 90 bridges onto Gate 76 at its weakest members (`discovered` /
`unreviewed`), so the two coexist without forking. What is missing is the
**work list**: 148 `TERMS_REVIEW_REQUIRED` and 10 `HUMAN_REVIEW_ONLY` rows are
flagged in the registry, but there is no queue, no reviewer, no review status
that can ever change, and no record of the four SPA terms pages whose text could
not be retrieved.

## Existing activation-gate patterns worth reusing

```text
hermetic_test_guard_service.assert_live_network_allowed
  raises rather than returning a sentinel — "there is no useful partial answer
  to a request we were not allowed to make"

source_ingestion_plan_gate_service
  env flag NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED, deny by default

active_source_activation_readiness_gate_service
  packet-shaped human gate
```

Gate 93 should follow the first pattern: refuse loudly, name the caller, name the
missing precondition.

## Missing activation blockers, ranked

```text
1  raw payload store              nothing durable retains transport evidence
2  runtime attribution surface    string exists only as a Python constant
3  terms/legal review queue       158 flagged rows, no work list
4  credential + SAM role model    no storage, no rotation, no role
5  unguarded fetch paths          3 of 4 live-HTTP sites bypass every gate
6  breaker wiring                 policy and column exist, unconnected
7  cadence policy per source      Gate 92 doc has the table, no code reads it
```

## Where Phase 1 collectors attach safely later

```text
transport      one guarded choke point per protocol; extend
               assert_live_network_allowed to cover polite_http_get and
               default_real_http_fetch rather than adding a third pattern
governance     source_crawler_governance_service.evaluate_fetch_permission,
               called before the transport, not after
evidence       raw payload store (Gate 93E), written before parsing
identity       opportunity_identity_versioning_service (Gate 92E)
scheduling     nf_opportunity_sources.next_check_due_at + nf_source_check_runs
surfacing      trust manifest attribution block gates customer visibility
```

Gate 93 builds the preconditions at contract level. It does not wire the
transport, and it does not close the three unguarded call sites — that is a code
change to shared modules with five live callers, and it belongs in its own gate
with its own regression run. It is recorded here as finding #5 and carried into
doc 529 as the top-ranked follow-up.
