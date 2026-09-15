# 811 — Gate 155: the next block, and why it wins

**Recommended: source collection runtime.**
**First gate: the scheduler runtime itself — hermetic, with an empty allowlist.**

## The rule that decided it

> Do not recommend another readiness wrapper around a blocker that only a
> person or an approval can clear.

Gates 146–150 already made every customer refusal exact. Describing the same
refusal in more detail is not progress, and four gates of it would look like
momentum while moving nothing. So each candidate was ranked by how many of its
blockers are **absent components** rather than **absent approvals**.

## The measurement

Taken from each lane's own verifier, not estimated.

```text
candidate                 blockers  human  engineering  verdict
source_collection_runtime      7      2         5       engineering can advance
additional_durability          0      0         0       nothing is blocked
email_activation               1      1         0       wrapper risk
object_storage_activation      1      1         0       wrapper risk
production_infrastructure      1      1         0       wrapper risk
customer_activation            4      4         0       wrapper risk
```

Source collection is the only candidate where engineering can clear a majority
of the blockers. It is not close.

## Why the other five lose

```text
customer_activation
  customer_auth_live                    a real person must sign in
  verified_operational_binding          an approval must be signed
  consent_and_data_boundary_documented  the customer must consent
  customer_beta_scope_approved          an approver must approve
  Highest customer value, zero engineering purchase. A real customer
  organization still does not exist.

email_activation
  no_email_provider_configured          an approver, then a provider admin
  One blocker, and it is a decision. Gate 142 already built the readiness.

object_storage_activation
  document_body_storage_is_not_configured   an approver, then provisioning
  Same shape. Gate 141 already built the adapter and the hermetic fake.

production_infrastructure
  no_managed_database_instance          procurement
  Unblocks two SKIP verifiers and nothing else, and it is a purchase.

additional_durability
  nothing is blocked
  Gates 151-154 proved the four lanes. Another durability gate would
  harden something already hard.
```

## What the source lane is actually blocked on

```text
terms_review_incomplete                                 human   171 sources
human_review_only_sources                               human     6 sources
scheduler_component_absent:scheduler_runtime            engineering
scheduler_component_absent:background_worker            engineering
scheduler_component_absent:periodic_trigger             engineering
scheduler_component_absent:persistent_backend           engineering
scheduler_component_absent:production_raw_payload_store  engineering
```

Measured from the registry today: 177 rows, 171 `terms_blocked`, 6
`human_review_blocked`, **0 `activation_approved`**, `scheduler_attached: False`.

`backend_lifespan_hook_service` has described itself since Gate 102 as *"the
attach point a future in-process scheduler would use, and a record of the fact
that nothing is attached to it."* The attach point has been waiting fifty gates.

## Why it is not a wrapper

A wrapper describes a refusal in more detail. This builds a thing that does not
exist. Five absent components is five pieces of real engineering with a working
artifact at the end, and the readiness gates have been pointing at exactly these
five for the whole campaign.

## Why it is safe to build now

A scheduler with an empty allowlist polls nothing and contacts nothing. With
zero sources approved there is no URL for it to fetch, which makes it provable
hermetically — and proving it *before* any source is approved is the correct
order, not a compromise.

## What the recommendation explicitly does not mean

- **Not** that `source_monitoring_live` would become true.
- **Not** that any source would be polled. 171 are `terms_blocked` and 0 are
  approved.
- **Not** that the two human source blockers are cleared. They stay human.
- **Not** that a collector is activated.
- **Not** that anything is activated at all.

It removes five of the seven reasons monitoring cannot start. When the terms
review completes, activation becomes one approval away instead of an approval
plus a runtime that does not exist.

## The branch this decision can take, and did not

If a real customer organization existed, a second identity were available, and
the consent decision could be made now, **customer activation would win
regardless of blocker counts** — a human blocker that a person is standing by to
clear is not a blocker in the sense that matters.

None of the three is available, so the branch was not taken. It is reachable and
a test proves it: supply all three prerequisites and the recommendation flips to
`customer_activation`. A branch nobody can reach would make the rule
unfalsifiable, which was Gate 134F's lesson.

## Why this recommendation is derived rather than written down

Two next-step constants in this repository have gone stale without failing
anything:

```text
beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION
  recommended finishing a matrix completed at Gate 145. Found by Gate 154.

customer_beta_reassessment_service.NEXT_BLOCK
  recommends Gates 151-155, which this gate closes. Spent.
```

A constant cannot go stale loudly. This ranking is computed from supplied
blocker counts, so a candidate whose blockers change gets a different answer
with nobody editing anything.

## Assumptions this recommendation rests on

```text
no real customer organization is created before the next block starts
no second identity becomes available
no consent decision is made
the 171 terms-blocked sources stay blocked
nobody provisions a managed database instance
```

If any of the first three changes, the decision service flips to customer
activation on its own. That is what deriving it buys.
