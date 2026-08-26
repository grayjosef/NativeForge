# 527 — Gate 93E: raw payload store contract

**No collectors were activated. No URLs were fetched. No live coverage is
claimed.** This contract stores nothing — `store_implemented: false`,
`payloads_stored: 0`, `network_access_performed: false`.

## Why this comes before the collectors

Gates 87 through 89 spent four consecutive gates measuring the same wound from
the other end: **185 corpus records, of which only 18 carry independent
transport evidence**, because when those records were made nobody kept the
bytes. Every flag reading `never_synthesized: True` turned out to be a hardcoded
literal, and the Sprint 313 guard checking it compared flags to flags.

The fix is not a better flag. It is keeping the payload, so a record's origin is
something you can re-derive rather than something you have to believe.

Building 381 sources' worth of collectors before the store exists would
reproduce that at scale. That is why `raw_payload_store` is a required
precondition for **all five** Phase 1 sources, and why the Gate 93A survey
ranked its absence the number-one missing blocker.

## What exists today

`nf_source_check_runs` records the shape of a check, not its evidence — counts,
statuses, timestamps, an error code, a `result_summary_json`. No raw payload, no
payload hash, no response status or headers, no per-payload `retrieved_at`, no
secret-scan status. The batch-fetch services hold response text in local dicts
during a run and persist only the parsed result.

## Sixteen required fields

```text
payload_id              retrieved_at            request_fingerprint
source_id               retrieval_method        response_status
response_headers_hash   raw_payload_hash        raw_payload_size_bytes
canonical_url           attribution_required    terms_status
parser_status           retention_policy        redaction_status
secret_scan_status
```

Four are **evidence-critical** and are checked for plausibility, not just
presence:

```text
payload_id  source_id  retrieved_at  raw_payload_hash
```

`raw_payload_hash` must be SHA-256 hex — 64 characters, all hex. `deadbeef` is
rejected. A record missing any evidence-critical field can never be
`payload_is_trustworthy_as_collected`, enforced by an invariant.

## A parsed record is not evidence of collection

`parser_status` sits deliberately apart from the payload fields, and
`payload_is_trustworthy_as_collected` reads the payload half, not the parsed
half. A record with `parser_status: parsed_ok` and no payload hash behind it is
a claim, not a collection, and is rejected.

## Secret scanning is a promotion gate

Gate 89 found a committed 143-character HS256 JWT in a fixture, tracked since
2026-06-20 and not gitignored. Raw API responses are exactly where the next one
arrives — a pre-signed URL, a session token echoed back in a header.

So `secret_scan_status` must be affirmatively `clean` before promotion.
`pending` and `unknown` do **not** qualify, and an invariant fails any record
where `promotion_allowed` is true without a clean scan.

Response headers are stored as a **hash**, never verbatim, because that is where
`Authorization` and `Set-Cookie` live. A record carrying a literal
`response_headers` object is rejected.

## Two shapes that look like data and are not

```text
zero-byte body on HTTP 200   the HUD dead-shell case from Gate 92H:
                             valid HTML, 200, nothing in it
parsed_ok with no hash       a parse result with no transport behind it
```

Both are rejected rather than stored, because both would later be
indistinguishable from a successful collection.

## Retention is explicit per payload

`retention_policy` is a required field with no default. The Grants.gov daily
extract is retained 7 days upstream; what NativeForge keeps is a separate
decision that has to be recorded, not inherited.
