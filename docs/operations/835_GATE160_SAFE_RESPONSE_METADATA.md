# 835 — Gate 160: safe response metadata

Which response headers reach the database, decided by an allowlist of header
names — and the commit where that filter refused everything while looking
perfectly healthy.

## Allowlist, not denylist

```text
allowlist   a header is kept because it is on a list of headers we understand
denylist    a header is kept because nothing on a list of bad words matched it
```

The second is how a credential in a header nobody anticipated gets stored. A new
provider invents `X-Acme-Session`, no pattern matches it, and it is persisted
forever. The first refuses it by default, which is the correct behaviour for a
header nobody has looked at.

```text
content-type      how to interpret the bytes
content-length    whether the body is complete
etag              whether the source changed since last time
last-modified     likewise, for sources without an ETag
date              when the origin generated the response
cache-control     whether a re-fetch would even reach the origin
expires / age / vary
retry-after       how long to wait before the next attempt
content-language / content-encoding
the ratelimit-* family   whether the next attempt is safe
```

Eighteen names. Everything else is refused.

## Why name membership and not a substring scan

This campaign has hit substring-vs-meaning thirteen times. Applied to headers, a
naive scan gets all three of these wrong:

```text
X-RateLimit-Remaining   contains "limit"   -> KEPT (correctly)
X-Cache-Key             contains "key"     -> refused (not on the allowlist)
X-Acme-Session          matches nothing    -> refused (not on the allowlist)
```

A scan for `"key"` would refuse the second as a credential and let the third
through. Name membership is exact.

`CREDENTIAL_HEADERS` — Authorization, Cookie, Set-Cookie, X-API-Key and sixteen
others — exists so a refusal can say *this is a known credential header* rather
than *something about this string looked alarming*. It is **not** what keeps
unknown headers out; the allowlist is. An invariant asserts the two sets do not
overlap.

## Values are inspected, as a second line

An allowlisted header could still carry a credential:

```text
Cache-Control: private, token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig
   -> refused_value_looked_like_a_credential  (jwt_token)

Cache-Control: public, max-age=300
   -> kept
```

The value check asks `raw_payload_secret_scan_service` — Gate 95D already knows
what a JWT, a bearer token and a private key look like, and two copies of those
patterns would drift. A finding **refuses** the header rather than redacting it:
a redacted value is neither the truth nor absent.

Refused header **values are never reported**. Only names appear in any output,
because reporting the value of a refused header would defeat refusing it.

## The defect: a filter that refused everything

```python
result = scan_payload_for_secrets(payload=value)
```

The signature is `scan_payload_for_secrets(*, body=None, headers=None)`.

So every call raised `TypeError`, the `except Exception` caught it, and
`_value_looks_like_a_credential` returned
`"scanner_failed_so_the_value_is_refused"` — for **every allowlisted header
value**. The filter would have refused `Content-Type: application/json`.

And it looked like working safety: refusals everywhere, no crash, a plausible
reason string on each one. Every refusal test would have passed.

**A guard that refuses everything is not a guard. It is a broken door that
happens to be shut.**

The only thing that catches it is asserting that a SAFE header *survives*, which
is why 160M requires "safe header survives filter" as its own numbered proof
alongside the four refusals, why it is one of Gate 160's five critical test ids,
and why the health lane has a `safe_headers_survive` condition that closes the
lane when the filter keeps nothing.

Failing closed is right for safety and wrong for diagnosis. That is a real
trade, and the answer is not to fail open — it is to test the permitting branch
as hard as the refusing one.

## Measured, both directions

```text
supplied=14  kept=8  refused=6

KEPT:
  cache-control          public, max-age=300
  content-length         412
  content-type           application/json; charset=utf-8
  date                   Tue, 15 Sep 2026 12:00:01 GMT
  etag                   W/"abc123"
  last-modified          Tue, 15 Sep 2026 12:00:00 GMT
  retry-after            120
  x-ratelimit-remaining  4999

REFUSED:
  authorization    known credential header
  cookie           known credential header
  set-cookie       known credential header
  x-api-key        known credential header
  server           not on the allowlist
  x-acme-session   not on the allowlist
```

Two refusal *kinds*, deliberately distinct: one is a known danger, the other an
unknown, and an operator reading the report should be able to tell them apart.

## Two doors, on purpose

The filter answers *which headers are safe*. The repository separately refuses a
write whose metadata contains a name outside the allowlist — answering *may I
write these*.

That is a second check on the same fact, and it can fail for a reason the first
never sees: a caller assembling a dict by hand and skipping the filter entirely.

## Bounds

```text
max header value length   1024 characters
max headers per response  64, or the whole response is refused
```

A very long value in an allowlisted header is either a bug or something being
smuggled through a field nobody expected to be large. A response with hundreds
of headers is refused wholesale rather than filtered one by one.

## The URL is not metadata

It is not stored at all — only `sha256(url)`. Query strings carry api keys often
enough that keeping the URL would be a credential-storage decision nobody made.
A fingerprint answers "is this the same endpoint as last time", which is the
only question the spine needs and the only one it can answer safely.
