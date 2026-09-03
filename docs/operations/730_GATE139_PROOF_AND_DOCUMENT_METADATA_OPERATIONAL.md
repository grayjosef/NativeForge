# 730 — Gate 139: proof/audit and document metadata operational

## Proof and audit events

```text
POST   .../requirements/{id}/proof-events            append
GET    .../requirements/{id}/proof-events            list
GET    .../proof-events/{event_id}                   read one
POST   .../proof-events/{event_id}/supersede         a later event replaces it
POST   .../proof-events/{event_id}/archive           archive
```

### Immutable, and the contract is the strongest in the codebase

> "There is no upsert and no update of an event's own facts. What was believed
> at the time is what the row says, forever."

`POST_INSERT_WRITABLE_COLUMNS` is `("superseded_at", "archived_at")` — two
columns, both lifecycle, neither a fact about what happened.

So a correction is a **supersede**: a new event naming the one it replaces,
with the old row's `superseded_at` set and every fact it recorded intact.

### The caller does not name the event type

`supersede_proof_event` sets `proof_superseded` itself. The first version of the
route passed the caller's `event_type` through and got

```text
TypeError: got multiple values for keyword argument 'event_type'
```

The repository names it because a supersede **is** a supersede, and letting a
caller call it something else would make the trail unreadable. `SupersedeBody`
has no `event_type` field, and a test asserts it.

### An accepted proof needs evidence

`proof_accepted` is a claim about a funder's decision, and the repository
refuses it without both an acceptance timestamp and a document reference:

```text
accepted_status_without_an_acceptance_timestamp
proof_accepted_without_a_document_reference
```

That reaches the caller unchanged as a 422. Paraphrasing it into an HTTP message
would have been a second, worse contract.

### A schema contradiction this gate found

Nothing had exercised supersede before, so nothing had met this:

```text
supersedes_event_id   FOREIGN KEY ... ON DELETE SET NULL
CHECK  (event_type = 'proof_superseded') = (supersedes_event_id IS NOT NULL)
```

Deleting a superseded event nulls its successor's pointer, which violates the
CHECK — **the delete is impossible**.

It does not fire in production: proof events are append-only, `rows_deleted` is
a constant `0`, and there is no DELETE path in the repository at all (asserted
by parsing). It fires only where something truncates tables, which is the test
suite.

Not fixed here. Changing the FK to CASCADE or relaxing the CHECK is a schema
change, and the audit model says these rows are never deleted. Recorded, with a
test that asserts both halves still say what they say, so the next person to
meet it knows why.

## Document metadata, and no bytes

```text
POST   .../awarded-grants/{award_id}/documents    a REFERENCE
GET    .../awarded-grants/{award_id}/documents    list
GET    .../documents/{document_id}                read one
POST   .../documents/{document_id}/archive        archive
```

### The database refuses a body, not just the route

```sql
-- nf_award_documents
object_key IS NULL OR object_store_configured
```

`object_store_configured` is bridged from Gate 96's `detect_body_store_mode()`,
never accepted from a caller, and measured:

```text
detect_object_store_configured()  ->  False
```

So metadata-only is not a convention this gate chose — it is what the table
permits. A document row is a reference; the row describes a document, it does
not contain one.

### A body is refused by name

```text
object_key  object_bucket  object_version  content  body  file  bytes
sha256_digest  content_length
```

Any of them is **422**:

```json
{"error": "document_body_storage_is_not_configured",
 "fields": ["object_key"],
 "object_store_configured": false}
```

Refused by name rather than ignored, for the reason Gates 110–113 settled for
labels: a caller that offered something should learn it was not honoured. A
silent drop is how somebody comes to believe a file was stored.

The proof-event route refuses the same fields, for the same reason — a proof
event may reference a document and may not carry one.

A read says it too, rather than leaving it to be inferred:

```json
"metadata_only": true, "body_available": false, "object_store_configured": false
```

And a test parses every route module for `boto3`, `s3_client`, `put_object`,
`upload_file` and `open(` and asserts none appear. **No object store is
contacted anywhere in this gate.**

### Attached to something

```text
awarded_grant_id      nullable
award_requirement_id  nullable
proof_event_id        nullable
at least one required — "a document attached to nothing is a file in a drawer"
```

All three are in `FORBIDDEN_ANCHOR_NAMES`: reaching the organization through
whichever join happened to be populated would make this table's policy depend
on three other tables' policies, and on which one a caller filled in.

### Legal hold refuses archive

`legal_hold_refuses_archive` reaches the caller unchanged. A document under
legal hold is one somebody has said must not move, and archiving is the only
lifecycle operation this table has.
