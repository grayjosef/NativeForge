# Gates 151-155 — operational durability, closed

## What the block did

```text
151  a digest is persisted and reads back with its payload hash intact
152  recorded evidence replays; legacy gaps are reported, never filled
153  that state exports, restores into an isolated database, and still
     passes the Gate 152 replay
154  service, migration and code-freshness state is modelled; ten
     failure modes are named; the next safe action is derived
155  this close
```

Together: evidence this system writes can be re-read, re-proved, moved
to another database and re-proved there, and the deployment can say
what state it is in.

## What the block did NOT do

**Nothing that was false at Gate 150 is true now.**

The four lanes above did not exist at Gate 150 - measured, zero files
mentioned any of them. They were created and proved. No approval was
granted, no capability activated, no decision moved.

```text
internal_demo_beta         GO          unchanged since Gate 145
controlled_customer_beta   LIMITED_GO  unchanged since Gate 145
production_rollout         NO_GO       unchanged since Gate 145
```

## The two claims a reader will reach for, and why both are wrong

```text
"NativeForge has backups"
  No. Gate 153 exports controlled dev/demo state and reloads it into
  an isolated database. The Gate 61/65 production harness needs a
  managed instance and still returns SKIP. Different harnesses,
  opposite questions.

"NativeForge is monitored"
  No. Gate 154 lets the deployment report its own state when asked.
  Nothing watches it. No APM, no alerting, no external monitor, no
  uptime record. A person runs a verifier.
```

## What comes next, and why

**source_collection_runtime** — the scheduler that would poll approved sources

```text
candidate                 blockers  human  engineering
source_collection_runtime      7      2            5
additional_durability          0      0            0
email_activation               1      1            0
object_storage_activation      1      1            0
production_infrastructure      1      1            0
customer_activation            4      4            0
```

Source collection is the only candidate where engineering can clear a
majority of the blockers. Five of its seven are absent components - a
scheduler runtime, a background worker, a periodic trigger, a durable
backend, a raw payload store. `backend_lifespan_hook_service` has
described itself since Gate 102 as "the attach point a future
in-process scheduler would use, and a record of the fact that nothing
is attached to it."

Every other candidate is blocked only by people:

```text
customer activation   4 approvals, 0 technical
email                 a provider configuration decision
object storage        a provisioning decision
production            procurement
more durability       nothing is blocked; it would harden the hardened
```

Recommending any of those would produce another readiness wrapper
around a blocker only a person can clear, which is the one thing this
gate is forbidden to do.

## What the recommendation does not mean

- **Not** that `source_monitoring_live` would become true.
- **Not** that any source would be polled. 171 registry sources are
  `terms_blocked`, 6 are `human_review_blocked`, and 0 are approved.
- **Not** that the two human source blockers are cleared. They stay.
- **Not** that a collector is activated.

A scheduler with an empty allowlist polls nothing and contacts
nothing, which is exactly how it should be proved before any source
is approved. It removes five of the seven reasons monitoring cannot
start; the remaining two stay human.
