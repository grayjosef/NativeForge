# 737 — Gate 141A: what object storage already is, and what is missing

Survey before implementation. Nothing was built while writing this.

## What exists, and it is a lot

Gates 95–98 built the raw-payload body store and its contract. Gate 127 built
the award document store repository. Gate 139 made document **metadata**
route-live. None of it is a stub:

```text
raw_payload_body_store_contract_service      the MODE detector, four modes
s3_raw_payload_body_store_service            an S3-shaped store, injected client
local_raw_payload_store_service              local dev only, gitignored
award_document_store_repository_service      the document metadata rows
award_document_store_persistence_validation  validate + detect_object_store_configured
award_document_routes                        Gate 139, four metadata routes
storage_adapter_interface_service            DESCRIPTIVE stubs, not a put/get seam
object_storage_signed_url_service            Block 50, behind feature flags
storage_feature_flag_service                 the flags
production_storage_readiness_validator       the production question
```

## Why `object_store_configured` is currently false

Derived, not declared, and it measures false honestly:

```text
detect_object_store_configured()
  -> detect_body_store_mode() in PRODUCTION_CAPABLE_MODES
  -> PRODUCTION_CAPABLE_MODES = {"s3_compatible_configured"}
```

and `detect_body_store_mode()` reads five settings:

```text
raw_payload_object_store_endpoint            attr present, value ABSENT
raw_payload_object_store_bucket              attr present, value ABSENT
raw_payload_object_store_region              attr present, value ABSENT
raw_payload_object_store_access_key_id       attr present, value ABSENT
raw_payload_object_store_secret_access_key   attr present, value ABSENT

detected mode                                unconfigured
implementation available                     true
```

So the implementation exists and the configuration does not. That is the
`no_config` state, and it is the right one: nothing is half-wired.

Values were checked for **presence only**. No endpoint, bucket, region, key id
or secret was read into a variable that is rendered, and none appears in this
document or in any artifact this gate writes.

## Is metadata-only document operation route-live?

Yes, since Gate 139:

```text
POST /v1/nf/demo/orgs/{org}/awarded-grants/{award}/documents
GET  /v1/nf/demo/orgs/{org}/awarded-grants/{award}/documents
GET  /v1/nf/demo/orgs/{org}/documents/{document_id}
POST /v1/nf/demo/orgs/{org}/documents/{document_id}/archive
```

All behind `require_demo_org_session`, org-anchored, proved by Gate 139's route
smoke and by `verify_nativeforge_awarded_operational_tracking.sh` (RESULT=PASS
as of `45b74cb`).

## Is body upload blocked at the route boundary?

Yes, and in two independent places.

**At the route**, `refuse_body_storage(body)` runs before anything else and
refuses nine field names:

```text
object_key  object_bucket  object_version  content  body  file  bytes
sha256_digest  content_length
        -> 422 document_body_storage_is_not_configured
```

**At the database**, `nf_award_documents` carries CHECK constraints:

```sql
object_key IS NULL OR object_store_configured
object_bucket IS NULL OR object_store_configured
object_version IS NULL OR object_key IS NOT NULL
object_store_provider IS NULL OR object_store_configured
```

and `object_store_configured` is in `DERIVED_ONLY_FIELDS` — a caller cannot
supply it.

Two layers, and the second does not depend on the first being correct. That is
the shape this gate must not weaken.

## Can any code path accidentally contact object storage?

No SDK is installed and none is importable:

```text
boto3 importable                    False
pyproject.toml / uv.lock            no boto3, botocore, minio, s3fs, aioboto3
s3_raw_payload_body_store_service   imports no http client; a test parses it
                                    with ast and asserts the absence
```

`s3_raw_payload_body_store_service` takes an **injected client** exposing
`put_object(Bucket=, Key=, Body=)`. With no client passed, and no SDK to
construct one from, there is nothing to contact. Gate 97's tests assert this by
parsing the module rather than by running it.

`object_storage_signed_url_service` (Block 50) is behind
`storage_feature_flag_service` and an owner approval token. It was read, not
touched.

## Are credentials present?

No. All five settings exist as attributes and all five are empty. The preflight
this gate builds reports **presence booleans by key name** and never a value —
`is_placeholder_value` already exists in Gate 97 for the case where a real-
looking value is a placeholder, and it is reused rather than rewritten.

## What is declared rather than derived — the actual Gate 141 work

Three constants where a measured fact belongs:

```text
awarded_operational_tracking_readiness_service.py:320
    "document_body_storage_ready": False       a literal

award_document_routes.py:155, :183, :212
    object_store_configured=False              a literal in the envelope,
                                               three times

post_award_common.py refuse_body_storage
    "object_store_configured": False           a literal in the refusal detail
```

Every one is **currently correct** and none of them is measured. If somebody
configured a bucket tomorrow, the routes would keep telling callers the store is
unconfigured and the readiness roll-up would keep saying body storage is not
ready. That is the same family Gate 114A removed for `customer_persistence_live`,
Gate 139A for `awarded_operational_tracking` and Gate 140F for
`tenant_digest_operational` — a fact that cannot change when the world does.

There is no shared **put/get** adapter either. `storage_adapter_interface_service`
returns dicts *describing* adapters; the only working in-memory fake is
`FakeObjectStoreClient` inside `tests/test_gate97_object_body_store.py`, which no
service, artifact or verifier can reach.

## What a safe fake adapter can prove hermetically

Everything except that a real bucket exists:

```text
a key is GENERATED, never accepted from a caller
a traversal key is refused                     ../  ./  absolute  backslash  NUL
an oversized body is refused                   against a declared limit
the stored bytes round-trip                    put -> head -> get -> delete
the hash is verified, not trusted
no body bytes reach a log, an artifact or a return value
the adapter is inert with no client injected
```

What it cannot prove: durability, cross-process retrieval, bucket policy,
region, credential validity, or that any external service exists. So a fake run
may never set `object_store_configured` — it is labelled `hermetic_fake` and
kept apart from `production_verified`.

## What real activation would require

```text
five settings with real values      endpoint, bucket, region, key id, secret
an injected client                  boto3 or a MinIO SDK, neither present and
                                    neither added by this gate
an owner decision                   production_storage_owner_decision_service
a safe external verifier            explicitly allowed, run by a person, and
                                    NOT run by this gate
secret scanning before promotion    REQUIRED_GUARANTEES already names it
retention and legal hold policy     the repository already models both
```

## Exact blockers remaining

```text
object_store_configured        false — five settings absent
document_body_storage_ready    false — no adapter proof, no route, no config
production storage             false — no owner decision, no external verification
body upload route              does not exist, and this gate does not add one
                               that pretends to store anything
```

## What this gate will and will not do

Will:

```text
build a configuration preflight that reports presence and never a value
build a real put/get/head/delete adapter boundary with an in-memory fake
give the fake a home in src/ so the artifact and the verifier share one
derive object_store_configured at the routes instead of writing False
derive document_body_storage_ready instead of writing False
add an explicit body-storage readiness route that REFUSES and says why
build a readiness service, a verifier and seven artifacts
```

Will not:

```text
contact an object store
add an SDK dependency or touch uv.lock
add a body upload route that stores bytes
read or hash a real customer file
print or commit a credential
make object_store_configured true
claim production storage
```
