# 781 — Gate 150: the customer beta reassessment, surveyed

Read-only. Nothing was activated, approved, or written.

## The measured state, today

```text
internal_demo_beta               GO           0 blockers
controlled_customer_beta         LIMITED_GO   4 blockers
production_rollout               NO_GO        8 blockers

customer_auth_live               false        stage: second_identity_signed_in
verified_operational_binding     false        5 refusals
consent_boundary_documented      false
customer_beta_scope_approved     false
controlled_customer_pilot        false        1 of 9 prerequisites
activation_mechanism_exists      false
```

## What changed since Gate 145

**No decision. No lane. Not one value.**

```text
internal_demo_beta         GO          ->  GO
controlled_customer_beta   LIMITED_GO  ->  LIMITED_GO
production_rollout         NO_GO       ->  NO_GO
```

That is the correct outcome and it was the expected one. Gates 146–149 were
boundary gates: they were built to make refusals exact, not to clear them. A
block of four gates that moved a lane without a new external approval would mean
one of them had granted itself something.

## What did change: what is understood

Each of the four found the same class of defect, in its own subject.

### Gate 146 — the blocker was one stage earlier than recorded

Gates 144 and 145 reported `invite_binding_passed`. True, and coarse: it is a
conjunction of three sequential events. The live database holds one identity —
the owner — and **no invite has ever been recorded**. So the state was not "an
invite is waiting to be accepted"; the second person has never signed in. An
operator acting on the old wording would have gone looking for an invite and
found nothing.

It also corrected doc 717, whose opening line ("Every command below exists and
has been run end to end") read as though the event had happened, in the runbook
for that very event.

### Gate 147 — one blocker was five

The cockpit reported `owner_decision_absent`, owner "the owner". Five refusals
stand, any one sufficient, and one of them never clears at all. More
importantly: even granting the owner decision moves nothing, because there is no
organization it could apply to.

### Gate 148 — the production-write gate checks identity, not consent

Every post-award repository gates a production write on exactly
`customer_auth_live` and `verified_operational_binding`. Both are identity facts.
Neither is consent. Gates 146 and 147 exist to make both true — so on the day
they succeed, a production customer write becomes permitted with nothing
recording that a tenant agreed. The boundary had to exist before those lanes
turn, which is why Gate 148 came before this one rather than after.

### Gate 149 — the pilot has no representation

`controlled_customer_pilot` is not a value that is false. No table records a
pilot approval, no environment flag exists, no code path assigns it. The package
states what must be true and builds no switch.

### The throughline

All four found the campaign describing a blocker as **one decision away** when
it was not. Three of the four landed on the same underlying fact:

```text
a real customer organization has to exist, and no approval supplies one
```

Gate 147 found it, Gate 148 inherited it, Gate 149 put it at the front of its
prerequisite list. It is the single most important thing this block established.

## Which blockers are now clearer

```text
customer_auth_live             a three-stage event; stage 1 not started; three
                               of the six steps are not commands and one is not
                               observable from this repository
verified_operational_binding   five refusals, one of which never clears
consent_and_data_boundary      a document nobody has written, then a record;
                               ten fields declared so its absence is a missing
                               record rather than an undefined concept
customer_beta_scope_approved   six fields declared; a decision, not work
controlled_customer_pilot      nine prerequisites, one satisfied, and no
                               mechanism to record an activation
```

## Which blockers are external or human

```text
a real customer organization        nobody in this repository
the second person signing in        the second person
Google OAuth test-user enrolment    Mayhem, in a console this repo cannot read
the consent document                Mayhem writes it; each tenant agrees
the customer beta scope approval    Mayhem
the verified binding authorization  Mayhem, and only after a customer exists
a support and rollback owner        Mayhem; two names
171 source terms reviews            humans, and weeks of work
```

## Which blockers are technical

```text
source_monitoring_live     robots.txt per source, an activation approval per
                           source, five scheduler components
email_delivery             a provider, a service module, a verified sender
                           domain, unsubscribe and bounce handling
object_store_configured    five settings, an injected client, an external
                           verification, secret scanning
digest persistence         delivery intents name a digest nobody kept
```

Note what is *not* on this list: nothing blocking the customer beta is
technical. All four of its approvals are human.

## Is internal/demo beta still GO?

Yes, 0 blockers. Nothing in Gates 146–149 touched it, and the eight conditions
it depends on are unchanged.

## Is controlled customer beta still LIMITED_GO?

Yes, with the same four approval blockers. None was granted, and none could have
been by a gate.

## Is production still NO_GO?

Yes, and it is not a computation. No branch anywhere returns anything else for
that scope.

## The safest next block

**Gates 151–155: the operational durability block.** The reasoning is that the
customer identity block is now blocked entirely on humans — every remaining
customer-beta blocker is an approval, a document, or a person signing in — and
there is nothing further engineering can do to advance it without them.

What *is* available and useful:

```text
151  digest persistence          delivery intents name a digest nobody kept;
                                 a digest that cannot be re-read cannot be
                                 audited after a missed deadline
152  source terms review tooling  171 sources need a human decision each; the
                                 long pole on source_monitoring_live, and the
                                 work is unblocked today
153  backup and restore proof     a pilot customer's data needs a restore path
                                 that has actually been exercised
154  operational runbook + oncall the support/rollback owner Gate 149 asked for
                                 needs something to hand them
155  the block close
```

The alternative — waiting on the customer identity approvals — leaves the
campaign idle on work that only Mayhem and a second person can do.

## What Mayhem may truthfully say to prospective beta customers

```text
"this is a controlled demonstration in a demo environment"
"the awarded-grants workspace, requirements and audit trail are working
 against fixture data"
"177 grant sources are catalogued; none is being monitored yet"
"nothing you see here is sent, monitored, or stored as your data"
"a weekly digest can be previewed in the product; it is not sent"
"we can show you exactly what would have to be true before your organization
 could use this, and who has to decide each part"
```

The last one is what this block actually bought, and it is a better thing to
say to a Tribal government than most of the alternatives.

## What remains unsafe to say

```text
"we monitor grant sources for you"
"you will get a weekly digest by email"
"your data is in our system"
"your organization is set up"
"we have verified your organization"
"the binding is in place, we just need an approval"
"we can turn email on as part of the pilot"
"we guarantee your eligibility" / "we guarantee these deadlines"
"a 65% improvement in anything"
```

The sixth is the dangerous one: nearly true and entirely wrong. The approval is
not what is missing — a customer organization is.

## What Gate 150 builds

A reassessment service that compares Gate 145's decision to the current one,
routes, a cockpit card, a verifier, artifacts and closeout docs. It activates
nothing, approves nothing, and creates no activation mechanism.
