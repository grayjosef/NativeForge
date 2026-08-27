# 549 — Gate 98A: scheduler and circuit breaker survey

Verified rather than assumed, and the verification corrected the brief in one
place.

## Scheduling columns: present, and written — but never read to trigger work

```text
nf_opportunity_sources (39 columns)
  next_check_due_at              present
  check_interval_days            present
  consecutive_failure_count      present
  consecutive_empty_check_count  present
  source_health_status           present
  last_check_status              present
  last_check_run_id              present
```

Prior gates recorded these as "columns exist, nothing writes them". **That is
wrong.** `source_freshness_service.finalize_completed_source_check` writes all of
them, and it is reachable:

```text
source_connectors/source_check_bridge.py:255, :391
api/opportunity_discovery_routes.py:1587, :1725
```

The bridge imports no HTTP client — it records the outcome of a check somebody
else performed.

So the scheduling **state** is maintained. What does not exist is anything that
**reads** `next_check_due_at` to decide a source is due and enqueue it. State is
written reactively when an operator or a connector records a check; nothing
drives the clock.

That distinction is the whole of this gate: the missing piece is a decision
layer and a runtime, not a schema.

## nf_source_check_runs: 22 columns, no evidence link

```text
id  organization_id  is_demo  source_registry_id  check_mode  check_status
started_at  completed_at  checked_for_period_start  checked_for_period_end
opportunities_seen_count  new_candidates_count  accepted_count
duplicate_count  rejected_count  review_items_created_count
error_code  error_message  operator_notes  result_summary_json
created_at  updated_at
```

Two gaps Gate 98's contract addresses:

* **No link to raw payload evidence.** A run says "42 opportunities seen" with
  no reference to the payloads that produced the number — the same shape as the
  185/18 corpus split Gates 87–89 measured. The contract carries
  `raw_payload_ids`, referencing `nf_raw_source_payloads` rows rather than
  restating them.
* **`error_message` is free text.** An HTTP client's error can carry a presigned
  URL or an echoed header, and this column would store it verbatim. The contract
  names the field `error_message_redacted` and requires the redaction.

## Circuit breaker: four counters, two thresholds, no owner

```text
1  source_crawler_governance_service.CIRCUIT_BREAKER_CONSECUTIVE_FAILURES = 5
   Gate 92's policy. Consulted by live_network_guard_service before a request.

2  source_freshness_service:242    if failure_count >= 3
   Derives source_health_status. A different threshold.

3  discovery_source_quality_service:581    >= 3
   A third site, same value as (2), independently written.

4  polite_http_fetch_service._consecutive_failures: dict[str, int]
   Per-process, in memory, keyed by domain, lost on restart.
```

Four places count failures and two disagree about how many is too many. A source
can be "unhealthy" at 3 by the freshness derivation while the network guard
still permits requests until 5.

None of them is a breaker in the usual sense: there is no state machine, no
cooldown, and no half-open probe. Gate 92 named the policy; Gate 94 consulted
the count; nothing ever transitions.

Gate 98 does not delete any of them — that would be a refactor with its own
regression surface — but it defines the single state machine that a scheduler
consults, and doc 553 records the consolidation as a follow-up.

## Scheduler runtime: none

```text
celery / rq / apscheduler / dramatiq / arq / huey / croniter
  pyproject.toml  0
  uv.lock         0

systemctl --user list-timers   no nativeforge timers
crontab -l                     no nativeforge entries

nativeforge user units:
  nativeforge-demo-preview.service    Vite preview on 127.0.0.1:5175
  nativeforge-mayhem-tunnel.service   Cloudflare tunnel
```

Neither unit schedules anything. There is no worker process, no queue, and no
periodic trigger of any kind.

So `scheduler_runtime_available` and `background_worker_available` are **false**,
detected rather than declared, and no argument to any function in this gate can
change that.

## Existing preflight and Phase 1 policy

Both are in place from Gates 93–97 and this gate extends rather than replaces
them:

```text
source_activation_preflight_service     9 requirements, collection_intent
phase1_collector_activation_policy      5 sources, all not_active
```

Gate 98 adds the distinction the gate asks for: **collector activation and
scheduler readiness are different questions.** A collector can be activated for
a manual, operator-triggered check without a scheduler existing; scheduled
monitoring needs a runtime and a breaker on top.

## Where a future scheduler writes

```text
1  decide      source_schedule_decision_service   is this source due, and safe?
2  breaker     source_circuit_breaker_service     is the circuit closed?
3  guard       live_network_guard_service          may the request go out?
4  fetch       the approved transport for its purpose
5  body        s3_raw_payload_body_store_service   bytes to the object store
6  metadata    production_raw_payload_repository   row in nf_raw_source_payloads
7  run record  nf_source_check_runs                what the check did
8  state       finalize_completed_source_check     next_check_due_at, counters
```

Steps 1 and 2 are what Gate 98 builds. Step 8 already exists and already works;
the scheduler feeds it rather than replacing it.

## What remains blocked by human decisions

```text
- object store deployment + a proven round trip     (Gate 97)
- SAM.gov API key and role                          10/day without it
- 185 terms-queue items reviewed                    148 + 62 + 4 + 1
- four SPA terms pages read by a human
- Simpler.Grants.gov tribal applicant_type enum
```

None of these is engineering. After Gate 98 the remaining *engineering* work is
a scheduler runtime — a worker process and a trigger — which is a deployment
decision about where it runs, not a contract.
