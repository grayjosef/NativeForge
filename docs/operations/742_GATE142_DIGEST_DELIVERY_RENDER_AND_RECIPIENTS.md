# 742 — Gate 142: rendering a digest, and who it would go to

## A deliverable shape, sent nowhere

`digest_delivery_renderer_service` turns a digest into what a provider would be
handed:

```text
subject_line       one line, bounded at 160 characters
body_text          plain text
body_render_hash   sha256 of the body
body_byte_length   bounded at 256 KiB
digest_period_key  cadence | period_start | period_end
```

No HTML. An HTML digest needs a template, a sanitiser and a link-tracking
decision, and none of those is this gate's question. `html_rendered`,
`tracking_pixels` and `links_rewritten` are reported and are all zero.

## The renderer takes no recipient

There is no recipient parameter, so a mailbox cannot reach a subject line, a
greeting, or a body. An invariant fails if an address-shaped string appears in a
rendered body, and the delivery queue stores a **hash** of the render rather
than the text.

## Every uncertainty survives into the words

This is the part that matters most, because an email is the copy a tenant keeps:

```text
eligibility unknown        "eligibility unknown", and the next step is
                           "review eligibility with a human"
deadline unverified        "due 2026-06-15 (not verified)"
no deadline at all         "no verified deadline"
blockers                   listed under "needs review:"
```

and the header counts both kinds:

> 9 of 9 matched notices are shown. 1 needs a human to settle eligibility and 4
> have no verified deadline.

The body closes with:

> This digest is assembled from recorded snapshots, not from live checks of any
> funder's site. Verify every deadline against the notice before relying on it.

## Seven phrases the body may never contain

```text
you are eligible          you are not eligible
guaranteed                you will receive
apply now                 act now
deadline confirmed
```

Each is a claim this system cannot support. A digest that made one would be the
fabrication the eligibility contract exists to prevent, arriving in the form the
tenant is most likely to act on. A render carrying one is refused, and an
invariant fails if a *deliverable* render contains one.

## A defect this gate found in Gate 140

The digest assembler never passed `period_start` / `period_end` to Gate 104's
builder, so every digest carried `period_start: None` and its `digest_id` was
derived from `(tenant, cadence, None, None)` — **identical for every week,
forever**.

Nothing depended on it until a delivery queue needed a period key to answer "has
this recipient already been recorded for this digest". A key that never changed
would have recorded a tenant once and refused every later week as a duplicate.

The period is not invented: a digest compares two recorded snapshots, so it is
about the span between when they were observed, and both timestamps were already
on the snapshots.

```text
before   digest_period_key: weekly|unknown|unknown
after    digest_period_key: weekly|2026-01-01T00:00:00+00:00|2026-01-08T00:00:00+00:00
```

## Recipients are fingerprints

`digest_recipient_validation_service` reads an address and returns a handle:

```text
in    an address, from nf_identities, in a local variable
out   recipient_fingerprint   sha256[:32] of the lowercased address
      recipient_domain        the domain, which names no mailbox
      recipient_verified      from nf_identities.email_verified
      blocked_reasons
```

`email_fingerprint` is imported from `membership_invite_repository_service`
rather than reimplemented. Two hashing schemes would drift and then disagree
about whether a recipient matched, and that module already documents why the
fingerprint exists:

> enough for acceptance to require that the identity accepting is the identity
> invited, without the row holding the address that would let something else
> send to it.

## Verified is a fact, not a shape

```text
recipient_verified   nf_identities.email_verified, which comes from an OIDC
                     token signature
```

A well-formed address nobody verified is refused with `recipient_not_verified`
rather than accepted because it parses. Same distinction the eligibility
contract makes everywhere else: a shape is not a fact.

## Five refusals, each driven for real

```text
verified_fixture       deliverable
unverified             recipient_not_verified
malformed              recipient_shape_invalid
domain_not_allowed     recipient_domain_not_allowed
unrecognised_source    recipient_source_not_recognised
```

Plus one the tests found by running against a real database:

```text
a member with no address on file   refused by name, and kept in the list
```

`nf_identities.email` is nullable, so that member really can exist. The first
version of the check required *every* recipient to carry a fingerprint and blew
up on the `None`, which read as "recipient validation is broken" when the truth
was "this member cannot be emailed and the system said so". The rule is now:
at least one recipient is deliverable, every deliverable one has a fingerprint,
and every undeliverable one carries a reason — an operator needs to see who
cannot be reached.

## Nothing is looked up

```text
dns_checked                 false
mx_checked                  false
provider_validation_called  false
network_calls               0
```

"Is this domain deliverable" is a question only a network can answer. This
module does not ask it, and names what it did not check rather than leaving a
reader to assume.
