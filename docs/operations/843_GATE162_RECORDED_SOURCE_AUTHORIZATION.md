# Gate 162 — recorded source authorization

What changed, and what is still exactly as false as it was.

## The one-line version

The live network guard's permitted branch is now reachable only from recorded,
attributable facts. Before this gate it was reachable only by fabricating them.

## What Gate 162 did NOT build

This matters more than what it did, because 149 service modules in this
repository match activation/approval terminology and the wrong move was to add
a 150th.

```text
no second activation system      three human activation gates already exist
no second approval service       nf_active_opportunity_sources already owns it
no second review workflow        terms + review share one decision table
no second allowlist              the allowlist is a projection, not a store
no terms review UI               terms review is a human process, not an API
```

Measured before writing anything: exactly **one** existing component could
decide source permission, and it decides only — it writes nothing. Doc 842
records the survey.

## The systems this gate REUSES

```text
live_network_guard_service                 Gate 94B. Every requirement and
                                           every permitting value is READ from
                                           it; none is restated
nf_active_opportunity_sources              activation_approved_by / _at /
                                           _artifact_id. Composed, joined by
                                           source_name
source_monitoring_approved_source_service  the 177-row registry
source_terms_review_queue_service          the human review queue
phase1_collector_activation_policy_service collector state
Gates 156-161 health lanes                 runtime readiness, six lanes
```

## What was genuinely missing

```text
a per-source TERMS decision          only legal_tos_review_required existed,
                                     which is a REQUIREMENT flag with nowhere
                                     to put the answer
a per-source REVIEW decision         likewise only
                                     broad_eligibility_human_review_required
any path from records to the guard   eight of its ten status inputs had no
                                     record anywhere to come from
```

## The problem this gate exists to fix

Gate 161 recorded that the guard *can* be satisfied by a caller supplying ten
booleans, and treated that as by design. The survey found the sharper version:

> Fed only what the registry could actually answer, the guard satisfied **2 of
> 10** requirements and blocked with eight reasons. There was no path from
> recorded facts to `allowed=true` at all.

Gate 134F's rule was *an unreachable permitted branch makes a refusal
unfalsifiable*. The converse is worse: **a permitted branch reachable only by
fabrication makes an approval unaccountable.** Nobody had written the caller
that knows.

## The eleven facts

```text
source_registered      recorded_registry    SATISFIED (177 sources)
terms_status           recorded_decision    a human reviewer
human_review_status    recorded_decision    a human reviewer
activation_status      recorded_decision    an operator, with attribution
attribution_status     recorded_decision    derived from the terms decision
collector_status       measured_runtime     observed
robots_status          unresolvable         needs a live fetch — Gate 163
credential_status      measured_runtime     observed
rate_limit_status      declared_policy      SATISFIED
user_agent_status      declared_policy      SATISFIED
runtime_status         measured_runtime     the six Gates 156-161 lanes
```

Facts are not equally good evidence, so each carries a
`derivation_strength`, and **only `recorded_decision` can authorize.** A ready
runtime, a registered source, an available adapter, a queued job and a hermetic
execution proof are prerequisites; none of them is permission. A queued job and
an execution proof are not facts in this model at all, which is the strongest
available form of that statement.

## Five ways to fail, kept distinguishable

```text
recorded       a decision exists and permits          THE ONLY permitting state
denied         a decision exists and refuses
needs_review   a decision exists and defers to a human
missing        NO record exists at all
unknown        a record exists and does not answer
stale          a record answered, and the answer expired
```

"Nobody has reviewed these terms" and "a reviewer read these terms and said
no" are opposite operational situations with the same effect on permission. A
boolean cannot tell them apart, so this model does not use one. `missing` is
never filled in with a refusing default: the refusal would be correct and the
diagnosis wrong.

## The signature is the security property

```python
resolve_source_authorization_facts(
    *, connection, organization_id, source_id, now
)
```

Four parameters, no `**kwargs`, no `*args`, and none of them can assert a fact.
There is no `terms_approved`, no `allow_live_fetch`, no override. A parameter
that does not exist cannot be misused, and the gate's tests parse this
signature to keep it that way.

## The bypass that remains, and why it is harmless

A caller can still import `build_live_network_decision` and pass ten
affirmative strings. It will return `allowed=true`, because it is a pure
decision function and that is what it is for.

What such a caller gets is an **opinion**:

```text
it cannot change authorize_source_for_live_access, which resolves from records
it cannot be recorded      the database refuses an approval with no signer,
                           no time and no evidence fingerprint
it cannot be dispatched    Gate 161 built no live transport and `live` is not
                           in DISPATCHABLE_KINDS
it cannot produce a row    migration 0047 refuses transport_kind='live'
```

## Authorization complete is not a permitted request

The distinction the gate turns on, and two separate fields:

```text
authorized=true        every required fact is a signed, fresh record
guard_allowed=false    and nobody has opted this request in to a live fetch
```

`authorize_source_for_live_access` hardcodes `allow_live_fetch=False`. A fully
authorized source sits at `live_fetch_not_opted_in`. Gate 163 is where that
becomes a code change rather than an argument.

## Current state

```text
sources evaluated                 179   (177 shipped + 2 synthetic fixtures)
real sources resolved             177
real sources approved               0
real sources allowlisted            0
synthetic fixtures allowlisted      1   (the reachability proof)
terms-blocked                     171
human-review-blocked                6
caller-supplied facts accepted      0
mutation endpoints                  0
live transport enabled          false
live source calls                   0
source_monitoring_live          false
```

## Falsifiability

A boundary that refuses everything passes every refusal test. So a **synthetic
fixture** under the reserved `nf162.fixture.` prefix reaches
`authorization_status=approved` with all eleven facts recorded — and it still
sits at `live_fetch_not_opted_in`.

Its terms approval is signed by `reviewer:nf162-verify` against a fingerprint
of a string in this repository, and its host is `.invalid`, reserved by RFC
2606 precisely so it cannot exist. It proves the chain can say yes. It proves
nothing about any real source.

See doc 844 for the guard input mapping, 845 for the decision facts, 846 for
the allowlist projection, and 847 for what Gate 163 inherits.
