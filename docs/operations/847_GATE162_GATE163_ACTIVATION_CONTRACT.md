# Gate 162 → 163 — the activation contract

What Gate 163 inherits, and what a human has to do first.

## Gate 163 is the first real source activation

Gate 162 built the machinery and approved nothing. Every approval it recorded
was for a synthetic fixture. **Zero real sources are approved, allowlisted, or
callable.**

## The activation packet is a read model

`source_activation_packet_service.build_activation_packet` reads recorded facts
and reports whether a source could be activated and what is missing. It writes
nothing, sets no flag, and calling it a thousand times changes nothing.

It exists so Gate 163 inherits a checklist that was written **before there was
anything to authorise** — a standard shaped by what the guard requires rather
than by what the first candidate source happens to have.

Every unresolved requirement names its own authority. A blocker with no owner
is a blocker nobody clears, and
`an_unresolved_requirement_with_no_authority` fails if one ever appears.

## What a real source needs, today

For `nf-seed-2026-fed-001`, resolved with no decisions on file:

```text
SATISFIED  4 of 11
  source_registered     registered
  credential_status     not_required   (public access posture)
  rate_limit_status     policy_declared
  user_agent_status     canonical

BLOCKING DECISIONS
  terms_status          missing   -> a human reviewer, against the source's
                                     actual terms
  human_review_status   missing   -> a human reviewer
  activation_status     missing   -> an operator, recorded with attribution
  attribution_status    missing   -> derived from the terms decision

BLOCKING PREREQUISITES
  robots_status         missing   -> a live fetch of robots.txt
  collector_status      denied    -> an operator, by starting a collector
  runtime_status        denied    -> the Gates 157-161 lanes
```

## The ordering constraint

`robots_status` cannot be answered without an HTTP request to the source. So:

> **Gate 163's first live call is a robots.txt fetch, not a collection.**

Its result must be recorded before any other request to that host is permitted.
That is the politeness requirement arriving before the traffic it governs, and
it is recorded in `GATE_163_SEQUENCE` rather than left to be rediscovered.

```text
1  a human reads the source's terms and records a signed terms decision
2  a human records a signed source review decision
3  an operator records an activation with attribution
4  a live robots.txt fetch is performed and its result recorded — the first
   live HTTP request the campaign makes
5  only then may a collection request to that host be permitted
6  and the live transport must still be implemented and made dispatchable,
   which Gate 161 deliberately did not do
```

The tests assert step 4 precedes step 5 by index, not by reading the prose.

## What a human must supply, precisely

The database refuses an approval without all three:

```text
reviewed_by            who decided
reviewed_at            when
evidence_fingerprint   a sha256 of the document they read
```

Plus, for a terms approval, a `guard_status` of `NO_REVIEW_REQUIRED` or
`ATTRIBUTION_REQUIRED`. An approval carrying a blocking guard status is a row
that contradicts itself and is refused.

**This is the decision Gate 162 cannot make.** The standing Gate 135
authorization covers dev/demo and the demo organization; it explicitly does not
authorize live grant source monitoring. Nobody has read any source's terms, and
the gate records that as `missing` rather than assuming it.

## What is still missing in code after all of that

```text
no live transport implementation   Gate 161 built none
live not dispatchable              DISPATCHABLE_KINDS = {hermetic}
allow_live_fetch hardcoded False   in authorize_source_for_live_access
migration 0047 CHECK constraints   refuse transport_kind='live' and
                                   live_source_call=1
```

A fully authorized source today sits at `live_fetch_not_opted_in`.
**Authorization complete is not a permitted request**, and the two are separate
fields so one cannot be read as the other.

Gate 163 changing `allow_live_fetch` must be a **code change**, not an
argument. The parameter is hardcoded for exactly that reason.

## Two things Gate 163 should fix, recorded here

**The activation join is by name.** `nf_active_opportunity_sources` has no
`source_id` column and the registry has no UUID, so the resolver joins on
`source_name`. That is weaker than an id join and it is reported as such rather
than quietly relied on. Give those two id spaces a real key before activating
anything.

**Gate 157's worker health reports a bare no.**
`source_collection_worker_health_service` returns `worker_runtime_ready: False`
with no `conditions_not_met`. Gate 162 surfaces it through a fallback `why`
rather than hiding it, and did not fix it — the instruction was to compose, not
to reopen Gate 157.

## The reading to guard against

The synthetic fixture reaching `approved` is what makes every refusal in Gate
162 falsifiable. Without it, a boundary that refused unconditionally would pass
every check.

The temptation at Gate 163 will be to treat that as evidence a real source can
be called. It is evidence the **mechanism** works. The mechanism is built; the
permission is a human's to give, and the database will not accept an approval
that nobody signed against a document nobody read.

## Current state, for the record

```text
sources evaluated                 179   (177 shipped + 2 synthetic fixtures)
real sources resolved             177
real sources approved               0
real sources allowlisted            0
synthetic fixtures allowlisted      1
terms-blocked                     171
human-review-blocked                6
caller-supplied facts accepted      0
mutation endpoints                  0
live transport enabled          false
live source calls                   0
live execution attempts             0
unsigned approvals                  0
source_monitoring_live          false
```
