# 792 — Gate 152: the audit replay gap, surveyed

Read-only. Nothing was replayed into existence, no evidence was written, no
external system was contacted.

## The chain, measured

```text
audit event  ──resolves──▶  delivery intent  ──?──▶  digest record

     85 / 85                      85                    0 / 85
```

Three tables exist and two of the three links already work.

```text
nf_audit_events                 present, 176 rows, all demo org
nf_digest_delivery_intents      present,  85 rows, all demo org
nf_tenant_digest_records        present,   1 row  (Gate 151's archived fixture)

intents naming a digest_id                 85
intents whose digest record exists          0
intents carrying an audit_event_id         85
intents whose audit_event_id resolves      85
audit events with action
  digest_delivery_intent_recorded          85
```

## The finding that reframes this gate

Gate 150 said "delivery intents name a digest nobody kept", and Gate 151
measured it at 71 of 71. That was true and it was only one link.

**The intents themselves are properly attributed.** Every one carries an
`audit_event_id`, every one of those resolves to a real audit event, and the
count of `digest_delivery_intent_recorded` events matches the intent count
exactly. Nothing has drifted.

So a replay today can already say *when* an intent was recorded and *under what
action*. What it cannot say is *what the digest contained*. The chain is
two-thirds intact, not absent — and describing it as absent would understate the
system as badly as claiming it complete would overstate it.

## What follows for the vocabulary

Evidence status has to be **per link, not per record**. The same delivery intent
is simultaneously:

```text
audit link    linked_record_found     the event resolves
digest link   legacy_gap              the record was never written
```

A single status per record would have to pick one and would be wrong about the
other. So a replay returns a chain of links, each with its own status, and the
record's overall status is derived from the weakest link rather than asserted.

## What can be replayed today

```text
a persisted digest by organization_id + digest_id       Gate 151
its payload hash, recomputed and compared               Gate 151
a delivery intent by id, org-scoped                     Gate 142
that intent's audit event, by audit_event_id            resolves 85/85
the intent's stored counts and blocked reasons          Gate 142
whether an intent's digest record exists                Gate 151's linkage
```

## What cannot be replayed today

```text
what any of the 85 legacy intents' digests contained
    the records were never written, and the snapshots they were built from
    are not guaranteed unchanged

which items a legacy digest showed or suppressed
    the counts survive on the intent; the items do not

what a tenant actually saw on screen
    nothing records a view; an intent is not a delivery and a digest record
    is not a page load

anything about the real organization
    it has 0 intents, 0 digest records, and is never addressed
```

## Can digest + intent + audit event be joined?

Yes, and the join keys already exist:

```text
intent.organization_id + intent.digest_id  ->  digest record
intent.audit_event_id                      ->  audit event
```

Note the direction. `nf_audit_events` has no `digest_id` or `intent_id` column —
it carries `review_artifact_id`, `tribal_profile_id`, `extraction_run_id` and a
JSON `payload`. The **intent** is what points at the audit event, not the other
way round. A replay that looked for the link on the event would find nothing and
report a gap that is not there.

## What must remain UNKNOWN or NOT_ATTESTABLE

```text
a legacy intent's digest contents        not_attestable, never fabricated
what a tenant read                       not_attributable - nothing records it
whether a digest was delivered           not_replayable - nothing was sent
production audit claims                  not_attestable in this scope
```

## What replay can safely prove without external calls

Everything above the line. Every join is a local read of three tables already in
the database; nothing needs a provider, a source, an object store or a network.
That is the whole reason this gate is possible before the capability gates.

## What must not be fabricated

The 85 legacy intents stay legacy. Their digests cannot be reconstructed: a
regenerated digest would be *a* digest for that period, not *the* one the intent
referred to, and storing one would produce a record that looks like evidence and
is not.

The verifier prints the count so it falls visibly as new intents are recorded
against persisted digests — which is the honest remedy, and the only one.

## The scope claim, stated narrowly

This is **controlled_dev_demo audit replay**, not legal-grade production audit.
It proves that records written by this system can be found, joined and checked
against their own hashes. It does not prove anything about a real tenant, and
`production_audit_ready` has no branch that returns true.

## Exact blockers remaining

```text
0 of 85 intents link to a digest      legacy; not backfilled
no live intent has yet been recorded  the linkage capability exists; Gate 152's
  with require_persisted_digest=True  verifier records the first one
no view or read event is recorded     out of scope, and named so it is not
                                      mistaken for something that exists
```

## What Gate 152 builds

An evidence status vocabulary, a replay service, an evidence ledger, routes, a
readiness service, a verifier, artifacts and docs. It writes no evidence,
fabricates nothing, and contacts nothing.
