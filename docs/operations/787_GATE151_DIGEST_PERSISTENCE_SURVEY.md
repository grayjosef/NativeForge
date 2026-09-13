# 787 — Gate 151: the digest persistence gap, surveyed

Read-only. No digest was persisted, no delivery queued, no mail sent.

## The gap, measured

```text
nf_tenant_digest_records                        does not exist
nf_digest_delivery_intents rows                 71
  of those, naming a digest_id                  71
  digest records they point at                  0
```

Every delivery intent in the database names a digest. Not one of those digests
is stored anywhere. Seventy-one rows asserting *"we intended to deliver digest
X"* where X cannot be re-read.

Gate 150 described this as "delivery intents name a digest nobody kept". The
measurement is worse than the description: it is not that digests are
occasionally unkept, it is that **none has ever been kept** and every intent
depends on one.

## Why that matters, concretely

A tenant misses a deadline. The question is: what did NativeForge tell them, and
when?

```text
the intent says      a digest with id abc… was queued on this date, with
                     4 items visible and 2 suppressed
the digest says      nothing. It does not exist.
```

So the audit trail records that something was intended and cannot say what. For
a product whose stated purpose is award compliance for Tribal governments, that
is the wrong half of the record to have.

## Does the digest survive a request today?

No. `build_tenant_digest` returns a dict, the route renders it, and the request
ends. Nothing writes it.

What *does* survive is the delivery intent, and it stores derived facts about
the digest — `items_total`, `items_visible`, `body_render_hash` — without the
digest itself. Those numbers are re-derivable only by regenerating the digest
from the snapshot, which requires the snapshot still to exist and to be
unchanged, which nothing guarantees.

## Is the digest id at least stable?

Yes, and this is the one piece of good news. `build_digest_id` is already
deterministic with no clock in it:

```python
sha256("tenant_id|cadence|period_start|period_end")
```

Gate 142 found and fixed the opposite defect — Gate 140's assembler passed no
period, so every week produced an identical id. The id is now a genuine key,
which means a records table can use it as one rather than inventing another.

## What must be stored

```text
digest_id                      the deterministic id, as the org-scoped key
organization_id                the partition
cadence, period_start/end      what window this covers
digest_payload_json            the normalized payload
payload_sha256                 so a re-render can be checked against it
snapshot_ids                   what it was built from
items_total/visible/suppressed the three counts, which must agree
items_human_review             the UNKNOWN / NEEDS HUMAN REVIEW count
items_with_unverified_deadlines
caveats_json, blockers_json    why anything was withheld or flagged
delivery_status                what happened to it, if anything
fact_status, is_demo           the labelling, forced not accepted
archived_at, created_at        lifecycle
created_by_identity_id         who generated it
```

## Normalized payload, or the rendered body?

**The normalized payload, and a hash.** Not the rendered body.

```text
the payload   is what the digest IS - items, counts, caveats, suppressions
the body      is one rendering of it, for one channel, at one moment
```

Storing the rendered body would mean storing something shaped like an email in
a table, which is how a preview-only lane quietly becomes a delivery lane. The
renderer can re-render from the payload and check its hash, which proves the
same thing without keeping the artefact.

The delivery intent already stores `body_render_hash` separately, so a stored
payload plus that hash lets a reader verify a specific rendering without the
rendering being retained.

## Preserving UNKNOWN and the caveats

Non-negotiable, and the reason a JSON payload beats a set of scalar columns.
The digest's honesty lives in:

```text
items_human_review               NEEDS HUMAN REVIEW, counted not hidden
items_with_unverified_deadlines  a date we have not confirmed
items_with_unknown_reporting_burden
items_suppressed                 withheld from the view, still counted
blocked_reasons                  including "items_suppressed:N"
```

Gate 140's invariant is that `items_total == visible + suppressed + unchanged`.
A records table that stored only the visible count would let that invariant stop
being checkable after the fact, which is exactly the failure this gate exists to
close.

## Preventing real customer data writes

The records table is subject to Gate 148's boundary like any other: a digest
built from real tenant data is `customer_operational_data`, and writing one
needs a consent record, a beta scope approval, live customer auth and a verified
binding — none of which exists.

In practice this gate writes only `fact_status=demo_fixture` rows in the demo
organization, forced by the route rather than accepted from a caller, the same
rule Gate 139 established and Gate 148's guard now enforces centrally.

## What must not be in the table

```text
no recipient address column      Gate 142's rule: an address has nowhere to be
                                 stored, so it cannot be stored
no rendered body column          a payload and a hash, not an artefact
no provider subject, token, cookie, state or PKCE
no document body bytes
```

A column that does not exist cannot be filled by a later mistake.

## Cleanup and archive

`archived_at`, following `nf_awarded_grants`. An archived digest is still
readable — an audit of a missed deadline needs the digest that was current at the
time, not only the current one — so archive is a state, not a delete.

Fixture cleanliness requires the verifier to leave zero live fixture records, so
the verifier archives what it creates and the fixture-cleanliness check confirms
it.

## What stays blocked

```text
email_delivery                 false
source_monitoring_live         false
object_store_configured        false
customer data writes           refused
production digest persistence  false
controlled_customer_pilot      false
```

`tenant_digest_persistence_live` may become true **for controlled_dev_demo
only**, on the evidence of a real round trip.

## Conventions to follow

`nf_awarded_grants` is the closest org-scoped precedent: `organization_id`,
`tenant_id_label`, `fact_status`, `human_review_required`, `is_demo`,
`blocked_reasons` as JSON, `created_by_identity_id`, `archived_at`, and
created/updated timestamps. The new table follows it rather than inventing a
shape.

## What Gate 151 builds

Migration 0042, an org-scoped repository, a persistence service, route
integration, a readiness service, a verifier, artifacts and docs. It sends no
mail, calls no source, contacts no object store, and writes no customer data.
