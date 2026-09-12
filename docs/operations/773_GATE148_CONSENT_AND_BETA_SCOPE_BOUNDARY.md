# 773 — Gate 148: consent and the customer beta scope

## Both are false, and neither is a code change

```text
consent_boundary_documented    false
customer_beta_scope_approved   false
```

Nothing in this repository records that a tenant was told what is collected,
retained, exported and deleted, and agreed to it. No consent table exists in any
migration. Gate 145 lists both as two of the four approvals the controlled
customer beta needs; the other two are `customer_auth_live` (Gate 146) and
`verified_operational_binding` (Gate 147).

## Why this gate comes before Gate 150 and not after

Every post-award repository gates a production write on exactly two things:

```text
production_write and not customer_auth_live            -> blocked
production_write and not verified_operational_binding  -> blocked
```

Both are identity facts. Neither is consent. Gates 146 and 147 exist to make
both true — and on the day they do, a production customer write becomes
permitted with no consent recorded anywhere.

The boundary has to exist before those lanes turn. That is the whole argument
for this gate's position in the block.

## What a consent record must contain

Ten fields, all of them. A partial record is not a weak consent; it is no
consent, and the boundary names it as such.

```text
organization_id        who agreed
agreed_by              the person who agreed on their behalf
agreed_at              when
what_is_collected
what_is_retained
retention_period
what_is_exported
how_it_is_deleted
withdrawal_method      how they take it back
document_version       which version of the document they agreed to
```

Gate 148 declares this shape and does not fill it in. Deciding what NativeForge
collects, retains, exports and deletes is a document somebody writes, not a
service somebody builds — which is exactly why Gate 142 named this gap and
declined to fill it. A consent model built before that decision would produce a
record that looks like agreement and is not, which is worse than its absence.

## What a beta scope approval must contain

```text
organization_id
approved_by
approved_at
scope
data_classes_permitted
expires_at
```

## Four things that look like consent and are not

All four become available as Gates 146 and 147 land, which is why they are
refused **by name** rather than left unmentioned. An omission here would be read
as permission.

```text
a login
    says       a person authenticated
    but        authenticating is not agreeing to anything

a membership
    says       somebody was added to an organization
    but        an owner added them; the member did not decide

an accepted invite
    says       a person accepted a seat
    but        the invite carries a role and an expiry and no terms

an operator note or a verbal yes
    says       somebody wrote it down, or said it
    but        it records what an operator believes, not what a Tribe agreed
               to, and a verbal yes is not in the system at all
```

A caller offering any of these keys — `login`, `membership`, `invite_accepted`,
`operator_note`, `verbal_consent`, `implied_consent`, `assumed_consent` and the
rest — gets `consent_was_inferred_rather_than_recorded` and learns their
reasoning was rejected, rather than having it silently dropped.

## The blocker stack today

```text
consent_boundary_not_documented                       a document, then a record
customer_beta_scope_not_approved                      Mayhem
real_customer_organization_missing                    nobody in this repository
demo_organization_is_not_a_customer_organization      never clears
customer_auth_live_false                              an event; Gate 146
verified_operational_binding_false                    five refusals; Gate 147
```

`real_customer_organization_missing` is still the front of the queue, as Gate
147 found. No approval supplies a customer.

## What stays allowed

```text
demo fixture writes to the demo organization, controlled demo scope
synthetic test data in hermetic tests
fingerprints and domain halves, never the value
```

This gate did not narrow the lane every existing route uses, and a test asserts
it: `test_demo_fixture_writes_are_still_allowed` is one of the five critical
node ids pinned in the coverage guard, because breaking that lane would stop the
demo working.

## What stays false

```text
consent_boundary_documented    false
customer_beta_scope_approved   false
customer data writes           refused
controlled_customer_pilot      false
production_rollout             false
```
