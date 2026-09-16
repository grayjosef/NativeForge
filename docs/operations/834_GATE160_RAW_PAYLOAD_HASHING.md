# 834 — Gate 160: exact-byte hashing

The rule, and the two ways this gate nearly broke it.

## The hash covers the bytes that arrived

```text
algorithm    sha256
input        the EXACT stored bytes
encoding     recorded BESIDE the hash, never applied before it
```

`source_raw_payload_hash_service` composes
`s3_raw_payload_body_store_service.body_hash` — Gate 97C's bytes-first digest,
the same one the production object key is derived from:

```text
raw_payloads/<hash[:2]>/<hash[2:4]>/<hash>.bin
```

If this gate had computed its own digest, the controlled-dev-demo row and the
production object key could disagree about which bytes they mean, which is
exactly the failure content addressing exists to prevent. A test parses the AST
to prove no `hashlib.sha256` call exists in the module and that `body_hash` is
imported.

## Never hash a reserialized structure

```text
arrives   412 bytes of JSON
hash      sha256 of those 412 bytes
NOT       sha256 of json.dumps(json.loads(body))
```

Measured:

```text
same bytes twice                   same hash
one byte changed                   different hash
reserialized json                  DIFFERENT hash
```

`json.dumps` round-tripping reorders keys and changes whitespace. It is what an
artifact writer does for a report, and it is the wrong operation for evidence —
the two look identical in a diff.

## Bytes, not text

The fixture used throughout Gate 160's verifier is deliberately **not valid
UTF-8** and contains a null byte:

```python
b'{"opportunities":[{"id":"ABC-123","note":"' b"\xff\xfe binary \x00 tail \x80\x81" b'"}]}'
```

A store that round-tripped only text would pass every test written with a JSON
fixture. `describe_encoding` reports whether the bytes decode and returns the
hash unchanged, because a decode is an *interpretation* of bytes and
interpretations do not alter evidence.

A `dict` is refused as a body outright. Accepting one would mean serializing it,
and a serialized dict is not the response that arrived.

## Oversize is refused, never truncated

```text
max      1 048 576 bytes
at limit accepted
over     refused, by the service AND by a database CHECK
```

Truncating and then hashing would produce a digest of bytes that never existed
anywhere. An oversize body still *has* a hash — hashable and storable are
different questions — and the refusal names the exact sizes.

The at-limit case is tested too. A limit that refused everything would pass the
refusal test and be a wall.

## Verified twice

```text
write   re-hash the bytes handed in, compare with the declared hash
read    re-hash the bytes read back, compare with the stored hash
```

A store that records a hash and never checks it again has recorded an intention.
The read-side check is what catches a body that changed underneath its row, and
it is the reason `replay_payload` can refuse a tampered payload rather than
hand it over with a warning.

A caller that declares a hash computed from different bytes than it passes is
refused at the door, with both digests named.

## The defect: a verified hash and an unusable body

```text
=== DURABILITY: a new connection reads the exact bytes back
  found=True hash_verified=True
  bytes identical: False          <--
  stored hash == recomputed: True
```

Both lines were true. The stored bytes were correct — `hash_verified` is
computed on the raw row value — but the value the *caller* received had passed
through `_json_safe`, which is `json.loads(json.dumps(..., default=str))`.
`bytes` is not JSON-serializable, so `default=str` turned it into a Python repr
string: `"b'{\"opportunities\"...'"`.

So the bytes were stored perfectly and handed back as something that cannot be
decoded. `hash_verified: True` made the readback look correct while what the
caller actually got was useless.

**The fix.** Two representations, both honest:

```text
payload.body_base64   inside the JSON envelope, round-trippable
result["body_bytes"]  attached AFTER the envelope, bypassing _json_safe
```

Verified against the non-UTF-8 fixture, which a text round-trip would corrupt:

```text
hash_verified          : True
raw bytes identical    : True
base64 round-trips     : True
non-utf8 bytes survived: True
```

This is the "green check with two possible causes" shape in a new place — and
the only thing that catches it is comparing the returned body with the original,
which is why that comparison is one of Gate 160's five critical test ids.

## The wire format

A JSON response cannot carry raw bytes, so the replay route returns base64. That
is what 160H means by "exact bytes or a safe encoded representation": a
`repr()` is neither, and base64 round-trips.
