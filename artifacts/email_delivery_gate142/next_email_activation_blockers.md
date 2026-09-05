# Gate 142 — what email delivery still does not reach

## Where this stands

```text
email_delivery_readiness   TRUE
email_delivery             FALSE
scope                      controlled_dev_demo
preflight state            dry_run_verified
send disabled because      no_email_provider_configured
```

A digest renders into a subject and a body, a recipient validates to a
fingerprint, an intent is recorded against the organization with an audit event
naming it, and the reason nothing will be sent is written on the row.

Nothing was sent.

## Readiness is not delivery

```text
email_delivery_readiness   can this system rehearse the whole path?
email_delivery             does mail reach anybody?
```

Collapsing those is how a deployment starts mailing people the day somebody
pastes an API key into an environment file. An invariant fails if a passing dry
run ever sets `email_delivery`, and the preflight reaches `send_activated` only
with three pieces of evidence a rehearsal cannot manufacture.

## An intent is not a queue position

Gate 104's digest builder owns `queued` and lists it under `DELIVERED_STATUSES`
— "statuses that assert something left the building". So this queue starts at
`dry_run_recorded` and the digest keeps `delivery_status: preview_only`.

The database enforces it rather than a service promising it:

```text
NOT send_attempted
NOT provider_contacted
emails_sent = 0
delivery_status <> 'queued' AND delivery_status <> 'sent'
length(recipient_fingerprint) = 32
recipient_fingerprint NOT LIKE '%@%'
```

A future gate that activates sending removes those in a migration somebody
reviews. It cannot happen by a default changing.

## No address, anywhere

```text
recipient stored as                    sha256[:32] fingerprint plus domain
address column in the queue            none
addresses in any route response        false
intents with an address-shaped
  fingerprint                          0
addresses in any committed artifact    none — every file is scanned for one
```

`nf_identities.email` holds a real address because OIDC handed it over.
`validate_recipient` is the only place it is read, and what comes out is a
handle.

## What the digest body does and does not say

```text
rendered                              true
bytes                                 2440
items shown                           9 of 9
eligibility nobody settled            1
deadlines nobody verified             4
forbidden claims present              []
contains an address                   false
contains HTML                         false
tells the reader to verify deadlines  true
says it is not a live check           true
```

The body itself is not committed. A digest body is tenant content; what belongs
in a repository is that it rendered and what it refuses to claim.

## What activation would require

```text
a provider, and its five settings with real values:
  nf_email_api_endpoint
  nf_email_api_key
  nf_email_provider
  nf_email_sender_address
  nf_email_sender_domain

an email delivery service      the module tenant_beta_readiness_service already
                               looks for, and which this gate did not write

send activation                a DECISION, not a config value. The preflight
                               refuses an activation setting that arrives
                               without an approval:
                               send_activation_setting_present_without_an_approval

a verified sender domain       SPF, DKIM, DMARC

unsubscribe and bounce handling  a digest nobody can stop receiving is worse
                               than one nobody receives

a recipient consent record     nothing in this repository records that a tenant
                               asked to be emailed. That is a gap this gate
                               names and does not fill.

customer_auth_live             for anything but fixture recipients
```

## What is NOT the blocker

```text
the render          works, bounded, and makes no claim it may not
the validation      works, and refuses four ways by name
the queue           writes, reads back, refuses duplicates, cancels without
                    deleting
the audit trail     one event per dry run, outside the security stream
a mail library      not needed to prove any of the above, and not imported
```

## Still false, and not touched

```text
email_delivery                 false
digest_email_delivery_live     false
production_email_delivery      false
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
object_store_configured        false
document_body_storage_ready    false
production_rollout             false
controlled_customer_pilot      false
```

## Nothing left the building

```text
emails sent                       0
send attempted                    false
provider contacted                false
network calls to a mail provider  0
intents claiming a send           0
intents for the real organization 0
intents that are not fixtures     0
delivery audit events             1
```
