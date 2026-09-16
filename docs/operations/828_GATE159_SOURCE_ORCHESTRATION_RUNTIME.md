# 828 — Gate 159: the source orchestration runtime

Something now wakes on a cadence, takes exactly one slot at a time, and recovers
the slots it missed while it was down. It contacts nothing, and it cannot.

```text
orchestration_runtime_ready   true
orchestration_process_active  false   the unit is written, NOT enabled
jobs_completed                0
collectors_invoked            0
live_source_calls             0
approved_source_count         0
source_monitoring_live        false
```

## What it composes

```text
Gate 156   evaluates every source against an injected clock
Gate 158   persists the durable job lifecycle, idempotently
Gate 157   claims jobs, refuses them, records why
```

All three already worked. What did not exist was anything that ran them in
order, on a cadence, exactly once per slot, surviving a restart. That is the
whole of Gate 159's contribution: **ordering, exclusivity and recovery.**

It adds no capability to the three gates it calls. After a cycle the same
sources are blocked for the same reasons.

## The order of one cycle

```text
1  evaluate the trigger against the last served slot
2  if it permits, acquire the cycle for this slot   (atomic, unique index)
3  run Gate 156 -> Gate 158 in evaluate_and_enqueue mode
4  run Gate 157 over the persisted backlog
5  recover missed slots, bounded
6  release the cycle, recording what it did
```

Measured against the real registry, one cycle:

```text
sources_seen            177
jobs_created            177
jobs_blocked            177
jobs_claimed              0   (--no-worker on that run)
jobs_executable           0
jobs_completed            0
collectors_invoked        0
live_source_calls         0
slot_key                  2026-09-16T17:00:00Z
next_trigger_at           2026-09-16T18:00:00Z
refusal reasons           5 distinct, x177 sources each
```

## Cycle identity

Deterministic over `(orchestration_version, cadence, slot_index)`, and
explicitly **not** over a PID, a worker id, a startup timestamp or a random
UUID. Suppression works by *recognising* that a slot has already been served,
and an identity that cannot repeat cannot be recognised.

The slot is a **floor**, so every instant inside one window resolves to one
index:

```text
12:00:00  slot 6204   cycle 4b122c04fa78882b...
12:59:59  slot 6204   cycle 4b122c04fa78882b...
13:00:00  slot 6205   cycle 99137a2ec5f767fa...
```

`build_owner_id` is the deliberate opposite: it carries a nonce, because two
processes contending for one cycle must be distinguishable or the loser would
believe it had won. An owner id is never part of a cycle id, and a test parses
`build_cycle_id`'s AST to prove it.

A cycle id is **not** Gate 158's `job_id`. One cycle covers every source and
produces many jobs; reusing the id would make "how many cycles ran" and "how
many jobs exist" the same question. The identity module never imports Gate 99B's
job digest.

## Ownership

`nf_source_orchestration_cycles`, migration 0045. Acquisition **inserts and
catches the integrity error** rather than checking first, because
check-then-insert has a window two processes can both pass through.

That is the third use of this primitive in the block — Gate 157 for the job
claim, Gate 158 for enqueue idempotency, Gate 159 for cycle ownership. The
survey measured **zero** advisory-lock primitives in the repository and a SQLite
backend, so a unique index is the portable atomic operation available.

```text
a live owner      refused: ownership_has_not_expired_and_cannot_be_stolen
an expired owner  reclaimable, and reclaim_count is incremented
a served slot     refused: this_slot_has_already_been_served
a recovery pass   acquires with allow_reclaim=False, so catching up on
                  history cannot steal a slot from the present
```

Staleness is **derived** on read against an injected clock, never stored. A
stored `stale` status would need a sweeper to keep it true and would be wrong
between sweeps.

## This is not a second job lease

```text
nf_source_collection_job_leases   per JOB    who is working this one piece
nf_source_orchestration_cycles    per CYCLE  who is running the loop
```

Measured, not asserted:

```text
lease columns declared on the cycle table   []
job columns declared on the cycle table     []
```

A job lease cannot express "one orchestrator at a time" because there is no
single job to hang it on, and hanging it on an arbitrary one would make the
loop's exclusivity depend on that job still existing.

## The three the database refuses

```sql
CHECK (jobs_completed = 0)
CHECK (collectors_invoked = 0)
CHECK (live_source_calls = 0)
```

The columns exist so a read can assert them rather than trust a Python constant,
and the verifier proves the constraint is real by going around the repository
with a raw `UPDATE` — which raises `IntegrityError`.

Plus: an `acquired` row must carry an `expires_at`, because an owner that could
never expire is how one crashed process blocks a slot forever.

## The process

`scripts/run_source_collection_orchestrator.py`, one-shot by default.

```text
--once           the default, and what the verifier and tests run
--loop           bounded by --max-cycles; there is no unbounded mode
--cadence        one of five, slot-aligned
--now            an ISO instant, for the verifier; otherwise the host clock
```

There is no `while True` — a test parses the AST rather than scanning the text,
because the module docstring says "there is no `while True` in this file" and a
grep for that string matches the sentence ruling it out.

The sleep between cycles is computed from the next **slot boundary**, not from a
fixed interval. A process that slept for `interval` from an arbitrary wake time
would drift off the boundary and eventually serve two slots in one window, or
none.

The entrypoint is the one correct place to read a real clock: it is the boundary
between the host and the deterministic code, and everything downstream receives
the instant as an argument.

## The unit, written and not enabled

`ops/systemd/nativeforge-source-orchestrator.service` exists. Nothing in the
repository installs or enables it, and this gate did not.

Writing the unit proves the runtime is supervisable. Starting it is a different
claim — that something *should* wake on its own on this host — and that is a
choice for whoever runs the host. The unit lists its own preconditions, all
currently verified.

It uses `Restart=on-failure`, deliberately not `always`: this process is
supposed to exit zero after `--max-cycles`, and `always` would make a clean
completion indistinguishable from a crash loop. The backend unit uses `always`
for the opposite reason, documented there.

## What ready does not mean

```text
a source was contacted        no
a collector ran               no
a source is approved          no. Zero are.
source terms were accepted    no. 171 are still blocked, on a human.
a schedule advanced           no. last_checked_at is untouched.
a job was completed           no, and the database refuses one
monitoring is live            no
```

**A trigger that fires is not a source that was checked. A running timer is not
live monitoring.**
