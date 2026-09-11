# 756 — Gate 145A: can NativeForge enter a controlled customer beta?

Survey before implementation. Nothing was built while writing this, and nothing
was activated.

## The question this gate answers, and the six it does not

```text
answers    can a controlled customer beta start, and under what constraints
does NOT   launch production
does NOT   activate live source monitoring
does NOT   permit real customer data
does NOT   turn on email sending
does NOT   configure object storage
does NOT   approve a pilot — that is Mayhem's decision, not a gate's
```

## What Gate 144's cockpit already reports

Fifteen lanes, measured:

```text
login                          operational              true
customer_persistence           operational              true
awarded_grants                 operational              true
tenant_digest                  operational              true
document_metadata              operational              true
email_delivery_readiness       operational              true
source_monitoring_preflight    operational              true

document_body_storage          not_configured           false
email_delivery                 not_configured           false
object_storage                 not_configured           false
source_monitoring              blocked                  false
customer_auth                  requires_human_approval  false
verified_operational_binding   requires_human_approval  false
controlled_customer_pilot      production_false         false
production_rollout             production_false         false
```

Seven operational, eight not — and every one of the eight names a blocker.

## What is operational now

Seven lanes, all `controlled_dev_demo`, each proved by its own verifier:

```text
login_live                       a person signs in with Google, reaches their org
customer_persistence_live        tenant rows write, read back by id, archive
awarded_operational_tracking     awards, requirements, proof events, document
                                 references — four lanes, route-live
tenant_digest_operational        weekly preview, daily opt-in, audit-backed
                                 suppression
document_metadata_operational    document references record, read back, archive
email_delivery_readiness         render, validate, queue, audit — sending nothing
source_monitoring_preflight_ready  177 sources classified, nothing called
```

## What is readiness-only, and why that is not the same thing

Three lanes prove **code** and not a **capability**:

```text
email_delivery_readiness   proves a digest can become an email. Proves nothing
                           about any mailbox.
source_monitoring_preflight_ready  proves every source can be evaluated. Proves
                           nothing about any publisher's terms.
document_metadata_operational  proves a reference records. Proves nothing about
                           where bytes would live.
```

Each has a sibling flag that is false, and the whole Gates 141–143 design exists
to keep them apart:

```text
email_delivery_readiness  ≠  email_delivery
source_monitoring_preflight_ready  ≠  source_monitoring_live
document_metadata_operational  ≠  document_body_storage_ready
customer_persistence_live  ≠  customer_auth_live
```

A decision matrix that conflated any pair would be the single most damaging
artifact this campaign could produce, because each pair reads as the same thing
to anyone who has not followed the gates.

## What is preview-only

```text
tenant_digest    delivery_status may only be preview_only. The digest's
                 candidates are labelled fixture snapshots, not live notices,
                 and change detection compares two recorded snapshots.
```

## What is blocked

```text
source_monitoring_live   171 sources unreviewed (UNKNOWN terms, which blocks),
                         6 needing a human because the terms page served no
                         policy text, and five absent scheduler components
```

## What requires human approval

Two, and no code change moves either:

```text
customer_auth_live             blocked by invite_binding_passed — a SECOND real
                               person accepting a real invite. Gate 136 built
                               the path and refused to fake the person.
verified_operational_binding   Gate 137's two-part owner decision
```

## What is explicitly not production

```text
controlled_customer_pilot   not approved
production_rollout          not approved
```

Neither has a branch anywhere in the codebase that sets it true.

## What would be safe for an internal / demo beta

Everything operational above, in the demo organization
`bbbbbbbb-cccc-dddd-eeee-ffffffffffff`, with fixture-labelled rows. That is the
standing authorization from Gate 135 and has not changed.

An internal operator can today: sign in, keep a tenant profile, record awarded
grants and their requirements and proof events and document references, preview
a weekly digest, suppress an item into a pursuit with an audit trail behind it,
rehearse a digest delivery, evaluate every source in the registry, and read a
cockpit that says exactly what all of that does and does not mean.

## What would be safe for a controlled customer beta

Less, and the gap is entirely about **who the customer is**, not about what the
software does:

```text
a real person signing in            customer_auth_live is false
a real organization                 verified_operational_binding is false
real customer data                  no consent, terms or data boundary is
                                    documented anywhere
```

`bbbbbbbb-…` is a demo organization. Treating it as a customer org would be the
substitution Gates 110–113 spent four gates preventing.

So a controlled customer beta is at most **LIMITED_GO**, and the limits are not
technical debt — they are the two human decisions above plus a consent boundary
nobody has written.

## What must happen before real customer data

```text
1. customer_auth_live              a second real person accepts a real invite
2. verified_operational_binding    Gate 137's two-part owner decision
3. a documented data boundary      what is collected, retained, exported, deleted
4. a consent record                Gate 142 named this gap and did not fill it:
                                   nothing in this repository records that a
                                   tenant asked for anything
```

## What must happen before live source monitoring

```text
1. a terms review per source       171 UNKNOWN, 6 unreadable without a human
2. robots.txt, fetched politely    never fetched, so unknown, so blocking
3. an activation approval per source
4. a credential where required     SAM.gov needs a key AND a role
5. five scheduler components       worker, trigger, persistent backend,
                                   production raw payload store, runtime
```

## What must happen before email sending

```text
1. a provider and five settings    none chosen, none configured
2. an email delivery service       the module tenant_beta_readiness_service
                                   already looks for
3. explicit send activation        a decision, not a config value
4. a verified sender domain        SPF, DKIM, DMARC
5. unsubscribe and bounce handling
6. a recipient consent record      the same gap as above
```

## What must happen before object storage

```text
1. five settings with real values
2. an injected S3-shaped client    no SDK installed; none added
3. an owner decision
4. an external verifier, allowed AND passed by a person
5. secret scanning before promotion
```

## What must happen before production rollout

All of the above, plus a decision nobody has made. Production is not the sum of
the technical gates; it is those gates **and** an owner saying yes.

## Customer-facing claims that would be unsafe today

The survey's most important output. Each of these is a sentence somebody could
reasonably say after reading a green cockpit, and each is false:

```text
"we monitor grant sources for you"        source_monitoring_live is false
"you'll get a weekly digest by email"     email_delivery is false
"upload your award documents"             body storage is not configured
"sign your team in"                       customer_auth_live is false
"your data is in our system"              no real customer data is written
"we cover N sources"                      zero are cleared for collection
"65% improvement in anything"             never claimed, and not measurable here
```

## Exact blockers remaining

```text
customer_auth_live             a second real person
verified_operational_binding   an owner decision
consent and data boundary      not modelled anywhere
source_monitoring_live         171 terms reviews + 5 scheduler components
email_delivery                 a provider, a service, an activation
object_store_configured        five settings + an owner decision
controlled_customer_pilot      Mayhem's decision, after the above
production_rollout             Mayhem's decision, after everything
```

## What this gate will and will not do

Will:

```text
build a decision service producing GO / LIMITED_GO / NO_GO for three scopes
keep the four dangerous conflations apart, with invariants
list the unsafe claims, the human approvals and the technical blockers
add four routes behind the demo org session
add a decision card to the Gate 144 cockpit
build a verifier, eight artifacts, tests and five docs
```

Will not:

```text
approve a controlled customer pilot
approve production rollout
change any lane's value
treat preview-only as production-live
treat the demo org as a customer org
fabricate a consent, an approval or a customer
```
