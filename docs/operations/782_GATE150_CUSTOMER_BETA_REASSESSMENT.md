# 782 — Gate 150: the customer beta reassessment

## The decision

```text
internal_demo_beta         GO
controlled_customer_beta   LIMITED_GO
production_rollout         NO_GO
```

## Did it change since Gate 145?

**No. Not one lane, not one value.**

```text
internal_demo_beta         GO          ->  GO
controlled_customer_beta   LIMITED_GO  ->  LIMITED_GO
production_rollout         NO_GO       ->  NO_GO
```

That is the correct answer and it was the expected one. Gates 146–149 were
boundary gates: built to make refusals exact, not to clear them. A block of four
gates that moved a lane without a new external approval would mean one of them
had granted itself something, and the right response would have been to distrust
the report rather than celebrate it.

## Did each specific lane change?

```text
customer_auth_live              false  ->  false
verified_operational_binding    false  ->  false
consent_boundary_documented     false  ->  false
customer_beta_scope_approved    false  ->  false
controlled_customer_pilot       false  ->  false
production_rollout              NO_GO  ->  NO_GO
```

Six questions, six no's.

## What did change: what is understood

### Gate 146 — customer auth

Was reported as `invite_binding_passed`. Is actually a conjunction of three
sequential events, none of which has started: one identity exists — the owner —
and no invite has ever been recorded. The state was never "an invite waiting to
be accepted", so an operator acting on the old wording would have gone looking
for one and found nothing.

### Gate 147 — verified binding

Was reported as `owner_decision_absent`, owned by "the owner". Is actually five
refusals, any one sufficient, one of which never clears. And granting the owner
decision would move nothing, because there is no organization it could apply to.

### Gate 148 — consent and customer data

Was reported as a named gap. Is actually a live exposure one gate ahead: every
post-award production write is gated on `customer_auth_live` and
`verified_operational_binding`, both identity facts and neither consent — so the
day Gates 146 and 147 succeed, a customer write becomes permitted with nothing
recording that a tenant agreed.

### Gate 149 — pilot activation

Was reported as "not approved". Is actually not a value at all: no table records
a pilot approval, no flag exists, no code path assigns it. Nine prerequisites,
one satisfied.

## The throughline

**A real customer organization has to exist, and no approval supplies one.**

Found independently by Gates 147, 148 and 149. The campaign had been describing
each remaining blocker as one decision away. None of them was, and the front of
the queue is not a decision at all.

## The four approvals still outstanding

```text
customer_auth_live
verified_operational_binding
consent_and_data_boundary_documented
customer_beta_scope_approved
```

**None is technical.** Every one is a person deciding, a person signing in, or a
document nobody has written. That is worth stating plainly because it means no
amount of further engineering advances this block.

## The six conflations

Each is a readiness fact that reads like the capability beside it:

```text
second_person_readiness_passed   is not  customer_auth_live          (146)
approval_boundary_ready          is not  verified_operational_binding (147)
customer_data_write_guard_ready  is not  customer data writes allowed (148)
activation_package_ready         is not  controlled_customer_pilot    (149)
prerequisites_would_permit       is not  may_activate                 (149)
the demo organization            is not  a customer organization      (145)
```

A reassessment that collapsed any of them would report a GO the evidence does
not support. That is the single failure mode this gate has, and the invariants
refuse it: a `controlled_customer_beta: GO` arriving without all four approvals
is rejected, and a test forges exactly that to prove the refusal fires.

The honest GO branch is kept reachable — with all four approvals granted the
delta correctly reports `changed: True` — because an unreachable permitted
branch makes the refusal above it unfalsifiable.

## What remains blocked

```text
customer_auth_live              an event, stage 1 of 3 not started
verified_operational_binding    five refusals, one never clears
consent_and_data_boundary       a document nobody has written
customer_beta_scope_approved    a decision
controlled_customer_pilot       nine prerequisites, one satisfied, and no
                                mechanism to record an activation
source_monitoring_live          171 terms reviews, then per-source approvals
email_delivery                  a provider and four other things
object_store_configured         five settings and an external verification
production_rollout              always NO_GO; not a computation
```

## Next

`783` on what is safe to say, `784` on what is not, `785` on the next block,
`786` on the block closeout.
