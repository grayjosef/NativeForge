# 788 — Gate 151: digest persistence

## The lane

```text
tenant_digest_persistence_live   true
scope                            controlled_dev_demo
production_digest_persistence    false, and never computed
```

## The gap, measured rather than described

```text
nf_tenant_digest_records                    did not exist
nf_digest_delivery_intents rows             71
  of those, naming a digest_id              71
  digest records they pointed at             0
```

Gate 150 called it "delivery intents name a digest nobody kept". The
measurement was worse than the description: it was not that some digests went
unkept, it is that **none had ever been kept** and every intent depended on one.

A tenant misses a deadline and asks what NativeForge told them. The intent could
say a digest was queued, with four items visible and two suppressed. The digest
could say nothing, because it did not exist. For a product whose purpose is
award compliance for Tribal governments, that is the wrong half of the record to
have kept.

## What now happens

```text
migration 0042        nf_tenant_digest_records
repository            insert, get, list, archive - all org-partitioned
service               persist, read, list, archive, verify_rendering
routes                POST persist, GET records, GET records/{id},
                      POST records/{id}/archive
readiness             seven conditions, each proved by something that happened
verifier              the round trip, end to end, against the live stack
```

## What is stored

The **normalized payload** and a sha256 over it. Not a rendering.

```text
the payload   is what the digest IS - items, counts, caveats, suppressions
the body      is one rendering of it, for one channel, at one moment
```

A table holding something email-shaped is how a preview-only lane quietly
becomes a delivery lane. The renderer can re-render from the payload and check
the hash, which proves the same thing without keeping the artefact.

## What is not stored

```text
no recipient, address or email column
no rendered body, html or mime column
no provider subject, token, cookie, state or PKCE
no document body bytes
```

These are absent columns, not conventions. Gate 142 wrote the rule for the
delivery queue — "there is physically nowhere to put one" — and it applies one
table upstream. A column that does not exist cannot be filled by a later
mistake.

## The honesty fields survive

```text
items_total / visible / suppressed / unchanged
items_human_review
items_with_unverified_deadlines
items_with_unknown_reporting_burden
caveats_json
blocked_reasons
```

Gate 140's invariant is `items_total == visible + suppressed + unchanged`. A
records table storing only the visible count would let that invariant stop being
checkable after the fact, which is the failure this gate exists to close. All
four counts are stored and the database CHECKs that they agree.

## Two defects found in this gate's own code

**A dialect split.** `period_start` and `period_end` are DATE columns and the
digest carries ISO strings. SQLite refuses a string outright; Postgres coerces
it. So the insert would have passed in one environment and failed in the other —
the same split Gate 142 hit when an untyped column bound a UUID on one dialect
and not the other. Fixed with explicit coercion in the repository.

**A misleading constant.** `organization_id` was listed in `CALLER_MAY_NOT_SET`,
which reads as "the repository refuses this" when it is the one thing every
function requires. A parametrised test collided on it and exposed the wording.
The entry is gone, with a note: the partition is authoritative, not forbidden.

## What did not change

```text
email_delivery                 false
source_monitoring_live         false
object_store_configured        false
customer_auth_live             false
verified_operational_binding   false
consent_boundary_documented    false
customer_beta_scope_approved   false
controlled_customer_pilot      false
production_rollout             NO_GO
```

No customer data was written, the real organization was counted and never
addressed, no mail was sent, no source was called, and no object store was
contacted.

## Next

`789` on the schema, `790` on the linkage, `791` on the delta. Then Gate 152 —
audit replay, for which a persisted digest is the first thing a replay has to be
able to read.
