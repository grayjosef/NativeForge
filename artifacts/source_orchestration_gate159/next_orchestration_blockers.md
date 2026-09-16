# Next: what still stands between a running loop and a collection

Gate 159 built the periodic orchestration runtime. Something now wakes on a
cadence, takes one slot at a time, and recovers the slots it missed. It contacts
nothing, and it cannot.

## What is now true

```text
a loop wakes on a cadence            hourly by default, slot-aligned
exactly one cycle per slot           unique index on (organization_id, cycle_id)
a duplicate trigger is named         already_triggered, not a silent skip
two owners cannot both hold a slot   the live one is not stealable
a crashed owner does not block it    expired ownership is reclaimable
missed slots recover once            bounded, and the dropped count reported
a restart recovers nothing new       the slot is already served
```

## What still blocks a collection, in the order it has to clear

```text
1  raw payload persistence   Gate 160. There is nowhere to put a response.
2  a collector envelope      Gate 161. No code can fetch anything.
3  source allowlist          Gate 162. Zero sources are approved, and this is
                             where approval gets defined.
4  source terms              a HUMAN must read them. 171 sources are blocked
                             on this and no gate can clear it.
5  human review              a HUMAN must look at each source.
```

Items 1 to 3 are engineering. Items 4 and 5 are not, and a loop that wakes every
hour does not make them so - it means the backlog is now measured hourly rather
than whenever somebody remembers to run a command.

Gate 155's rule stands: do not recommend more wrapper gates around a blocker
only a person or an approval can clear.

## The one decision this gate deliberately left to a human

`ops/systemd/nativeforge-source-orchestrator.service` is written and **not
enabled**. Nothing in the repository installs or enables it.

Writing the unit proves the runtime is supervisable. Starting it is a different
claim - that something should wake on its own on this host - and that is a
choice for whoever runs the host. The unit lists its own preconditions, and all
of them are currently verified.

## What the cadence now makes askable

```text
when did the loop last run              last_cycle_completed_at
when will it run next                   next_trigger_at
did it miss anything while down         missed_windows_detected / recovered
is anything holding a slot it lost      stale_cycle_owners
how long has blocked work been waiting  oldest_live_job_queued_at (Gate 158)
```

That last line is the one the campaign has been building toward. The backlog was
countable after Gate 158; it is now counted on a schedule, which is what makes
"these 171 sources have been waiting since June" a number somebody can watch
grow rather than a thing they have to go and ask for.
