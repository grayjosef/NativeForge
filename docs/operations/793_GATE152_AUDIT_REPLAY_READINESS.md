# 793 — Gate 152: audit replay readiness

## The lane

```text
audit_replay_ready         true, controlled_dev_demo
production_audit_ready     false, and never computed
```

This means: the records this system wrote can be found, joined, and checked
against their own hashes. It does not mean this would satisfy an auditor or a
court, that any digest was delivered, or that any tenant read anything.

## What the survey found, and how it reframed the gate

```text
audit event  ──resolves──▶  delivery intent  ──?──▶  digest record
     85 / 85                      85                    0 / 85
```

Gate 150 said "delivery intents name a digest nobody kept". True, and one link.
Every intent also carries an `audit_event_id`, **all 85 of which resolve**, with
exactly 85 matching `digest_delivery_intent_recorded` events. The chain was
two-thirds intact.

That forced evidence status to be **per link, not per record**. Each legacy
intent is simultaneously `linked_record_found` on its audit link and
`legacy_gap` on its digest link; a single status would have to pick one and be
wrong about the other. A chain's status is the **weakest link**, never an
average.

## The defect Gate 152 found in Gate 151

**The persisted-digest delivery guard reported without enforcing.**

`record_delivery_intent` gates its write on `decision["storage_allowed"]`, which
`prepare_delivery_intent` computes from its own blocked list and cannot know
about persistence — it takes no connection, deliberately. Gate 151 appended
`digest_id_names_no_persisted_digest` to the *caller's* list instead. The reason
appeared in the result and the row was written anyway.

It shipped looking correct because Gate 151's verifier exercised
`digest_record_exists` directly rather than driving `record_delivery_intent` end
to end.

**And it briefly read green here, for a second reason.** Gate 152's verifier
first reported the refusal as working — but only because an invalid recipient
fingerprint was blocking the write on unrelated grounds. Fixing the fingerprint
removed the real blocker and the unpersisted-digest intent was accepted. A green
check with two possible causes has only been half-tested.

A second half of the same defect: the result spread `**decision`, so the
*reported* `storage_allowed` could read `True` beside a blocker and
`rows_written: 0`. Three fields, two of them right.

### The fix

The merged verdict gates the write **and** overrides the reported field.
`storage_allowed`, `blocked_reasons` and `rows_written` now all say the same
thing, on every branch:

```text
absent digest, enforcement ON   -> storage_allowed False, rows 0, blocker named
persisted digest, enforcement ON -> storage_allowed True,  rows 1, no blocker
absent digest, enforcement OFF   -> storage_allowed True,  rows 1
```

Every one of those uses a **valid** fingerprint, so the digest linkage is the
only thing that can refuse.

## What can be replayed

```text
a persisted digest by organization and id
its payload hash, recomputed and compared
a delivery intent by id, org-scoped
that intent's digest record, if one exists
that intent's audit event, by audit_event_id
whether an intent's digest was ever persisted
```

## What cannot

```text
what any legacy intent's digest contained    never written; not reconstructable
which items a legacy digest showed           counts survive, items do not
what a tenant actually saw                   nothing records a view
anything about the real organization         0 rows, never addressed
```

## The six conditions

```text
tenant_digest_persistence_live      Gate 151's lane
digest_hash_verification_works      stored hash == recomputed, tampering fails
delivery_intent_linkage_works       an enforced intent resolves to its digest
legacy_gaps_reported                counted and surfaced, NOT backfilled
evidence_ledger_generates           one normalized entry per record
cross_org_replay_refused            same answer as a record that does not exist
```

The fourth is what distinguishes this lane from a vanity check. **A backfill
fails it rather than passing it** — a replay that quietly produced digests for
the legacy intents would score better on every other condition and be worthless.

## What the verifier proves

It builds the first fully linked chain in the database: persist a digest, write
a real `digest_delivery_intent_recorded` audit event, record an intent against
both with `require_persisted_digest=True`, then replay everything.

```text
delivery_intent   linked_record_found
digest_record     linked_record_found
payload_hash      hash_verified
audit_event       linked_record_found
```

The happy path uses a **real** audit event. Referencing a random id would be
manufacturing a broken link and then congratulating the verifier for catching
it; the dangling-reference case is a negative test in the suite instead.

## Next

`794` on the ledger, `795` on the legacy gaps, `796` on the delta.
