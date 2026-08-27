# 547 — Gate 97C: S3-compatible body store contract

**The body-store implementation exists. No live object store was contacted.**
No collectors were activated, no source monitoring started, no live source
coverage is claimed, and secrets are never surfaced.

## No dependency was added

`s3_raw_payload_body_store_service` imports no SDK. It takes any object exposing
`put_object(Bucket=..., Key=..., Body=...)` — the shape boto3, MinIO's client and
every S3-compatible library already speak. Production passes a real client; a
test passes a fake.

`uv.lock` is untouched, and a test greps `pyproject.toml` and `uv.lock` to assert
no `boto3`/`botocore`/`minio`/`s3fs`/`aioboto3` appears in either.

This is not deferral. **A body store whose refusal logic can only be tested by
mocking around a network call is a body store whose refusal logic is not
tested.** Every path below is exercised for real.

## Content-addressed, two levels deep

```text
raw_payloads/<hash[:2]>/<hash[2:4]>/<hash>.bin
s3://<bucket>/raw_payloads/cd/a7/cda7...66d.bin
```

Two prefix levels because object stores shard on key prefix and a million
objects under one prefix is a hot partition. The key derives from
`response_body_hash` — the same hash the metadata row carries — so a key and its
row cannot disagree about which bytes they mean.

## The hash is verified, not trusted

`store_body` re-hashes the bytes it was handed and refuses if they differ from
the declared `response_body_hash`. A caller that hashed different bytes than it
passed makes content addressing meaningless, and catching it costs one
`sha256()`.

Neither hash is rendered in the refusal — what matters is that they disagreed.

## Four refusals, four separate switches

```text
allow_write=False               default: nothing is written
secret_scan_status != clean     a scanned-dirty body never reaches a bucket
hash mismatch                   the bytes are not what the caller said
customer data                   its own explicit opt-in
```

Plus: no bucket configured, and no client supplied. Each is a different mistake,
so each is a different switch — one opt-in never grants another.

`raw_payload_ref` is returned **only** after a successful write, and an
invariant fails any refused result that carries one.

## The client's exception is not the client's message

```python
except Exception as exc:
    return _refused(reasons=[f"object_store_write_failed:{type(exc).__name__}"])
```

The class name, not the text. An S3 client's error message can carry a presigned
URL, a signature, or an echoed header. A test raises an exception whose message
contains `X-Amz-Signature=...` and asserts neither the signature nor the
parameter name appears in the result.

## Nothing is logged

No logger, no `print`, no body or credential in any exception message. A test
parses the module and asserts it calls none of `print`, `info`, `debug`,
`warning`, `error`, `exception`.

A log line is a copy, and a copy of a response body in a log is a response body
in a log aggregator, a terminal scrollback, and a support ticket.

## Modes: a rename with a reason

Gate 96 called the production-capable mode `object_store_required`. Gate 97
renames it `s3_compatible_configured`.

A mode should say what **is**, not what is **needed**. Reading
`mode: object_store_required` told you nothing about whether one existed, which
is the only question a mode is ever asked. The old name is asserted absent from
the vocabulary and asserted not production-capable, so it cannot return by
accident.

## Two facts, kept apart

```text
body_store_implementation_available   the write seam exists          true
body_store_configured                 an environment supplies it     false
```

Gate 96 folded these by requiring an *installed* SDK. With an injected-client
seam the client arrives at call time, so that check could never have passed
however correctly an operator configured their environment.

Production availability requires both, plus the metadata table, the secret
scanner and the promotion gate — five components. Splitting the fact does not
loosen the verdict; it makes each half checkable, and an invariant fails any
result where one stands in for the other.
