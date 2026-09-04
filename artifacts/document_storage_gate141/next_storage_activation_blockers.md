# Gate 141 — what document storage still does not reach

## Where this stands

```text
document_metadata_operational   TRUE
document_body_storage_ready     FALSE
object_store_configured         FALSE
scope                           none
preflight state                 hermetic_fake_verified
```

A tenant can record a document REFERENCE, read it back anchored on
`organization_id`, list an award's documents and archive one. Its BYTES have
nowhere to live, and every route says so by name rather than by 404.

## Metadata does not need the object store

```text
object_store_required_for_metadata   false
body_bytes_required_for_metadata     false
documents stored with an object_key  0
documents claiming a configured store 0
```

Stated as fields rather than implied. Requiring a store for metadata would make
the metadata lane permanently unreachable and every "not ready" above it
unfalsifiable — the unsatisfiable conjunct Gate 134F removed from the
customer-auth chain.

## What every route refuses

```text
unauthenticated                             401, all six routes
a forged X-NF-Org-Id                        401 — not a parameter on any route
a caller setting is_demo or fact_status      400, named
object_key, object_bucket, content, body,
  bytes, sha256_digest, content_length       422, body storage not configured
POST .../body with no store                  422, with the missing key NAMES
POST .../body naming its own object key      422, caller keys not accepted
a cross-organization read                    403/404, which confirms nothing
```

## What the fake adapter proved, and what it cannot

Fourteen checks passed hermetically:

```text
the key is GENERATED, never accepted from a caller
award_documents/<org[:2]>/<org[2:4]>/<org>/<doc>.<ext>
ten unsafe keys refused — traversal, absolute, backslash, NUL, empty
                          segment, foreign namespace, tilde, empty
an oversized body refused against a declared 16777216 byte limit
an empty body refused
a declared digest that does not match the bytes refused
put -> head -> get -> delete round trips
the external adapter is INERT with no client, no config and no permission
```

The body route's storing branch was reached under the fake and refused without
it:

```text
refused without an adapter        true
stored with the fake adapter      true
scope labelled hermetic_fake      true
production_storage stayed false   true
```

None of that proves durability, that a bucket exists, that a credential works,
or that any external service is reachable. So it may not set
`object_store_configured`, and an invariant fails if a hermetic scope ever does.

## What real activation would require

```text
five settings, with real values:
  raw_payload_object_store_access_key_id
  raw_payload_object_store_bucket
  raw_payload_object_store_endpoint
  raw_payload_object_store_region
  raw_payload_object_store_secret_access_key

an injected client        there is no boto3, botocore, minio, s3fs or aioboto3
                          in this project and this gate added none. uv.lock is
                          untouched. The external adapter takes any object
                          speaking the S3 API shape.

an owner decision         production_storage_owner_decision_service exists and
                          was not invoked

an external verifier      explicitly allowed AND passed, run by a person.
                          `production_verified` cannot be produced from
                          configuration alone: five settings being filled in and
                          five settings reaching a bucket that accepts writes are
                          different claims.

secret scanning           REQUIRED_GUARANTEES already names
                          secret_scan_clean_before_promotion
```

## What is NOT the blocker

```text
the metadata lane      operational, proved by calling the routes
the adapter            written, bounded, and proved hermetically
the refusals           explicit, named, and reachable
the database           nf_award_documents already CHECKs
                       object_key IS NULL OR object_store_configured
an SDK                 not needed to prove any of the above, and not added
```

## Still false, and not touched

```text
object_store_configured        false
document_body_storage_ready    false
production_storage             false
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
production_rollout             false
controlled_customer_pilot      false
```

## Nothing was contacted

```text
external object store contacted   false
network calls to object storage   0
body bytes sent                   0
body bytes written externally     0
real customer files read          0
real customer files hashed        0
credential values reported        false
```
