# 764 — Gate 146: what `customer_auth_live` may and may not mean

## Two questions, never collapsed

```text
readiness_passed     is the path correct, safe and runnable?     true
customer_auth_live   has anybody actually walked it?             false
```

The verifier reports both and returns `RESULT=PASS`. That PASS is the first
question only, and the second is printed on its own line beside it with its own
blocker and stage.

This is the sixth time this campaign has drawn the same line. Gate 145 named
five of them:

```text
email_delivery_readiness           is not  email_delivery
source_monitoring_preflight_ready  is not  source_monitoring_live
document_metadata_operational      is not  document_body_storage_ready
customer_persistence_live          is not  customer_auth_live
the demo organization              is not  a customer organization
```

Gate 146 adds:

```text
second_person_readiness_passed     is not  customer_auth_live
```

## Why readiness passing is not a failure being hidden

The remaining blocker is a real human event. A gate that failed because a human
has not yet done a human thing would go red every run until somebody did it —
and an operator who has watched a check go red every day for a fortnight has
stopped reading it. That is how a real failure gets missed.

So: PASS on the path, BLOCKED on the event, both on the output, and
`RESULT=BLOCKED` reserved for the path itself being broken — the backend down,
the evidence unreadable, an invariant failing, or the gate claiming
`customer_auth_live` while the measurements disagree.

## What `customer_auth_live` will mean when it is true

```text
a real second Google account completed real OAuth
that account was invited to the demo organization
that invite was accepted, and the membership names it
the accepter is an identity distinct from the owner
scope    controlled_dev_demo_org_only
```

## What it will still not mean

```text
not     a customer organization exists
not     verified_operational_binding is true
not     a controlled customer pilot has started
not     production is approved
not     any real customer data may be written
not     consent or a data boundary has been documented
```

Gate 145's decision matrix requires four approvals for the controlled customer
beta, and `customer_auth_live` is one of them. The other three do not move when
it does.

## Structurally impossible to assert

`build_second_person_checklist()` does not take `customer_auth_live`,
`invite_binding_passed`, or `readiness_passed` as parameters. All three are
derived from the same evidence, and a test inspects the signature to prove a
caller cannot hand the gate the answer it exists to compute.

This is the rule Gate 145 applied to the four capability flags, applied here to
the one that matters most.

## The invariants

A checklist claiming `customer_auth_live` is refused if it:

```text
has no invite binding behind it
read nothing
carries blockers
is not at the complete stage
has no accepted invite
has no membership from a completed invite
passed on a refused organization
claimed the event without the readiness
```

The reverse direction is deliberately allowed: readiness may pass while the
event has not happened. That is today's state and the expected one.

## What must never be printed

```text
the invited address          nf_identities.email
the provider subject         nf_identities.subject
the session cookie
the OAuth state and PKCE verifier
```

Reported instead: the domain half, two fingerprints, counts, booleans, stage
names and blocker names. The checklist payload is scanned for all four shapes
before it is returned, the route refuses rather than emits if one appears, and
the artifact builder raises rather than writes.

The invite id is the one identifier that is safe to print — the operator needs
it for the accept step and it identifies no person.

## What stays false

```text
customer_auth_live             false
invite_binding_passed          false
verified_operational_binding   false
controlled_customer_pilot      false
production_rollout             false
```
