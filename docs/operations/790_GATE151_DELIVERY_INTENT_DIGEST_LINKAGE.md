# 790 — Gate 151: the delivery intent → digest linkage

## The question that could not be asked before

*Does the digest this delivery intent names actually exist?*

Before migration 0042 there was nowhere for it to exist, so the question had no
answer. `nf_digest_delivery_intents.digest_id` was a nullable Text column with
no table behind it and no foreign key — 71 rows naming 71 digests, none stored.

## Measured always, enforced opt-in

```text
digest_record_persisted      computed on every record_delivery_intent call
digest_linkage_enforced      true only when the caller asks
require_persisted_digest     adds digest_id_names_no_persisted_digest
```

The route passes `require_persisted_digest=True`. That is what makes the new
path correct.

## Why not enforce it unconditionally

Two reasons, and the first is the one that matters.

**The 71 existing rows predate the table.** A blocker applied unconditionally
would retroactively invalidate history that is not wrong — only un-storable at
the time. Those intents recorded a real intention accurately; what they could
not do was keep the thing they referred to, because there was nothing to keep it
in.

**Gate 142's callers pass no persisted digest and are correct as written.** Its
116 tests still pass unchanged, which was checked before anything else in this
gate was built.

A guard that silently broke 116 passing tests and rewrote 71 rows' worth of
history would be the wrong trade for a default.

## Why the legacy intents are not backfilled

The digests they named cannot be reconstructed. Regenerating a digest requires
the snapshot it was built from to still exist and be unchanged, and nothing
guarantees either. A regenerated digest would be *a* digest for that period, not
*the* one the intent referred to.

Manufacturing one would produce a record that looks like evidence and is not,
which is worse than the gap it fills. So the 71 stay as they are, and the
verifier reports them:

```text
delivery_intents_total                       71
legacy_intents_without_a_persisted_digest    71
```

Reported rather than hidden, so the number goes down visibly as new intents are
recorded against persisted digests.

## The linkage is org-scoped

`digest_record_exists` matches on `organization_id` **and** `digest_id`. A digest
persisted under one organization does not satisfy an intent under another, which
is the same partitioning rule every read in the repository follows.

## An absent table answers False rather than raising

```text
no connection      -> False
no digest_id       -> False
table not present  -> False
```

An older database is a fact about the environment, not a defect in the caller.
An intent recorded against one should get "no persisted digest", not a stack
trace. A test asserts both the `None` connection and the missing-table paths
return `False`.

## What would make enforcement unconditional

```text
1  every live intent resolves to a persisted digest
2  the legacy rows are archived, or accepted as pre-table history
3  the flag default flips, in a change somebody reviews
```

Step 2 is a decision rather than work. Those rows are not wrong; they are older
than the table, and somebody has to say whether that is acceptable in the audit
record or whether they should be marked.

## What this does not do

```text
not  send anything                  email_delivery is false
not  queue anything for sending     the intent's own vocabulary starts at
                                    dry_run_recorded
not  store a recipient              no column for one, in either table
not  store a rendered body          the payload and a hash, not the artefact
```
