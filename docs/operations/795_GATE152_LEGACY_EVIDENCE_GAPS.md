# 795 — Gate 152: the legacy evidence gaps

## What they are

Delivery intents whose digest was never persisted. They named a digest, the
digest was real at the time, and there was nowhere to keep it.

```text
status       legacy_gap
backfilled   false
count        reported on every verifier run
```

## Why `legacy_gap` and not `missing_record`

A missing record is one that should exist and does not. These are not that.

The intents recorded a real intention accurately. What they could not do was
keep the thing they referred to, because `nf_tenant_digest_records` did not
exist until migration 0042. They are **not wrong; they were un-storable at the
time**, and calling them missing would blame the record for the schema.

The distinction is load-bearing. `missing_record` implies somebody owes a
record and can produce it. `legacy_gap` says nobody can, ever, for these.

## Why they are not backfilled

The digests cannot be reconstructed.

Regenerating one requires the snapshot it was built from to still exist and be
unchanged, and nothing guarantees either. A regenerated digest would be *a*
digest for that period, not *the* one the intent referred to.

Storing it would produce a record that looks like evidence and is not — which is
worse than the gap it fills, because a gap is honest and a plausible fabrication
is not. An auditor reading a backfilled digest would have no way to tell it from
a contemporaneous one.

**No fake evidence was backfilled.**

## Reporting a gap is a readiness condition

`legacy_gaps_reported` is one of the six conditions on `audit_replay_ready`, and
`legacy_gaps_backfilled` is checked as a blocker. A replay that quietly produced
digests for these intents would score better on every other condition and be
worthless, so:

```text
a backfill FAILS the lane rather than passing it
```

A test asserts exactly that.

## How the count falls

Honestly, and only forward.

```text
require_persisted_digest=True   enforced end to end since Gate 152
```

Every new intent recorded with enforcement on must resolve to a persisted
digest or it is refused — `storage_allowed` false, no row written, blocker
named. The verifier prints the remaining legacy count on every run, so it falls
visibly as new intents accumulate.

The default is off, deliberately: the existing intents predate the table, and
Gate 142's callers pass no persisted digest and are correct as written. A
blocker applied unconditionally would retroactively invalidate history that is
not wrong.

## What would close them

```text
1  every live intent resolving to a persisted digest
2  the legacy rows archived, or accepted as pre-table history
3  the flag default flipped, in a change somebody reviews
```

Step 2 is a decision rather than work. Those rows are older than the table, and
somebody has to say whether that is acceptable in the audit record or whether
they should be marked.

## What an operator should say about them

```text
say    "these intents predate the digest records table; the digests they
        named were never stored and cannot be reconstructed"
say    "every intent recorded since enforcement is linked and verifiable"

avoid  "those digests are missing"       they were never storable
avoid  "we can regenerate them"          not the same digests
avoid  "the audit trail is complete"     it is complete going forward
```
