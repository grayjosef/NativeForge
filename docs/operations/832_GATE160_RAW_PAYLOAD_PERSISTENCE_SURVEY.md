# 832 — Gate 160: where a response body would land, and why it currently cannot

Read-only survey. Every value was measured by running the code it describes.

## There is already a raw payload table. It holds no bodies.

`nf_raw_source_payloads`, created by **migration 0028**, 32 columns, **0 rows**:

```text
identity       payload_id  source_id  collector_id
retrieval      retrieved_at  retrieval_method  request_method
               request_url  request_fingerprint  canonical_url
response       response_status  response_headers_hash
               response_body_hash (NOT NULL)  response_body_size_bytes
               content_type
the body       raw_payload_ref  VARCHAR(1024)  NOT NULL
governance     redaction_status  secret_scan_status  terms_status
               attribution_required  parser_status  promotion_status
               retention_policy
provenance     created_from_live_fetch  created_from_fixture
               blocked_reasons_json  metadata_json
```

`raw_payload_ref` is a **pointer**, not bytes. The row records where a body is
and what it hashed to; it does not record the body.

That is deliberate. `production_raw_payload_repository_service` (Gate 96C) says
so in its own docstring and enforces it:

> `store_body=True` is rejected outright rather than silently ignored, because a
> caller asking this repository to hold a body has misunderstood which layer
> they are at, and a silent no-op would let them keep believing it.

## The production body store exists and is not configured

`s3_raw_payload_body_store_service` (Gate 97C) is the intended home for bodies:
an injected S3-shaped client, content-addressed keys
`raw_payloads/<h[:2]>/<h[2:4]>/<h>.bin`, hash verified on write, refusing by
default. It imports no SDK and there is no `boto3` in this project.

Measured:

```text
raw_payload_object_store_endpoint        ''
raw_payload_object_store_bucket          ''
raw_payload_object_store_region          ''
raw_payload_object_store_access_key_id   ''
build_client_config(...).configured      False
```

And the readiness lane, derived rather than declared:

```text
metadata_table_available                 True
secret_scan_available                    True
promotion_gate_available                 True
body_store_configured                    FALSE
production_raw_payload_store_available   False
production_storage_live                  False
```

Three of four requirements are satisfied. The fourth is a credential nobody has.

## So: are raw responses persisted anywhere?

```text
is response METADATA persisted?        yes, a table exists (0 rows)
is the response BODY persisted?        NO. There is nowhere to put bytes.
does metadata survive normalization?   the columns exist; nothing writes them
is exact response replay possible?     NO - the bytes are not anywhere
is the body currently discarded?       there is no collector, so no body has
                                       ever existed to discard. When one does,
                                       there is nowhere for it to go.
```

**The exact missing component: a landing zone for bytes in
`controlled_dev_demo`.** Everything around it — metadata schema, hash function,
secret scan, promotion gate, production body store design — is built.

## Is object storage required for the first implementation?

No, and building a second one would be worse than not building it.

Option B (metadata-only DB + object-store body) is **already implemented**, by
Gate 97C, and is blocked on configuration rather than on code. Adding another
object-store abstraction to satisfy this gate would produce two stores, one of
them fake, and Gate 160's own rules forbid exactly that:

> Do not fake object-store readiness. Do not add a fake S3 abstraction simply to
> say one exists.

## The 160J decision: A, a DB-backed body for controlled_dev_demo

```text
A  controlled_dev_demo DB-backed payload body, explicit size limit   <- chosen
B  metadata-only DB + object-store body                              already
                                                                     built, and
                                                                     unconfigured
```

**Why A is safe here.** A controlled-dev-demo body store answers a different
question from the production one: *can a collector's exact bytes be persisted,
re-read and verified at all*. Proving that needs bytes somewhere, and the only
storage this environment actually has is the database.

**Why it must be a NEW table.** Adding a body column to
`nf_raw_source_payloads` would contradict Gate 96C's contract and its stated
reason:

> A 78 MB Grants.gov extract is not a database row, and a table that sometimes
> holds bodies is a table whose size nobody can predict.

That argument is correct and this gate does not get to overturn it by widening
the same table. So migration 0046 adds `nf_source_collection_raw_payloads` for
controlled-dev-demo bodies, and `nf_raw_source_payloads` keeps its
metadata-only contract untouched.

**The size limit.** Gate 141's `object_storage_adapter_service` uses
`MAX_BODY_BYTES = 16 MiB`. That is an OBJECT adapter's limit; a database row is
not an object. Gate 160 takes **1 MiB (1,048,576 bytes)** and refuses above it,
deterministically — large enough for a synthetic fixture or a realistic API
page, small enough that nobody mistakes this for the production path.

## What `nf_raw_source_payloads` is missing, for the record

Not defects in Gate 96 — it is a production metadata table and these are the
things a controlled-dev-demo body store needs that it never claimed to have:

```text
no organization_id      every Gate 141+ table has one; this predates that
no attempt identity     payload_id exists; attempt_number does not
no job_id               no linkage to Gate 158's job store
no unique index         all five indexes are non-unique, so two rows may
                        share a payload_id
no archived_at          retention_policy is a vocabulary, not a lifecycle
no body column          by design
```

`request_url` is stored in full, which is worth naming: URLs carry credentials
in query strings often enough that Gate 160's own table stores a **fingerprint**
rather than the URL.

## What exists to compose, not rebuild

```text
body_hash(bytes|str)            Gate 97C. Bytes-first, sha256, str convenience.
                                Gate 160 composes it; a second sha256 would be
                                a second source of truth for one fact.
RETENTION_POLICIES              raw_payload_store_contract_service:
                                retain_7_days, retain_90_days, retain_1_year,
                                retain_indefinite
raw_payload_secret_scan_service scans BODY content for credentials
MAX_BODY_BYTES                  Gate 141's 16 MiB object adapter limit
```

Measured absent: **no compression utilities anywhere** (`gzip`, `zlib`, `lzma`
are imported by nothing), and **no response-header filter**. The
`dev_header_*` services concern inbound dev REQUEST headers, not stored response
headers, so 160F is genuinely new work.

## What Gate 160 will build

```text
migration 0046    nf_source_collection_raw_payloads, bodies for dev/demo
attempt identity  over (job_id, source_id, attempt_number, collector_version)
a hash service    composing Gate 97C's body_hash, bytes-first
a header filter   explicit ALLOWLIST by header name, not a denylist
a write envelope  validate -> filter -> hash -> persist -> re-read -> verify
a replay service  hash verified before returning; provenance resolved
health + routes + verifier + tests + artifacts + docs
```

## What it will not do

```text
contact a source          zero are approved; no collector exists
configure object storage  object_store_configured stays FALSE
fake an S3 abstraction    Gate 97C already has the real design
store a credential        allowlist by header name, and a URL fingerprint
                          rather than a URL
define execution proof    Gate 158 left `completed` unreachable; a stored
                          payload is NOT an execution proof and this gate
                          does not create one
```

**A stored payload is not a payload that was fetched.** The bytes this gate
persists are synthetic, supplied by a caller, and a row proves only that the
spine works.
