# 784 — Gate 150: what must not be said

Ten claims, each paired with the true statement it should be replaced by. An
inventory of what may not be said is not a saying of it.

## The ten

```text
not  "we monitor grant sources for you"
say  177 sources are catalogued and none is monitored yet

not  "you will get a weekly digest by email"
say  a digest can be previewed in the product

not  "your data is in our system"
say  the demo organization holds fixture-labelled rows

not  "your organization is set up"
say  there is one demo organization and one refused real one

not  "we have verified your organization"
say  no organization has been verified; the path refuses

not  "the binding is in place, we just need an approval"
say  a customer organization has to exist first

not  "we can turn email on as part of the pilot"
say  the pilot gives a digest in the product, not by mail

not  "we guarantee your eligibility"
say  we surface sources and requirements; you decide

not  "we guarantee these deadlines"
say  published dates are shown with their source

not  "a 65% improvement in anything"
say  no improvement figure is claimed
```

## The dangerous one

```text
"the binding is in place, we just need an approval"
```

Nearly true and entirely wrong, which is the worst combination. It would pass a
casual internal review because every word of it sounds like the current state.
The approval is not what is missing. **A customer organization is**, and no
approval supplies one.

This is the claim Gate 147 was written to prevent, and it is the reason the
cockpit lane was changed from "owner_decision_absent, owner: the owner" to the
full five-refusal stack with the owner named as "Mayhem, and only after a real
customer organization exists".

## Why "we can turn email on as part of the pilot" is on the list

Because it sounds like a scoping detail and is a capability activation. Gate 149
refuses ten separate keys that would bundle email, source monitoring, object
storage or production into a pilot request — refused even when every pilot
prerequisite is satisfied.

The useful reply is usually that the thing being asked for already exists in a
form needing no activation: the digest is available as a preview in the product.

## Why the eligibility and deadline claims are on the list

Not because the data is wrong, but because the product deliberately never makes
those determinations for a tenant. Gate 144's cockpit guard scans for `eligib`
and `deadline` in any customer-facing payload and fails the verifier if either
appears — a guard strong enough that Gate 147 tripped it by writing
"categorically ineligible" about an organization's fitness for a *binding*.

The wording was changed rather than the guard. A surface forbidden from
discussing eligibility should not carry the vocabulary for any subject.

## Why the 65% claim is on the list

No such measurement exists. It has been a standing prohibition across the
campaign, and Gate 145 had to fix a guard that fired on the inventory recording
it — an inventory of prohibited claims is not a prohibited claim.

This gate's scan looks for value *shapes* — an address, a token, a provider
subject — and the inventory contains none of them, so it needs no exemption at
all. An exemption that protects against nothing is an unscanned region.

## How to use this list

Before any customer-facing sentence ships — a deck, an email, a demo script, a
contract — check it against these ten. If it is a paraphrase of one, it is one.

The list lives in `customer_beta_reassessment_service.UNSAFE_CLAIMS`, is served
by `GET /v1/nf/demo/orgs/{org}/beta-reassessment/unsafe-claims`, and is
committed to
`artifacts/customer_beta_reassessment_gate150/unsafe_customer_facing_claims.json`.

A test asserts every entry carries a true alternative, and that all eight known
traps appear in it.
