# 581 — Gate 104E: tenant pursuit suppression contract

`src/nativeforge/services/tenant_pursuit_suppression_service.py`

Once a tenant starts pursuing an opportunity, it stops appearing in that tenant's
"new / unpursued" digest. That is the entire feature, and every hard rule around
it exists to keep it from becoming something larger.

## Suppression is tenant-specific

`suppress_for_tenant` takes one tenant id and returns one record. There is no
"suppress everywhere" entry point to call by mistake, and `suppressed_globally`
is a constant `False` on every record and on every summary.

Two tenants pursuing the same opportunity produce two independent records. One
tenant's suppression says nothing about the other's digest, and
`is_suppressed_for_tenant` filters by tenant id **before** it looks at anything
else, so another tenant's record can never satisfy the call. A test proves both
directions: suppressed for this tenant, not suppressed for another.

An invariant fails any record with no tenant id, on the reasoning that a
suppression with no owner is a global one.

`summarise_suppressions` reports `suppressed_by_tenant` and deliberately offers
no global total — an aggregate is the shape a global suppression would arrive in.

## Suppression never deletes source history or provenance

Five constants and three preserved facts, all held by invariants:

```text
opportunity_deleted       false
source_record_deleted     false
provenance_deleted        false
audit_record_deleted      false
suppressed_globally       false

source_history_preserved  true
provenance_preserved      true
visible_in_pipeline       true
```

Gate 104A asked the question directly and answered it: suppression can **never**
delete history. Gates 86–88 built provenance and audit records precisely so that
"where did this come from" stays answerable, and a view filter that erases them
would undo that work through the side door.

The operational form of the argument: a tenant who starts a pursuit and later
asks why an opportunity stopped appearing must be able to find it. Suppression
that deletes is indistinguishable from data loss, and the point of the feature is
that the item **moved** rather than vanished.

`summarise_suppressions` reports `opportunities_deleted: 0` and
`provenance_deleted: 0` as measured counts rather than assurances.

## Suppressed items remain visible in the pipeline

`visible_in_pipeline` is `True` on every record, and an invariant fails any
record that dropped it. Suppression removes an item from the *new-opportunity
digest* only. It stays in the tenant's pursuit pipeline, where it is now being
worked — that is why it left the digest in the first place.

The digest builder counts suppressed items in `items_total` and reports
`items_suppressed` alongside `items_visible`. The tenant can always see how many
were withheld and why, rather than reading a shorter list with no explanation.

## Awarded routes to the Awarded Grants workspace

`pursuit_awarded` sets `visible_in_awarded_workspace`, and an invariant fails any
record where that flag and the reason disagree — in either direction, so a
non-awarded item cannot drift into the awarded workspace either.

Doc 570 is explicit that the pursuit pipeline and the Awarded Grants workspace
answer different questions — *should we chase this* versus *what are we now
responsible for*. This service routes between them; it does not blur them.

## A suppression needs a pursuit record, or a person

```text
pursuit_record_id present  ->  suppressed_from_new_digest
no pursuit record          ->  human_review_required, nothing suppressed
```

Auditability again: a suppression with nothing behind it cannot be explained six
months later, and "why did we stop seeing this?" is exactly the question an
operator asks after missing a deadline. The unbacked case is held for a person
rather than refused outright, and it does not suppress while it waits.

An invariant fails any active suppression with neither a pursuit record nor an
acknowledged human review, and refusals must name themselves in `blocked_reasons`.

## What this contract deliberately does not decide

Gate 104A found three pursuit-stage vocabularies in the tree —
`PursuitWorkflowStatus`, `pursuit_workspace_contract_service.PURSUIT_STATUSES`,
and doc 570's seven stages. Reconciling them is real work and it is not this
gate's work.

So suppression takes a `pursuit_record_id` and stays out of the stage question
entirely. It needs to know *that* a pursuit exists, never *which stage* it is in.
Picking a winner here would have hard-coded one vocabulary into a customer-facing
surface before the reconciliation gate that should decide it.
