# Gate 148 — the next consent and data boundary action

Two of the four approvals the controlled customer beta needs are
recorded nowhere, and neither is a code change.

```text
consent_boundary_documented    false
customer_beta_scope_approved   false
```

## The order

```text
1  a real customer organization has to exist
     Gate 147's finding, and still the front of the queue. There is
     none in this deployment other than the refused one.

2  decide what NativeForge collects, retains, exports and deletes
     a document, not a code change. Gate 142 declined to build a
     consent model before this existed, and was right to: a record
     that looks like agreement and is not would be worse than none.

3  decide how a tenant records agreement, and how they withdraw it

4  Mayhem approves the controlled customer beta scope

5  a consent record per organization, with all ten fields
```

## What is not consent

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
    says       somebody wrote something down, or said it
    but        it records what an operator believes, not what a Tribe agreed to, and a verbal yes is not in the system at all
```

All four become available as Gates 146 and 147 land, which is why they
are refused by name rather than left unmentioned.

## What stays allowed

```text
demo fixture writes to the demo organization, controlled demo scope
synthetic test data in hermetic tests
fingerprints and domain halves, never the value
```

## What stays false

```text
consent_boundary_documented   false
customer_beta_scope_approved   false
customer_auth_live   false
verified_operational_binding   false
controlled_customer_pilot   false
production_rollout   false
```

This gate built the boundary. It created no consent and approved
nothing.
