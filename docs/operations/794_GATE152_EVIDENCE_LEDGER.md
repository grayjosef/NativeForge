# 794 — Gate 152: the evidence ledger

## What an entry is

One record this system wrote, named by type and id, with whatever it points at,
the status that gives it, and what a replay still cannot say about it.

```text
organization_id        the partition
evidence_type          digest_record | delivery_intent | audit_event
record_id
related_record_ids     what it links to, when the link resolves
evidence_status        one of ten
is_proof               true for exactly three of them
payload_hash           digests only
created_at
fact_status, is_demo
replay_limitations     always present
```

## Every entry carries its limitations, not only its status

A `linked_record_found` delivery intent is still a plan nobody sent. An entry
reporting the status without that would be read as stronger than it is, so the
limitations are a required field and a test asserts no entry ships without them.

```text
digest_record     nothing records whether a tenant read this digest
                  an archived digest is still readable; archive is a state
delivery_intent   an intent is a plan; nothing was sent
                  it stores counts, not the items the digest showed
audit_event       records an action, not what a tenant saw
```

## The ten statuses, and the three that are proof

```text
proof       attested, hash_verified, linked_record_found
not proof   legacy_gap, missing_record, not_attributable, not_replayable,
            not_attestable, unknown, blocked
```

`unknown` and `legacy_gap` are the two most likely to be skimmed past as mild
versions of "fine". They are ranked below every proving status, so a chain
cannot read green through either.

The vocabulary is **closed**: anything outside it normalizes to `blocked`. A
closed vocabulary that can emit a value outside itself is not closed, and a
caller indexing the definitions with the result would raise.

## The ledger is as good as its worst entry

`overall_status` is the weakest entry's, never an average. An empty ledger is
`unknown` rather than `attested` — nothing examined is not the same as nothing
wrong.

## Awarded proof events are deliberately excluded

`nf_award_requirement_proof_events` exists and Gate 126 made it operational, so
including it would have been easy and wrong. Its rows are about award compliance
evidence, which is a different subject from *did this system show a tenant a
digest and record an intention to deliver it*. One ledger answering both would
have summary counts that answer neither.

A later gate that wants an award evidence ledger should build one and say so.
`nf_award_documents` is excluded for a simpler reason: it holds metadata and no
body is stored anywhere.

Both exclusions are recorded in the ledger output, so their absence reads as a
decision rather than an oversight.

## A false negative found while building it

The first version read digest payloads with a raw `sa.text()` SELECT. On SQLite
that returns the JSON column as a **`str`**; only the typed `sa.Table` path
deserializes it. So the ledger hashed the JSON *string* while the stored hash
was computed over the parsed dict, and reported a perfectly sound digest as
`missing_record`.

In an audit ledger that is the worst direction of error: it tells an operator
their evidence is broken when it is not. Same family as Gate 151's DATE
coercion — an untyped read behaving differently from the typed one.

The fix was not to normalize separately but to **read through the repository
that owns the read**, so the two paths agree by construction rather than by
coincidence.

## What the ledger never exposes

```text
a recipient address      the intent table has no column for one
a provider subject
a rendered body          the digest table has no column for one
a document body
```

Every payload is scanned before it is returned and the builder refuses rather
than emits.
