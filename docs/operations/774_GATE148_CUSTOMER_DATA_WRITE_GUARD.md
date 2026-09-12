# 774 — Gate 148: the customer data write guard

## What it is

One call a write path makes before it writes:

```python
evaluate_write(
    organization_id=..., data_class=..., scope=..., fact_status=...,
    route_context=..., org_type_in_database=...,
    consent_record=..., beta_scope_approval=...,
    customer_auth_live=..., verified_operational_binding=...,
    object_store_configured=..., email_delivery=..., source_monitoring_live=...,
)
```

It returns `write_allowed` and every reason it may not. It performs no write,
opens no connection, and contacts nothing — `rows_written` is 0 on every branch
including the permitted one.

## Why one guard rather than a check in each repository

Gate 148A's finding is that four post-award repositories each gate a production
write on the same two identity facts and none of them checks consent. Adding a
third check to each would be four chances to get consent subtly different — the
reasoning Gate 139 used when it put one fixture-labelling in one place rather
than four.

## Why it is not wired into the existing write paths

Deliberately. Those paths force `fact_status=demo_fixture` and refuse a
caller-supplied label, so they cannot reach a customer write today. Adding a
guard call to them would be untested code on an unreachable branch.

It is built and proved now so that the path which eventually writes customer
data has something correct to call, rather than being the gate that has to
invent consent under pressure.

## Deny by default, at four levels

```text
an unknown data class          refused
a missing route context        refused - a write nobody can attribute to a
                               route is a write nobody can audit
an unknown scope               refused rather than treated as permissive
a missing capability           refused, per class
```

## The decision table

```text
demo fixture, demo org, controlled demo scope          allowed
customer data, demo org, controlled demo scope         refused
    - customer data in the demo scope is the substitution this block exists
      to prevent
a fixture labelled demo_fixture with fact_status tenant_supplied
                                                       refused
an unclassified data class                             refused
consent offered as a login, membership or invite       refused by name
customer document body, object storage off             refused
customer recipient, email delivery off                 refused
a provider subject, everything else granted            refused, never clears
the refused real organization, everything granted      refused by name
a fixture customer organization, everything granted    allowed, 0 rows written
```

## The permitted branch is reachable

Against a fixture customer organization that is neither the demo org nor the
refused real one, with a complete consent record, a beta scope approval, live
customer auth and a verified binding, the guard returns `write_allowed: True`.

Nothing in runtime reaches it. A test does, because an unreachable permitted
branch makes every refusal above it unfalsifiable — Gate 134F's lesson, now
earning its keep in a seventh gate.

And even on that branch it writes nothing. `write_performed` is false and
`rows_written` is 0, because deciding a write is allowed and performing it are
different actions with different owners.

## What the guard does not decide

It does not classify. `customer_data_classification_service` answers "what is
this", and the guard answers "may it be written". A classification that also
decided permission would make every new data class a permission change.

## Invariants

A guard result is refused if it:

```text
allowed a write alongside blockers
allowed customer data without consent
allowed customer data without the beta scope
allowed customer data in the demo scope
allowed an unknown data class
claimed to have written, opened a connection, touched the real organization,
  started a pilot, or approved production
reported rows written
```

## The route

`POST /v1/nf/demo/orgs/{org}/data-boundary/dry-run-write` evaluates a
hypothetical write. The capability flags are **measured, not accepted from the
body** — a caller handing the guard its own capability flags would be handing it
the answer, and a test supplies `object_store_configured: true` in the body and
asserts the write is still refused.
