# Gate 162A — source activation and allowlist survey

Measured before writing anything. No gate prompt was supplied for 162, so the
scope below is derived from Gate 161's carry-forward (*Gate 162 owns
activation/allowlist permission; Gate 163 is first approved live source*) and
from the block intent (*keep every live-source path hermetic and inactive*).

**Nothing in this gate approves a source.** Gate 163 is the first approved live
source, and source terms are a human decision that the Gate 135 standing
authorization explicitly withholds.

## What already exists — 149 modules, and why 148 of them are not it

```text
modules matching activation/allowlist/approval by name      149
  packet / document builders (planning, authorization briefs) 99
  candidate runtime modules                                   50
functions that can actually grant a SOURCE permission          1
```

That last number was **101** on the first pass, because my verb list contained
`grant` — which in this repository is overwhelmingly a noun. It matched
`grants_gov`, `grant_spark`, `awarded_grant` and eighty others. Occurrence
**fifteen** of the campaign's substring-versus-meaning defect, committed inside
the survey that was measuring for it.

Corrected to whole `_`-separated segments, verb senses only, and requiring the
object to be a source or collector:

```text
seed_source_human_activation_service::activate_single_seed_source_human_gate
    params: session, org, seed_id, operator_confirmation, authorized_seeds
    "Activate exactly one authorized seed - is_active=True for that source only"
    and it DECIDES only; it writes nothing
```

Two batch gates exist alongside it (`tier1_batch_federal_activation_service`,
`tier3_foundation_batch_activation_service`), both requiring
`operator_confirmation`.

**So: do not create another activation system.** Three human gates, a terms
review queue, a per-source activation policy, an allowlist evaluator and a live
network guard all already exist.

## The gap is a bridge, not a system

`build_live_network_decision` (Gate 94B) takes **18** inputs, of which 10 are
the per-source statuses that decide permission.
`source_monitoring_approved_source_service.evaluate_source` produces **24**
fields. They overlap on **two**.

```text
the guard wants            the registry produces
-----------------------    ---------------------------------
source_id         HAVE     source_id
terms_status      HAVE     terms_status            (= "UNKNOWN")
activation_status MISSING  activation_approved     (a bool, different name)
collector_status  MISSING  collector_activated     (a bool, different name)
credential_status MISSING  credential_required     (a bool, different name)
robots_status     MISSING  robots_fetched          (a bool, different name)
rate_limit_status MISSING  —
user_agent_status MISSING  —
attribution_status MISSING —
collector_type    MISSING  —
```

Fed only what the registry can actually answer, the guard blocks:

```text
requirements_satisfied   2 of 10
blocked_reasons          8
    activation_not_allowed:activation_unknown
    collector_not_active:not_active
    credential_missing:unknown
    live_fetch_not_opted_in
    rate_limit_policy_missing:unknown
    robots_does_not_permit:unknown
    terms_status_blocks:UNKNOWN
    user_agent_not_canonical:unknown
```

### Why that matters more than it looks

Gate 161 recorded that the guard **can** be satisfied — by a caller supplying
all 18 inputs — and treated that as by design, since Gate 162 would do it
deliberately. The survey shows the sharper version of the problem:

> Today the guard's permitted branch is reachable **only by fabrication.**

No path exists from recorded facts to `allowed=true`, because eight of the ten
inputs have no record to come from. A caller who wants permission must invent
it. Gate 134F's rule was *an unreachable permitted branch makes a refusal
unfalsifiable*; its converse is worse — **a permitted branch reachable only by
fabrication makes an approval unaccountable.**

Gate 162's job is therefore not to grant anything. It is to make the permitted
branch reachable **only from recorded facts**, and to leave those facts saying
no.

## Two further gaps found

**There is nowhere to record a terms decision.** `evaluate_source` reports
`terms_status: UNKNOWN` with the blocker
`registry_has_no_terms_column_for_this_source`. The terms review queue holds 5
pending items and 0 approvals, and a human's answer has no durable home. 171 of
177 sources are `terms_blocked` for want of a column.

**The phase-1 activation policy's readiness has gone stale.**

```text
phase1_collector_activation_policy_service reports
  scheduler_runtime_available            False
  production_raw_payload_store_available False
  live_collection_requires_production_store True

but on disk now
  source_collection_scheduler_runtime_service        EXISTS
  source_collection_worker_runtime_service           EXISTS
  source_collection_orchestration_runtime_service    EXISTS
  source_collector_execution_service                 EXISTS
```

`scheduler_runtime_available` is derived by `_scheduler_runtime_available()`,
which predates Gate 157 and looks for a broker dependency rather than for the
runtime Gates 157–161 actually built. This is the mirror image of the
campaign's usual defect: not a declared fact pretending to be derived, but a
derivation that has quietly stopped describing the thing it names.

The `production_raw_payload_store_available: False` is **not** stale — Gate 160
measured the object store as unconfigured, and that remains true.

## The registry, as it stands

```text
registry rows               177
activation_approved_count     0
monitorable_count             0
terms_blocked_count         171
human_review_blocked_count    6
api_key_missing_count         0
```

The allowlist of *approved network call sites* (8 entries) is a different
thing entirely — code sites permitted to import `httpx`, not sources permitted
to be called. Gate 161's chokepoint already measures that the envelope is
absent from it.

## Scope this survey supports

```text
162B  a source activation PERMISSION record - what must be true, each field
      read from a record rather than passed as a verdict
162C  alembic 0048 - where a terms/activation decision lives, with CHECK
      constraints that refuse a permission claiming live
162D  the permission repository
162E  the guard input adapter - derives the guard's inputs from RECORDS only.
      Every input with no record resolves to REFUSED, never to unknown-passes
162F  wire Gate 161's execution policy to consult a permission record instead
      of a caller's is_synthetic_fixture claim, for real sources
162G  the approved-source allowlist: explicitly empty, and derived
162H  refresh the phase-1 policy's stale readiness derivation
162I  health, chokepoint, verifier, tests, artifacts, docs
```

## What Gate 162 must NOT do

- Not approve a source. Zero approved at the end, and the count is measured.
- Not create a fourth activation gate. The three that exist are composed.
- Not make a live call. Gate 161's four structural stops remain in place.
- Not decide source terms. That is a human's answer and it is not in hand.
- Not bind the real organization. Standing authorization is demo-org only.

## The one thing to get right

A permission record makes approval *possible to express*. The temptation is to
make it possible to express and then express it. The measured end state of this
gate must be: the machinery exists, the allowlist is empty, and the reason it
is empty is a human decision nobody has made — recorded as absent rather than
assumed.
