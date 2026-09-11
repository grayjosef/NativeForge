# 759 — Gate 145: controlled customer beta — LIMITED GO

## Decision

```text
controlled_customer_beta   LIMITED_GO
```

Not because the software is unfinished. Every lane an operator needs is proved.
Because of four things, none of which is a code change.

## The four blockers

```text
approval_absent:customer_auth_live
approval_absent:verified_operational_binding
approval_absent:consent_and_data_boundary_documented
approval_absent:customer_beta_scope_approved
```

Two are decisions a person makes, one is a boundary nobody has written, and one
is the scope approval itself. Listing them as approvals rather than as work is
the difference between "fix this" and "decide this" — an operator reading
"blocked" looks for a bug, and there is none.

## What LIMITED GO permits

```text
an operator walking a customer through the product
the demo organization, with fixture-labelled rows
```

That is a real and useful thing. A prospective Tribal customer can be shown the
awarded-grants workspace, a weekly digest preview, a pursuit suppression with
its audit trail, and a cockpit that states plainly what is and is not live.

## What it does not permit

```text
a real customer signing in          customer_auth_live is false
writing real customer data          no consent or data boundary exists
sending any email                   email_delivery is false
monitoring any live source          source_monitoring_live is false
storing any document bytes          object storage is not configured
```

## Why the demo organization is not a customer organization

`bbbbbbbb-cccc-dddd-eeee-ffffffffffff` is a demo org holding fixture-labelled
rows. Treating it as a customer org would be the substitution Gates 110–113
spent four gates preventing, and it is named as the fifth conflation in the
decision service for exactly that reason.

Running a "controlled customer beta" inside it is a demonstration with a
customer present. That is worth doing, and worth naming accurately.

## The GO branch is reachable, and was tested

```text
customer_auth_live                    true
verified_operational_binding          true
consent_and_data_boundary_documented  true
customer_beta_scope_approved          true
  ->  controlled_customer_beta        GO
```

Nothing in runtime reaches it. A test does, because an unreachable permitted
branch makes every refusal above it unfalsifiable — and that test found a real
defect: the demo scope was propagating its honesty conditions into this scope,
which requires the opposite of two of them.

## What must happen before real customer data

```text
1. a second real person accepts a real invite   -> customer_auth_live
2. the two-part owner binding decision          -> verified_operational_binding
3. a documented consent and data boundary       what is collected, retained,
                                                exported, deleted
4. the scope approval itself                    Mayhem
```

Item 3 is a gap Gate 142 named and deliberately did not fill: nothing in this
repository records that a tenant asked for anything. Building a consent model
without first deciding what consent means here would be worse than its absence.

## What to say to a customer today

```text
say     "this is a controlled demonstration in a demo environment"
say     "nothing you see here is sent, monitored, or stored as your data"
say     "177 grant sources are catalogued and none is being monitored yet"

avoid   "we monitor grant sources for you"
avoid   "you will get a weekly digest by email"
avoid   "your data is in our system"
```

The decision service carries seven such pairs, and every product surface is
tested against making the wrong half of one.
