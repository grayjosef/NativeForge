# 777 — Gate 149: the controlled customer pilot activation package

## The answer

```text
controlled_customer_pilot      false
activation_package_ready       true
prerequisites satisfied        1 of 9
activation_mechanism_exists    false
rows written                   0
```

Two facts, reported separately and never collapsed:

```text
activation_package_ready     the prerequisites are stated and measurable
controlled_customer_pilot    a pilot is running
```

That is the seventh instance of the distinction this campaign keeps drawing, and
it is now the most reliable thing to check when reading any of these gates.

## The finding: the pilot is not a value that is false

It is not a value at all.

```text
a table recording pilot approval        none, in any migration
an environment flag                     none
a code path that sets it true           none
what every route returns                the literal False
```

A reader given a list of prerequisites assumes satisfying them flips a switch,
and then goes looking for the switch. There isn't one — and this gate
deliberately does not build one. A switch that exists before its prerequisites
do is a switch somebody flips early.

Two tests hold that line permanently: one asserts no file under `api/` ever puts
`True` on a line mentioning `controlled_customer_pilot`, and one asserts no
migration creates a pilot-approval table. Both are pinned in the coverage guard.

## The nine prerequisites

```text
real_customer_organization_exists     a customer          nobody here
second_person_event_complete          an event            Gate 146
customer_auth_live                    derived             Gate 146
verified_operational_binding          five refusals       Gate 147
consent_boundary_documented           a document          Gate 148
customer_beta_scope_approved          a decision          Gate 145
customer_data_write_guard_ready       code                Gate 148  SATISFIED
support_and_rollback_owner_named      two names           Gate 149
pilot_scope_limitations_documented    a document          Gate 149
```

One is satisfied. The front of the queue is still a customer — the third gate
running that has landed on the same answer, and the only item no approval can
supply.

The cheapest outstanding one is the support and rollback owner: one decision and
two names. It is worth doing early because a pilot without a named owner is a
pilot whose first incident has no addressee.

## What a pilot would unlock

```text
a real customer organization using the product, with their own data
customer identifying and operational data writes, under a recorded consent
  and an approved scope
the awarded-grants workspace, requirements, proof events and audit trail
  against real awards
a weekly digest preview - rendered and read in the product, not sent
```

## What it would not

```text
any email leaving the system
any live grant source being monitored
any document body being stored
production rollout
a second customer, unless separately scoped
```

The second list is the one a customer conversation gets wrong, which is why the
checklist reports both halves on every call.

## Bundling is the failure this gate exists to prevent

Ten keys are refused, each naming the capability it would have turned on:

```text
source_monitoring_live, activate_source_monitoring   -> source_monitoring_live
email_delivery, activate_email, send_email           -> email_delivery
object_store_configured, activate_object_storage     -> object_store_configured
production_rollout, activate_production, go_live     -> production_rollout
```

Refused **even when every prerequisite and the activation approval are
satisfied**. Being allowed to start a pilot is not being allowed to start
anything else. A pilot that quietly turned on email because "a pilot obviously
needs notifications" would undo four gates in one sentence.

Each of the ten is tested individually, with everything else granted.

## The dead GO branches, left alone on purpose

Several older assembler services carry:

```python
"controlled_customer_pilot_status": "NO_GO",
...
if surface.get("controlled_customer_pilot_status") == "GO":
```

The assignment is a constant, so the branch is unreachable. Read as code it is
dead; read as policy it is the deliberate modelling gate Gate 115 described for
`login_live_promotion_gate_service`. Rewriting five of them to be reachable
would manufacture exactly the switch this gate declined to build, so they stay
as they are.

## What the routes do

```text
GET  .../pilot-activation/checklist                 nine prerequisites
GET  .../pilot-activation/blockers                  each, with its owner
GET  .../pilot-activation/unsafe-bundled-requests   the ten keys
POST .../pilot-activation/dry-run-decision          decides; activates nothing
```

Every prerequisite is **measured**, never taken from the body. A test supplies
`customer_auth_live: true`, `verified_operational_binding: true` and
`real_customer_organization_exists: true` in the request and asserts the answer
does not move — a caller supplying those would be supplying the answer.

## What stays false

```text
controlled_customer_pilot      false
production_rollout             NO_GO
customer_auth_live             false
verified_operational_binding   false
consent_boundary_documented    false
customer_beta_scope_approved   false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

## Next

`778` on the prerequisites, `779` on the unsafe bundles, `780` on the delta.
Gate 150 re-decides the controlled customer beta with 146–149 established.
