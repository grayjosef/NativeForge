# Gate 172 — Source Fleet Health, Freshness and Drift Operations

**Verifier:** `scripts/verify_nativeforge_source_fleet_health_gate172.sh` → `RESULT=PASS`, `gate172_ready=true` (107 checks)
**Migration:** `0058_source_operations_events` (head `0057` → `0058`)
**Network requests: 0.** Every phase replaces `socket.socket` with one that raises and counts; the sum of those counts is asserted to be zero.
**Proven at 5,000 sources.** No source was added, activated or fetched.

---

## 1. What this gate is

Gate 171 proved NativeForge can collect from three real, structurally
different sources. Three sources can be watched by a person. **Five thousand
cannot**, and the failure mode of a fleet that size is not that it breaks —
it is that it breaks quietly, in one dimension, on one source, while the
dashboard stays green.

So this gate does not add a health endpoint. It builds the layer that answers
four questions without a human asking them:

1. **What state is this source in, and why?**
2. **Is it still producing intelligence, or merely still returning 200?**
3. **Has the source changed underneath the adapter?**
4. **Which of those facts does an operator actually need to be told?**

## 2. Eleven states, derived from eleven independent dimensions

A source's state is **derived**, never asserted. It comes from eleven
dimensions, each owned by exactly one layer:

| dimension | owned by |
|---|---|
| `authorization_health` | the authority ladder |
| `transport_health` | the execution envelope |
| `source_availability_health` | the attempt record |
| `parser_health` | the adapter |
| `schema_health` | the drift detector |
| `freshness_health` | the expectation layer |
| `volume_health` | the volume baseline |
| `evidence_health` | the evidence store |
| `backlog_health` | the job queue |
| `scheduler_health` | the scheduler |
| `worker_health` | the worker pool |

Independence is asserted one dimension at a time: degrade each of the eleven
in turn and the other ten must remain `ok`. A model that collapses to a single
verdict cannot tell an operator *which part* of a source is broken, which is
the only thing the operator needs.

**`UNKNOWN` is not `HEALTHY`.** `blank_dimensions()` defaults every dimension
to unmeasured. This is the difference between a fleet that reports itself
green while collecting nothing and one that says so.

Precedence is written once, in order, rather than implied by the order
somebody happened to write the branches:

```text
retired / disabled  →  rate_limited  →  review_required  →  a failed dimension
  →  consecutive failures  →  stale  →  degraded or a named gap  →  unknown  →  HEALTHY
```

Operator intent outranks measurement: a disabled source with eleven failed
dimensions is `DISABLED`, not `FAILING`. Nobody is trying. And a source that
asked us to slow down is `RATE_LIMITED`, not `FAILING` — treating a
rate-limit as a failure is how a fleet earns a block.

## 3. The defect this gate existed to find

The read model could not tell **"authorization refused"** from
**"authorization not yet measured."**

Both arrived as an absent grant, so a revoked source classified as `FAILING`
with `transport_health` still `ok` — a source we had been told to stop
collecting from, still permitted to collect. That is the single outcome the
authorization boundary exists to prevent, and the seventeen-row failure matrix
found it:

```python
    # REVOKED is not UNKNOWN. Gate 172's failure matrix found that this row
    # could not tell the two apart, so an authorization refusal classified as
    # FAILING with transport still permitted - which is the one outcome 172S
    # exists to prevent.
    authorization_revoked: bool = False,
    transport_blocked: bool = False,
```

Three answers, not two: granted, **refused**, and nobody has asked. A revoked
source is now `AUTHORIZATION_REQUIRED` with `is_collecting=False`, and restore
is data-driven — the switch is a row, not a deploy.

## 4. A 200 is not intelligence

Five success levels, because collapsing them is how a source that has silently
returned nothing for six weeks keeps reporting itself healthy:

```text
transport_success → payload_success → parse_success
  → observation_success → useful_intelligence_success
```

Freshness is measured from **five distinct timestamps** (`last_attempt_at`,
`last_success_at`, `last_payload_at`, `last_observation_at`,
`last_useful_change_at`) against *this source's* cadence, resolved through
three layers: fleet default → adapter default → operator override.

Two rules that are easy to get wrong and are asserted permanently:

- **Never collected is not stale.** A source that has never run has no
  freshness to have lost. It is unmeasured.
- **An unscheduled cadence carries no freshness SLA.** Otherwise every
  `manual` and `event_driven` source is permanently overdue.

And freshness is **not** derived from scheduler lag. A punctual source can be
stale — it ran exactly on time and returned nothing new. Deriving one from the
other hides that case completely.

## 5. Drift: the adapter is never rewritten automatically

Ten drift signals across four classes. A `BREAKING_DRIFT` signal moves the
source to `REVIEW_REQUIRED` and **asks for a human**. The alternative is a
parser that silently adapts to a change nobody reviewed and writes plausible
wrong records into the canonical store — worse than a stopped source, because
it is trusted.

Volume baselines are **per source**. A source that publishes three records a
week is not anomalous because another publishes three thousand a day, and the
first run is never an anomaly: one observation is not a baseline
(`MINIMUM_HISTORY = 3`).

## 6. Events mark transitions, not polls

Migration `0058` adds `nf_source_operations_events` and
`nf_source_operator_alerts`. The central constraint:

