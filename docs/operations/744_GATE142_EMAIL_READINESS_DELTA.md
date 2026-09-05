# 744 — Gate 142: the email readiness delta

## What changed

```text
                                before Gate 142   after Gate 142
email_delivery_readiness        did not exist     true, controlled_dev_demo
email_delivery                  false             false
digest renders for delivery     nothing rendered  true
recipient validation            did not exist     true, fingerprints only
dry-run delivery queue          did not exist     nf_digest_delivery_intents
delivery audit verbs            none              two, outside the security stream
delivery routes                 none              6
email provider preflight        did not exist     five states
digest_period_key               weekly|unknown|unknown   a real span
alembic head                    0041 added
```

`email_delivery` is still false. What is new is that this system can now
**rehearse** the whole path and say precisely where it stops.

## Readiness is not delivery

```text
email_delivery_readiness   can this system render a digest, validate a
                           recipient, record an intent and audit it?   TRUE

email_delivery             does mail actually reach anybody?           FALSE
```

Collapsing those is how a deployment starts mailing people the day somebody
pastes an API key into an environment file. Two invariants stop it:

```text
a_dry_run_activated_email_delivery
a_rehearsal_activated_email_delivery
```

and `send_activated` needs three pieces of evidence a rehearsal cannot
manufacture — `provider_verification_allowed`, `provider_verification_passed`
and `send_activation_approved`. Each is tested, including the permitted branch,
so the refusals stay falsifiable.

A setting is explicitly **not** an approval:

```text
send_activation_setting_present_without_an_approval
```

## What readiness does not require

```text
provider_required_for_readiness            false
send_activation_required_for_readiness     false
real_recipient_required_for_readiness      false
```

All three stated as fields. Requiring a configured vendor for a rehearsal would
make the readiness lane unreachable on every deployment that has not chosen one,
and an unsatisfiable conjunct makes every "not ready" above it unfalsifiable —
Gate 134F's lesson, kept out of a third lane now.

## Was any email sent?

```text
emails sent                       0
send attempted                    false
provider contacted                false
network calls to a mail provider  0
intents claiming a send           0
```

And it is a property of the code rather than a claim about one run: four
delivery modules are parsed with `ast` and assert they import no mail library.
`smtplib` ships with Python, so unlike Gate 141's object-store SDK there is no
"not installed" guarantee available — the guarantee is that nothing imports it.

## Was any provider contacted?

No. There is no provider, no client, no socket, and no configuration to build
one from:

```text
nf_email_provider          absent
nf_email_api_endpoint      absent
nf_email_api_key           absent
nf_email_sender_address    absent
nf_email_sender_domain     absent
preflight state            no_config
```

Setting **names** reach every report and no value does. The preflight tests
construct a settings object carrying a real-looking vendor and a real-looking
sender address, then assert neither string appears in the serialised result.

## Were real customer recipients committed?

No. The delivery queue has **no address column**, two CHECK constraints stop the
fingerprint column becoming one, and every artifact is scanned with a mailbox
regex before it is returned:

```text
recipient stored as                 sha256[:32] fingerprint plus domain
addresses in any route response     none
addresses in any committed file     none
intents with an address-shaped
  fingerprint                       0
```

The one address that exists in this gate's fixtures lives at a `.invalid`
domain, which RFC 2606 reserves precisely so nothing can ever be delivered to
it.

One thing worth recording about that guard: the first version scanned for a bare
`@` and fired on the migration's own CHECK — `recipient_fingerprint NOT LIKE
'%@%'` — quoted in an artifact as evidence. A guard that cannot tell a mailbox
from the SQL that forbids one would have forced the guarantee out of the
artifact to keep the check quiet. It now looks for an address shape.

## Was real customer data written?

No. Every row is `demo_fixture`-labelled in the demo organization
`bbbbbbbb-cccc-dddd-eeee-ffffffffffff`. The real organization
`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` was not addressed by any route.

```text
intents for the real organization   0
intents that are not fixtures       0
intents left live after the verifier 0
persistence rows left live           0
```

## Did production delivery change?

No. `production_email_delivery` is false in the preflight, the readiness
service, every route and every artifact, and no branch anywhere in this gate
sets it. `digest_email_delivery_live` in the entitlement service is untouched
and still false — entitlement is permission, delivery is a capability, and the
block comment in that module exists to keep them apart.

## What activation would require later

```text
1. a provider, and five settings with real values      absent, named by key
2. an email delivery service                           the module
                                                       tenant_beta_readiness_service
                                                       already looks for
3. send activation                                     a DECISION, not a config
                                                       value; the preflight
                                                       refuses a setting that
                                                       arrives without an approval
4. a verified sender domain                            SPF, DKIM, DMARC
5. unsubscribe and bounce handling                     a digest nobody can stop
                                                       receiving is worse than one
                                                       nobody receives
6. a recipient consent record                          NOTHING in this repository
                                                       records that a tenant asked
                                                       to be emailed
7. customer_auth_live                                  for anything but fixture
                                                       recipients
```

Item 6 is a gap this gate **names and does not fill**. Consent is not a
technical control that can be inferred from a membership row, and building one
without deciding what consent means here would be worse than the absence.

## What is NOT the blocker

```text
the render          works, bounded, and refuses seven claims by name
the validation      works, and refuses five ways plus the member with no address
the queue           writes, reads back, refuses duplicates, cancels without deleting
the audit trail     one event per dry run, rolled back if nothing is recorded
a mail library      not needed to prove any of it, and not imported
```

## Defects found and fixed

```text
Gate 140's assembler passed no period to the digest builder, so every
digest_id was derived from (tenant, cadence, None, None) - identical for every
week forever. A delivery queue keyed on that would have recorded a tenant once
and refused every later week as a duplicate. The period comes from the two
snapshots the digest compares.

`sa.table()` builds untyped columns, so sqlite refused a bound uuid.UUID. Every
other repository in this campaign uses `sa.Table` with real types.

The artifact's address guard scanned for a bare `@` and fired on a CHECK
constraint quoted as evidence.

Both the smoke and a test required every recipient to carry a fingerprint.
`nf_identities.email` is nullable, so a member with no address made the check
fail on a None - which read as "validation is broken" when the truth was "this
member cannot be emailed and the system said so".
```

## Still false, and not touched

```text
email_delivery                 false
digest_email_delivery_live     false
production_email_delivery      false
source_monitoring_live         false
object_store_configured        false
document_body_storage_ready    false
customer_auth_live             false
verified_operational_binding   false
production_rollout             false
controlled_customer_pilot      false
```

## Next gate

Gate 143. What remains, in the order the blockers unblock:

```text
customer_auth_live             blocked on invite_binding_passed — a second real
                               person accepting a real invite (Gate 136)
verified_operational_binding   Gate 137's two-part owner decision
source_monitoring_live         a collector activated under the existing gates,
                               which is what would give the digest live
                               candidates instead of fixture snapshots
digest persistence             no nf_tenant_digest_records; a digest that cannot
                               be re-read cannot be audited after a missed
                               deadline — and now that delivery intents ARE
                               persisted, an intent naming a digest nobody
                               kept is the next inconsistency
recipient consent              named above, not modelled anywhere
email_delivery                 the seven items above
object_store_configured        Gate 141's five settings and owner decision
```
