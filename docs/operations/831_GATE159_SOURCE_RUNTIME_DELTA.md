# 831 — Gate 159 delta: what changed, and what is next

## Lanes

```text
orchestration_runtime_ready   created, and TRUE
collection_job_store_ready    unchanged, true
worker_runtime_ready          unchanged, true
scheduler_runtime_ready       unchanged, true
source_monitoring_live        unchanged, FALSE
approved_source_count         unchanged, 0
```

One lane was created. None that was false became true.

## What Gate 159 added

```text
migration 0045          nf_source_orchestration_cycles, ownership only
an identity service     cycle_id over (version, cadence, slot); NOT the job id
a trigger service       7 states, injected clock, slot-aligned wakes
a lock repository       atomic acquire, reclaim, release, staleness
a missed-window service bounded catch-up, restart-idempotent
an orchestration runtime scheduler -> store -> worker, one report
a health lane           orchestration_runtime_ready, 9 conditions
4 routes                3 GET, 1 dry-run POST that rolls back
a process               one-shot default, bounded loop, no `while True`
a systemd unit          WRITTEN, deliberately NOT enabled
a verifier              36 checks, phases in separate processes
146 tests
10 artifacts
4 docs                  827, 828, 829, 830, 831
```

## What it did not add

```text
a collector                     Gate 161
raw payload persistence         Gate 160
an approved source              Gate 162, and then a human
accepted source terms           a human. No gate clears this.
a schedule advance              last_checked_at untouched
a completed job                 the database refuses one
a running process               the unit is written, not enabled
```

## Four defects found by measuring, all mine

**1. The reclaim path was unreachable.** `read_last_served_slot` counted a
crashed slot as served, so the trigger refused before acquisition. The expiry
existed, the reclaim existed, and nothing could reach them — one crashed
orchestrator would have blocked its slot forever, which is exactly what the
migration's `owner_has_an_expiry` CHECK was written to prevent. Doc 829 has the
measurement and the fix.

**2. A health condition that could not fail.** `catchup_is_bounded` compared
`slots_offered` with itself. Now it checks the recoverable set against the
bound, and that `catchup_was_bounded` agrees with the dropped count — falsifiable
in both directions.

**3. The orchestrator had no default clock.** Its help text said `--now`
"defaults to the real clock"; nothing implemented that, so the documented
default invocation refused with `no_clock_supplied` and printed a report of
nulls. The systemd unit would have called it exactly that way.

**4. A probe measured one case twice under two names.** "A live owner" and "an
expired owner" were both evaluated at 09:00 and 09:20 — the same hourly slot.
Both branches did fire; the labels lied. Each case now runs in its own slot.

And the substring-vs-meaning defect for the **seventh and eighth** times: a
`grep -c "while True"` matched the docstring sentence saying there is none, and
a test assertion matched the phrase `"only recovery may report"` against the
identifier `only_recovery_may_report`. Both are now AST parses or exact-key
matches. The running tally is in doc 825.

## The block's intent, checked

> Build the runtime machinery required for source collection while keeping every
> live-source path hermetic and inactive. Do not let runtime existence imply
> live monitoring.

Gate 159 is where that instruction bites hardest, because a periodic trigger is
the single most plausible thing in this campaign to mistake for live monitoring:
something now wakes on a cadence and writes rows. The four separations remain
separately reportable:

```text
runtime exists            orchestration_runtime_ready = true
collection is approved    approved_source_count = 0
source terms approved     171 blocked, terms_state = terms_unknown
live monitoring active    source_monitoring_live = false
```

Gate 159 moved only the first.

## The one decision left to a human

`ops/systemd/nativeforge-source-orchestrator.service` is written and **not
enabled**. Nothing in the repository installs or enables it.

Writing the unit proves the runtime is supervisable. Starting it is a different
claim — that something should wake on its own on this host — and that belongs to
whoever runs the host. All six of the unit's stated preconditions are currently
verified by `scripts/verify_nativeforge_source_orchestration_runtime.sh`.

## What still blocks a collection

```text
1  raw payload persistence   Gate 160   engineering
2  a collector envelope      Gate 161   engineering
3  source allowlist boundary Gate 162   engineering
4  source terms              171 sources — a HUMAN must read them
5  human review              a HUMAN must look at each source
```

A loop that wakes every hour does not make items 4 and 5 into engineering. It
means the backlog is now measured hourly rather than whenever somebody remembers
to run a command. Gate 155's rule stands: **do not recommend more wrapper gates
around a blocker only a person or an approval can clear.**

## Gate 160 carry-forward

```text
- Gate 156 owns schedule evaluation.
- Gate 157 owns worker execution and job leases.
- Gate 158 owns the persistent job lifecycle.
- Gate 159 owns periodic orchestration and cycle ownership.
- Do not build another job table, job lease, or orchestration lock.
- Do not use nf_source_check_runs for queue or cycle state.
- Job identity stays Gate 99B-compatible; cycle identity is separate and is
  NOT a job id.
- A stored payload is not a payload that was fetched.
- A payload row must not imply a source was contacted, exactly as a persisted
  job does not imply a collection and a fired trigger does not imply a check.
- `completed` remains unreachable without execution proof. If Gate 160 defines
  what an execution proof IS, that is the moment "a job finished" becomes a
  claim this system can make - it deserves the whole gate, not a corner of one.
- Nothing may set execution_proof_ref until that gate exists.
- Do not advance last_checked_at. Writing it asserts a check occurred.
- source_monitoring_live remains false.
- Verifier cleanup runs after the FINAL process write.
- Always re-stamp after commit.
```

## The alembic head pins

Migration 0045 moved **ten** real head pins from 0044, found on the first pass by
running the unquoted structural sweep — including `== "0044 (head)"`, which no
grep for the bare quoted revision finds. Gates 158 and 159 have now both caught
that line first time.

Nine mentions of 0044 were deliberately left alone as provenance: which migration
created the jobs table, Gate 158's own `MIGRATION` constant, the verifier's check
that the 0044 *file* exists, and the `migration_added_by_this_gate` line Gate 158
renamed precisely so it would not go stale here. It did not.
