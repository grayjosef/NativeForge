# 738 — Gate 141: document storage readiness, made exact

## The two questions, kept apart

```text
document_metadata_operational   TRUE   a tenant can record and read a document
                                       REFERENCE. Route-live since Gate 139.
document_body_storage_ready     FALSE  its BYTES have nowhere to live, and
                                       every route says so by name.
object_store_configured         FALSE  five required settings are absent.
scope                           none
```

These are different claims and this gate is the first to answer them
separately. Before it, `document_body_storage_ready` was a literal `False` in
`awarded_operational_tracking_readiness_service.py:320` and no service derived
it.

## Metadata does not need the object store

Stated as fields rather than left to inference:

```text
object_store_required_for_metadata   false
body_bytes_required_for_metadata     false
```

Requiring a store for metadata would have made the metadata lane permanently
unreachable and every "not ready" above it unfalsifiable — the unsatisfiable
conjunct Gate 134F removed from the customer-auth chain and Gate 140F kept out
of the digest preview.

The four Gate 139 routes work unchanged:

```text
POST /v1/nf/demo/orgs/{org}/awarded-grants/{award}/documents
GET  /v1/nf/demo/orgs/{org}/awarded-grants/{award}/documents
GET  /v1/nf/demo/orgs/{org}/documents/{document_id}
POST /v1/nf/demo/orgs/{org}/documents/{document_id}/archive
```

and two are new:

```text
GET  /v1/nf/demo/orgs/{org}/documents/{document_id}/body-storage
POST /v1/nf/demo/orgs/{org}/documents/{document_id}/body
```

## The body route is an explicit refusal, not an absence

Gate 139 left no route for a document's bytes at all, so a caller asking for one
got a 404 that reads as "wrong URL" rather than "this deployment has nowhere to
put a file". The new route answers:

```text
422 document_body_storage_is_not_configured
    object_store_configured   false
    adapter_available         false
    preflight_state           no_config
    missing_configuration     raw_payload_object_store_access_key_id
                              raw_payload_object_store_bucket
                              raw_payload_object_store_endpoint
                              raw_payload_object_store_region
                              raw_payload_object_store_secret_access_key
```

Key **names**, never values. A reader needs to know which setting to fill in;
the value is not part of that and no branch in this gate puts one into a result,
a message or an exception.

`GET .../body-storage` answers the same question without reading the document
row, because whether an object store exists is a property of the deployment and
reading the row first would make an unconfigured store look like a missing
document.

## Three constants replaced by measurement

```text
award_document_routes.py:155, :183, :212
    object_store_configured=False           -> object_store_configured()

post_award_common.refuse_body_storage
    "object_store_configured": False        -> object_store_configured()

awarded_operational_tracking_readiness_service.py:320
    "document_body_storage_ready": False    -> document_storage_readiness_service
```

Each was correct and none was measured. `object_store_configured()` asks Gate
127's detector, which asks Gate 96's `detect_body_store_mode()`; that reads
settings and opens no socket. A test asserts the literal has not come back:

```python
assert "object_store_configured=False" not in source
assert "object_store_configured=object_store_configured()" in source
```

and the readiness detector reports
`route_module_hardcodes_object_store_configured_false` if it does.

## What every route refuses

```text
unauthenticated                              401, all six
a forged X-NF-Org-Id                         401 — not a parameter on any route
a caller setting is_demo or fact_status       400, named
object_key, object_bucket, object_version,
  content, body, file, bytes, sha256_digest,
  content_length                              422, document_body_storage_is_not_configured
POST .../body with no adapter                 422, with the missing key names
POST .../body naming its own object key       422, caller_supplied_object_keys_are_not_accepted
a cross-organization read                     403/404 — which confirms nothing
```

The database refuses independently, and did before this gate:

```sql
object_key IS NULL OR object_store_configured
object_bucket IS NULL OR object_store_configured
object_version IS NULL OR object_key IS NOT NULL
object_store_provider IS NULL OR object_store_configured
```

`object_store_configured` is in `DERIVED_ONLY_FIELDS` — a caller cannot supply
it. Two layers, and the second does not depend on the first being right.

## One defect the hermetic proof found

`refuse_if_blocked(stored, wrote="document_body")` reads `rows_written` — a
**repository's** vocabulary. An adapter result says `stored`, so a successful
put read as a refusal with an empty reason list: the bytes were in the fake
adapter and the caller got a 422 saying nothing. The route now checks the
adapter's own contract and passes its reasons through unchanged.

That is the kind of thing a reachable permitted branch is for. Without one, the
storing path would have shipped broken behind a refusal nobody could get past.

## What the verifier answers

```bash
bash scripts/verify_nativeforge_document_storage_readiness.sh
```

```text
RESULT=PASS
document_metadata_operational=true
document_body_storage_ready=false
body_storage_blocker=document_body_storage_is_not_configured
object_store_configured=false
object_store_contacted=false
body_bytes_written=0
credentials_required=false
credentials_printed=false
production_storage=false
scope=none
```

`document_body_storage_ready=false` is the **expected** answer, not a failure. A
verifier that failed on it would be demanding the gate lie. It fails only if the
metadata path breaks or the blocker stops being what it should be.

Run twice in a row and both pass: the fixture award number is fresh per run and
the archive posts the body its route requires. The first version did neither,
and the second run bailed on a unique index — the same defect Gate 138 found
with a fixed persistence seed.
