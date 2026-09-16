# 829 — Gate 159: duplicate trigger suppression and cycle ownership

How repeated polling, two competing processes and a restart all resolve to one
effect — and how a crashed process gets its slot back.

## The measurement that makes a periodic trigger safe at all

Gate 158's `job_id` digests `scheduled_for`, which is Gate 156's computed
`next_run_at`. If that moved with the observer's clock, every poll would mint a
new id and Gate 158's idempotency would be worthless the moment anything polled.

Measured before building anything:

```text
now=2026-09-16T12:00:00Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-16T12:00:01Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-16T18:44:13Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-17T03:00:00Z  next_run_at=2026-09-08T00:00:00+00:00
```

`next_run_at` is `last_checked_at + interval`, derived from stored facts and not
from `now`. And end to end, two committed cycles 7.5 hours apart:

```text
cycle A   created=3  deduplicated=0
cycle B   created=0  deduplicated=3
job rows                          3
```

**Job-level idempotency already held.** Gate 159 did not need to protect job
rows. It needed to protect everything else: cycle work, cycle records, and the
slot itself.

## The seven trigger states

```text
not_due            the window has not turned over
due                this slot has not been served and should be
already_triggered  this exact slot has been served
missed_window      slots between the last served one and now went unserved
recovered          reported by the recovery pass, never decided by the trigger
blocked            a prerequisite for triggering at all is absent
unknown            the inputs do not support a decision
```

`already_triggered` and `not_due` are deliberately different. "Not due" is a
statement about the clock; "already triggered" is a statement about history.
Collapsing them would make a duplicate attempt indistinguishable from a poll
that arrived early — and duplicate suppression is the thing this gate must
prove.

Decided, not described:

```text
nothing ever served        due                run=True   missed=0
this slot already served   already_triggered  run=False  missed=0
later in the same slot     already_triggered  run=False  missed=0
the next slot              due                run=True   missed=1
a five hour gap            missed_window      run=True   missed=6
the clock went backwards   blocked            run=False
the trigger is disabled    blocked            run=False
```

A clock that moved backwards is **blocked, not reinterpreted**. Serving a slot
already passed would re-run history.

`should_run_a_cycle` is checked against the permitting set in both directions by
the invariant checker, so a state added later that nobody wired in refuses by
default rather than being permitted by omission.

## Suppression, measured end to end

```text
cycle 1  at 12:00:00  ran=True   trigger=due                rows: 1 cycle, 3 jobs
cycle 2  at 12:59:59  ran=False  trigger=already_triggered  rows: unchanged
                                 duplicate_triggers_suppressed=1
cycle 3  at 12:00:00  ran=False  trigger=already_triggered  rows: unchanged
         (a DIFFERENT owner)     duplicate_triggers_suppressed=1
cycle 4  at 13:00:00  ran=True   trigger=due                created=0, reused=3
```

Cycle 4 is the permitting branch. A trigger that never fired would prove nothing
about the refusals.

## Two layers, not one

```text
the slot     ux_nf_source_orchestration_cycles_cycle_id
the work     ux_nf_source_collection_jobs_job_id        (Gate 158)
```

Even if a cycle row were somehow re-acquired, the work it does is idempotent on
Gate 158's deterministic `job_id`, so the store deduplicates. A duplicated cycle
costs time, not correctness.

## Ownership, and the two branches

```text
CASE 1  a LIVE owner, slot 12:00, one-hour lease
        theft at 12:10  -> acquired=False
        refused with    -> ownership_has_not_expired_and_cannot_be_stolen

CASE 2  an EXPIRED owner, slot 15:00, one-minute lease
        reclaim at 15:30 -> acquired=True, reclaimed=True
        new owner        -> owner-rescuer
        reclaim_count    -> 1
        outcome          -> reclaimed_from_an_expired_owner

CASE 3  a RECOVERY pass, allow_reclaim=False
        -> acquired=False. Catching up on history does not compete for now.
```

Each case runs in its **own slot**. An earlier probe used 09:00 and 09:20 for
what it called a live owner and an expired one — the same hourly slot, so it
measured the expired case twice under two names. Both branches did fire; only
the labels lied. One slot per case, or the labels cannot be trusted.

## The defect this gate found in itself

The reclaim above was, at first, **unreachable**.

```text
=== 9. EXPIRY RECLAIM: an owner that never released
  first acquire ran=True
  stale owners at +5min: 1
  reclaim ran=False           <-- the reclaim never happened
  trigger=already_triggered
```

`read_last_served_slot` returned the highest slot index for which **any** row
existed, in any status. So a process that acquired a slot and crashed left an
`acquired` row, and every later process inside that slot asked the trigger
first, was told `already_triggered`, and returned before attempting
acquisition. The expired ownership was never reclaimed — for that slot, forever.

That is exactly the failure the migration's `owner_has_an_expiry` CHECK was
written to prevent. The expiry existed, the reclaim existed, and the trigger
made the reclaim unreachable.

Gate 134F's rule is that an unreachable permitted branch makes a refusal
unfalsifiable. Here it made a **recovery** unfalsifiable, which is worse: the
system looked like it had a safety net it could not use. The probe printed
`stale owners: 1` and `reclaim ran=False` in the same breath, and both lines had
to be read together to notice.

### The fix

A slot with a crashed owner is **unfinished**, not served:

```text
counted       released                   somebody completed it
counted       acquired, not yet expired  somebody is on it right now
NOT counted   acquired, expired          the owner is gone; reclaimable
NOT counted   expired / abandoned        explicitly given up
```

`read_last_served_slot` now takes the clock, because "expired" is derived
against it. `unfinished_slot_count` is reported alongside, so a later reclaim is
explicable rather than looking like a slot that ran twice.

After:

```text
history at T+5: last_served=None unfinished=1
RECLAIM ran=True reclaimed=True
row now: owner_id=owner-rescuer, cycle_status=released,
         cycle_outcome=completed_normally, reclaim_count=1
```

## What a crash costs

One lease window. A cycle killed mid-pass leaves its ownership row `acquired`
with an expiry; another process reclaims it once that expiry lapses. Not the
slot forever, and not a manual row deletion.
