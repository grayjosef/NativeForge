# 743 — Gate 142: the dry-run delivery queue, and why it may not say "queued"

## The constraint that shaped the table

Gate 104's digest builder already owns the vocabulary:

```text
DELIVERY_STATUSES         not_configured  preview_only  queued  sent  failed  unknown
PREVIEW_DELIVERY_STATUSES not_configured  preview_only
DELIVERED_STATUSES        queued  sent      "statuses that assert something
                                             left the building"
```

with an invariant that fails on `delivery_status_beyond_preview`.

So a dry-run queue **may not borrow `queued`**. Recording an intention and
holding a position in a provider's send queue are different facts, and using one
word for both would have forced Gate 104's invariant to be weakened — turning a
check on this system into a lie about it.

The queue starts at `dry_run_recorded`, and the digest it names keeps
`delivery_status: preview_only`.

## `nf_digest_delivery_intents`

Migration `0041`. The interesting columns:

```text
organization_id            uuid, FK CASCADE. The only authority.
tenant_id_label            a label, and never that.
digest_period_key          cadence | period_start | period_end
recipient_fingerprint      sha256[:32]. There is no address column.
recipient_domain           names no mailbox
recipient_verified         from nf_identities.email_verified
subject_line               what would have been sent
body_render_hash           a hash, not the body
delivery_status            CHECKed against the queue's own vocabulary
blocked_reason             why this stops here — always populated
send_attempted             CHECK (NOT send_attempted)
provider_contacted         CHECK (NOT provider_contacted)
emails_sent                CHECK (emails_sent = 0)
audit_event_id             the row in nf_audit_events that names this
cancelled_at               null while live
```

## Six CHECKs the database enforces

```sql
NOT send_attempted
NOT provider_contacted
emails_sent = 0
delivery_status <> 'queued' AND delivery_status <> 'sent'
length(recipient_fingerprint) = 32
recipient_fingerprint NOT LIKE '%@%'
```

Not a service promising — a constraint. A future gate that activates sending has
to remove these in a migration somebody reviews; it cannot happen by a default
changing somewhere. Three tests insert directly and assert each refusal.

The last two are worth naming: the fingerprint column is exactly where an
address would end up if a caller or a future service got careless, so the
database says it cannot.

## `blocked_reason` is always populated, including when nothing is wrong

```text
send_activation_absent           the normal answer
no_email_provider_configured     this deployment's answer
recipient_not_verified
recipient_domain_not_allowed
recipient_shape_invalid
digest_not_deliverable
cancelled_by_tenant
human_review_required
```

Leaving the field null when everything is fine would make a reader guess whether
"no reason" meant "will send" or "nobody wrote one down". The normal case has a
name.

## The state is derived, in one place

```text
recipient not verified              -> recipient_refused / recipient_not_verified
digest not deliverable              -> recipient_refused / digest_not_deliverable
source needs human review           -> needs_human_review / human_review_required
send activated                      -> dry_run_recorded / unknown
no provider configured              -> send_disabled / no_email_provider_configured
otherwise                           -> dry_run_recorded / send_activation_absent
```

The `send activated` branch is **unreachable in this deployment and deliberately
present**. A state nothing can produce is a state nobody can test, and an
activation path that first appears on the day it is needed is not a path.

## One live intent per period and recipient

A partial unique index on
`(organization_id, digest_period_key, recipient_fingerprint)` where
`cancelled_at IS NULL`, plus a service-level check that names the refusal before
the index has to raise:

```text
this_recipient_is_already_recorded_for_this_period
```

Recording the same intention twice is how a tenant gets two copies of one digest
the day sending is switched on. A *different* period records fine — tested, because
a key that never changed would have recorded a tenant once and refused every
week after.

## The audit row goes first, and is rolled back if nothing is written

Same shape Gate 140 used for pursuit suppression:

```text
1. append_org_audit_event(action=digest_delivery_intent_recorded, payload={
     event, cadence, digest_period_key, recipient_count,
     deliverable_recipient_count, body_render_hash,
     emails_sent: 0, send_attempted: false, provider_contacted: false })
2. db.flush()
3. record an intent per recipient, each carrying the audit id
4. if nothing was written: db.rollback()
5. db.commit()
```

The payload carries counts and a hash. No address and no body: an audit trail
that quoted the digest would be a second copy of tenant content in a table
nobody reads with that in mind.

A test drives the refusal path and asserts the audit count is unchanged.

## Two new audit verbs, and one deliberately absent

```text
digest_delivery_intent_recorded
digest_delivery_refused
```

`nf_audit_events.action` is `sa.String(64)`, not a database enum, so no
migration was needed.

Neither is in `SECURITY_AUDIT_ACTIONS`. `feedback_alert_attempted` and
`feedback_alert_failed` already existed and nearly fit — and reusing one would
have put a tenant digest into the security event stream, where a reader
filtering for security events would have to learn to ignore it.

`digest_delivery_sent` does not exist, because nothing in this system can
produce it. A test asserts no audit verb in the whole enum ends in `_sent`.

## Cancelling keeps the row

`cancel_delivery_intent` is an UPDATE that sets `cancelled_at`:

```text
rows_written   1
rows_deleted   0
list (default)          the intent is gone
list?include_cancelled  the intent is there
```

The partial unique index stops treating a cancelled intent as the live one, so a
tenant can withdraw and be recorded again later without the first decision
disappearing.
