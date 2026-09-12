# 776 — Gate 149: the controlled customer pilot activation, surveyed

Read-only. No pilot was activated, no approval granted, no customer data
written, no organization touched.

## The finding that shapes this gate

`controlled_customer_pilot` is not a value that is currently false. **It is not
a value at all.**

```text
a table recording pilot approval        none, in any migration
an environment flag                     none
a code path that sets it true           none
what every route returns                the literal False
what every service returns              the literal False
```

Nothing in this repository can flip it, because there is nothing to flip. The
flag is a constant in every place it appears.

That matters for how this package is written. A reader given a list of
prerequisites naturally assumes that satisfying them flips a switch, and then
goes looking for the switch. There isn't one — and building one is not this
gate's job, because a switch that exists before its prerequisites do is a switch
somebody eventually flips early.

So the package answers "what must be true", and says plainly that "how it gets
recorded" is a later decision.

## A related pattern, named so it is not mistaken for a hole

Several older assembler services carry:

```python
"controlled_customer_pilot_status": "NO_GO",
...
if surface.get("controlled_customer_pilot_status") == "GO":
```

The assignment is a constant, so the `== "GO"` branch is unreachable. Read as
code it is dead; read as policy it is the deliberate modelling gate Gate 115
described for `login_live_promotion_gate_service`. Those branches are left
exactly as they are: a dead branch that refuses is not a defect, and rewriting
five of them to be reachable would be manufacturing the switch this gate has
just declined to build.

## The measured decisions

```text
internal_demo_beta         GO           0 blockers
controlled_customer_beta   LIMITED_GO   4 blockers
production_rollout         NO_GO        8 blockers
```

The customer beta's four:

```text
approval_absent:customer_auth_live
approval_absent:verified_operational_binding
approval_absent:consent_and_data_boundary_documented
approval_absent:customer_beta_scope_approved
```

Gates 146, 147 and 148 each took one of the first three and made it exact. None
of them moved a value, and none was supposed to.

## Why the pilot is false — the prerequisites that are missing

```text
a real customer organization exists        no. Gate 147's finding, and still
                                           the front of the queue. No approval
                                           supplies a customer.
a second real identity signed in           no. Gate 146: one identity, the
                                           owner; no invite has been recorded.
customer_auth_live                         false
verified_operational_binding               false, behind five refusals
consent boundary documented                false. No consent table exists.
customer beta scope approved               false
customer data write guard ready            TRUE - the one prerequisite that
                                           is already satisfied
a named support and rollback owner         absent. Nothing in this repository
                                           records who a pilot customer calls
                                           when something breaks, or who can
                                           end the pilot.
pilot scope limitations documented         this gate writes them
```

Eight prerequisites, one satisfied.

## What is deliberately not a prerequisite

These four must stay **separately gated**, and bundling any of them into pilot
activation is the failure mode this gate exists to prevent:

```text
source_monitoring_live      171 sources need a human terms review; robots.txt
                            per source; an activation approval per source
email_delivery              a provider, a verified sender domain, unsubscribe
                            and bounce handling
object_store_configured     five settings, an injected client, an owner
                            decision, an external verification
production_rollout          always NO_GO; not a computation
```

A pilot that quietly turned on email because "a pilot obviously needs
notifications" would be four gates of careful work undone in one sentence. The
activation boundary refuses a request that bundles them, by name.

## What pilot activation would unlock

```text
a real customer organization using the product, with their own data
customer_identifying_data and customer_operational_data writes, under a
  recorded consent and an approved scope
the awarded-grants workspace, requirements, proof events and audit trail
  against real awards
a weekly digest PREVIEW - rendered, read in the product, not sent
```

## What it would still not unlock

```text
any email leaving the system
any live grant source being monitored
any document body being stored
production rollout
a second customer, unless separately scoped
```

## Can any route accidentally activate a pilot?

No, and for the strongest available reason: no route mutates the flag because no
route can. Every occurrence in `api/` is a constant `False` written into a
response envelope. Gate 149's own POST is a dry run whose boundary service has no
connection parameter and no write path.

## Does any table record a pilot approval?

No. Gate 149 declares the shape an approval object would need so that its
absence is a missing record rather than an undefined concept — the same
treatment Gate 148 gave the consent record and Gate 147 gave the binding
approval. It creates no table.

## Exact next human actions

```text
1  a real customer organization has to exist
     still the front of the queue, three gates running

2  the second-person invite event               Gate 146
3  the verified binding approval                Gate 147, five refusals
4  the consent document, then a consent record  Gate 148
5  the customer beta scope approval             Gate 145's fourth
6  name a support and rollback owner            new, and the cheapest of the
                                                six: it is one decision and
                                                two names
7  then decide how a pilot activation is recorded
```

Item 6 is worth doing early precisely because it is cheap and because a pilot
without a named owner is a pilot whose first incident has no addressee.

## What Gate 149 builds

A checklist service, an activation boundary that is dry-run only, four routes,
a cockpit lane, a verifier, artifacts and docs. It activates nothing, approves
nothing, and creates no mechanism by which the pilot could be activated.
