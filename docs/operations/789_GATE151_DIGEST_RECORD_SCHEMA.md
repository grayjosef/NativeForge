# 789 — Gate 151: the digest record schema

Migration **0042**, table `nf_tenant_digest_records`. Head pins moved from 0041
to 0042 in seven declaring places.

## The key

```text
organization_id + digest_id, unique where archived_at IS NULL
```

`digest_id` is already deterministic and has been since Gate 142:

```python
sha256("tenant_id|cadence|period_start|period_end")
```

No clock in it. Gate 142 fixed the opposite defect — Gate 140's assembler passed
no period, so every week produced an identical id — which means the id is a real
key now rather than a surrogate this gate would have had to invent.

Persisting the same period twice is therefore a defect, not a second version,
and the repository names it `digest_already_persisted_for_this_period` before
the unique index has to.

## The columns

```text
id                                    uuid, primary key
organization_id                       uuid, FK organizations, CASCADE
is_demo                               bool, forced
tenant_id_label                       text, a label only
digest_id                             text, the deterministic id
digest_period_key                     text
cadence                               weekly | daily | manual_preview | unknown
period_start, period_end              date

digest_payload_json                   the normalized digest
payload_sha256                        char(64)
snapshot_ids                          json

items_total                           int
items_visible                         int
items_suppressed                      int
items_unchanged                       int
items_human_review                    int
items_with_unverified_deadlines       int
items_with_unknown_reporting_burden   int
caveats_json                          json
blocked_reasons                       json

delivery_status                       preview_only | queued | cancelled |
                                      needs_human_review | unknown
email_delivery_live                   bool, CHECKed false
source_monitoring_live                bool, CHECKed false

fact_status                           demo_fixture | tenant_supplied |
                                      verified | unknown
human_review_required                 bool
created_by_identity_id                uuid
archived_at, created_at, updated_at   timestamptz
```

## The columns that are deliberately absent

```text
recipient, recipient_email, email, address
rendered_body, body, html, mime
document_body
provider subject, token, cookie, state, PKCE
```

Not a convention callers are asked to follow. There is nowhere to put any of
them, which is the only version of this rule that survives a later gate written
by somebody who has not read this page.

## The constraints the database enforces

```sql
CHECK (items_total >= items_visible + items_suppressed)
CHECK (items_visible >= 0 AND items_suppressed >= 0
       AND items_unchanged >= 0 AND items_total >= 0)
CHECK (items_human_review >= 0
       AND items_with_unverified_deadlines >= 0
       AND items_with_unknown_reporting_burden >= 0)
CHECK (delivery_status <> 'sent')
CHECK (NOT email_delivery_live)
CHECK (NOT source_monitoring_live)
CHECK ((NOT is_demo) OR fact_status = 'demo_fixture')
CHECK (length(payload_sha256) = 64)
```

Three of these are the campaign's standing pattern: a capability that must stay
off is CHECKed rather than defaulted, so a future gate that activates sending
has to remove the constraint in a migration somebody reviews.

## `queued` is permitted here and refused on 0041

Which looks backwards until you read Gate 104. The builder owns `queued` for a
digest whose delivery was recorded; 0041 refuses it because a delivery *intent*
is not a position in a send queue. A digest record may carry the builder's own
status, and still asserts nothing left the building, because
`email_delivery_live` and `source_monitoring_live` are CHECKed false beside it.

## `tenant_supplied` is permitted and never written

The `fact_status` constraint accepts it because the column means the same thing
everywhere else in the schema. Nothing writes it: a digest built from real
tenant data is `customer_operational_data` under Gate 148's classification, and
writing one needs a consent record, a beta scope approval, live customer auth
and a verified binding — none of which exists.

A verifier check counts `tenant_supplied` rows and requires zero.

## What the caller may not set

```text
is_demo
fact_status
email_delivery_live
source_monitoring_live
payload_sha256
```

Each decides whether a write is a production write or what the record claims
about itself. A caller supplying one gets `caller_may_not_set:<field>` rather
than an override — Gate 137A found a verified binding written onto the demo
organization because the caller said it was not one.

`organization_id` is **not** on this list, and the omission is deliberate: it is
a required parameter of every function in the repository, so listing it would
say the repository refuses the one thing it cannot work without. The partition
is authoritative, not forbidden. An earlier draft had it there and a
parametrised test collided on it.

## Row-level security

An org-isolation policy on PostgreSQL, matching 0041:

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

## Archive is a state, not a delete

`archived_at` set; the row stays readable by id and drops out of the default
list. An audit of a missed deadline needs the digest that was current at the
time, not only the current one.
