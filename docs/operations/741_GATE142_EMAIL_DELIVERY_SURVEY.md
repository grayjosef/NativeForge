# 741 — Gate 142A: what email delivery already is, and what is missing

Survey before implementation. Nothing was built while writing this.

## Why `email_delivery` is false

Because there is nothing. Not a stub, not a disabled adapter — nothing:

```text
src/nativeforge/services/email_delivery_service.py        ABSENT
any smtp / sendgrid / mailgun / postmark / ses module     ABSENT
any email setting in lib/settings.py                      ABSENT
any recipient column on nf_tenant_beta_profiles           ABSENT
any delivery table                                        ABSENT
```

`tenant_beta_readiness_service:222` derives it honestly:

```python
email_delivery = _module_importable("nativeforge.services.email_delivery_service")
```

The module does not exist, so the answer is false and always has been. That is
one of the few flags in this campaign that was never a lie — it was a correct
report about an absence.

## What is declared rather than derived

One place:

```text
tenant_beta_feature_entitlement_service.py:248
    "digest_email_delivery_live": False        a literal
```

sitting in a block labelled "Entitlement is permission. These are the things it
is not." Correct, and a constant. Two beta features are gated on it:

```text
weekly_nofo_digest        -> digest_email_delivery_live
optional_daily_alerts     -> digest_email_delivery_live
```

So a tenant can be *entitled* to a weekly digest and still receive nothing, and
the entitlement service says so. Gate 142 does not change that: entitlement is
permission and delivery is a capability, and collapsing the two is exactly the
mistake the block comment is there to prevent.

## What Gate 104 already decided about delivery

`tenant_nofo_digest_builder_service` has the vocabulary:

```text
DELIVERY_STATUSES         not_configured  preview_only  queued  sent  failed  unknown
PREVIEW_DELIVERY_STATUSES not_configured  preview_only
DELIVERED_STATUSES        queued  sent          "statuses that assert something
                                                 left the building"
```

and an invariant fails on `delivery_status_beyond_preview`.

This is the sharpest constraint on Gate 142. **A dry-run queue may not set
`queued`.** `queued` means a provider accepted it; recording an intention is a
different fact and needs a different word, or the digest's own invariant would
have to be weakened to accommodate a lie. The digest's `delivery_status` stays
`preview_only` and the queue carries its own status.

## Where a recipient would come from, and the doctrine already in place

```text
nf_identities.email                     String(320), nullable — a REAL address
nf_membership_invites.invited_email_domain        the domain only
nf_membership_invites.invited_email_fingerprint   sha256[:32] of the lowercased
                                                  address, added by 0039
```

The split is deliberate and documented in `membership_invite_repository_service`:

> Not secrecy, and not claimed as secrecy — plausible addresses are few enough
> to enumerate. It is matching: enough for acceptance to require that the
> identity accepting is the identity invited, without the row holding the
> address that would let something else send to it.

`nf_identities` holds the address because OIDC handed it over and the identity
is who it is. Everything downstream of it holds a fingerprint.

A delivery queue is downstream. So the queue stores a **fingerprint and a
domain**, never an address, and `email_fingerprint()` is reused rather than a
second hashing scheme being invented — two fingerprint functions would drift and
then disagree about whether a recipient matched.

Live counts, presence only:

```text
identities                    1
identities with an email value 1
identities with email_verified 1
active memberships             1
```

One person, the demo organization's owner. No address was read into a variable
that this document, any artifact, or any log renders.

## Can anything contact a provider?

No, and it is a property of the dependency set:

```text
no smtp/sendgrid/mailgun/postmark/ses package installed
Python's own smtplib      not imported by any service
hermetic_network_enforcement_service already scans services/ for network
                          imports and call sites, with an approved-site list
```

`smtplib` is in the standard library, so "not installed" is not available as a
guarantee the way it was for boto3 in Gate 141. The guarantee has to be that no
module imports it — which is checkable by parsing, and which the hermetic
enforcement service already does for the modules it covers.

## What the audit trail can carry

`nf_audit_events.action` is `sa.String(64)` — not a database enum. So adding an
`AuditAction` member needs **no migration**, only the enum and whatever
references it.

Existing actions that nearly fit and do not:

```text
feedback_alert_attempted / feedback_alert_failed
    security verbs, in SECURITY_AUDIT_ACTIONS, and about operator feedback
    alerts rather than tenant digest delivery. Reusing one would put a digest
    into the security event stream, where a reader filtering for security
    events would have to learn to ignore it.
```

So Gate 142 adds its own verb rather than borrowing one whose meaning it would
have to stretch.

## What a dry run can prove, and what it cannot

Can:

```text
the digest renders into a deliverable shape        subject, body, item count
a recipient is validated, or refused by name       shape, domain, verification
an intended delivery is recorded, org-anchored
an audit event names it
the send-disabled blocker is explicit
the same recipient is not queued twice for one digest period
```

Cannot:

```text
that any address exists
that a provider would accept it
that a message would arrive
deliverability, bounce handling, unsubscribe, or DMARC alignment
```

So a passing dry run may set `email_delivery_readiness` for
`controlled_dev_demo` and may never set `email_delivery`. Same separation Gate
141 made between `hermetic_fake_verified` and `production_verified`, and for the
same reason: a rehearsal that could flip the live flag makes every "not live"
above it unfalsifiable.

## What real activation would require

```text
a provider and its configuration     none chosen, none configured
an email delivery service            the module tenant_beta_readiness_service
                                     already looks for
explicit send activation             a decision, not a config value
a verified sender domain             SPF, DKIM, DMARC
unsubscribe and bounce handling      a digest nobody can stop receiving is
                                     worse than one nobody receives
a recipient consent record           nothing in this repository records that a
                                     tenant asked to be emailed
customer_auth_live                   for anything but fixture recipients
```

## Exact blockers remaining

```text
email_delivery                 false — no service, no provider, no configuration
digest_email_delivery_live     false — the entitlement constant above
send activation                absent — and this gate does not add one
recipient consent              not modelled anywhere
```

## What this gate will and will not do

Will:

```text
add a provider configuration preflight that reports names and states
add a digest delivery renderer      a deliverable shape, sent nowhere
add recipient validation            fingerprint + domain, never an address
add a dry-run delivery queue        an INTENT, with its own vocabulary
add a delivery audit verb           digest_delivery_* , no migration needed
add delivery routes behind the demo org session, if they refuse safely
derive email_delivery_readiness for controlled_dev_demo
keep email_delivery false, and fail an invariant if a dry run sets it
```

Will not:

```text
send an email
contact a provider
import smtplib or any mail library
store a recipient address
add a dependency or touch uv.lock
set delivery_status to queued or sent
claim production delivery
```
