# 830 — Gate 159: missed-window recovery

What happens when the orchestrator was down, and why recovering a window
correctly produces no new work.

## A missed window is a TRIGGER slot, not a source check

Measured in the survey:

```text
nf_opportunity_sources rows            40
rows with last_checked_at NULL          0
newest last_checked_at        2026-06-29 21:44:29
nf_source_check_runs rows               0
```

`last_checked_at` is roughly eleven weeks stale and nothing advances it, because
advancing it is what an actual source check does and none has happened. Every
source therefore sits **permanently due in a slot that never moves**.

Two consequences:

1. A missed window cannot be derived from source cadence. The source slot is the
   same slot it was in June, so there is no sequence of missed source windows to
   walk. Missed windows come from the **orchestration trigger slot** — a wall
   clock cadence this gate owns.

2. The orchestrator **must not advance `last_checked_at`**. Writing it would
   assert that a check occurred, which is the `persisted job != execution` rule
   applied to schedule advancement. Gate 159 leaves it alone, which means every
   source stays due and the backlog stays visible.

A test parses every Gate 159 module's AST to prove none of them passes
`last_checked_at` as a keyword argument — parsed rather than scanned, because
several of those modules discuss it in prose to explain why they must not.

## Recovering a slot does not invent work

Because the source slot never moves, every recovered orchestration slot
evaluates the same source schedules and computes the same Gate 158 job ids:

```text
recovering 1 missed slot    creates 1 cycle row,  0 new job rows
recovering 4 missed slots   creates 4 cycle rows, 0 new job rows
```

Measured:

```text
=== MISSED WINDOW: jump 5 hours forward
  ran=True trigger=missed_window
  missed_detected=5 recovered=4
  created=0 reused=3
  job rows=3  (still 3: recovery invents no work)
  cycle rows=7
```

That is not a defect — it is the reason recovery is safe. Gate 158's
deterministic `job_id` plus its unique index absorb the repetition: recovery
records *that the slot was served* and re-enqueues the same work, which
deduplicates. It does not fabricate five copies of a backlog.

`jobs_created` being zero on a recovery pass is the honest number, and reused
rows are **not** counted as created ones.

## The bound

```text
default max_catchup_slots   6
applied by                  the TRIGGER, not the recovery pass
```

The bound lives on the trigger so a caller cannot request an unbounded catch-up
by calling recovery directly. Recovery serves exactly the slots the trigger
declared recoverable and reports how many the bound dropped.

Measured, a thirty-hour outage at hourly cadence with a bound of four:

```text
trigger=missed_window
missed_detected=30
recovered=3
dropped_by_bound=26
```

Recovered is three rather than four because the **current** slot is served by
the cycle itself and is excluded from recovery — `recovery_excludes_the_current_slot`
is reported so that difference is explicable rather than looking like an
off-by-one.

Without a bound, a process down for a month at hourly cadence would wake and
replay seven hundred slots, each one a full scheduler pass over 177 sources, all
producing the same deduplicated rows.

### The bound keeps the most RECENT slots

```text
recoverable_slot_indexes == missed_slot_indexes[-bound:]
```

The oldest slots describe work the newest already covers. Serving the oldest
four of a thirty-slot gap would leave the system twenty-six hours behind and
having done nothing useful.

`slots_dropped_by_the_bound` is reported rather than discarded silently — an
operator who lost a week of slots should be told how many were not replayed. The
health condition checks both halves: that the recoverable set never exceeded the
bound, **and** that `catchup_was_bounded` agrees with whether anything was
dropped. A system that quietly threw away a week would otherwise pass.

## Restart idempotency

```text
=== RESTART IDEMPOTENCY: run the same instant again
  ran=False trigger=already_triggered
  duplicate_suppressed=1
  cycle rows 7 -> 7  (unchanged)
  job rows=3
```

Recovery acquires the cycle row for each slot, and acquisition is atomic on the
unique index. A second restart finds those rows present and reports them
suppressed rather than recovering them again.

Recovering the **same outage** twice likewise recovers nothing:

```text
second_recovery_recovered   0
cycle rows                  unchanged
```

## A worker does not re-chew a settled backlog

After a cycle, the job rows are `refused` — neither `queued` nor `retry_wait` —
so the next worker pass loads zero of them. Clearing the blocker is what puts a
job back in the worker's path, via Gate 158's `refused -> queued` transition.

That transition is the one this campaign is built around: when somebody finally
reads those 171 sets of terms, the jobs become runnable work again rather than
needing to be recreated, and the record of how long they waited survives.

## What recovery never does

```text
jobs_completed              0
collectors_invoked          0
live_source_calls           0
network_calls               0
last_checked_at_advanced    false
source_monitoring_live      false
```

And a recovery pass acquires with `allow_reclaim=False`, so catching up on
history cannot steal a slot another process is actively serving. It is
reconstructing the past, not competing for the present.
