# 808 — Gate 155: the operational durability reassessment

## What improved

Four things this system could not do before Gate 151:

```text
151  a digest it wrote can be read back, and its payload hash checked
152  the evidence chain it recorded can be replayed, and the gaps in that
     chain are counted and reported rather than filled in
153  that operational state can be exported, loaded into a separate
     database, and re-verified there with the Gate 152 replay unchanged
154  the deployment can say which services are up, whether its database
     matches its migrations, whether the built frontend matches HEAD, and
     whether the running backend predates the code
```

`operational_durability_improved` is **true**, and it is derived from all four
lanes being proved — not supplied.

## Exactly which lanes moved

```text
tenant_digest_persistence_live      151   did not exist at Gate 150
audit_replay_ready                  152   did not exist at Gate 150
operational_backup_restore_ready    153   did not exist at Gate 150
operational_health_ready            154   did not exist at Gate 150
```

Measured: `git grep` for each lane name across `src/` at commit `4d336d1`, the
Gate 150 commit. All four returned **zero files**.

## The distinction that matters most in this document

**These four lanes were created. Nothing that was false became true.**

A lane that did not exist was never `false` — it was unmeasured. "Four lanes
went true" invites the reading that four blocked things became unblocked, and
none did. `lanes_that_were_false_and_became_true` is an explicit empty list in
the reassessment payload, in the cockpit card, and in the artifacts, and an
invariant fails if anything ever populates it.

## What remains controlled_dev_demo only

Every one of the four. Each is scoped to one demo organization holding fixture
data:

```text
the digest that persists          a fixture digest
the evidence that replays         fixture intents and audit events
the state that restores           6,000-odd fixture rows for one demo org
the deployment that reports       this host, one backend, one preview
```

No customer data exists, so nothing has been made durable for a customer.

## What remains false

```text
customer_auth_live             false   a real person must sign in as themselves
verified_operational_binding   false   an approval must be signed
consent_boundary_documented    false   the customer organization must consent
customer_beta_scope_approved   false   an approver must approve the scope
source_monitoring_live         false   approvals, and a runtime that is absent
email_delivery                 false   a provider configuration decision
object_store_configured        false   a provisioning decision
controlled_customer_pilot      false   not activated; no mechanism exists
production_backup_ready        false   Gate 61/65 harness, re-run, still SKIP
production_monitoring          false   nothing watches this system
```

Eight of these were recorded by Gate 150 as `not_approved`. All eight are still
not approved. Gates 151–154 touched none of them.

## The customer beta decision

**LIMITED_GO** — unchanged since Gate 145.

The four outstanding approvals are unchanged and none is technical. A durability
block that moved a customer decision would mean one of its gates had granted
itself an approval.

## The production decision

**NO_GO** — unchanged since Gate 145, and no branch in this gate computes
anything else.

```text
what would have to happen first
  a managed database instance            procurement
  backup automation                      needs the instance
  point-in-time recovery                 needs a provider that has it
  an executed provider restore           needs all three
  monitoring and alerting                none of it exists
```

The Gate 61/65 harness was re-run by this gate's verifier and still returns
`RESULT=SKIP`. Gate 153 did not move it and Gate 154 did not move it.

## Two conflations this reassessment refuses to make

```text
operational_backup_restore_ready  is NOT  production_backup_ready
operational_health_ready          is NOT  production monitoring
```

These are the two a reader reaches for, and both are held by invariants: if
either warning is ever removed from the payload,
`durability_reassessment_invariant_failures` fails.

## Decisions are compared, never recomputed

Gate 150 established this and Gate 155 keeps it. `build_durability_reassessment`
takes each decision from the service that owns it and compares it to the
recorded baseline. A summariser that computed its own verdict would be supplying
its own evidence — the defect Gate 144 spent a gate learning.

## Next block

**source_collection_runtime.** See doc 811 for the ranking and the rule that
produced it.
