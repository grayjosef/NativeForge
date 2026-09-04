# 739 — Gate 141: the object storage activation boundary

## Five states, because "configured" hides four situations

`object_storage_configuration_preflight_service`:

```text
no_config                  nothing is set. The honest default, and where this
                           checkout is.
partial_config             some set, some not. The dangerous one: it looks
                           configured to a reader and can store nothing.
configured_but_unverified  all five set. Nothing has proved they work.
hermetic_fake_verified     an in-memory adapter passed. Proves the CODE, and
                           nothing about any bucket anywhere.
production_verified        an external check was explicitly allowed AND passed.
```

`object_store_configured` is true only for `production_verified`.

## A fake may never configure a store

This is the load-bearing rule of the gate, and it is enforced by an invariant
rather than by a convention:

```python
if state == HERMETIC_FAKE_VERIFIED and result["object_store_configured"]:
    fails.append("a_fake_adapter_configured_the_object_store")
```

with the same check in the readiness service and a test that forges the result
and asserts the invariant catches it. A hermetic proof that could flip a
production flag would make every "not configured" above it unfalsifiable — which
is the whole failure mode the separation exists to prevent.

## Presence, never a value

```text
reports   which required key NAMES are present, absent or placeholder
          a state, one of five
          booleans and counts
never     an endpoint, a bucket, a region, an access key id, a secret,
          a prefix of any of them, or a length that would narrow one
```

`inspect_required_keys` reads each value, tests it with `bool()` and Gate 97's
`is_placeholder_value`, and discards it inside the function. Three fields say so
out loud — `values_read`, `values_reported`, `value_lengths_reported` — because a
reader should not have to infer a guarantee from the absence of a field that
would have carried the value.

An invariant serialises the whole result and fails on `http://`, `https://`,
`AKIA`, `aws_secret` or `-----BEGIN`, so a nested field cannot smuggle one past
a per-key check.

`SecretStr` is unwrapped for the presence test on purpose: pydantic's `str()` of
a secret is the literal `'**********'`, which would read as a present value for
every unset secret in the project.

## Two adapters, and only one can reach anything

`object_storage_adapter_service`:

```text
InMemoryObjectStorageAdapter    a dict. Proves the refusals and the round trip.
ExternalObjectStorageAdapter    wraps an INJECTED client. Inert without one, and
                                inert with one unless the caller both configured
                                a store and explicitly allowed it.
```

Three things must all be true before the external adapter calls anything:

```text
a client was injected              there is no SDK here to build one from
object storage is configured       the preflight said production_verified
allow_external=True                never a default
```

Any one missing and every method refuses by name without touching the client.
Default construction — no arguments — can reach nothing, and a test constructs
it with a client whose every method raises to prove the client is not called.

## No SDK, and no new dependency

```text
boto3 importable                     False
pyproject.toml / uv.lock             no boto3, botocore, minio, s3fs, aioboto3
uv.lock                              untouched by this gate
```

The external adapter takes any object exposing `put_object`, `get_object`,
`head_object`, `delete_object` — the S3 API shape boto3, MinIO's SDK and every
S3-compatible client already speak. Gate 97's body store made the same choice
and for the same reason: an adapter whose refusal logic can only be tested by
mocking around a network call is an adapter whose refusal logic is not tested.

Three modules are parsed with `ast` and asserted to import no network library at
all, and the adapter is asserted to contain no logging call — a log line is a
copy.

## The key is generated, never accepted

```text
award_documents/<org[:2]>/<org[2:4]>/<organization_id>/<document_id>.<ext>
```

Two levels of prefix because object stores shard on key prefix and one prefix
per tenant is a hot partition waiting for the tenant that grows. Namespaced
`award_documents/` so this corpus can never collide with Gate 97's
`raw_payloads/`.

There is no parameter that accepts a key. `put` takes an organization id and a
document id and computes the rest; `object_key` exists on the signature *only*
so a caller offering one is refused by name rather than having it silently
ignored — Gate 139 found a pydantic model dropping `is_demo: false` instead of
refusing it, and a silently ignored key is how a caller comes to believe they
chose the location.

`assert_safe_key` runs anyway, for keys arriving from a stored row rather than a
caller. Ten probes, each a different way of leaving the namespace:

```text
award_documents/../../etc/passwd     traversal
../award_documents/x.bin             traversal from outside
/award_documents/x.bin               absolute
award_documents//x.bin               empty segment
award_documents/x/../../../y.bin     traversal mid-key
award_documents\x.bin                backslash
award_documents/x\x00.bin            NUL
other_namespace/x.bin                foreign namespace
~/award_documents/x.bin              home expansion
""                                   empty
```

A refused key is **not echoed** in the exception. A refused key can be
attacker-shaped, and a message that repeats it is a message that carries it
onward.

## Bodies are bounded and never rendered

```text
MAX_BODY_BYTES        16 MiB, refused above
empty body            refused
sha256                computed and VERIFIED against the caller's declared digest
returned              a key, a length, a digest, a status. Never bytes.
get()                 separate from head(), so nothing that builds a report can
                      reach the bytes by accident
```

A limit that exists is a limit that can be tested. "Whatever fits" is how a
400 MB upload becomes an incident nobody predicted.

## What the hermetic proof establishes

Fourteen checks, all passing:

```text
key_is_generated                        key_is_safe
stored                                  head_found_it
round_trip_bytes_match                  digest_verified
caller_supplied_key_refused             oversized_body_refused
empty_body_refused                      wrong_digest_refused
every_unsafe_key_refused                delete_removed_it
external_adapter_is_inert_by_default    nothing_left_in_the_fake
```

and, through `dependency_overrides`, the body route's storing branch:

```text
refused_without_an_adapter              stored_with_the_fake_adapter
key_was_generated                       key_names_the_organization
adapter_was_the_fake                    scope_was_labelled_fake
no_external_contact                     production_storage_stayed_false
caller_named_key_refused                one_object_in_the_fake
```

## What it cannot establish

```text
durability                     a dict is not a bucket
that a bucket exists
that credentials work
cross-process retrieval
bucket policy or region
```

Reported as fields — `proves_durability`, `proves_a_bucket_exists`,
`proves_credentials_work`, all false — rather than left for a reader to work out
from what is missing.

## What real activation would require

```text
five settings with real values
    raw_payload_object_store_endpoint
    raw_payload_object_store_bucket
    raw_payload_object_store_region
    raw_payload_object_store_access_key_id
    raw_payload_object_store_secret_access_key

an injected client        no SDK is present and this gate added none

an owner decision         production_storage_owner_decision_service exists and
                          was not invoked

an external verifier      explicitly allowed AND passed, run by a person.
                          `production_verified` cannot be produced from
                          configuration alone: five settings filled in and five
                          settings reaching a bucket that accepts writes are
                          different claims, and the second is the one that
                          matters.

secret scanning           raw_payload_body_store_contract_service already names
                          secret_scan_clean_before_promotion in
                          REQUIRED_GUARANTEES
```

A verification result nobody authorized asking for is refused rather than
believed:

```text
external_verification_passed_without_being_allowed
```

## What this gate did not touch

```text
object_storage_signed_url_service         Block 50, behind feature flags and an
                                          owner approval token. Read, not changed.
production_storage_owner_decision_service not invoked
s3_raw_payload_body_store_service         Gate 97's store. Its shape was reused;
                                          the module was not modified.
local_raw_payload_store_service           local dev only, gitignored
uv.lock                                   untouched
```
