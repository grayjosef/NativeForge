# 810 — Gate 155: what may be said after the block, and what may not

Read both halves. Serving only the safe list makes the omissions invisible, and
the omissions are the point.

## Safe to say

```text
a digest this system wrote can be read back, and its payload hash checked

the evidence chain this system recorded can be replayed

the gaps in that chain are counted and reported, and were not filled in

controlled dev/demo operational state can be exported, restored into an
isolated database, and re-verified there

this deployment can say which services are up, whether its database matches
its migrations, whether the built frontend matches HEAD, and whether the
running backend predates the code

ten named operational failure modes are detected and given an exact action

no readiness lane above required a new approval, and none granted one
```

Every one is scoped to `controlled_dev_demo` and to fixture data for one demo
organization. Said without that scope, each becomes a claim about a product.

## Unsafe to say

### "NativeForge has backups"

No managed database instance exists, no backup automation, no PITR, and no
provider restore has ever run. The Gate 61/65 verifier measures exactly this and
returns `RESULT=SKIP`; Gate 155's verifier re-runs it to confirm.

**True instead:** controlled dev/demo state can be exported and restored into an
isolated database.

### "NativeForge is monitored"

Nothing watches this system. No APM, no alerting, no external monitor, no uptime
record, no error budget, no rota. A person runs a verifier.

**True instead:** the deployment can report its own state when asked, and names
what it cannot observe.

### "Customer data is safe / durable / backed up"

No customer data exists. Nothing has been made durable for a customer.

**True instead:** fixture data for one demo organization is durable.

### "The audit trail would satisfy an auditor"

Replay proves internal consistency, not legal standing, and 85 legacy delivery
intents still name digests that were never written.

**True instead:** records can be joined and checked against their own hashes.

### "The controlled customer beta is ready to start"

Four approvals are outstanding and none is technical. Gates 151–154 did not
touch any of them.

**True instead:** LIMITED_GO, unchanged since Gate 145.

### "Operational durability moves the product toward production"

Production is blocked on procurement and approvals. Durability work does not
shorten that queue.

**True instead:** the controlled dev/demo system is materially harder to lose
data in and easier to diagnose.

## The five conflations held by invariants

```text
operational_backup_restore_ready  is not  production_backup_ready
operational_health_ready          is not  production monitoring
audit_replay_ready                is not  a legally sufficient audit trail
tenant_digest_persistence_live    is not  a digest was delivered or read
durable in controlled_dev_demo    is not  ready for production
```

The first two are checked directly: remove either warning from the reassessment
payload and `durability_reassessment_invariant_failures` fails.

## The sentence that carries the whole gate

> Four lanes are true that were not true before, and **nothing that was false
> became true**.

Both halves are needed. The first without the second overstates the block; the
second without the first understates it.
