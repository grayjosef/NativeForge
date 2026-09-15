# 807 — Gate 155: what Gates 151–154 actually moved

Read-only survey. Every number below was measured, and the method is named.

## The four lanes did not go from false to true

They did not exist.

```text
measured at 4d336d1 (Gate 150), across src/:

tenant_digest_persistence_live      0 files mention it
audit_replay_ready                  0 files mention it
operational_backup_restore_ready    0 files mention it
operational_health_ready            0 files mention it
```

So the honest delta is **four lanes created and proved**, not four false lanes
flipped. A lane that did not exist was never `false`; it was unmeasured. The
distinction matters because "four lanes went true" invites the reading that four
things that were blocked became unblocked, and nothing did.

**Nothing that was false at Gate 150 is true now.**

## The nine that were false are still false

Gate 150 recorded these as `not_approved`, in
`artifacts/customer_beta_reassessment_gate150/customer_beta_reassessment_survey.json`:

```text
controlled_customer_pilot          false  ->  false
production_rollout                 NO_GO  ->  NO_GO
customer_auth_live                 false  ->  false
verified_operational_binding       false  ->  false
consent_boundary_documented        false  ->  false
customer_beta_scope_approved       false  ->  false
source_monitoring_live             false  ->  false
email_delivery                     false  ->  false
object_store_configured            false  ->  false
```

Confirmed today by each lane's own verifier. All nine unchanged.

## The three decisions

```text
                          Gate 145   Gate 150   Gate 155
internal_demo_beta        GO         GO         GO
controlled_customer_beta  LIMITED_GO LIMITED_GO LIMITED_GO
production_rollout        NO_GO      NO_GO      NO_GO
```

No decision changed, and none should have: Gates 151–154 were durability gates,
not approval gates. A block of four gates that moved a customer or production
decision without a new external approval would mean one of them had granted
itself something.

## What became durable in controlled_dev_demo

```text
151  a digest is persisted and reads back with its payload hash intact
152  recorded evidence replays; 85 legacy gaps are REPORTED, never backfilled
153  that state exports, restores into an isolated database, and still passes
     the Gate 152 replay
154  service, migration and code-freshness state is modelled; ten failure modes
     are detected and named; the next safe action is derived
```

Together: evidence this system writes can now be re-read, re-proved, moved to
another database and re-proved there, and the deployment can say what state it
is in. None of that was true four gates ago.

## What remains production-only or false

```text
production_backup_ready      Gate 61/65 harness, RESULT=SKIP. Needs a managed
                             PostgreSQL instance. Gate 153 did not move it and
                             its verifier was re-run to confirm.
production_monitoring        false. No APM, no alerting, no external monitor,
                             no uptime record. Gate 154 did not move it.
production_postgres_rls      SKIP, same reason as the backup harness.
```

## Gate 150's next-block constant is now spent

`customer_beta_reassessment_service.NEXT_BLOCK` is a module constant reading
`Gates 151-155, operational durability`. That block is now complete, so the
constant points at finished work.

This is the same staleness Gate 154 found in
`beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION`, which had been
recommending a matrix finished at Gate 145. Neither failed anything, because a
constant cannot go stale loudly.

Gate 155 must therefore produce a **new** recommendation rather than inherit
one, and the same trap applies to whatever it writes down.

Worth recording: Gate 150 predicted the block's shape and got two of five
slightly wrong — it expected 152 to be source terms tooling and 154 to be
on-call. The block ran 152 as audit replay and 154 as observability. A
prediction is not a measurement.

## Does more durability work have unlock value?

Measured against what each candidate is actually blocked on, rather than
against how the last four gates felt.

```text
CUSTOMER ACTIVATION                            4 blockers, 4 human
  customer_auth_live                           a real person must sign in
  verified_operational_binding                 an approval must be signed
  consent_and_data_boundary_documented         the customer must consent
  customer_beta_scope_approved                 an approver must approve
  -> engineering can advance NONE of these

SOURCE MONITORING ACTIVATION                   7 blockers, 5 ENGINEERING
  terms_review_incomplete                      human: 171 sources terms_blocked
  human_review_only_sources                    human: 6 sources
  scheduler_component_absent:scheduler_runtime          engineering
  scheduler_component_absent:background_worker          engineering
  scheduler_component_absent:periodic_trigger           engineering
  scheduler_component_absent:persistent_backend         engineering
  scheduler_component_absent:production_raw_payload_store engineering
  -> engineering can advance FIVE

EMAIL ACTIVATION                               1 blocker
  no_email_provider_configured                 an approver, then a provider
                                               admin. Configuring it sends mail
                                               on someone's behalf.
  -> engineering can advance NONE

OBJECT STORAGE ACTIVATION                      1 blocker
  document_body_storage_is_not_configured      an approver, then engineering
                                               provisions a store
  -> engineering can advance NONE without the provisioning decision

PRODUCTION INFRASTRUCTURE                      procurement
  a managed database instance                  not engineering work
  -> engineering can advance NONE

MORE DURABILITY                                nothing is blocked
  -> the four lanes are proved. Another durability gate would harden
     something already hard.
```

Measured from the source registry today:

```text
registry rows                177
terms_blocked                171
human_review_blocked           6
activation_approved            0
scheduler_attached         False
collectors_started         False
```

## The wrapper test

Gate 155's own rule: do not recommend another readiness wrapper around a
blocker only a person can clear.

```text
email          one blocker, and it is a provider configuration decision.
               Another readiness gate would describe the same refusal in more
               detail. WRAPPER.
object store   same shape. WRAPPER.
customer       four blockers, all human. Gates 146-150 already made each
               refusal exact. WRAPPER.
source         five of seven blockers are ABSENT COMPONENTS. Building a
               scheduler runtime is a missing thing being built, not a
               refusal being re-described. NOT a wrapper.
```

`backend_lifespan_hook_service` (Gate 102) documents itself as "the attach point
a future in-process scheduler would use, and a record of the fact that nothing
is attached to it." `scheduler_attached` is `False` today. The attach point has
been waiting for fifty gates.

## Which block has the highest dependency unlock

Source collection runtime, and it is not close.

- It is the only candidate where engineering can clear a majority of the
  blockers.
- It is upstream of the product: a grant intelligence system whose sources are
  never polled is a system that shows a tenant the same data forever.
- It can be built and proved with **zero approved sources**, contacting nothing.
  A scheduler with an empty allowlist polls nothing, which is exactly how it
  should be proved before any source is approved.
- It does not make `source_monitoring_live` true, and must not. It removes five
  of the seven reasons it cannot be.

The two human blockers stay human. When the terms review completes, activation
becomes one approval away instead of an approval plus a runtime that does not
exist.

## What Gate 155 builds

A reassessment service that compares rather than recomputes, a next-activation
decision service that ranks by measured unlock value, four GET routes, a
cockpit closeout card, a verifier, artifacts and docs. It activates nothing,
creates no activation mechanism, and changes no lane.
