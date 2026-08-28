# 595 — Gate 108B: awarded grant record contract

`src/nativeforge/services/awarded_grant_record_service.py`

## Awarded Grants is a separate workspace from the pursuit pipeline

Two different questions, and the product depends on never confusing them:

```text
pursuit pipeline   should we chase this, and where are we in chasing it?
Awarded Grants     what are we now legally, financially, administratively and
                   operationally responsible for?
```

An awarded record carries `is_pursuit_record: False` and holds
`pursuit_record_id` and `source_opportunity_id` as references rather than as
things it consumed.

## Creating an award consumes nothing

```text
pursuit_history_preserved   true
source_history_preserved    true
pursuit_record_deleted      false
source_opportunity_deleted  false
```

Held by invariants on every record. A tenant who marks a grant awarded and later
asks what they originally submitted must be able to find it.

## This does not replace Gate 91

`awarded_grant_portfolio_service` already owns the award record: lifecycle
statuses, required detail fields, and the rule that a missing award date is a
review item rather than a computed one. Its `LIFECYCLE_STATUSES` and
`REQUIRED_AWARD_DETAIL_FIELDS` are imported here, and
`portfolio_lifecycle_is_fully_mapped()` fails if Gate 91 grows a status this
mapping misses.

Seven award statuses extend Gate 91's four:

```text
draft_award_record  active_award  closeout_pending  closed
cancelled           mistaken_award  unknown
```

## Two identity spaces, deliberately not merged

The most consequential decision in this gate.

```text
customer_org_id   Gates 90-91, 3 services
tenant_id         Gates 103-104, 13 services
no bridge exists anywhere in the tree
```

The tempting move is to declare one tenant equals one customer org and derive
one from the other. That is a product and data-model claim nobody has verified,
and a silent equivalence between two identity spaces is how a cross-tenant leak
gets built.

So both are carried, both must be supplied, neither is derived:

```text
tenant_org_binding_status   caller_supplied   both ids given
                            unknown           one is missing
```

An invariant fails a record claiming `caller_supplied` without both, and a
mutation setting the binding unconditionally is caught. Reconciling the two
spaces is the first item in the readiness service's next actions.

## An award may exist before anyone knows what it obliges

The state this contract exists to allow. A tenant marks the grant awarded on the
day the letter arrives, months before anyone reads the terms.

```text
requirements_extraction_status   not_attempted is a normal state
active_obligations_supported     false until evidence or a person says otherwise
missing_award_details            listed, never filled in
```

That record is not degraded, it is honest. Refusing to create it until
requirements are known would push tenants back into tracking awards in a
spreadsheet, which is the problem the product exists to solve.

## Nothing is computed from a default

A performance period requires both dates or it says so:

```text
both dates supplied   derived_from: award_dates_as_supplied
either missing        derived_from: incomplete_award_dates
```

An invariant fails a period claiming both dates it does not have. `match_required`
without an amount or a percent is a blocked reason, never a computed figure.