```sql
CHECK (from_state IS NULL OR from_state <> to_state)
```

**An event that is not a transition is unrepresentable.** `plan_transition()`
returns `None` when nothing changed, rather than leaving callers to filter —
a caller that has to filter afterwards will eventually forget to, and the
events table becomes a poll log nobody reads. Three identical sweeps wrote
**one** event and advanced a detection counter to 3; `first_detected_at` never
moved.

A first sighting is not a recovery, either. Without that rule every source in
the fleet emits `SOURCE_RECOVERED` the first time health is ever computed.

`DEGRADED`, `UNKNOWN` and `RETIRED` **never page an operator.** Alert fatigue
is the failure mode that makes an operations layer useless. Each of the ten
alert conditions carries a severity *and* a recommended action; nothing in
this gate delivers anything.

## 7. The health of the health system

Seven self-health conditions, because a health layer that cannot notice it
skipped 2,000 sources is worse than none — it is trusted. The fleet report
reconciles registered against evaluated, checks its own age, and fails if any
source carries failures with no classified failure type.

It caught a fixture of mine during this gate: the sequential-isolation
fixture gave source B two consecutive failures and no failure type, and
`every_failure_is_classified` correctly refused it.

## 8. Fleet scale — 5,000 sources

| | 100 | 1,000 | 5,000 |
|---|---|---|---|
| sweep | 20.3 ms | 130.9 ms | **678.6 ms** |
| statements per source | 0.01 | 0.001 | **0.0002** |
| fleet-global computations | 1 | 1 | **1** |

Population grew **50×**; sweep time grew **33×**. Statements per source *fall*
with scale because fleet-global facts are hoisted once per sweep (Gate 166)
rather than recomputed per source. Peak memory 86.5 MB. All 5,000 fixture rows
removed.

### The access-path rule is selectivity-aware, deliberately

`sources_due` returns **100% of the population** — every fixture source is due.
A scan is the *correct* plan for a query that returns the whole table; an index
would read the index and then the table, and be slower. Adding one to turn that
red green would be making the measurement agree instead of making the system
right.

So the asserted invariant is: **every selective query uses an index, and any
exemption is named rather than silently dropped.** Selectivity is measured, not
declared:

| query | selectivity | plan |
|---|---|---|
| `source_by_id` | 0.0002 | index |
| `latest_attempt_per_source` | 0.0 | index |
| `latest_success_per_source` | 0.0 | index |
| `active_lease_per_source` | 0.0 | index |
| `events_by_source` | 0.0 | index |
| `unresolved_alerts` | 0.0 | index |
| `sources_stale` / `sources_failing` | 0.1111 | index |
| `sources_review_required` | 0.4439 | index |
| `sources_due` | **1.0** | scan — **named exemption** |

Asserted at all three scales, not just the largest: a query that uses an index
at 100 sources and scans at 5,000 is exactly the regression worth catching.

## 9. Sequential isolation

One health run must not decide the next one's answer. Fixture A → cleanup →
fixture B, each in its **own process** (in-process reuse shares SQLAlchemy
state and ContextVars — the contamination this exists to detect). B after A
was field-for-field identical to B alone, `differing_fields = []`, and A and B
were genuinely different fixtures (`HEALTHY` vs `DEGRADED`).

Gate 171's `sequential_lineage_isolation` is **re-measured here, not quoted**.

**Gate 171's root cause remains UNKNOWN.** Four mechanisms were ruled out with
evidence and the cause was never identified. This gate measures the
regression; it does not claim the cause was found.

## 10. What this gate did not do

- **No network requests.** Zero, asserted by counting refused sockets.
- **No new sources, no new adapters, no activations.**
- **No notification delivery.** The alert *contract* exists; nothing sends.
- **No Postgres concurrency measurement.** SQLite cannot demonstrate it, and
  it is reported as `UNKNOWN - not measured` rather than inferred.
- **No BIA robots body.** Gate 171's evidence gap is permanent and is carried
  as a named gap that degrades the source, not as an absence that looks fine.

## 11. Lessons

**A green matrix is meaningless if the fixture does not feed the classified
condition into the actual model.** The seventeen-row failure matrix first
passed `live_opted_in` for a `ROBOTS_RESTRICTED` row, so every classification
produced the same authorization dimension and the matrix went green without
exercising a single branch. The fixture now *derives* the model's inputs from
the classification. This is a permanent test principle, and
`test_the_failure_matrix_feeds_its_classification_into_the_model` enforces it.

**A detector that cannot fail proves nothing.** The first fairness simulation
produced identical output for strict priority and for aging, because it had no
continuous arrivals — the one condition under which starvation appears. It now
runs both: the aging scheduler must be clean *and* the strict-priority
scheduler must starve.

**Measure the access path the service actually takes.** The first index audit
omitted `organization_id`, so the planner could not use any of the org-prefixed
indexes and reported five scans — a finding about the audit, not the schema.
It also compared `str(UUID)` against a column SQLAlchemy stores as 32 hex
characters without dashes, returning **zero rows** while still printing query
plans.

**The instrument needs the same scepticism as the code.** Every defect above
was in a measurement, and each one produced a confident wrong number. Four of
this gate's permanent regressions test the instruments rather than the product,
for that reason.
