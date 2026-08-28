# 582 — Gate 104F/G: digest builder and readiness delta

`src/nativeforge/services/tenant_nofo_digest_builder_service.py`
`src/nativeforge/services/tenant_nofo_digest_readiness_service.py`

What changed at Gate 104, and — more importantly — what did not.

## The tenant NOFO digest contract now exists

Gate 103's readiness report named `digest_contract_available` as missing. It is
now present: eight services, a labelled ten-opportunity fixture pair, six
committed artifacts and 113 tests.

Gate 103's readiness service pointed at a module name that was never created
(`tenant_nofo_digest_service`). That was corrected to the module this gate
actually built, and Gate 103's test asserting the digest contract is absent was
inverted rather than deleted — the absence it guarded is now a presence, and the
test says so.

## The digest is preview-only, not email-live

```text
delivery_status        preview_only | not_configured
email_delivery_live    false
emails_sent            0
recipients_contacted   0
```

Constants on every digest, held by invariants, and `PREVIEW_DELIVERY_STATUSES`
is derived affirmatively — the allowed set is the two preview statuses, not
"anything that is not a send". An invariant fails any digest whose delivery
status leaves that set.

There is no email service in this repository. Gate 103 found zero, Gate 104A
confirmed zero, and this gate added zero. A digest is a rendered preview; nothing
leaves the building.

## Weekly is the default; daily alerts are optional

```text
DEFAULT_CADENCE = "weekly"
```

Doc 570's requirement. Daily is **opt-in** per tenant: a daily digest requested
for a tenant whose profile does not enable daily alerts falls back to weekly and
records `daily_alerts_not_enabled_for_this_tenant` in `blocked_reasons`.

The fallback is the safe direction. Silently honouring the request would make a
tenant preference decorative, and a daily cadence nobody chose is the shape a
digest becomes noise in.

## Unverified deadlines and unknown burden stay visible

The digest counts them rather than filtering them:

```text
items_with_unverified_deadlines
items_with_unknown_reporting_burden
items_human_review
items_suppressed
```

Hiding an uncertain row would make the digest look cleaner and leave a real
opportunity unseen. Counting it keeps the row in front of the tenant **and**
tells them how much of the list is not yet established. Both counts appear on the
demo digest — five and five out of ten — because the fixture set was built to
make the uncertainty visible rather than to look finished.

Suppressed items are counted in `items_total` too, so the tenant can always see
how many were withheld.

## Operational digest readiness remains false

```text
ready_for_demo_preview        true
ready_for_operational_digest  false
```

Two questions, two answers. The preview is a screen; an operational digest is a
promise about something arriving on a Monday. Three components are missing, each
**detected by import** rather than declared:

```text
email_delivery_available          no email service exists
live_source_collection_available  bridged from Gate 93's activation matrix
customer_persistence_live         no digest or tenant table exists
```

`DEMO_SCOPE` is `digest_preview_from_labelled_fixture_snapshots` and travels into
the committed artifact, so the scope of the demo is recorded next to the demo
rather than in a slide.

An invariant fails any readiness result claiming operational readiness while a
component is missing, and another fails a result claiming preview readiness with
no demo fixtures.

## Next actions, in order

1. **Build email delivery** — a weekly digest nobody receives is not a weekly
   digest.
2. **Persist tenant digests** — a digest that cannot be re-read cannot be audited
   after a missed deadline.
3. **Activate a collector under the existing gates** — change detection compares
   two recorded snapshots today; a live comparison needs a second real
   observation.
4. **Settle the pursuit pipeline vocabulary** — three disagree today, and
   suppression stayed out of the question rather than picking a winner.
5. **Extend Awarded Grants requirement tracking** (Gate 105) — separate projected
   burden from active obligations.
