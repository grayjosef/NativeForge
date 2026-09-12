# 778 — Gate 149: the pilot prerequisites

Nine. One satisfied. Each named with what satisfies it and who owns it, because
"blocked" without that distinction sends somebody looking for a bug that is not
there.

## 1 — a real customer organization exists

```text
kind    a customer
owner   nobody in this repository
gate    147
```

There is none in this deployment other than the refused one. No approval
supplies a customer, no code change creates one, and this has been the front of
the queue for three gates running.

It is listed first because every other prerequisite is downstream of it: there
is nothing to bind, nothing to consent on behalf of, and nobody to scope a beta
for until it exists.

## 2 — the second-person invite event

```text
kind    an event
owner   the second person, then the operator
gate    146
```

A real second Google account completing real OAuth, being invited to the
organization, and having that invite accepted. Gate 146 measured the live state:
one identity — the owner — and no invite recorded. Three of the six steps are
not commands, and one of them (Google test-user enrolment) is not observable
from this repository at all.

## 3 — `customer_auth_live`

```text
kind    derived from an event
owner   follows prerequisite 2
gate    146
```

Not a separate decision. `invite_binding_passed` becoming true carries it.

## 4 — `verified_operational_binding`

```text
kind    five refusals
owner   Mayhem, and only after a real customer organization exists
gate    147
```

Five refusals stand and any one is sufficient. One of them —
`demo_organization_is_never_a_verified_operational_binding` — never clears at
all, which is why this prerequisite cannot be satisfied against the demo
organization no matter what else is true.

## 5 — `consent_boundary_documented`

```text
kind    a document, then a record
owner   Mayhem writes it; each tenant agrees to it
gate    148
```

No consent table exists in any migration. Deciding what NativeForge collects,
retains, exports and deletes is a document somebody writes; Gate 148 declared
the ten-field record shape so its absence is a missing record rather than an
undefined concept, and deliberately did not invent what the document should say.

A login, a membership, an accepted invite and an operator's note are each not
consent, and each is refused by name.

## 6 — `customer_beta_scope_approved`

```text
kind    a recorded decision
owner   Mayhem
gate    145
```

The fourth of the four approvals Gate 145's matrix says the controlled customer
beta needs.

## 7 — `customer_data_write_guard_ready` — **satisfied**

```text
kind    code
owner   done
gate    148
```

The only one already true. Gate 148 built and proved the guard a future write
path calls, deliberately not wiring it into the existing demo-fixture-only paths
because those cannot reach a customer write and a guard call there would be
untested code on an unreachable branch.

## 8 — `support_and_rollback_owner_named`

```text
kind    two names
owner   Mayhem
gate    149
```

Who a pilot customer calls when something breaks, and who can end the pilot.
Both are required; a record with one and not the other does not count, and a
test asserts that.

This is the cheapest outstanding prerequisite and worth doing early. A pilot
without a named owner is a pilot whose first incident has no addressee.

## 9 — `pilot_scope_limitations_documented`

```text
kind    a document
owner   Mayhem
gate    149
```

This gate's docs state them — what a pilot unlocks, what it does not, and what
may never be bundled with it. An owner still has to accept them, which is why it
is reported false rather than marked satisfied by the existence of the file you
are reading.

## The order

```text
1  a real customer organization                  everything waits on it
2  the second-person invite event                Gate 146
3  customer_auth_live                            follows 2
4  the verified binding approval                 Gate 147
5  the consent document, then a record           Gate 148
6  the customer beta scope approval              Gate 145
7  (already satisfied)
8  name a support and rollback owner             cheap; do it early
9  an owner accepts the scope limitations
```

Then, and only then, a decision about how a pilot activation gets recorded —
because nothing records one today, and this gate built no mechanism.

## What removing any one of them does

Every prerequisite is required. A test removes exactly one at a time, with the
other eight satisfied, and asserts `controlled_customer_pilot` stays false and
the missing one is named. Nine parametrised cases, no exceptions.
