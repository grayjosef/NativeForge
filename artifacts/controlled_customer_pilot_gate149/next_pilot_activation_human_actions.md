# Gate 149 — the next pilot activation actions

`controlled_customer_pilot` is false, and there is nothing to set it
with: no table records a pilot approval, no flag exists, and no code
path assigns it. This gate states the package and builds no switch.

## The nine prerequisites

```text
real_customer_organization_exists
    kind    a_customer
    owner   nobody in this repository
    gate    147
second_person_event_complete
    kind    an_event
    owner   the second person, then the operator
    gate    146
customer_auth_live
    kind    derived_from_an_event
    owner   follows the second-person event
    gate    146
verified_operational_binding
    kind    five_refusals
    owner   Mayhem, and only after a real customer organization exists
    gate    147
consent_boundary_documented
    kind    a_document_then_a_record
    owner   Mayhem writes it; each tenant agrees to it
    gate    148
customer_beta_scope_approved
    kind    recorded_decision
    owner   Mayhem
    gate    145
customer_data_write_guard_ready
    kind    code
    owner   done
    gate    148
support_and_rollback_owner_named
    kind    two_names
    owner   Mayhem
    gate    149
pilot_scope_limitations_documented
    kind    a_document
    owner   Mayhem
    gate    149
```

One is satisfied: the customer data write guard, from Gate 148.

## The order

```text
1  a real customer organization has to exist
     the front of the queue for the third gate running, and the only
     item no approval can supply

2  the second-person invite event                  Gate 146
3  the verified binding approval                   Gate 147
4  the consent document, then a consent record     Gate 148
5  the customer beta scope approval                Gate 145
6  name a support and rollback owner               cheap; do it early
7  an owner accepts the pilot scope limitations
8  then decide how a pilot activation is recorded
```

Item 6 is one decision and two names, and a pilot without a named
owner is a pilot whose first incident has no addressee.

## What a pilot would unlock

```text
- a real customer organization using the product, with their own data
- customer identifying and operational data writes, under a recorded consent and an approved scope
- the awarded-grants workspace, requirements, proof events and audit trail against real awards
- a weekly digest preview - rendered and read in the product, not sent
```

## What it would not

```text
- any email leaving the system
- any live grant source being monitored
- any document body being stored
- production rollout
- a second customer, unless separately scoped
```

## What may never be bundled with it

```text
source_monitoring_live       gate 143
                             171 sources need a human terms review, robots.txt per source, and an activation approval per source
email_delivery               gate 142
                             a provider, a verified sender domain, unsubscribe and bounce handling
object_store_configured      gate 141
                             five settings, an injected client, an owner decision and an external verification
production_rollout           gate 145
                             always NO_GO; not a computation
```

Refused even when every prerequisite is satisfied.

## What stays false

```text
controlled_customer_pilot   false
production_rollout   false
customer_auth_live   false
verified_operational_binding   false
consent_boundary_documented   false
customer_beta_scope_approved   false
source_monitoring_live   false
email_delivery   false
object_store_configured   false
```

This gate assembled the package. It activated nothing.
